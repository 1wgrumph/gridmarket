"""S10 heartbeat, health checks, and outage checks (SEIT-GM-PROV-03/04)."""

import asyncio
import sqlite3
import threading
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gridmarket_server import decision_router, ercot, health, main
from gridmarket_server.contracts import WorkerStats
from gridmarket_server.providers import enabled


@pytest.fixture
def service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "health.db"
    monkeypatch.setenv("GRIDMARKET_DB", str(db_path))
    monkeypatch.setenv("GRIDMARKET_LONESTAR", "on")
    monkeypatch.setenv("GRIDMARKET_NWS", "off")
    monkeypatch.setenv("GRIDMARKET_ADMIN_KEY", "s10-local-admin-key")
    monkeypatch.delenv("GRIDMARKET_WORKER_URL", raising=False)
    with TestClient(main.create_app(), client=("127.0.0.1", 0)) as client:
        with sqlite3.connect(db_path) as db:
            for provider in ("base_sim", "lonestar"):
                db.execute(
                    "INSERT OR IGNORE INTO providers (id, display_name) VALUES (?, ?)",
                    (provider, provider),
                )
                db.execute(
                    "INSERT OR REPLACE INTO provider_health "
                    "(provider_id, online, last_heartbeat) VALUES (?, 1, CURRENT_TIMESTAMP)",
                    (provider,),
                )
        yield client, db_path


def _heartbeat_age(db_path: Path, provider: str, seconds: int) -> None:
    stamp = (datetime.now(UTC) - timedelta(seconds=seconds)).isoformat()
    with sqlite3.connect(db_path) as db:
        db.execute(
            "UPDATE provider_health SET last_heartbeat=? WHERE provider_id=?", (stamp, provider)
        )


def test_seit_gm_prov_04_heartbeat_every_enabled_adapter(service, monkeypatch) -> None:
    _, db_path = service
    calls = []
    for name, adapter in enabled().items():
        monkeypatch.setattr(adapter, "heartbeat", lambda self, name=name: calls.append(name))
    health.tick()
    assert set(calls) == {"base_sim", "lonestar"}
    with sqlite3.connect(db_path) as db:
        rows = dict(db.execute("SELECT provider_id, last_heartbeat FROM provider_health"))
    assert all(rows[name] for name in calls)


def test_seit_gm_prov_04_heartbeat_30_second_boundary_and_recovery(service) -> None:
    _, db_path = service
    _heartbeat_age(db_path, "lonestar", 29)
    assert health.is_online("lonestar") is True
    _heartbeat_age(db_path, "lonestar", 31)
    assert health.is_online("lonestar") is False
    with sqlite3.connect(db_path) as db:
        assert (
            db.execute(
                "SELECT online FROM provider_health WHERE provider_id='lonestar'"
            ).fetchone()[0]
            == 0
        )
    health.heartbeat("lonestar")
    assert health.is_online("lonestar") is True


def test_seit_gm_router_03_worker_and_provider_health_bands(service, monkeypatch) -> None:
    _, db_path = service
    monkeypatch.setattr(ercot, "worker_stats", lambda: WorkerStats(requests=100, snapshot_age_s=0))
    healthy = [row for row in decision_router.evaluate() if row.family == "health"]
    assert {row.subject.lower() for row in healthy} >= {"worker", "base_sim", "lonestar"}
    assert all(row.horizon_s == 900 and 0 <= row.probability < 0.5 for row in healthy)
    assert all(row.band == "log" for row in healthy)
    monkeypatch.setattr(
        ercot,
        "worker_stats",
        lambda: WorkerStats(
            requests=100, errors=100, http_429=100, latencies_ms=[20_000] * 100, snapshot_age_s=3600
        ),
    )
    _heartbeat_age(db_path, "lonestar", 31)
    unhealthy = [row for row in decision_router.evaluate() if row.family == "health"]
    by_subject = {row.subject.lower(): row for row in unhealthy}
    assert by_subject["worker"].probability >= 0.8
    assert by_subject["worker"].band == "alert"
    assert by_subject["lonestar"].probability == 1.0
    assert by_subject["lonestar"].band == "alert"
    assert all(0 <= row.probability <= 1 for row in unhealthy)


