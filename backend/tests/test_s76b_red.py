"""S76b red tests: scoring, router and health honesty (sweep R3/R4/R6/R7 + A3/A8).

Each test reproduces its finding through the real boundary as flown (real
SQLite store, real tick functions, logical clocks). No wall-clock dependence:
all times are fixed or injected.
"""

import math
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from gridmarket_server import decision_router, ercot, health, market, scoring
from gridmarket_server.contracts import CheckResult, WorkerStats

SCHEMA = Path(scoring.__file__).with_name("schema.sql").read_text()
HOUR = datetime(2026, 9, 28, 20, tzinfo=UTC)  # Mon 15:00 CDT


@pytest.fixture
def db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "s76b.db"
    monkeypatch.setenv("GRIDMARKET_DB", str(path))
    monkeypatch.setenv("GRIDMARKET_NWS", "off")
    monkeypatch.delenv("GRIDMARKET_WORKER_URL", raising=False)
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA)
    return path


@pytest.fixture
def registry(monkeypatch: pytest.MonkeyPatch):
    saved = dict(decision_router.registry)
    decision_router.registry.clear()
    monkeypatch.setattr(decision_router, "now", lambda: datetime.now(UTC))
    yield decision_router.registry
    decision_router.registry.clear()
    decision_router.registry.update(saved)


def add_signal(
    db: sqlite3.Connection,
    report: str,
    zone: str,
    interval: str,
    value: float,
    minutes: int = 60,
    fetched: str | None = None,
) -> None:
    stamp = fetched or datetime.now(UTC).isoformat()
    db.execute(
        "INSERT INTO signals VALUES (?,?,?,?,?,?,?,?,?)",
        (os.urandom(8).hex(), report, zone, interval, minutes, value, "$/MWh", stamp, stamp),
    )


def dart_probability(score: float, da: float, rt: float) -> float:
    sign = (da > rt) - (da < rt)
    return 1 / (1 + math.exp(-(decision_router.K * (score - 50) / 50 + decision_router.B * sign)))


def test_r4_07_on_peak_is_he7_he22_central(db_path: Path) -> None:
    """NERC 5x16 on UTC production inputs: HE7-HE22 Mon-Fri Central (R4 probe C)."""
    assert scoring.on_peak(datetime.fromisoformat("2026-09-28T23:00:00+00:00")) is True  # Mon HE19
    assert (
        scoring.on_peak(datetime.fromisoformat("2026-09-28T07:00:00+00:00")) is False
    )  # Mon 02 CDT
    assert scoring.on_peak(datetime.fromisoformat("2026-10-03T01:00:00+00:00")) is True  # Fri HE21
    assert scoring.on_peak(datetime.fromisoformat("2026-09-28T11:00:00+00:00")) is True  # Mon HE7
    assert scoring.on_peak(datetime.fromisoformat("2026-09-27T18:00:00+00:00")) is False  # Sun
    assert scoring.on_peak(datetime.fromisoformat("2026-09-29T03:00:00+00:00")) is False  # Mon HE23


def test_r4_09_dart_check_aligned_with_outcome(db_path: Path) -> None:
    """Persistence must predict the outcome: DA>RT stays below DA (R4 probe step 2)."""
    with sqlite3.connect(db_path) as db:
        add_signal(db, "NP4-190-CD", "LZ_HOUSTON", HOUR.isoformat(), 60.0)
        for offset in range(4):
            add_signal(
                db,
                "NP6-905-CD",
                "LZ_HOUSTON",
                (HOUR + timedelta(minutes=15 * offset)).isoformat(),
                30.0,
                15,
            )
        db.commit()
    outcome = decision_router._market_outcome(f"LZ_HOUSTON:{HOUR.isoformat()}")
    scored = scoring.score_hour(
        zone="LZ_HOUSTON",
        delivery_hour="2026-09-28T04:00:00+00:00",
        da_price=60,
        rt_price=30,
        hub_price=30,
        load_mw=1,
        load_mean_mw=1,
        outage_mw=0,
        outage_median_mw=0,
        shadow_prices={},
        temperature_f=None,
        alerts=0,
        fresh=True,
        market_price=None,
    )
    assert outcome is not None
    assert (dart_probability(scored.score, 60, 30) > 0.5) == outcome


