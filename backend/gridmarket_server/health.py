"""Provider heartbeats, the 30 s offline rule, health checks, and simulated outages."""

import hmac
import ipaddress
import logging
import math
import os
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

# Module import, not `from .providers import enabled`: base_sim imports health back.
from . import providers
from .contracts import CheckResult


@asynccontextmanager
async def _lifespan(app):
    from . import decision_router

    decision_router.register("health", checks)
    yield


router = APIRouter(lifespan=_lifespan)
log = logging.getLogger(__name__)

OFFLINE_AFTER_S = 30
OUTAGE = timedelta(minutes=10)
HORIZON_S = 900
TIMEOUT_MS = 20_000
SNAPSHOT_POLL_S = 60
# Calibration knobs: p = logistic(BIAS + WEIGHT * sum of risk terms, each clamped to 0..1).
BIAS, WEIGHT = -3.0, 2.0


def _path() -> Path:
    # Health probes run in fresh processes, so empty means unset here too.
    return Path(os.getenv("GRIDMARKET_DB") or "/data/gridmarket.db")


@contextmanager
def _db(timeout: float = 5.0):
    db = sqlite3.connect(_path(), timeout=timeout)
    try:
        with db:
            yield db
    finally:
        db.close()


def _now() -> datetime:
    return datetime.now(UTC)


def _parse(stamp: str) -> datetime:
    moment = datetime.fromisoformat(stamp)
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _age(stamp: str | None) -> float | None:
    return (_now() - _parse(stamp)).total_seconds() if stamp else None


def _state(provider_id: str) -> tuple[int, str | None, str | None] | None:
    """(online, last_heartbeat, outage_until), or None before any health row exists."""
    if not _path().exists():
        return None
    with _db() as db:
        return db.execute(
            "SELECT online, last_heartbeat, outage_until FROM provider_health WHERE provider_id=?",
            (provider_id,),
        ).fetchone()


def heartbeat(provider_id: str) -> None:
    with _db() as db:
        db.execute(
            "INSERT INTO provider_health (provider_id, online, last_heartbeat) VALUES (?, 1, ?) "
            "ON CONFLICT(provider_id) DO UPDATE SET online=1, last_heartbeat=excluded.last_heartbeat "
            "WHERE provider_health.outage_until IS NULL "
            "OR julianday(provider_health.outage_until)<=julianday(excluded.last_heartbeat)",
            (provider_id, _now().isoformat()),
        )


def is_online(provider_id: str) -> bool:
    state = _state(provider_id)
    if state is None:
        return True
    online, last, until = state
    if until and _parse(until) > _now():
        return False
    age = _age(last)
    if age is not None and age > OFFLINE_AFTER_S:
        if online:
            # The baseline rule. Short timeout: the order path may hold the write lock;
            # the next tick persists the mark then.
            try:
                with _db(timeout=0.1) as db:
                    db.execute(
                        "UPDATE provider_health SET online=0 WHERE provider_id=?", (provider_id,)
                    )
            except sqlite3.OperationalError:
                pass
        return False
    return bool(online)


def tick() -> None:
    """Every 10 s: each enabled adapter heartbeats unless in a simulated outage."""
    for provider_id, adapter in providers.enabled().items():
        try:
            state = _state(provider_id)
            until = state[2] if state else None
            if until and _parse(until) <= _now():
                with _db() as db:
                    db.execute(
                        "UPDATE provider_health SET outage_until=NULL "
                        "WHERE provider_id=? AND outage_until=?",
                        (provider_id, until),
                    )
                until = None
            if not until:
                adapter().heartbeat()
                heartbeat(provider_id)
            is_online(provider_id)
        except Exception:
            log.exception("heartbeat failed for %s", provider_id)


def _risk(terms: list[float]) -> float:
    return 1 / (1 + math.exp(-(BIAS + WEIGHT * sum(min(max(t, 0.0), 1.0) for t in terms))))


