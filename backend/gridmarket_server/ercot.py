"""Cached ERCOT Worker signals and the shared SQLite signal store."""

import asyncio
import logging
import os
import sqlite3
import time
from collections import deque
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode
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
    "ESR": "/api/report/esr/charging_mw",
}
POLL_MINUTES = {
    "NP6-905-CD": 5,
    "NP4-190-CD": 60,
    "NP3-565-CD": 60,
    "NP3-233-CD": 60,
    "NP6-86-CD": 5,
    "ESR": 5,
    "NWS-TEMP": 60,
    "NWS-ALERTS": 5,
}
CENTRAL = ZoneInfo("America/Chicago")
logger = logging.getLogger(__name__)
_last_polled: dict[tuple[str, str], float] = {}
_latencies: deque[tuple[float, float]] = deque()


class RequestBudget:
    # 18 per 60 s is the market's specified share of the Worker's per-client
    # quota (spec T3); one hourly cycle with paging needs about 15.
    def __init__(
        self, limit: int = 18, window_s: float = 60, clock: Callable[[], float] = time.monotonic
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


class BudgetExhausted(Exception):
    """The per-cycle request budget is spent; the next cycle retries."""


# Deterministic client errors: retrying within this cycle cannot help.
FAIL_FAST = {400, 401, 403, 404}


def _acquire(budget: RequestBudget) -> None:
    if not budget.try_acquire():
        raise BudgetExhausted("request budget exhausted for this poll cycle")


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
            # Upsert: re-polling an interval replaces its row instead of
            # duplicating it (no schema change; the schema is frozen).
            db.execute(
                "DELETE FROM signals WHERE report_id=? AND zone=? AND interval_start=?",
                (signal.report_id, signal.zone, signal.interval_start),
            )
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

    def history(
        self, report_id: str, zone: str, start: str, end: str, limit: int = 10001
    ) -> list[dict]:
        """De-duplicated UTC observations per interval_start (latest poll wins), sorted."""
        if not self._path().exists():
            return []
        with self._connect() as db:
            rows = db.execute(
                "SELECT s.* FROM signals s WHERE s.rowid IN ("
                "SELECT MAX(t.rowid) FROM signals t WHERE t.report_id=? AND t.zone=? "
                "AND t.interval_start>=? AND t.interval_start<? GROUP BY t.interval_start"
                ") ORDER BY s.interval_start LIMIT ?",
                (report_id, zone, start, end, limit),
            ).fetchall()
        now = datetime.now(UTC)
        bound = 2 * POLL_MINUTES.get(report_id, 5) * 60
        failed = (str(self._path()), report_id) in self.failed or (
            str(self._path()),
            "*",
        ) in self.failed
        result = []
        for row in rows:
            start_dt = datetime.fromisoformat(row["interval_start"])
            age = _data_age(row["fetched_at"], row["interval_start"], row["published_at"], now)
            result.append(
                {
                    "interval_start": row["interval_start"],
                    "interval_end": (
                        start_dt + timedelta(minutes=row["interval_minutes"])
                    ).isoformat(),
                    "value": row["value"],
                    "unit": row["unit"],
                    "published_at": row["published_at"],
                    "stale": age > bound or failed,
                }
            )
        return result

    def staleness(self, report_id: str) -> float | None:
        if not self._path().exists():
            return None
        with self._connect() as db:
            row = db.execute(
                "SELECT fetched_at, interval_start, published_at FROM signals WHERE report_id=? "
                "ORDER BY fetched_at DESC LIMIT 1",
                (report_id,),
            ).fetchone()
        return _data_age(row[0], row[1], row[2], datetime.now(UTC)) if row else None

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
            age = _data_age(row["fetched_at"], row["interval_start"], row["published_at"], now)
            limit = 2 * POLL_MINUTES.get(row["report_id"], 5) * 60
            result.append(
                {
                    **{name: row[name] for name in Signal.__dataclass_fields__},
                    "age_s": age,
                    "stale": age > limit
                    or (str(self._path()), row["report_id"]) in self.failed
                    or (str(self._path()), "*") in self.failed,
                }
            )
        return result


signals = SignalStore()
stats = WorkerStats()
_snapshot_asof: datetime | None = None


def _data_age(fetched_at: str, interval_start: str, published_at: str, now: datetime) -> float:
    """Worst of fetch, interval, and publish ages; naive stamps carry no zone info."""
    ages = [(now - datetime.fromisoformat(fetched_at)).total_seconds()]
    for text in (interval_start, published_at):
        if not text:
            continue
        try:
            stamp = datetime.fromisoformat(text)
        except ValueError:
            continue
        if stamp.tzinfo is not None:
            ages.append((now - stamp).total_seconds())
    return max(0.0, max(ages))


def worker_stats() -> WorkerStats:
    if _snapshot_asof is not None:
        stats.snapshot_age_s = max(0, (datetime.now(UTC) - _snapshot_asof).total_seconds())
    return stats


def map_weather_zone_load(rows: Mapping[str, float]) -> dict[str, float]:
    groups = {
        "LZ_HOUSTON": ("Coast",),
        "LZ_NORTH": ("North", "North Central", "East"),
        "LZ_SOUTH": ("South Central", "Southern"),
        "LZ_WEST": ("West", "Far West"),
    }
    return {zone: sum(rows.get(name, 0) for name in names) for zone, names in groups.items()}


def _hour(date: str, ending: int, interval: int = 1, dst: bool = False) -> str:
    """Interval start in UTC for a Central hour ending. DST-safe: local midnight
    anchors the day, then the ordinal clock hour is added, so the repeated and
    skipped hours on transition days never collide."""
    day = datetime.fromisoformat(date).date()
    local_midnight = datetime(day.year, day.month, day.day, tzinfo=CENTRAL)
    midnight = local_midnight.astimezone(UTC)
    hours_in_day = round(
        ((local_midnight + timedelta(days=1)).astimezone(UTC) - midnight).total_seconds() / 3600
    )
    if hours_in_day == 23:  # Spring forward: HE02 is skipped.
        ordinal = ending - 1 if ending < 3 else ending - 2
    elif hours_in_day == 25:  # Fall back: HE02 repeats; DSTFlag marks the second.
        ordinal = ending - 1 + (1 if (ending == 2 and dst) or ending > 2 else 0)
    else:
        ordinal = ending - 1
    return (midnight + timedelta(hours=ordinal, minutes=15 * (interval - 1))).isoformat()


def _sced_time(stamp: str, repeated: bool = False) -> str:
    """SCEDTimestamp is Central prevailing time without an offset; fold from repeatedHourFlag."""
    when = datetime.fromisoformat(stamp)
    if when.tzinfo is None:
        when = when.replace(tzinfo=CENTRAL, fold=1 if repeated else 0)
    return when.astimezone(UTC).isoformat()


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
    """Store the Worker's real snapshot shape; nulls are skipped, missing sections
    are marked failed, and an empty snapshot leaves freshness untouched (A1-empty)."""
    global _snapshot_asof
    at = payload["asOf"]
    stored = 0
    demand = payload.get("demand") or {}
    if demand.get("mw") is not None:
        _store("SNAPSHOT-DEMAND", "ERCOT", at, 5, demand["mw"], "MW", at)
        stored += 1
    else:
        signals.mark_failed("SNAPSHOT-DEMAND")
    hubs = [h for h in payload.get("hubs") or [] if isinstance(h, Mapping)]
    priced = [h for h in hubs if h.get("price") is not None]
    for hub in priced:
        _store("SNAPSHOT-HUBS", hub["hub"], at, 5, hub["price"], "$/MWh", at)
    if priced:
        stored += 1
    else:
        signals.mark_failed("SNAPSHOT-HUBS")
    dam = payload.get("dam") or {}
    if dam.get("price") is not None and dam.get("hub"):
        _store("SNAPSHOT-DAM", dam["hub"], at, 60, dam["price"], "$/MWh", at)
        stored += 1
    else:
        signals.mark_failed("SNAPSHOT-DAM")
    sced = payload.get("sced") or {}
    if sced.get("systemLambda") is not None:
        _store("SNAPSHOT-SCED", "lambda", at, 5, sced["systemLambda"], "$/MWh", at)
        stored += 1
    else:
        signals.mark_failed("SNAPSHOT-SCED")
    if not stored:
        return
    _snapshot_asof = datetime.fromisoformat(at)
    stats.snapshot_age_s = max(0, (datetime.now(UTC) - _snapshot_asof).total_seconds())


# AGCExecTimeUTC is ERCOT's UTC stamp without an offset; AGCExecTime is Central
# prevailing time, so it is deliberately not read.
_ESR_TIMES = ("agcexectimeutc", "timestamp", "scedtimestamp", "intervalstart", "publishtime")
_ESR_VALUES = (
    "systemwideesrchargingmw",
    "systemwidechargingmw",
    "esrchargingmw",
    "chargingmw",
    "mw",
    "value",
)


def _field_names(payload: dict) -> list[str]:
    """ERCOT sends fields as {"name", "label", "dataType"} objects; plain names pass through."""
    return [f["name"] if isinstance(f, Mapping) else f for f in payload.get("fields") or []]


def _esr_stamp(norm: Mapping[str, object]) -> datetime | None:
    """The row's source measurement time in UTC, or None when it has no usable one."""
    name = next((name for name in _ESR_TIMES if norm.get(name) is not None), None)
    if name is None:
        return None
    try:
        when = datetime.fromisoformat(str(norm[name]))
    except ValueError:
        return None
    if when.tzinfo is None:
        if name != "agcexectimeutc":
            return None  # Unknown zone: never guess.
        when = when.replace(tzinfo=UTC)
    return when.astimezone(UTC)


def parse_esr(payload: dict) -> None:
    """Store the latest system-wide ESR charging MW row (negative = discharging).

    Rows without a source timestamp are skipped, never stamped with the fetch time.
    """
    fields = _field_names(payload)
    rows = payload.get("data") or []
    latest: tuple[datetime, float, str] | None = None
    for row in rows:
        record = row if isinstance(row, Mapping) else dict(zip(fields, row))
        norm = {
            "".join(ch for ch in str(key).lower() if ch.isalnum()): val
            for key, val in record.items()
        }
        value = next((norm[name] for name in _ESR_VALUES if norm.get(name) is not None), None)
        if value is None:
            continue
        stamp = _esr_stamp(norm)
        if stamp is None:
            continue
        published = str(record.get("publishTime") or stamp.isoformat())
        if latest is None or stamp >= latest[0]:
            latest = (stamp, float(value), published)
    if latest is not None:
        _store("ESR", "ERCOT", latest[0].isoformat(), 1, latest[1], "MW", latest[2])


# NP3-565-CD wide columns -> weather-zone display names (map_weather_zone_load groups these).
_ZONES_565 = {
    "coast": "Coast",
    "east": "East",
    "farWest": "Far West",
    "north": "North",
    "northCentral": "North Central",
    "southCentral": "South Central",
    "southern": "Southern",
    "west": "West",
}
# NP3-233-CD wide columns -> load zones.
_ZONES_233 = {
    "totalResourceMWZoneSouth": "LZ_SOUTH",
    "totalResourceMWZoneNorth": "LZ_NORTH",
    "totalResourceMWZoneWest": "LZ_WEST",
    "totalResourceMWZoneHouston": "LZ_HOUSTON",
}


def parse_report(report: str, payload: dict) -> int:
    """Store one report payload by its spec columns; return _meta.totalPages."""
    if report == "ESR":
        parse_esr(payload)
        return 1
    fields = _field_names(payload)
    records = [dict(zip(fields, row, strict=True)) for row in payload.get("data") or []]
    loads: dict[str, dict[str, float]] = {}
    roll_published: dict[str, str] = {}
    for row in records:
        if report == "NP6-86-CD":
            start = _sced_time(row["SCEDTimestamp"], row.get("repeatedHourFlag", False))
            end = (datetime.fromisoformat(start) + timedelta(minutes=5)).isoformat()
            _store(report, row["constraintName"], start, 5, row["shadowPrice"], "$/MWh", end)
        elif report == "NP3-233-CD":
            start = _hour(row["operatingDate"], int(row["hourEnding"]))
            published = row.get("postedDatetime") or ""
            for column, zone in _ZONES_233.items():
                if row.get(column) is not None:
                    _store(report, zone, start, 60, row[column], "MW", published)
        elif report == "NP3-565-CD":
            if "inUseFlag" in row and not row["inUseFlag"]:
                continue
            start = _hour(
                row["deliveryDate"],
                int(str(row["hourEnding"])[:2]),
                dst=row.get("DSTFlag", False),
            )
            published = row.get("postedDatetime") or ""
            bucket = loads.setdefault(start, {})
            for column, zone in _ZONES_565.items():
                if row.get(column) is not None:
                    _store(report, zone, start, 60, row[column], "MW", published)
                    bucket[zone] = float(row[column])
            roll_published[start] = published
        else:  # NP6-905-CD, NP4-190-CD: no publish-time column, so use the interval end.
            ending = row.get("deliveryHour", row.get("hourEnding"))
            quarter = row.get("deliveryInterval", 1)
            minutes = 15 if report == "NP6-905-CD" else 60
            start = _hour(
                row["deliveryDate"],
                int(str(ending)[:2]),
                int(quarter or 1),
                dst=row.get("DSTFlag", False),
            )
            end = (datetime.fromisoformat(start) + timedelta(minutes=minutes)).isoformat()
            _store(
                report,
                row["settlementPoint"],
                start,
                minutes,
                row["settlementPointPrice"],
                "$/MWh",
                end,
            )
    for start, bucket in loads.items():
        if not bucket:  # All eight zones null: nothing measured, nothing rolled up.
            continue
        for zone, value in map_weather_zone_load(bucket).items():
            _store(report, zone, start, 60, value, "MW", roll_published[start])
    return max(1, int((payload.get("_meta") or {}).get("totalPages") or 1))


def _is_snapshot(path: str) -> bool:
    return path == "/api/snapshot" or path.startswith("/api/snapshot?")


async def _get(client: httpx.AsyncClient, path: str, budget: RequestBudget, key: str) -> dict:
    for attempt in range(7):
        _acquire(budget)
        start = time.monotonic()
        stats.requests += 1
        try:
            response = await client.get(
                path, headers={} if _is_snapshot(path) else {"x-gridmarket-key": key}
            )
            response.raise_for_status()
            result = response.json()
            _record_latency(start)
            return result
        except httpx.HTTPStatusError as exc:
            stats.errors += 1
            if exc.response.status_code == 429:
                stats.http_429 += 1
            _record_latency(start)
            if exc.response.status_code in FAIL_FAST or attempt == 6:
                raise
            await asyncio.sleep(backoff_seconds(attempt))
        except (httpx.HTTPError, ValueError):
            stats.errors += 1
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
    try:
        await _poll()
    except Exception:
        logger.warning("ercot poll failed", exc_info=True)


# Settlement points the market actually prices: the four product zones plus
# the hub average scoring compares against. Exact names from ERCOT NP4-160-SG.
PRICE_POINTS = ("LZ_HOUSTON", "LZ_NORTH", "LZ_SOUTH", "LZ_WEST", "HB_HUBAVG")


def _report_queries(report: str, now_ct: datetime) -> list[dict[str, str]] | None:
    """Bounded per-report queries using the spec's parameter names.

    Returns None for a single unfiltered GET (only ESR, whose endpoint is
    absent from the published spec, so no filter vocabulary can be sourced).
    """
    today = now_ct.date().isoformat()
    if report in ("NP6-905-CD", "NP4-190-CD"):
        tomorrow = (now_ct.date() + timedelta(days=1)).isoformat()
        return [
            {
                "deliveryDateFrom": today,
                "deliveryDateTo": tomorrow,
                "settlementPoint": point,
                "size": "1000",
                "sort": "deliveryDate",
            }
            for point in PRICE_POINTS
        ]
    if report == "NP3-565-CD":
        horizon = (now_ct.date() + timedelta(days=2)).isoformat()
        return [
            {
                "deliveryDateFrom": today,
                "deliveryDateTo": horizon,
                "inUseFlag": "true",
                "size": "1000",
                "sort": "deliveryDate",
            }
        ]
    if report == "NP3-233-CD":
        horizon = (now_ct.date() + timedelta(days=2)).isoformat()
        return [
            {
                "operatingDateFrom": today,
                "operatingDateTo": horizon,
                "size": "1000",
                "sort": "operatingDate",
            }
        ]
    if report == "NP6-86-CD":
        fmt = "%Y-%m-%dT%H:%M:%S"  # Spec format: Central time, no offset.
        return [
            {
                "SCEDTimestampFrom": (now_ct - timedelta(minutes=15)).strftime(fmt),
                "SCEDTimestampTo": now_ct.strftime(fmt),
                "size": "1000",
                "sort": "SCEDTimestamp",
            }
        ]
    return None


async def _poll() -> None:
    base = os.getenv("GRIDMARKET_WORKER_URL")
    if not base:
        return
    signals.mark_failed("*")
    budget = RequestBudget()
    complete = True
    key = os.getenv("GRIDMARKET_WORKER_KEY", "")
    now_ct = datetime.now(CENTRAL)
    pending: list[tuple[str, str, dict[str, str], int]] = []
    async with httpx.AsyncClient(base_url=base, timeout=20) as client:
        for report, path in [(None, "/api/snapshot"), *REPORTS.items()]:
            # ESR rides a separate API product/key; opt in per deployment so fleets
            # without the ESR key don't burn retry budget on a 503 every cycle.
            if report == "ESR" and os.getenv("GRIDMARKET_ESR", "off") == "off":
                continue
            report_key = report or "SNAPSHOT"
            stamp_key = (str(signals._path()), report_key)
            minutes = POLL_MINUTES.get(report_key, 5)
            if time.monotonic() - _last_polled.get(stamp_key, float("-inf")) < minutes * 60:
                continue
            try:
                if report is None:
                    parse_snapshot(await _get(client, path, budget, key))
                else:
                    # Page 1 of every query first, so one huge result set cannot
                    # starve the other reports; remaining pages follow below.
                    for params in _report_queries(report, now_ct) or [None]:
                        target = (
                            path if params is None else f"{path}?{urlencode({**params, 'page': 1})}"
                        )
                        total = parse_report(report, await _get(client, target, budget, key))
                        if params is not None and total > 1:
                            pending.append((report, path, params, total))
                _last_polled[stamp_key] = time.monotonic()
            except BudgetExhausted:
                complete = False
                break  # The budget is per-cycle; the next cycle retries.
            except Exception:
                logger.warning("ercot poll for %s failed", path, exc_info=True)
                if report is not None:
                    signals.mark_failed(report_key)
                complete = False
                continue
        for report, path, params, total in pending:
            try:
                for page in range(2, total + 1):
                    target = f"{path}?{urlencode({**params, 'page': page})}"
                    parse_report(report, await _get(client, target, budget, key))
            except BudgetExhausted:
                complete = False
                break
            except Exception:
                logger.warning("ercot poll for %s failed", path, exc_info=True)
                signals.mark_failed(report)
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
