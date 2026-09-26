"""Decision router: check-family registry, 60 s tick, and GET /v1/router (DES-GM-ROUTER).

The router holds no account key and never calls the order path (AC-GM-ROUTER-02).
"""

import dataclasses
import json
import math
import os
import sqlite3
import uuid
from collections.abc import Callable
from contextlib import closing
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Request, Response

from . import ercot, jev, scoring
from .contracts import CheckResult

router = APIRouter()
registry: dict[str, Callable[[], list[CheckResult]]] = {}

DA_REPORT = "NP4-190-CD"
RT_REPORT = "NP6-905-CD"
# Calibration knobs: p = logistic(K * (score - 50) / 50 + B * sign(DA - last RT)).
K = 2.0
B = 0.3
REVIEW = 0.50
ALERT = 0.80
HOUR = timedelta(hours=1)
COLUMNS = (
    "check_id, family, subject, horizon_s, probability, band, baseline, jev_probability, "
    "created_at, resolves_at, outcome"
)


def now() -> datetime:
    return datetime.now(UTC)


def register(family: str, fn: Callable[[], list[CheckResult]]) -> None:
    registry[family] = fn


def band(probability: float) -> str:
    if probability < REVIEW:
        return "log"
    return "review" if probability < ALERT else "alert"


def market_checks() -> list[CheckResult]:
    """DART spread check per zone and delivery hour in the 24 clock hours after now's hour."""
    t = now().astimezone(UTC)
    start = t.replace(minute=0, second=0, microsecond=0)
    results = []
    for p in scoring.predict():
        hour = datetime.fromisoformat(p.delivery_hour).astimezone(UTC)
        if not start < hour <= start + 24 * HOUR:
            continue
        da = ercot.signals.series(DA_REPORT, p.zone, hour.isoformat(), (hour + HOUR).isoformat())
        if not da:
            continue  # no DA price, so the outcome could never resolve
        rt = ercot.signals.latest(RT_REPORT, p.zone)
        diff = da[0].value - rt.value if rt else 0.0
        sign = (diff > 0) - (diff < 0)
        probability = 1 / (1 + math.exp(-(K * (p.score - 50) / 50 + B * sign)))
        resolves = hour + HOUR
        results.append(
            CheckResult(
                check_id=f"market:{p.zone}:{hour.isoformat()}",
                family="market",
                subject=f"{p.zone}:{hour.isoformat()}",
                horizon_s=int((resolves - t).total_seconds()),
                probability=probability,
                band=band(probability),
                baseline=True,
                jev_probability=None,
                created_at=t.isoformat(),
                resolves_at=resolves.isoformat(),
            )
        )
    return results


register("market", market_checks)


def evaluate() -> list[CheckResult]:
    results = [check for fn in list(registry.values()) for check in fn()]
    if not jev.enabled():
        return results
    return [
        dataclasses.replace(check, jev_probability=jev.probability(check))
        if check.band != "log"
        else check
        for check in results
    ]


def _connect() -> closing[sqlite3.Connection]:
    return closing(sqlite3.connect(os.getenv("GRIDMARKET_DB", "/data/gridmarket.db")))


def _market_outcome(subject: str) -> bool | None:
    """RT hourly average > DA for the delivery hour; None until a full hour of RT exists."""
    zone, start = subject.split(":", 1)
    end = (datetime.fromisoformat(start) + HOUR).isoformat()
    da = ercot.signals.series(DA_REPORT, zone, start, end)
    rt = ercot.signals.series(RT_REPORT, zone, start, end)
    if not da or sum(s.interval_minutes for s in rt) < 60:
        return None
    return sum(s.value for s in rt) / len(rt) > da[0].value


def resolve(db: sqlite3.Connection, t: datetime) -> None:
    # ponytail: only the market family resolves here; health outcomes need their own resolver.
    subjects = db.execute(
        "SELECT DISTINCT subject FROM router_results "
        "WHERE family = 'market' AND outcome IS NULL AND resolves_at <= ?",
        (t.isoformat(),),
    ).fetchall()
    for (subject,) in subjects:
        outcome = _market_outcome(subject)
        if outcome is not None:
            db.execute(
                "UPDATE router_results SET outcome = ? "
                "WHERE family = 'market' AND subject = ? AND outcome IS NULL",
                (int(outcome), subject),
            )


def tick() -> None:
    t = now().astimezone(UTC)
    results = evaluate()
    with _connect() as db, db:
        resolve(db, t)
        for c in results:
            db.execute(
                f"INSERT INTO router_results (id, {COLUMNS}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (uuid.uuid4().hex, *dataclasses.astuple(c)),
            )
            if c.band == "alert":
                # One alert event per check, not one per tick.
                db.execute(
                    "INSERT INTO events (id, entry_type, subject_id, payload_json, created_at) "
                    "SELECT ?, 'alert', ?, ?, ? WHERE NOT EXISTS "
                    "(SELECT 1 FROM events WHERE entry_type = 'alert' AND subject_id = ?)",
                    (
                        uuid.uuid4().hex,
                        c.check_id,
                        json.dumps(dataclasses.asdict(c)),
                        t.isoformat(),
                        c.check_id,
                    ),
                )


@router.get("/v1/router")
def get_router(request: Request, response: Response) -> dict:
    origin = os.getenv("GRIDMARKET_CORS_ORIGIN")
    if origin and request.headers.get("origin") == origin:
        response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Vary"] = "Origin"
    # ponytail: full-table scan per request; add a retention window if router_results grows large.
    with _connect() as db:
        rows = db.execute(f"SELECT {COLUMNS} FROM router_results ORDER BY created_at").fetchall()
    latest: dict[str, dict] = {}
    errors: dict[str, list[float]] = {}
    for row in rows:
        item = dict(zip(COLUMNS.split(", "), row, strict=True))
        item["baseline"] = bool(item["baseline"])
        if item["outcome"] is not None:
            item["outcome"] = bool(item["outcome"])
            errors.setdefault(item["check_id"], []).append(
                (item["probability"] - item["outcome"]) ** 2
            )
        latest[item["check_id"]] = item
    return {
        "checks": list(latest.values()),
        "brier": {check_id: sum(e) / len(e) for check_id, e in errors.items()},
        "jev_enabled": jev.enabled(),
    }
