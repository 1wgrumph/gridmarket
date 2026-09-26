"""Cached ERCOT Worker signals and the shared SQLite signal store."""

import asyncio
import os
import sqlite3
import time
from collections import deque
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx

from . import api
from .contracts import Signal, WorkerStats

REPORTS = {
    "NP6-905-CD": "/api/report/np6-905-cd/spp_node_zone_hub",
    "NP4-190-CD": "/api/report/np4-190-cd/dam_stlmnt_pnt_prices",
    "NP3-565-CD": "/api/report/np3-565-cd/lf_by_model_weather_zone",
    "NP3-233-CD": "/api/report/np3-233-cd/hourly_res_outage_cap",
    "NP6-86-CD": "/api/report/np6-86-cd/shdw_prices_bnd_trns_const",
}
POLL_MINUTES = {
    "NP6-905-CD": 5,
    "NP4-190-CD": 60,
    "NP3-565-CD": 60,
    "NP3-233-CD": 60,
    "NP6-86-CD": 5,
    "NWS-TEMP": 60,
    "NWS-ALERTS": 5,
}
CENTRAL = ZoneInfo("America/Chicago")
_last_polled: dict[tuple[str, str], float] = {}
_latencies: deque[tuple[float, float]] = deque()


class RequestBudget:
    def __init__(
        self, limit: int = 12, window_s: float = 60, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.limit, self.window_s, self.clock = limit, window_s, clock
        self.sent: deque[float] = deque()

    def try_acquire(self) -> bool:
        now = self.clock()
        while self.sent and self.sent[0] <= now - self.window_s:
            self.sent.popleft()
        if len(self.sent) >= self.limit:
            return False
        self.sent.append(now)
        return True


def backoff_seconds(attempt: int) -> int:
    return min(300, 5 * 2 ** min(attempt, 6))


class SignalStore:
    def __init__(self) -> None:
        self.failed: set[tuple[str, str]] = set()

    @staticmethod
    def _path() -> Path:
        return Path(os.getenv("GRIDMARKET_DB", "/data/gridmarket.db"))

    @staticmethod
    def _connect() -> sqlite3.Connection:
        path = SignalStore._path()
        path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(path)
        db.row_factory = sqlite3.Row
        db.executescript(Path(__file__).with_name("schema.sql").read_text())
        return db

    def add(self, signal: Signal) -> None:
        self.failed.discard((str(self._path()), signal.report_id))
        with self._connect() as db:
            db.execute(
                "INSERT INTO signals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (str(uuid4()), *vars(signal).values()),
            )

    def latest(self, report_id: str, zone: str) -> Signal | None:
        if not self._path().exists():
            return None
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM signals WHERE report_id=? AND zone=? "
                "ORDER BY fetched_at DESC, rowid DESC LIMIT 1",
                (report_id, zone),
            ).fetchone()
        return Signal(*(row[name] for name in Signal.__dataclass_fields__)) if row else None

    def mark_failed(self, report_id: str) -> None:
        self.failed.add((str(self._path()), report_id))

    def clear_failed(self, report_id: str) -> None:
        self.failed.discard((str(self._path()), report_id))

    def series(self, report_id: str, zone: str, start: str, end: str) -> list[Signal]:
        if not self._path().exists():
            return []
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM signals WHERE report_id=? AND zone=? "
                "AND interval_start>=? AND interval_start<? ORDER BY interval_start",
                (report_id, zone, start, end),
            ).fetchall()
        return [Signal(*(row[name] for name in Signal.__dataclass_fields__)) for row in rows]

    def staleness(self, report_id: str) -> float | None:
        if not self._path().exists():
            return None
        with self._connect() as db:
            row = db.execute(
                "SELECT fetched_at FROM signals WHERE report_id=? ORDER BY fetched_at DESC LIMIT 1",
                (report_id,),
            ).fetchone()
        return (
            max(
                0,
                (datetime.now(UTC) - datetime.fromisoformat(row[0])).total_seconds(),
            )
            if row
            else None
        )

    def current(self) -> list[dict]:
        if not self._path().exists():
            return []
        with self._connect() as db:
            rows = db.execute(
                "SELECT s.* FROM signals s WHERE s.rowid=(SELECT max(t.rowid) FROM signals t "
                "WHERE t.report_id=s.report_id AND t.zone=s.zone) ORDER BY s.report_id,s.zone"
            ).fetchall()
        result = []
        now = datetime.now(UTC)
        for row in rows:
            age = max(
                0,
                (now - datetime.fromisoformat(row["fetched_at"])).total_seconds(),
            )
            result.append(
                {
                    **{name: row[name] for name in Signal.__dataclass_fields__},
                    "age_s": age,
                    "stale": age > 2 * POLL_MINUTES.get(row["report_id"], 5) * 60
                    or (str(self._path()), row["report_id"]) in self.failed
                    or (str(self._path()), "*") in self.failed,
                }
            )
        return result


signals = SignalStore()
stats = WorkerStats()


def worker_stats() -> WorkerStats:
    return stats


def map_weather_zone_load(rows: Mapping[str, float]) -> dict[str, float]:
    groups = {
        "LZ_HOUSTON": ("Coast",),
        "LZ_NORTH": ("North", "North Central", "East"),
        "LZ_SOUTH": ("South Central", "Southern"),
        "LZ_WEST": ("West", "Far West"),
    }
    return {zone: sum(rows.get(name, 0) for name in names) for zone, names in groups.items()}