def test_a3_four_distinct_quarter_hours_required(db_path: Path) -> None:
    """Four copies of one RT reading must not resolve; four distinct ones must (A3)."""
    with sqlite3.connect(db_path) as db:
        add_signal(db, "NP4-190-CD", "LZ_HOUSTON", HOUR.isoformat(), 40.0)
        for dup in range(4):
            add_signal(
                db,
                "NP6-905-CD",
                "LZ_HOUSTON",
                HOUR.isoformat(),
                900.0,
                15,
                fetched=f"2026-09-28T20:{5 * dup:02d}:00+00:00",
            )
        db.commit()
        assert decision_router._market_outcome(f"LZ_HOUSTON:{HOUR.isoformat()}") is None
        db.execute("DELETE FROM signals WHERE report_id='NP6-905-CD'")
        for offset in range(4):
            add_signal(
                db,
                "NP6-905-CD",
                "LZ_HOUSTON",
                (HOUR + timedelta(minutes=15 * offset)).isoformat(),
                30.0,
                15,
            )
        db.commit()
        assert decision_router._market_outcome(f"LZ_HOUSTON:{HOUR.isoformat()}") is not None


def test_a3_latest_observation_wins_per_boundary(db_path: Path) -> None:
    """A corrected interval uses the latest observation, not a duplicate-weighted mean."""
    with sqlite3.connect(db_path) as db:
        add_signal(db, "NP4-190-CD", "LZ_HOUSTON", HOUR.isoformat(), 50.0)
        add_signal(
            db,
            "NP6-905-CD",
            "LZ_HOUSTON",
            HOUR.isoformat(),
            0.0,
            15,
            fetched="2026-09-28T20:05:00+00:00",
        )
        add_signal(
            db,
            "NP6-905-CD",
            "LZ_HOUSTON",
            HOUR.isoformat(),
            100.0,
            15,
            fetched="2026-09-28T20:55:00+00:00",
        )
        for offset in range(1, 4):
            add_signal(
                db,
                "NP6-905-CD",
                "LZ_HOUSTON",
                (HOUR + timedelta(minutes=15 * offset)).isoformat(),
                100.0,
                15,
            )
        db.commit()
    # Latest RT average is 100, above DA 50.
    assert decision_router._market_outcome(f"LZ_HOUSTON:{HOUR.isoformat()}") is False


def test_r4_12_freshness_is_twice_each_poll_interval(db_path: Path) -> None:
    """RT (5-min poll) fetched 100 min ago is stale even though < 7200 s (R4-12)."""
    hour = (datetime.now(UTC) + timedelta(hours=3)).replace(minute=0, second=0, microsecond=0)
    now = datetime.now(UTC)
    with sqlite3.connect(db_path) as db:
        db.execute(
            "INSERT INTO products(id,symbol,zone,delivery_hour) VALUES ('p','x','LZ_HOUSTON',?)",
            (hour.isoformat(),),
        )
        for report in ("NP4-190-CD", "NP3-565-CD", "NP3-233-CD", "NP6-86-CD"):
            add_signal(db, report, "LZ_HOUSTON", hour.isoformat(), 1, fetched=now.isoformat())
        add_signal(
            db,
            "NP6-905-CD",
            "LZ_HOUSTON",
            hour.isoformat(),
            1,
            fetched=(now - timedelta(minutes=100)).isoformat(),
        )
        add_signal(db, "NP6-905-CD", "HB_HUBAVG", hour.isoformat(), 1, fetched=now.isoformat())
        db.commit()
    (result,) = scoring.predict()
    assert any(row["report_id"] == "NP6-905-CD" and row["stale"] for row in ercot.signals.current())
    fresh_db = db_path.parent / "fresh.db"
    with sqlite3.connect(fresh_db) as db:
        db.executescript(SCHEMA)
        db.execute(
            "INSERT INTO products(id,symbol,zone,delivery_hour) VALUES ('p','x','LZ_HOUSTON',?)",
            (hour.isoformat(),),
        )
        for report in ("NP4-190-CD", "NP3-565-CD", "NP3-233-CD", "NP6-86-CD", "NP6-905-CD"):
            add_signal(db, report, "LZ_HOUSTON", hour.isoformat(), 1, fetched=now.isoformat())
        add_signal(db, "NP6-905-CD", "HB_HUBAVG", hour.isoformat(), 1, fetched=now.isoformat())
        db.commit()
    os.environ["GRIDMARKET_DB"] = str(fresh_db)
    try:
        (fresh_result,) = scoring.predict()
    finally:
        os.environ["GRIDMARKET_DB"] = str(db_path)
    assert result.confidence == pytest.approx(0.6 * fresh_result.confidence)


