"""Red tests for the decision router (S32).

SEIT-GM-ROUTER-01, SEIT-GM-ROUTER-02, SEIT-GM-API-05.

Tick reads ``decision_router.now()``, ``scoring.predict()``, and
``ercot.signals`` (DA ``NP4-190-CD`` hourly, RT ``NP6-905-CD`` 15-minute).
``series`` is half-open on ``interval_start``. Future delivery hours are the
24 clock hours after the hour that contains ``now``. ``check_id`` is
``market:{zone}:{delivery_hour}`` with ``delivery_hour`` the hour-start
isoformat. Bands: log < 0.50, review 0.50 to below 0.80, alert >= 0.80.
"""

import ast
import json
import math
import socket
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import uvicorn

from gridmarket_server import decision_router, ercot, jev, scoring
from gridmarket_server.contracts import CheckResult, Prediction, Signal
from gridmarket_server.main import app

ZONES = ("LZ_HOUSTON", "LZ_NORTH", "LZ_SOUTH", "LZ_WEST")
DA_REPORT = "NP4-190-CD"
RT_REPORT = "NP6-905-CD"
NOW = datetime(2026, 9, 26, 12, 30, tzinfo=UTC)
HOUR = datetime(2026, 9, 26, 12, tzinfo=UTC)
SCHEMA = Path(__file__).resolve().parents[1] / "gridmarket_server" / "schema.sql"
ROUTER_PY = Path(__file__).resolve().parents[1] / "gridmarket_server" / "decision_router.py"
ORIGIN = "https://views.example"
OTHER_ORIGIN = "https://evil.example"


def dart_probability(score: float, da: float, rt: float) -> float:
    sign = (da > rt) - (da < rt)
    return 1 / (1 + math.exp(-(2.0 * (score - 50) / 50 + 0.3 * sign)))


def band_for(probability: float) -> str:
    if probability < 0.50:
        return "log"
    if probability < 0.80:
        return "review"
    return "alert"


def score_for(probability: float, da: float = 0.0, rt: float = 0.0) -> float:
    sign = (da > rt) - (da < rt)
    logit = math.log(probability / (1 - probability))
    return 50 + 50 * (logit - 0.3 * sign) / 2.0


def delivery(offset: int) -> datetime:
    return HOUR + timedelta(hours=offset)


def check_id(zone: str, hour: datetime) -> str:
    return f"market:{zone}:{hour.isoformat()}"


def prediction(zone: str, hour: datetime, score: float) -> Prediction:
    return Prediction(
        zone=zone,
        delivery_hour=hour.isoformat(),
        score=score,
        level="MEDIUM",
        confidence=1.0,
        expected_value=0.0,
        market_price=None,
        drivers=[],
        disclaimer="Simulation estimate, not guaranteed profit.",
        generated_at=NOW.isoformat(),
    )


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value)


def as_bool(value: object) -> bool | None:
    if value is None:
        return None
    if value in (1, True):
        return True
    if value in (0, False):
        return False
    raise AssertionError(value)


class MemorySignals:
    def __init__(self) -> None:
        self.rows: list[Signal] = []

    def add(self, report_id: str, zone: str, start: datetime, minutes: int, value: float) -> None:
        self.rows.append(
            Signal(
                report_id=report_id,
                zone=zone,
                interval_start=start.isoformat(),
                interval_minutes=minutes,
                value=value,
                unit="$/MWh",
                published_at=NOW.isoformat(),
                fetched_at=NOW.isoformat(),
            )
        )

    def latest(self, report_id: str, zone: str) -> Signal | None:
        found = [row for row in self.rows if row.report_id == report_id and row.zone == zone]
        return max(found, key=lambda row: row.interval_start) if found else None

    def series(self, report_id: str, zone: str, start: object, end: object) -> list[Signal]:
        opened = _at(start)
        closed = _at(end)
        return [
            row
            for row in self.rows
            if row.report_id == report_id
            and row.zone == zone
            and opened <= _at(row.interval_start) < closed
        ]

    def staleness(self, report_id: str) -> float | None:
        return 0.0 if any(row.report_id == report_id for row in self.rows) else None


def _at(value: object) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    return datetime.fromisoformat(str(value))