def test_seit_gm_router_03_each_worker_stat_changes_probability(service, monkeypatch) -> None:
    def worker_probability(stats: WorkerStats) -> float:
        monkeypatch.setattr(ercot, "worker_stats", lambda: stats)
        checks = [row for row in decision_router.evaluate() if row.family == "health"]
        return next(row.probability for row in checks if row.subject.lower() == "worker")

    baseline = worker_probability(WorkerStats(requests=100, snapshot_age_s=0))
    variants = (
        WorkerStats(requests=100, errors=100, snapshot_age_s=0),
        WorkerStats(requests=100, http_429=100, snapshot_age_s=0),
        WorkerStats(requests=100, latencies_ms=[20_000] * 100, snapshot_age_s=0),
        WorkerStats(requests=100, snapshot_age_s=3600),
    )
    assert all(worker_probability(stats) > baseline for stats in variants)


def test_seit_gm_api_07_outage_is_admin_only(service) -> None:
    client, db_path = service
    url = "/v1/admin/providers/lonestar/outage"
    with sqlite3.connect(db_path) as db:
        outage_before = db.execute(
            "SELECT outage_until FROM provider_health WHERE provider_id='lonestar'"
        ).fetchone()[0]
    for headers, status in (
        ({}, 401),
        ({"Authorization": "Bearer wrong"}, 401),
        ({"Authorization": "Bearer s10-local-admin-key", "CF-Connecting-IP": "192.0.2.1"}, 403),
    ):
        response = client.post(url, headers=headers, json={"active": True})
        assert response.status_code == status, response.text
        with sqlite3.connect(db_path) as db:
            assert (
                db.execute(
                    "SELECT outage_until FROM provider_health WHERE provider_id='lonestar'"
                ).fetchone()[0]
                == outage_before
            )
    remote = TestClient(client.app, client=("192.0.2.1", 0))
    assert (
        remote.post(
            url, headers={"Authorization": "Bearer s10-local-admin-key"}, json={"active": True}
        ).status_code
        == 403
    )


def test_seit_gm_prov_03_outage_start_end_and_auto_end(service) -> None:
    client, db_path = service
    url = "/v1/admin/providers/lonestar/outage"
    headers = {"Authorization": "Bearer s10-local-admin-key"}
    started = client.post(url, headers=headers, json={"active": True})
    assert started.status_code in (200, 201, 204), started.text
    with sqlite3.connect(db_path) as db:
        expires = db.execute(
            "SELECT outage_until FROM provider_health WHERE provider_id='lonestar'"
        ).fetchone()[0]
    expiry = datetime.fromisoformat(expires)
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)
    assert (
        timedelta(minutes=9, seconds=50)
        <= expiry - datetime.now(UTC)
        <= timedelta(minutes=10, seconds=10)
    )
    _heartbeat_age(db_path, "lonestar", 31)
    health.tick()
    assert health.is_online("lonestar") is False
    assert health.is_online("base_sim") is True
    assert "lonestar" in client.get("/v1/providers/health").text.lower()
    decision_router.tick()
    checks = client.get("/v1/router")
    assert checks.status_code == 200
    assert "lonestar" in checks.text.lower() and "alert" in checks.text.lower()
    assert client.post(url, headers=headers, json={"active": False}).status_code in (200, 204)
    health.tick()
    assert health.is_online("lonestar") is True
    assert client.post(url, headers=headers, json={"active": True}).status_code in (200, 204)
    with sqlite3.connect(db_path) as db:
        db.execute(
            "UPDATE provider_health SET outage_until=? WHERE provider_id='lonestar'",
            ((datetime.now(UTC) - timedelta(seconds=1)).isoformat(),),
        )
    health.tick()
    assert health.is_online("lonestar") is True