def test_r4_12_disabled_nws_does_not_cap_confidence(
    db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With GRIDMARKET_NWS=off, absent NWS rows are not stale inputs (R4-12)."""
    monkeypatch.setenv("GRIDMARKET_NWS", "off")
    hour = (datetime.now(UTC) + timedelta(hours=3)).replace(minute=0, second=0, microsecond=0)
    now = datetime.now(UTC)
    with sqlite3.connect(db_path) as db:
        db.execute(
            "INSERT INTO products(id,symbol,zone,delivery_hour) VALUES ('p','x','LZ_HOUSTON',?)",
            (hour.isoformat(),),
        )
        add_signal(db, "NP4-190-CD", "LZ_HOUSTON", hour.isoformat(), 50, fetched=now.isoformat())
        add_signal(db, "NP6-905-CD", "LZ_HOUSTON", hour.isoformat(), 50, fetched=now.isoformat())
        add_signal(db, "NP6-905-CD", "HB_HUBAVG", hour.isoformat(), 50, fetched=now.isoformat())
        add_signal(db, "NP3-565-CD", "LZ_HOUSTON", hour.isoformat(), 1000, fetched=now.isoformat())
        add_signal(db, "NP3-233-CD", "LZ_HOUSTON", hour.isoformat(), 500, fetched=now.isoformat())
        add_signal(db, "NP6-86-CD", "C1", hour.isoformat(), 5, fetched=now.isoformat())
        db.commit()
    (result,) = scoring.predict()
    assert result.confidence > 0.6


def test_r4_15_event_and_aggregate_brier(db_path: Path) -> None:
    """One forecast per event plus an aggregate, alongside per-check Brier (R4 probe 3)."""
    with sqlite3.connect(db_path) as db:
        for tick in range(60):
            probability, outcome = (0.9, 1) if tick == 59 else (0.1, 1)
            db.execute(
                "INSERT INTO router_results VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    f"id{tick}",
                    "market:LZ_HOUSTON:x",
                    "market",
                    "LZ_HOUSTON:x",
                    60,
                    probability,
                    "log",
                    1,
                    None,
                    f"2026-09-28T19:{tick:02d}:00+00:00",
                    "2026-09-28T21:00:00+00:00",
                    outcome,
                ),
            )
        db.commit()

    namespace = SimpleNamespace(headers={})
    body = decision_router.get_router(namespace, namespace)
    assert body["brier"]["market:LZ_HOUSTON:x"] == pytest.approx(0.7967, abs=1e-4)
    assert body["brier_events"]["LZ_HOUSTON:x"] == pytest.approx(0.01)
    assert body["brier_mean"] == pytest.approx(0.01)


def test_r3_07_alert_created_at_matches_activity_format(db_path: Path, registry) -> None:
    """Alert events sort below later orders in /v1/market/activity (R3 p06)."""
    tick_at = datetime(2026, 9, 26, 20, 50, 54, tzinfo=UTC)
    decision_router.register(
        "market",
        lambda: [
            CheckResult(
                "m:z:1",
                "market",
                "z:1",
                60,
                0.9,
                "alert",
                True,
                None,
                tick_at.isoformat(),
                tick_at.isoformat(),
            )
        ],
    )
    decision_router.tick()
    with sqlite3.connect(db_path) as db:
        (created,) = db.execute("SELECT created_at FROM events WHERE entry_type='alert'").fetchone()
        assert "T" not in created
        later = (datetime.fromisoformat(created) + timedelta(seconds=1)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        db.execute("INSERT INTO accounts(id,display_name) VALUES ('a','A')")
        db.execute(
            "INSERT INTO products(id,symbol,zone,delivery_hour) VALUES "
            "('p','FLEX-LZ_HOUSTON-2026092623','LZ_HOUSTON','2026-09-26T23:00:00+00:00')"
        )
        db.execute(
            "INSERT INTO orders(id,account_id,product_id,side,quantity,remaining_qty,"
            "price_cents,status,created_at) VALUES ('o','a','p','buy',1,1,11,'open',?)",
            (later,),
        )
        db.commit()
    feed = market.activity()
    kinds = [(row["type"], row["created_at"]) for row in feed]
    assert kinds[0][0] == "order", kinds
    assert kinds[1][0] == "alert", kinds


def test_r3_08_second_outage_episode_alerts_again(
    db_path: Path, registry, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A new outage episode raises a new alert event; ticks within one episode do not (R3 p07)."""
    clock = {"t": datetime(2026, 9, 26, 12, tzinfo=UTC), "p": 1.0}

    def checks() -> list[CheckResult]:
        probability = clock["p"]
        return [
            CheckResult(
                "health:base_sim",
                "health",
                "base_sim",
                900,
                probability,
                decision_router.band(probability),
                True,
                None,
                clock["t"].isoformat(),
                clock["t"].isoformat(),
            )
        ]

    decision_router.register("health", checks)
    monkeypatch.setattr(decision_router, "now", lambda: clock["t"])

    def alerts() -> int:
        with sqlite3.connect(db_path) as db:
            return db.execute(
                "SELECT COUNT(*) FROM events WHERE entry_type='alert' "
                "AND subject_id='health:base_sim'"
            ).fetchone()[0]

    decision_router.tick()  # episode 1 alert
    clock["t"] += timedelta(seconds=60)
    decision_router.tick()  # same episode: no duplicate
    assert alerts() == 1
    clock["p"] = 0.05  # recovered
    clock["t"] += timedelta(seconds=60)
    decision_router.tick()
    clock["p"] = 1.0  # episode 2 alert
    clock["t"] += timedelta(seconds=60)
    decision_router.tick()
    assert alerts() == 2


def test_r6_06_total_worker_loss_is_alert(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unreachable Worker and very stale snapshots are alert-band, not log (R6-06)."""
    monkeypatch.setattr(ercot, "worker_stats", lambda: WorkerStats(requests=7, errors=7))
    (worker,) = [c for c in health.checks() if c.subject == "worker"]
    assert worker.band == "alert", worker.probability
    monkeypatch.setattr(
        ercot, "worker_stats", lambda: WorkerStats(requests=100, snapshot_age_s=1000)
    )
    (worker,) = [c for c in health.checks() if c.subject == "worker"]
    assert worker.band == "alert", worker.probability


def test_r6_06_fresh_worker_stays_log(monkeypatch: pytest.MonkeyPatch) -> None:
    """A fresh successful snapshot keeps the worker check in log band."""
    monkeypatch.setattr(ercot, "worker_stats", lambda: WorkerStats(requests=100, snapshot_age_s=0))
    (worker,) = [c for c in health.checks() if c.subject == "worker"]
    assert worker.band == "log", worker.probability


def test_r7_07_unparsed_responses_are_alert(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """200 responses that never parse (zero signals) are alert-band (R7-07)."""
    monkeypatch.setattr(ercot, "worker_stats", lambda: WorkerStats(requests=6))
    assert ercot.signals.current() == []
    (worker,) = [c for c in health.checks() if c.subject == "worker"]
    assert worker.band == "alert", worker.probability


def test_a8_outage_alert_within_60_seconds(
    db_path: Path, registry, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The audit schedule: heartbeat t=0, outage t=1, router ticks t=10,70 (A8)."""
    monkeypatch.setenv("GRIDMARKET_LONESTAR", "on")
    t0 = datetime(2026, 9, 26, 12, tzinfo=UTC)
    with sqlite3.connect(db_path) as db:
        for provider in ("base_sim", "lonestar"):
            db.execute("INSERT INTO providers(id,display_name) VALUES (?,?)", (provider, provider))
            db.execute(
                "INSERT INTO provider_health(provider_id,online,last_heartbeat) VALUES (?,1,?)",
                (provider, t0.isoformat()),
            )
        db.execute(
            "UPDATE provider_health SET outage_until=? WHERE provider_id='lonestar'",
            ((t0 + timedelta(seconds=601)).isoformat(),),
        )
        db.commit()
    decision_router.register("health", health.checks)
    clock = {"t": t0}
    monkeypatch.setattr(health, "_now", lambda: clock["t"])
    monkeypatch.setattr(decision_router, "now", lambda: clock["t"])
    first_alert_age = None
    for second in (10, 20, 30, 40, 50, 60, 61, 70):
        clock["t"] = t0 + timedelta(seconds=second)
        health.tick()
        if second in (10, 70):
            decision_router.tick()
        with sqlite3.connect(db_path) as db:
            row = db.execute(
                "SELECT band, created_at FROM router_results WHERE subject='lonestar'"
                " ORDER BY rowid DESC LIMIT 1"
            ).fetchone()
        if row and row[0] == "alert" and first_alert_age is None:
            created = datetime.fromisoformat(row[1])
            first_alert_age = (created - t0).total_seconds() - 1
    assert first_alert_age is not None
    assert first_alert_age <= 60, first_alert_age