def _check(subject: str, probability: float, now: datetime) -> CheckResult:
    band = "alert" if probability >= 0.8 else "review" if probability >= 0.5 else "log"
    return CheckResult(
        check_id=f"health:{subject}",
        family="health",
        subject=subject,
        horizon_s=HORIZON_S,
        probability=probability,
        band=band,
        baseline=True,
        jev_probability=None,
        created_at=now.isoformat(),
        resolves_at=(now + timedelta(seconds=HORIZON_S)).isoformat(),
    )


def checks() -> list[CheckResult]:
    from . import ercot

    now = _now()
    stats = ercot.worker_stats()
    requests = max(stats.requests, 1)
    latencies = sorted(stats.latencies_ms)
    p95 = latencies[math.ceil(0.95 * len(latencies)) - 1] if latencies else 0.0
    worker = [
        stats.errors / requests,
        stats.http_429 / requests,
        p95 / TIMEOUT_MS,
        (stats.snapshot_age_s or 0.0) / (2 * SNAPSHOT_POLL_S),
    ]
    results = [_check("worker", _risk(worker), now)]
    for provider_id in providers.enabled():
        if is_online(provider_id):
            state = _state(provider_id)
            age = _age(state[1]) if state else None
            results.append(_check(provider_id, _risk([(age or 0.0) / OFFLINE_AFTER_S]), now))
        else:
            results.append(_check(provider_id, 1.0, now))
    return results


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


_ADMIN_NETS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("fd00::/8"),
)


def _local(host: str) -> bool:
    """Loopback or a compose-subnet peer (the bridge gateway); see api.admin_local."""
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_loopback or any(address in net for net in _ADMIN_NETS)


def _admin_denied(request: Request) -> JSONResponse | None:
    if request.headers.get("cf-connecting-ip") or not _local(
        request.client.host if request.client else ""
    ):
        return _error(403, "FORBIDDEN", "Admin routes are local only")
    key = os.getenv("GRIDMARKET_ADMIN_KEY", "")
    given = request.headers.get("authorization", "")
    if not key or not hmac.compare_digest(
        given.encode("utf-8", "ignore"), f"Bearer {key}".encode()
    ):
        return _error(401, "UNAUTHENTICATED", "Admin key required")
    return None


def db_writable() -> bool:
    """A real write, rolled back: False when the DB is read-only or the disk is full."""
    try:
        with _db(timeout=2.0) as db:
            db.execute("INSERT OR IGNORE INTO provider_health (provider_id) VALUES ('_probe')")
            db.rollback()
    except sqlite3.Error:
        return False
    return True


@router.post("/v1/admin/providers/{id}/outage")
async def outage(id: str, request: Request):
    provider_id = id
    if denied := _admin_denied(request):
        return denied
    if provider_id not in providers.enabled():
        return _error(404, "NOT_FOUND", "Unknown provider")
    try:
        body = await request.json()
    except ValueError:
        body = None
    active = body.get("active") if isinstance(body, dict) else None
    if not isinstance(active, bool):
        return _error(422, "VALIDATION_ERROR", "active must be true or false")
    until = (_now() + OUTAGE).isoformat() if active else None
    with _db() as db:
        db.execute(
            "INSERT INTO provider_health (provider_id, outage_until) VALUES (?, ?) "
            "ON CONFLICT(provider_id) DO UPDATE SET outage_until=excluded.outage_until",
            (provider_id, until),
        )
    return {"provider_id": provider_id, "active": active, "outage_until": until}


@router.get("/v1/providers/health")
def providers_health() -> list[dict]:
    rows = []
    for provider_id, adapter in providers.enabled().items():
        online = is_online(provider_id)
        _, last, until = _state(provider_id) or (1, None, None)
        active = bool(until) and _parse(until) > _now()
        rows.append(
            {
                "id": provider_id,
                "display_name": adapter.display_name,
                "online": online,
                "online_assets": sum(
                    bool(adapter().asset_status(asset["id"])["online"])
                    for asset in adapter().list_assets()
                )
                if online
                else 0,
                "last_heartbeat": last,
                "heartbeat_age_s": _age(last),
                "outage_active": active,
                "outage_until": until if active else None,
            }
        )
    return rows