def test_seit_gm_prov_04_public_health_route(service) -> None:
    client, _ = service
    response = client.get("/v1/providers/health")
    assert response.status_code == 200
    assert "base_sim" in response.text and "lonestar" in response.text


def test_seit_gm_prov_04_heartbeat_loop_runs_every_ten_seconds() -> None:
    assert "repeat(10, health.tick, delay_first=True)" in Path(main.__file__).read_text()


def test_health_live_provider_documents(service, monkeypatch) -> None:
    """F1/ATE-P2-05: real routes expose joinable counts and heartbeat/outage state."""
    client, db_path = service
    now = datetime.now(UTC)
    monkeypatch.setattr(health, "_now", lambda: now)
    health.tick()
    decision_router.tick()
    documents = {}
    for path in ("/v1/providers", "/v1/providers/health", "/v1/router"):
        response = client.get(path)
        assert response.status_code == 200
        documents[path] = response.json()
    with sqlite3.connect(db_path) as db:
        counts = dict(db.execute("SELECT provider_id, COUNT(*) FROM assets GROUP BY provider_id"))
    rows = {row["id"]: row for row in documents["/v1/providers/health"]}
    assert set(rows) == {"base_sim", "lonestar"}
    for provider in documents["/v1/providers"]:
        name = provider["id"]
        assert provider["participants"] == (40 if name == "base_sim" else 20)
        assert rows[name] == {
            "id": name,
            "display_name": provider["display_name"],
            "online": True,
            "online_assets": counts[name] - (name == "lonestar"),
            "last_heartbeat": now.isoformat(),
            "heartbeat_age_s": 0.0,
            "outage_active": False,
            "outage_until": None,
        }
        assert any(
            check["subject"] == name and check["family"] == "health"
            for check in documents["/v1/router"]["checks"]
        )
    headers = {"Authorization": "Bearer s10-local-admin-key"}
    expiry = (now + timedelta(minutes=10)).isoformat()
    response = client.post(
        "/v1/admin/providers/lonestar/outage", headers=headers, json={"active": True}
    )
    assert response.status_code == 200
    assert response.json() == {"provider_id": "lonestar", "active": True, "outage_until": expiry}
    monkeypatch.setattr(health, "_now", lambda: now + timedelta(seconds=31))
    health.tick()
    row = next(row for row in health.providers_health() if row["id"] == "lonestar")
    assert row == {
        "id": "lonestar",
        "display_name": "LoneStar Storage",
        "online": False,
        "online_assets": 0,
        "last_heartbeat": now.isoformat(),
        "heartbeat_age_s": 31.0,
        "outage_active": True,
        "outage_until": expiry,
    }
    monkeypatch.setattr(health, "_now", lambda: now + timedelta(minutes=10))
    health.tick()
    row = next(row for row in health.providers_health() if row["id"] == "lonestar")
    assert row["online"] is True and row["online_assets"] == counts["lonestar"] - 1
    assert row["outage_active"] is False and row["outage_until"] is None
    with sqlite3.connect(db_path) as db:
        assert db.execute(
            "SELECT outage_until FROM provider_health WHERE provider_id='lonestar'"
        ).fetchone() == (None,)