def prepare(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "router.db"
    monkeypatch.setenv("GRIDMARKET_DB", str(path))
    monkeypatch.setenv("GRIDMARKET_NWS", "off")
    monkeypatch.delenv("GRIDMARKET_WORKER_URL", raising=False)
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript(SCHEMA.read_text())
    return path


def install(
    monkeypatch: pytest.MonkeyPatch,
    store: MemorySignals,
    predictions: list[Prediction],
    clock: dict[str, datetime],
) -> None:
    monkeypatch.setattr(decision_router, "now", lambda: clock["t"], raising=False)

    def predict() -> list[Prediction]:
        return predictions

    monkeypatch.setattr(scoring, "predict", predict)
    if hasattr(decision_router, "predict"):
        monkeypatch.setattr(decision_router, "predict", predict)
    monkeypatch.setattr(ercot, "signals", store)
    if hasattr(decision_router, "ercot"):
        monkeypatch.setattr(decision_router.ercot, "signals", store)
    if hasattr(decision_router, "signals"):
        monkeypatch.setattr(decision_router, "signals", store)


def rows(path: Path) -> list[sqlite3.Row]:
    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row
        return list(db.execute("SELECT * FROM router_results ORDER BY created_at, check_id"))


def alert_events(path: Path) -> list[sqlite3.Row]:
    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row
        return list(db.execute("SELECT * FROM events WHERE entry_type = 'alert'"))


def counts(path: Path) -> dict[str, int]:
    with sqlite3.connect(path) as db:
        return {
            table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("orders", "trades", "accounts", "reservations")
        }


def forbid_import(module: str | None, names: list[str]) -> str | None:
    roots = {"market", "api", "keys"}
    mod = module or ""
    tail = mod.split(".")[-1]
    if tail in roots:
        return mod or tail
    if mod == "gridmarket" or mod.startswith("gridmarket."):
        return mod
    for name in names:
        root = name.split(".")[-1]
        if root in roots or name == "gridmarket" or name.startswith("gridmarket."):
            return name
    return None


def order_imports() -> list[str]:
    tree = ast.parse(ROUTER_PY.read_text())
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                hit = forbid_import(alias.name, [])
                if hit:
                    found.append(hit)
        elif isinstance(node, ast.ImportFrom):
            hit = forbid_import(node.module, [alias.name for alias in node.names])
            if hit:
                found.append(hit)
    return found


@contextmanager
def serve() -> Iterator[int]:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error", access_log=False)
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None  # type: ignore[method-assign]
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    while not server.started:
        if time.monotonic() > deadline:
            server.should_exit = True
            thread.join(timeout=2)
            pytest.fail("uvicorn did not bind 127.0.0.1")
        time.sleep(0.05)
    try:
        yield port
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def get_router(port: int, origin: str) -> tuple[int, str | None, bytes]:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/router",
        headers={"Origin": origin},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return (
                response.status,
                response.headers.get("Access-Control-Allow-Origin"),
                response.read(),
            )
    except urllib.error.HTTPError as err:
        return err.code, err.headers.get("Access-Control-Allow-Origin"), err.read()


def test_seit_gm_router_01_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SEIT-GM-ROUTER-01: tick evaluates a registered family and stores its checks."""
    path = prepare(tmp_path, monkeypatch)
    install(monkeypatch, MemorySignals(), [], {"t": NOW})
    probe = CheckResult(
        check_id="probe-1",
        family="health",
        subject="probe",
        horizon_s=60,
        probability=0.1,
        band="log",
        baseline=True,
        jev_probability=None,
        created_at=NOW.isoformat(),
        resolves_at=(NOW + timedelta(seconds=60)).isoformat(),
    )
    decision_router.register("health", lambda: [probe])
    try:
        decision_router.tick()
        stored = [row["check_id"] for row in rows(path)]
        assert "probe-1" in stored
    finally:
        decision_router.registry.pop("health", None)


def test_seit_gm_router_01_future_hours(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SEIT-GM-ROUTER-01: one market check per zone and future delivery hour."""
    path = prepare(tmp_path, monkeypatch)
    store = MemorySignals()
    predictions = []
    for zone in ZONES:
        store.add(RT_REPORT, zone, HOUR + timedelta(minutes=15), 15, 10.0)
        for offset in (0, *range(1, 25), 25):
            hour = delivery(offset)
            store.add(DA_REPORT, zone, hour, 60, 10.0)
            predictions.append(prediction(zone, hour, 50.0))
    install(monkeypatch, store, predictions, {"t": NOW})
    decision_router.tick()
    stored = rows(path)
    expected = {check_id(zone, delivery(offset)) for zone in ZONES for offset in range(1, 25)}
    assert {row["check_id"] for row in stored} == expected
    sample_hour = delivery(1)
    sample = next(row for row in stored if row["check_id"] == check_id("LZ_HOUSTON", sample_hour))
    assert sample["family"] == "market"
    assert sample["subject"] == f"LZ_HOUSTON:{sample_hour.isoformat()}"
    assert sample["baseline"] in (1, True)
    assert sample["jev_probability"] is None
    assert parse_ts(sample["created_at"]) == NOW
    assert parse_ts(sample["resolves_at"]) == sample_hour + timedelta(hours=1)
    assert sample["horizon_s"] == 5400
    assert sample["probability"] == pytest.approx(dart_probability(50.0, 10.0, 10.0))
    assert sample["band"] == "review"
    assert as_bool(sample["outcome"]) is None
    far = next(row for row in stored if row["check_id"] == check_id("LZ_WEST", delivery(24)))
    assert parse_ts(far["resolves_at"]) == delivery(24) + timedelta(hours=1)
    assert far["horizon_s"] == int((delivery(24) + timedelta(hours=1) - NOW).total_seconds())


def test_seit_gm_router_01_probability(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SEIT-GM-ROUTER-01: p = logistic(2*(score-50)/50 + 0.3*sign(DA-last RT))."""
    path = prepare(tmp_path, monkeypatch)
    store = MemorySignals()
    zone = "LZ_HOUSTON"
    rt = 30.0
    store.add(RT_REPORT, zone, HOUR + timedelta(minutes=15), 15, rt)
    cases = ((1, 40.0), (2, 20.0), (3, 30.0))
    predictions = []
    for offset, da in cases:
        hour = delivery(offset)
        store.add(DA_REPORT, zone, hour, 60, da)
        predictions.append(prediction(zone, hour, 60.0))
    install(monkeypatch, store, predictions, {"t": NOW})
    decision_router.tick()
    stored = {row["check_id"]: row for row in rows(path)}
    assert set(stored) == {check_id(zone, delivery(offset)) for offset, _da in cases}
    for offset, da in cases:
        row = stored[check_id(zone, delivery(offset))]
        expected = dart_probability(60.0, da, rt)
        assert row["probability"] == pytest.approx(expected)
        assert row["band"] == band_for(expected)


def test_seit_gm_router_01_bands(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SEIT-GM-ROUTER-01: boundaries 0.4999 log, 0.5 review, 0.7999 review, 0.8 alert."""
    path = prepare(tmp_path, monkeypatch)
    store = MemorySignals()
    targets = {
        "LZ_HOUSTON": 0.4999,
        "LZ_NORTH": 0.5,
        "LZ_SOUTH": 0.7999,
        "LZ_WEST": 0.8,
    }
    hour = delivery(1)
    predictions = []
    for zone, target in targets.items():
        store.add(RT_REPORT, zone, HOUR + timedelta(minutes=15), 15, 25.0)
        store.add(DA_REPORT, zone, hour, 60, 25.0)
        predictions.append(prediction(zone, hour, score_for(target)))
    install(monkeypatch, store, predictions, {"t": NOW})
    decision_router.tick()
    stored = {row["check_id"]: row for row in rows(path)}
    assert set(stored) == {check_id(zone, hour) for zone in targets}
    for zone, target in targets.items():
        row = stored[check_id(zone, hour)]
        assert row["probability"] == pytest.approx(target, abs=1e-9)
        assert row["band"] == band_for(target)


def test_seit_gm_router_01_outcome_brier(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SEIT-GM-ROUTER-01: horizon outcome, unresolved excluded, per-check Brier mean."""
    path = prepare(tmp_path, monkeypatch)
    store = MemorySignals()
    hour = delivery(1)
    later = delivery(6)
    store.add(RT_REPORT, "LZ_HOUSTON", HOUR + timedelta(minutes=15), 15, 30.0)
    store.add(DA_REPORT, "LZ_HOUSTON", hour, 60, 30.0)
    store.add(DA_REPORT, "LZ_HOUSTON", later, 60, 30.0)
    store.add(RT_REPORT, "LZ_NORTH", HOUR + timedelta(minutes=15), 15, 40.0)
    store.add(DA_REPORT, "LZ_NORTH", hour, 60, 40.0)
    high = score_for(0.8)
    low = score_for(0.2)
    predictions = [
        prediction("LZ_HOUSTON", hour, high),
        prediction("LZ_HOUSTON", later, 50.0),
        prediction("LZ_NORTH", hour, 50.0),
    ]
    clock = {"t": NOW}
    install(monkeypatch, store, predictions, clock)
    decision_router.tick()
    clock["t"] = NOW + timedelta(seconds=1)
    predictions[0] = prediction("LZ_HOUSTON", hour, low)
    decision_router.tick()
    houston = check_id("LZ_HOUSTON", hour)
    north = check_id("LZ_NORTH", hour)
    pending = check_id("LZ_HOUSTON", later)
    open_rows = [row for row in rows(path) if row["check_id"] == houston]
    assert [row["probability"] for row in open_rows] == pytest.approx([0.8, 0.2])
    assert all(as_bool(row["outcome"]) is None for row in rows(path))

    clock["t"] = hour + timedelta(hours=1)
    decision_router.tick()
    assert all(as_bool(row["outcome"]) is None for row in rows(path) if row["check_id"] == houston)

    for minutes, houston_rt, north_rt in (
        (0, 100.0, 100.0),
        (15, 10.0, 10.0),
        (30, 10.0, 10.0),
        (45, 10.0, 10.0),
    ):
        store.add(RT_REPORT, "LZ_HOUSTON", hour + timedelta(minutes=minutes), 15, houston_rt)
        store.add(RT_REPORT, "LZ_NORTH", hour + timedelta(minutes=minutes), 15, north_rt)
    decision_router.tick()
    resolved = [row for row in rows(path) if row["check_id"] == houston]
    assert [as_bool(row["outcome"]) for row in resolved] == [True, True]
    assert [row["probability"] for row in resolved] == pytest.approx([0.8, 0.2])
    north_rows = [row for row in rows(path) if row["check_id"] == north]
    assert [as_bool(row["outcome"]) for row in north_rows] == [False, False]
    assert all(as_bool(row["outcome"]) is None for row in rows(path) if row["check_id"] == pending)

    monkeypatch.setattr(decision_router, "tick", lambda: None)
    monkeypatch.setenv("GRIDMARKET_CORS_ORIGIN", ORIGIN)
    with serve() as port:
        status, _allow, body = get_router(port, ORIGIN)
    assert status == 200
    payload = json.loads(body)
    brier = payload["brier"]
    assert brier[houston] == pytest.approx(((0.8 - 1) ** 2 + (0.2 - 1) ** 2) / 2)
    assert brier[north] == pytest.approx(0.25)
    assert pending not in brier
    latest = {item["check_id"]: item for item in payload["checks"]}
    assert latest[houston]["probability"] == pytest.approx(0.2)
    assert as_bool(latest[houston]["outcome"]) is True
    assert as_bool(latest[north]["outcome"]) is False
    assert as_bool(latest[pending]["outcome"]) is None


def test_seit_gm_router_01_alert_feed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SEIT-GM-ROUTER-01: an alert-band check appends one alert activity event."""
    path = prepare(tmp_path, monkeypatch)
    store = MemorySignals()
    targets = {
        "LZ_HOUSTON": 0.4999,
        "LZ_NORTH": 0.5,
        "LZ_SOUTH": 0.7999,
        "LZ_WEST": 0.8,
    }
    hour = delivery(1)
    predictions = []
    for zone, target in targets.items():
        store.add(RT_REPORT, zone, HOUR + timedelta(minutes=15), 15, 25.0)
        store.add(DA_REPORT, zone, hour, 60, 25.0)
        predictions.append(prediction(zone, hour, score_for(target)))
    install(monkeypatch, store, predictions, {"t": NOW})
    decision_router.tick()
    alert_id = check_id("LZ_WEST", hour)
    events = alert_events(path)
    assert [event["subject_id"] for event in events] == [alert_id]
    assert events[0]["entry_type"] == "alert"
    assert check_id("LZ_HOUSTON", hour) not in {event["subject_id"] for event in events}
    assert check_id("LZ_SOUTH", hour) not in {event["subject_id"] for event in events}


def test_seit_gm_router_01_jev_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SEIT-GM-ROUTER-01: GET /v1/router reports jev.enabled()."""
    prepare(tmp_path, monkeypatch)
    install(monkeypatch, MemorySignals(), [], {"t": NOW})
    state = {"on": False}

    def flag() -> bool:
        return state["on"]

    monkeypatch.setattr(jev, "enabled", flag)
    if hasattr(decision_router, "jev"):
        monkeypatch.setattr(decision_router.jev, "enabled", flag)
    if hasattr(decision_router, "enabled"):
        monkeypatch.setattr(decision_router, "enabled", flag)
    monkeypatch.setenv("GRIDMARKET_CORS_ORIGIN", ORIGIN)
    with serve() as port:
        off_status, _off_allow, off_body = get_router(port, ORIGIN)
        state["on"] = True
        on_status, _on_allow, on_body = get_router(port, ORIGIN)
    assert off_status == 200
    assert json.loads(off_body)["jev_enabled"] is False
    assert on_status == 200
    assert json.loads(on_body)["jev_enabled"] is True


def test_seit_gm_router_02_no_order_no_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SEIT-GM-ROUTER-02: alert ticks place no orders and the module holds no key."""
    path = prepare(tmp_path, monkeypatch)
    store = MemorySignals()
    hour = delivery(1)
    zone = "LZ_WEST"
    store.add(RT_REPORT, zone, HOUR + timedelta(minutes=15), 15, 25.0)
    store.add(DA_REPORT, zone, hour, 60, 25.0)
    install(
        monkeypatch,
        store,
        [prediction(zone, hour, score_for(0.8))],
        {"t": NOW},
    )
    before = counts(path)
    decision_router.tick()
    assert any(row["band"] == "alert" for row in rows(path))
    assert counts(path) == before
    source = ROUTER_PY.read_text()
    for needle in (
        "GRIDMARKET_ADMIN_KEY",
        "GRIDMARKET_WORKER_KEY",
        "GRIDMARKET_JEV_KEY",
        "Authorization",
        "Bearer ",
    ):
        assert needle not in source
    assert order_imports() == []


def test_seit_gm_api_05_router_cors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SEIT-GM-API-05: /v1/router echoes GRIDMARKET_CORS_ORIGIN and no other origin."""
    prepare(tmp_path, monkeypatch)
    install(monkeypatch, MemorySignals(), [], {"t": NOW})
    monkeypatch.setenv("GRIDMARKET_CORS_ORIGIN", ORIGIN)
    with serve() as port:
        status, allow, _body = get_router(port, ORIGIN)
        other_status, other_allow, _other = get_router(port, OTHER_ORIGIN)
    assert status == 200
    assert allow == ORIGIN
    assert other_status == 200
    assert other_allow is None


def test_router_matches_live_report_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    """F2: market checks resolve against the uppercase ids the poller stores."""
    assert decision_router.DA_REPORT == "NP4-190-CD"
    assert decision_router.RT_REPORT == "NP6-905-CD"
    store = MemorySignals()
    hour = delivery(2)
    store.add("NP4-190-CD", "LZ_HOUSTON", hour, 60, 80.0)
    store.add("NP6-905-CD", "LZ_HOUSTON", HOUR + timedelta(minutes=15), 15, 90.0)
    install(monkeypatch, store, [prediction("LZ_HOUSTON", hour, 50.0)], {"t": NOW})
    assert [c.check_id for c in decision_router.market_checks()] == [
        check_id("LZ_HOUSTON", hour)
    ]
    for minutes in (0, 15, 30, 45):
        store.add("NP6-905-CD", "LZ_HOUSTON", hour + timedelta(minutes=minutes), 15, 90.0)
    assert decision_router._market_outcome(f"LZ_HOUSTON:{hour.isoformat()}") is True