def _hour(date: str, ending: int, interval: int = 1) -> str:
    start = datetime.fromisoformat(date).replace(tzinfo=CENTRAL) + timedelta(
        hours=ending - 1, minutes=15 * (interval - 1)
    )
    return start.astimezone(UTC).isoformat()


def _store(
    report: str, zone: str, interval: str, minutes: int, value: float, unit: str, published: str
) -> None:
    signals.add(
        Signal(
            report,
            zone,
            interval,
            minutes,
            float(value),
            unit,
            published,
            datetime.now(UTC).isoformat(),
        )
    )


def parse_snapshot(payload: dict) -> None:
    at = payload["asOf"]
    values = [("demand", "ERCOT", payload.get("demand", {}).get("current"), "MW")]
    for section in ("hubs", "dam"):
        values.extend(
            (section, zone, value, "$/MWh") for zone, value in payload.get(section, {}).items()
        )
    values.append(("sced", "lambda", payload.get("sced", {}).get("lambda"), "$/MWh"))
    for section, zone, value, unit in values:
        if value is not None:
            _store(f"SNAPSHOT-{section.upper()}", zone, at, 5, value, unit, at)
    stats.snapshot_age_s = max(0, (datetime.now(UTC) - datetime.fromisoformat(at)).total_seconds())


def parse_report(report: str, payload: dict) -> None:
    fields = payload["fields"]
    records = [dict(zip(fields, row, strict=True)) for row in payload["data"]]
    loads: dict[str, float] = {}
    for row in records:
        published = row["publishTime"]
        if report == "NP6-86-CD":
            zone, value, interval, minutes, unit = (
                row["constraintName"],
                row["shadowPrice"],
                row["scedTimestamp"],
                5,
                "$/MWh",
            )
        else:
            ending = row.get("deliveryHour", row.get("hourEnding"))
            quarter = row.get("deliveryInterval", 1)
            interval = _hour(row["deliveryDate"], ending, quarter)
            if report == "NP6-905-CD":
                zone, value, minutes, unit = (
                    row["settlementPointName"],
                    row["settlementPointPrice"],
                    15,
                    "$/MWh",
                )
            elif report == "NP4-190-CD":
                zone, value, minutes, unit = (
                    row["settlementPoint"],
                    row["settlementPointPrice"],
                    60,
                    "$/MWh",
                )
            elif report == "NP3-565-CD":
                zone, value, minutes, unit = row["weatherZone"], row["loadForecast"], 60, "MW"
                loads[zone] = value
            else:
                zone, value, minutes, unit = row["loadZone"], row["outageCapacity"], 60, "MW"
        _store(report, zone, interval, minutes, value, unit, published)
    if loads:
        for zone, value in map_weather_zone_load(loads).items():
            _store(report, zone, interval, 60, value, "MW", published)


async def _get(client: httpx.AsyncClient, path: str, budget: RequestBudget, key: str) -> dict:
    for attempt in range(7):
        while not budget.try_acquire():
            await asyncio.sleep(1)
        start = time.monotonic()
        stats.requests += 1
        try:
            response = await client.get(
                path, headers={"x-gridmarket-key": key} if path != "/api/snapshot" else {}
            )
            response.raise_for_status()
            result = response.json()
            _record_latency(start)
            return result
        except (httpx.HTTPError, ValueError) as exc:
            stats.errors += 1
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
                stats.http_429 += 1
            _record_latency(start)
            if attempt == 6:
                raise
            await asyncio.sleep(backoff_seconds(attempt))
    raise RuntimeError("unreachable")


def _record_latency(start: float) -> None:
    now = time.monotonic()
    _latencies.append((now, (now - start) * 1000))
    while _latencies and _latencies[0][0] < now - 900:
        _latencies.popleft()
    stats.latencies_ms[:] = [latency for _, latency in _latencies]


async def poll() -> None:
    base = os.getenv("GRIDMARKET_WORKER_URL")
    if not base:
        return
    signals.mark_failed("*")
    budget = RequestBudget()
    complete = True
    async with httpx.AsyncClient(base_url=base, timeout=20) as client:
        for report, path in [(None, "/api/snapshot"), *REPORTS.items()]:
            report_key = report or "SNAPSHOT"
            stamp_key = (str(signals._path()), report_key)
            minutes = POLL_MINUTES.get(report_key, 5)
            if time.monotonic() - _last_polled.get(stamp_key, float("-inf")) < minutes * 60:
                continue
            try:
                payload = await _get(client, path, budget, os.getenv("GRIDMARKET_WORKER_KEY", ""))
                parse_report(report, payload) if report else parse_snapshot(payload)
                _last_polled[stamp_key] = time.monotonic()
            except (httpx.HTTPError, ValueError, KeyError, TypeError):
                complete = False
                continue
    if complete:
        signals.clear_failed("*")


@api.router.get("/v1/signals")
def signal_api() -> list[dict]:
    return signals.current()


@api.router.get("/v1/predictions")
def predictions_api() -> list:
    from .scoring import predict

    return predict()


@api.router.get("/v1/predictions/{zone}")
def prediction_api(zone: str) -> list:
    return [item for item in predictions_api() if item.zone == zone]