def test_health_admin_error_contract(service, monkeypatch) -> None:
    """ATE-P2-01: deny missing keys and nonlocal callers with the API envelope."""
    # Exercise the health router guard itself; the app also guards admin paths.
    app = FastAPI()
    app.include_router(health.router)
    client = TestClient(app, client=("127.0.0.1", 0))
    url = "/v1/admin/providers/lonestar/outage"
    authorized = {"Authorization": "Bearer s10-local-admin-key"}
    for headers in (
        {},
        {"Authorization": "Bearer wrong"},
        {"Authorization": "bearer s10-local-admin-key"},
    ):
        response = client.post(url, headers=headers, json={"active": True})
        assert response.status_code == 401
        assert response.json() == {
            "error": {"code": "UNAUTHENTICATED", "message": "Admin key required"}
        }
    for host, headers in (
        ("192.0.2.1", authorized),
        ("untrusted", authorized),
        ("127.0.0.1", authorized | {"CF-Connecting-IP": "192.0.2.1"}),
    ):
        remote = TestClient(client.app, client=(host, 0))
        response = remote.post(url, headers=headers, json={"active": True})
        assert response.status_code == 403
        assert response.json() == {
            "error": {"code": "FORBIDDEN", "message": "Admin routes are local only"}
        }
    for host in ("::1", "172.23.0.1"):
        local = TestClient(client.app, client=(host, 0))
        assert local.post(url, headers=authorized, json={"active": False}).status_code == 200
    denied = TestClient(client.app, client=("testclient", 0))
    assert denied.post(url, headers=authorized, json={"active": False}).status_code == 403
    monkeypatch.delenv("GRIDMARKET_ADMIN_KEY")
    response = client.post(url, headers={"Authorization": "Bearer "}, json={"active": True})
    assert response.status_code == 401


def test_health_risk_calibration_and_check_contract(service, monkeypatch) -> None:
    """ATE-P2-01: health calibration, p95 and bands retain their numeric contract."""
    import math

    now = datetime.now(UTC)
    monkeypatch.setattr(health, "_now", lambda: now)
    health.tick()
    # Existing worker telemetry fields: partial errors, throttling, latency and snapshot age.
    monkeypatch.setattr(
        ercot,
        "worker_stats",
        lambda: WorkerStats(
            requests=100,
            errors=10,
            http_429=20,
            latencies_ms=list(range(1000, 21000, 1000)),
            snapshot_age_s=30,
        ),
    )
    rows = {row.subject: row for row in health.checks()}
    probability = 1 / (1 + math.exp(-(-3 + 2 * (0.1 + 0.2 + 0.95 + 0.25))))
    assert rows["worker"].probability == pytest.approx(probability)
    for p, band in ((0.49, "log"), (0.5, "review"), (0.79, "review"), (0.8, "alert")):
        row = health._check("worker", p, now)
        assert asdict(row) == {
            "check_id": "health:worker",
            "family": "health",
            "subject": "worker",
            "horizon_s": 900,
            "probability": p,
            "band": band,
            "baseline": True,
            "jev_probability": None,
            "created_at": now.isoformat(),
            "resolves_at": (now + timedelta(seconds=900)).isoformat(),
            "outcome": None,
        }
    assert health._risk([-1, 2]) == pytest.approx(1 / (1 + math.exp(1)))
    assert rows["base_sim"].probability == pytest.approx(1 / (1 + math.exp(3)))


def test_s43b_startup_waits_for_first_health_tick(tmp_path, monkeypatch):
    monkeypatch.setenv("GRIDMARKET_DB", str(tmp_path / "startup.db"))
    monkeypatch.setenv("GRIDMARKET_NWS", "off")
    monkeypatch.delenv("GRIDMARKET_WORKER_URL", raising=False)
    entered, release = threading.Event(), threading.Event()
    real_tick = health.tick

    def held_tick():
        entered.set()
        assert release.wait(5), "startup test did not release health tick"
        real_tick()

    monkeypatch.setattr(health, "tick", held_tick)

    async def start():
        app = main.create_app()
        lifespan = app.router.lifespan_context(app)
        startup = asyncio.create_task(lifespan.__aenter__())
        try:
            assert await asyncio.to_thread(entered.wait, 5), "first health tick did not start"
            assert not startup.done(), "startup accepted requests before health tick completed"
        finally:
            release.set()
            await startup
            await lifespan.__aexit__(None, None, None)

    asyncio.run(start())
