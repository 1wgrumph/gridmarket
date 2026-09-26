"""S10 heartbeat, health checks, and outage checks (SEIT-GM-PROV-03/04)."""

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
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
    monkeypatch.setattr(ercot, "worker_stats", lambda: WorkerStats(requests=100))
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

    baseline = worker_probability(WorkerStats(requests=100))
    variants = (
        WorkerStats(requests=100, errors=100),
        WorkerStats(requests=100, http_429=100),
        WorkerStats(requests=100, latencies_ms=[20_000] * 100),
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
    assert "repeat(10, health.tick)" in Path(main.__file__).read_text()
