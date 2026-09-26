"""S77 sweep repair: deployment-as-flown regressions (R5-01/02/03, R6-01/02/07/08/09/11/12, R4-01/02/11/16/17).

Each test fails on candidate fd1b9c4 for the finding's reason and passes after
the repair. Live-server tests use loopback only (see conftest.py).
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import sqlite3
import sys
import threading
import time
from dataclasses import asdict
from pathlib import Path

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
SDK = ROOT / "sdk" / "python"
if str(SDK) not in sys.path:
    sys.path.insert(0, str(SDK))
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from gridmarket import Client, GridMarketError  # noqa: E402

from gridmarket_server import bots, economy, health, main, population  # noqa: E402

SCHEMA = ROOT / "backend/gridmarket_server/schema.sql"
SECRET = "s77-bot-secret"
ADMIN = "s77-admin-key"
MASTER = "20260926"
GATEWAY = ("172.23.0.1", 41100)  # compose bridge gateway as the app sees the host


@pytest.fixture
def app_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "s77.db"
    monkeypatch.setenv("GRIDMARKET_DB", str(db_path))
    monkeypatch.setenv("GRIDMARKET_NWS", "off")
    monkeypatch.setenv("GRIDMARKET_BOT_SECRET", SECRET)
    monkeypatch.setenv("GRIDMARKET_BOT_MASTER_SEED", MASTER)
    monkeypatch.setenv("GRIDMARKET_ADMIN_KEY", ADMIN)
    monkeypatch.delenv("GRIDMARKET_WORKER_URL", raising=False)
    return db_path


def key_for(index: int, secret: str = SECRET) -> str:
    digest = hmac.new(secret.encode(), f"bot:{index}".encode(), hashlib.sha256).digest()
    return "gm_" + base64.urlsafe_b64encode(digest).decode("ascii")[:32]


# R6-01: empty env must mean unset, not override image/code defaults.
def test_s77_empty_env_means_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GRIDMARKET_DB", "")
    monkeypatch.setenv("GRIDMARKET_BOT_MASTER_SEED", "")
    main.normalize_env()
    assert "GRIDMARKET_DB" not in os.environ
    assert "GRIDMARKET_BOT_MASTER_SEED" not in os.environ
    from gridmarket_server import seed

    db_path = tmp_path / "seed.db"
    with sqlite3.connect(db_path) as db:
        db.executescript(SCHEMA.read_text())
        seed.seed(db)
        assert db.execute("SELECT value FROM bot_meta WHERE key='master_seed'").fetchone() == (
            MASTER,
        )


def test_s77_env_example_comments_defaulted_keys() -> None:
    example = (ROOT / ".env.example").read_text()
    assert "\nGRIDMARKET_DB=\n" not in example
    assert "\nGRIDMARKET_BOT_MASTER_SEED=\n" not in example


# R5-02/R6-07: the host owner behind the compose gateway may act with the key.
@pytest.mark.parametrize("path", ["/v1/admin/bots", "/v1/admin/providers/base_sim/outage"])
def test_s77_gateway_peer_with_key_may_act(app_env, path: str) -> None:
    body = {"count": 1} if path.endswith("bots") else {"active": True}
    with TestClient(main.create_app(), client=GATEWAY) as client:
        response = client.post(
            path, json=body, headers={"Authorization": f"Bearer {ADMIN}"}
        )
        assert response.status_code == 200, response.text


@pytest.mark.parametrize("path", ["/v1/admin/bots", "/v1/admin/providers/base_sim/outage"])
def test_s77_admin_denies_tunnel_public_and_testclient(app_env, path: str) -> None:
    body = {"count": 1} if path.endswith("bots") else {"active": True}
    key = {"Authorization": f"Bearer {ADMIN}"}
    with TestClient(main.create_app(), client=GATEWAY) as client:
        assert (
            client.post(
                path, json=body, headers=key | {"CF-Connecting-IP": "203.0.113.5"}
            ).status_code
            == 403
        )
        assert (
            client.post(
                path,
                json=body,
                headers={"Authorization": "Bearer wrong", "CF-Connecting-IP": "203.0.113.5"},
            ).status_code
            == 403
        )
        assert (
            client.post(path, json=body, headers={"Authorization": "Bearer wrong"}).status_code
            == 401
        )
    with TestClient(main.create_app(), client=("203.0.113.5", 50000)) as remote:
        assert remote.post(path, json=body, headers=key).status_code == 403
    with TestClient(main.create_app()) as default:  # peer "testclient" is not allowlisted
        assert default.post(path, json=body, headers=key).status_code == 403


# R5-03/R4-11: spawn refuses without GRIDMARKET_BOT_SECRET; no public keys.
def test_s77_spawn_requires_bot_secret(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "s77-nosecret.db"
    monkeypatch.setenv("GRIDMARKET_DB", str(db_path))
    monkeypatch.setenv("GRIDMARKET_NWS", "off")
    monkeypatch.delenv("GRIDMARKET_BOT_SECRET", raising=False)
    monkeypatch.setenv("GRIDMARKET_BOT_MASTER_SEED", MASTER)
    monkeypatch.setenv("GRIDMARKET_ADMIN_KEY", ADMIN)
    monkeypatch.delenv("GRIDMARKET_WORKER_URL", raising=False)
    with TestClient(main.create_app(), client=("127.0.0.1", 0)) as client:
        response = client.post(
            "/v1/admin/bots", json={"count": 1}, headers={"Authorization": f"Bearer {ADMIN}"}
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "BOT_SECRET_UNSET"
        public = key_for(60, secret="")
        assert (
            client.get("/v1/account", headers={"Authorization": f"Bearer {public}"}).status_code
            == 401
        )
        with sqlite3.connect(db_path) as db:
            assert db.execute("SELECT COUNT(*) FROM bots").fetchone()[0] == 60


def _profile(bot_type: str, zone: str = "LZ_HOUSTON", **extra) -> dict:
    base: dict = {
        "bot_type": bot_type,
        "blend": {bot_type: 0.7, "noise trader": 0.2, "saver": 0.1},
        "traits": {
            "risk appetite": 0.6,
            "patience": 0.5,
            "reaction delay": 0.2,
            "loss aversion": 0.3,
            "herd versus contrarian": 0.5,
            "daily activity pattern": 0.7,
            "wealth": 0.5,
        },
        "household": {"batteries": [13.5], "zone": zone, "reserve_pct": 0.2},
        "employed": True,
        "losses": 0,
        "loss_share": 0.0,
    }
    base.update(extra)
    return base


def _products() -> list[dict]:
    return [
        {
            "id": f"{kind}-{zone}-20260926{hour:02d}",
            "symbol": f"{kind}-{zone}-20260926{hour:02d}",
            "zone": zone,
            "delivery_hour": f"2026-09-26T{hour:02d}:00:00+00:00",
            "status": "open",
        }
        for zone in ("LZ_HOUSTON", "LZ_NORTH")
        for kind in ("SPOT", "FLEX")
        for hour in (14, 18)
    ]


def _predictions(level: str = "MEDIUM", confidence: float = 0.6, ev: float = 0.2) -> list[dict]:
    return [
        {
            "zone": zone,
            "delivery_hour": f"2026-09-26T{hour:02d}:00:00+00:00",
            "score": 80.0 if level == "HIGH" else 46.0,
            "level": level,
            "confidence": confidence,
            "expected_value": ev,
            "market_price": 0.10,
            "drivers": [],
        }
        for zone in ("LZ_HOUSTON", "LZ_NORTH")
        for hour in (14, 18)
    ]


# R4-02: orders depend on the bot's blend and on live predictions.
def test_s77_strategy_orders_differ_by_blend() -> None:
    products, predictions = _products(), _predictions()
    maker = bots.strategy_order(
        {"bot_index": 0, "bot_type": "market maker"},
        _profile("market maker"),
        products,
        predictions,
        [],
        {},
        0,
    )
    noise = bots.strategy_order(
        {"bot_index": 59, "bot_type": "noise trader"},
        _profile("noise trader", zone="LZ_NORTH"),
        products,
        predictions,
        [],
        {},
        0,
    )
    assert maker is not None and noise is not None
    assert (maker["product_id"], maker["side"], maker["price_cents"], maker["quantity"]) != (
        noise["product_id"],
        noise["side"],
        noise["price_cents"],
        noise["quantity"],
    )


def test_s77_score_follower_buys_only_high_conviction() -> None:
    products = _products()
    row = {"bot_index": 4, "bot_type": "score follower"}
    profile = _profile("score follower")
    high = bots.strategy_order(
        row, profile, products, _predictions("HIGH", 0.9, 0.5), [], {}, 0
    )
    assert high is not None and high["side"] == "buy" and high["product_id"].startswith("FLEX-")
    assert bots.strategy_order(row, profile, products, _predictions(), [], {}, 0) is None


def test_s77_heat_seller_stays_in_own_zone() -> None:
    order = bots.strategy_order(
        {"bot_index": 8, "bot_type": "heat seller"},
        _profile("heat seller", zone="LZ_NORTH"),
        _products(),
        _predictions(),
        [],
        {},
        0,
    )
    assert order is not None and order["side"] == "sell"
    assert order["product_id"].startswith("SPOT-LZ_NORTH-")


@pytest.fixture
def server(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    db_path = tmp_path / "s77-live.db"
    monkeypatch.setenv("GRIDMARKET_DB", str(db_path))
    monkeypatch.setenv("GRIDMARKET_NWS", "off")
    monkeypatch.setenv("GRIDMARKET_BOT_SECRET", SECRET)
    monkeypatch.setenv("GRIDMARKET_BOT_MASTER_SEED", MASTER)
    monkeypatch.setenv("GRIDMARKET_ADMIN_KEY", ADMIN)
    monkeypatch.delenv("GRIDMARKET_WORKER_URL", raising=False)
    app = main.create_app()
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    running = uvicorn.Server(config)
    thread = threading.Thread(target=running.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not running.started and time.monotonic() < deadline:
        time.sleep(0.01)
    assert running.started
    port = running.servers[0].sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}", db_path
    finally:
        running.should_exit = True
        thread.join(timeout=5)


class Clock:
    def __init__(self) -> None:
        self.t = 1_000_000.0

    def now(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def test_s77_step_all_places_diverse_orders(server, monkeypatch) -> None:
    base_url, db_path = server
    monkeypatch.setattr(bots, "_roster", [])
    monkeypatch.setattr(bots, "_roster_at", None)
    monkeypatch.setattr(bots, "_roster_url", None)
    monkeypatch.setattr(bots, "_limits", {})
    clock = Clock()
    for _ in range(12):
        bots.step_all(base_url, clock)
        clock.advance(10)
    with sqlite3.connect(db_path) as db:
        rows = db.execute("SELECT DISTINCT product_id FROM orders").fetchall()
        prices = db.execute("SELECT DISTINCT price_cents FROM orders").fetchall()
        count = db.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    assert count >= 10
    assert len(rows) > 1
    assert len(prices) > 1


# R4-16: rejections are logged with their code instead of swallowed.
def test_s77_submit_logs_rejections(caplog: pytest.LogCaptureFixture) -> None:
    class Clock:
        def now(self) -> float:
            return 1.0

    class Denied:
        base_url = "http://127.0.0.1:9"

        def place_order(self, order, key):
            raise GridMarketError(400, "INSUFFICIENT_CAPACITY", "no capacity")

    with caplog.at_level(logging.WARNING, logger="gridmarket_server.bots"):
        assert bots.submit(8, Denied(), Clock(), {"product_id": "p"}) is None
    assert "INSUFFICIENT_CAPACITY" in caplog.text or "400" in caplog.text


# R4-17: rebuild replays the cohort seed and runs at startup.
def test_s77_rebuild_replays_cohort_seed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "s77-rebuild.db"
    monkeypatch.setenv("GRIDMARKET_DB", str(db_path))
    spec = population.sample(MASTER, 60, 1, seed="cohort-seed")[0]
    profile = asdict(spec) | {"cohort_seed": "cohort-seed"}
    with sqlite3.connect(db_path) as db:
        db.executescript(SCHEMA.read_text())
        db.execute("INSERT INTO bot_meta VALUES ('master_seed', ?)", (MASTER,))
        db.execute(
            "INSERT INTO accounts(id, display_name, cash_cents) VALUES ('acct-bot-60', 'x', 100)"
        )
        db.execute(
            "INSERT INTO bots(id, account_id, bot_index, bot_type, provider_id, profile_json) "
            "VALUES ('bot-60', 'acct-bot-60', 60, 'tampered', 'base_sim', ?)",
            (json.dumps(profile),),
        )
        db.commit()
        economy.rebuild(db)
        db.commit()
        rebuilt = json.loads(
            db.execute("SELECT profile_json FROM bots WHERE bot_index = 60").fetchone()[0]
        )
    assert rebuilt["bot_type"] == spec.bot_type
    assert rebuilt["traits"] == spec.traits
    assert rebuilt["cohort_seed"] == "cohort-seed"


def test_s77_startup_rebuilds_spawned_cohort(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "s77-restart.db"
    monkeypatch.setenv("GRIDMARKET_DB", str(db_path))
    monkeypatch.setenv("GRIDMARKET_NWS", "off")
    monkeypatch.setenv("GRIDMARKET_BOT_SECRET", SECRET)
    monkeypatch.setenv("GRIDMARKET_BOT_MASTER_SEED", MASTER)
    monkeypatch.setenv("GRIDMARKET_ADMIN_KEY", ADMIN)
    monkeypatch.delenv("GRIDMARKET_WORKER_URL", raising=False)
    with TestClient(main.create_app(), client=("127.0.0.1", 0)) as client:
        spawned = client.post(
            "/v1/admin/bots",
            json={"count": 1, "seed": "cohort-seed"},
            headers={"Authorization": f"Bearer {ADMIN}"},
        )
        assert spawned.status_code == 200, spawned.text
    with TestClient(main.create_app(), client=("127.0.0.1", 0)) as client:
        body = client.get("/v1/bots/bot-60").json()
    spec = population.sample(MASTER, 60, 1, seed="cohort-seed")[0]
    assert body["bot_type"] == spec.bot_type
    assert body["traits"] == spec.traits


# R6-08: write failures are honest: envelope + failing writability probe.
def test_s77_readonly_db_envelope_and_unwritable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "s77-ro.db"
    monkeypatch.setenv("GRIDMARKET_DB", str(db_path))
    monkeypatch.setenv("GRIDMARKET_NWS", "off")
    monkeypatch.setenv("GRIDMARKET_BOT_SECRET", SECRET)
    monkeypatch.setenv("GRIDMARKET_BOT_MASTER_SEED", MASTER)
    monkeypatch.setenv("GRIDMARKET_ADMIN_KEY", ADMIN)
    monkeypatch.delenv("GRIDMARKET_WORKER_URL", raising=False)
    with TestClient(
        main.create_app(), client=("127.0.0.1", 0), raise_server_exceptions=False
    ) as client:
        assert client.post("/v1/sandbox/keys", json={}).status_code == 200
        assert health.db_writable() is True
        db_path.chmod(0o444)
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(db_path) + suffix)
            if sidecar.exists():
                sidecar.chmod(0o444)
        try:
            assert health.db_writable() is False
            failed = client.post("/v1/sandbox/keys", json={})
            assert failed.status_code == 500
            assert failed.json() == {
                "error": {"code": "INTERNAL_ERROR", "message": "Internal error"}
            }
            assert client.get("/v1/market/status").status_code == 200
        finally:
            db_path.chmod(0o644)
            for suffix in ("-wal", "-shm"):
                sidecar = Path(str(db_path) + suffix)
                if sidecar.exists():
                    sidecar.chmod(0o644)


# R5-01/R6-02/R4-01, R6-09/11/12: flown wiring is pinned in the repo files.
def test_s77_compose_and_image_wire_bots() -> None:
    compose = (ROOT / "deploy/compose.yaml").read_text()
    assert "GRIDMARKET_URL: http://app:8000" in compose
    assert "gridmarket-bots-pass" in compose
    dockerfile = (ROOT / "deploy/Dockerfile").read_text()
    assert "sdk/python/gridmarket" in dockerfile
    assert "db_writable" in dockerfile


def test_s77_dev_proxy_port_and_frozen_docs() -> None:
    vite = (ROOT / "dashboard/vite.config.ts").read_text()
    assert "proxy" in vite and "/v1" in vite and "127.0.0.1:8000" in vite
    readme = (ROOT / "README.md").read_text()
    assert "--env-file .env" in readme
    assert "uv run --project backend --frozen" in readme
