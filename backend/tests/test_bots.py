"""S28 red tests for the bot loop and bots API (SEIT-GM-BOT-01/03/07, SEIT-GM-UI-03-API)."""

import ast
import base64
import hashlib
import hmac
import json
import logging
import sqlite3
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient

SDK = Path(__file__).resolve().parents[2] / "sdk" / "python"
if str(SDK) not in sys.path:
    sys.path.insert(0, str(SDK))

from gridmarket import Client

from gridmarket_server import bots, main

BOTS_SOURCE = Path(bots.__file__).read_text()
SECRET = "test-bot-secret"
ADMIN = "test-admin-key"
SCHEMA = Path(__file__).resolve().parents[1] / "gridmarket_server" / "schema.sql"


class Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def now(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def bot_key(index: int) -> str:
    digest = hmac.new(SECRET.encode(), f"bot:{index}".encode(), hashlib.sha256).digest()
    token = base64.urlsafe_b64encode(digest).decode("ascii")
    return "gm_" + token[:32]


def _isolated() -> None:
    tree = ast.parse(BOTS_SOURCE)
    for node in ast.walk(tree):
        names: list[str] = []
        module = ""
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = [alias.name for alias in node.names]
        else:
            continue
        assert "sqlite3" not in module
        assert not module.endswith("market")
        assert "market" not in names
        assert "sqlite3" not in names


def _window_ok(calls: list[tuple[str, float]]) -> None:
    by_key: dict[str, list[float]] = {}
    for key, stamp in calls:
        by_key.setdefault(key, []).append(stamp)
    for stamps in by_key.values():
        stamps.sort()
        for stamp in stamps:
            assert sum(stamp - 60 < earlier <= stamp for earlier in stamps) <= 6


@pytest.fixture
def server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "gridmarket.db"
    monkeypatch.setenv("GRIDMARKET_DB", str(db_path))
    monkeypatch.setenv("GRIDMARKET_NWS", "off")
    monkeypatch.setenv("GRIDMARKET_BOT_SECRET", SECRET)
    monkeypatch.setenv("GRIDMARKET_BOT_MASTER_SEED", "20260926")
    monkeypatch.setenv("GRIDMARKET_ADMIN_KEY", ADMIN)
    monkeypatch.delenv("GRIDMARKET_WORKER_URL", raising=False)
    app = main.create_app()
    app.state.bot_reads = []

    @app.middleware("http")
    async def record_bot_reads(request, call_next):
        if request.method == "GET" and request.url.path == "/v1/bots":
            app.state.bot_reads.append(request.url.path)
        return await call_next(request)

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
        yield f"http://127.0.0.1:{port}", db_path, app
    finally:
        running.should_exit = True
        thread.join(timeout=5)


def _patch_orders(monkeypatch, clock: Clock, calls: list[tuple[str, float]]):
    def wrapped(self, order, idempotency_key):
        calls.append((self.api_key, clock.now()))
        response = httpx.post(
            f"{self.base_url}/v1/orders",
            json=order,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Idempotency-Key": idempotency_key,
            },
            timeout=5,
        )
        if response.status_code >= 400:
            return {"id": idempotency_key, "status": response.status_code}
        return response.json()

    monkeypatch.setattr(Client, "place_order", wrapped)


def test_SEIT_GM_BOT_01_seeded_orders(server, monkeypatch) -> None:
    """Sixty simulated seconds, at least 10 SDK orders from at least 3 derived keys."""
    base_url, db_path, _app = server
    _isolated()
    assert callable(getattr(bots, "step_all", None))
    clock = Clock()
    calls: list[tuple[str, float]] = []
    _patch_orders(monkeypatch, clock, calls)
    started = time.monotonic()
    for _ in range(60):
        bots.step_all(base_url, clock)
        clock.advance(1)
    assert time.monotonic() - started < 30
    assert len(calls) >= 10
    assert len({key for key, _stamp in calls}) >= 3
    conn = sqlite3.connect(db_path)
    try:
        for key, _stamp in calls:
            try:
                account = Client(base_url, key).account()
            except httpx.HTTPError as exc:
                pytest.fail(f"order key was not that bot's derived key: {exc}")
            account_id = account.get("account_id", account.get("id"))
            row = conn.execute(
                "SELECT bot_index FROM bots WHERE account_id = ?", (account_id,)
            ).fetchone()
            assert row is not None
            assert key == bot_key(int(row[0]))
    finally:
        conn.close()


def test_SEIT_GM_BOT_03_order_limit(server, monkeypatch) -> None:
    """At most 6 orders per bot per 60s, and the server rejects an oversized order."""
    base_url, db_path, _app = server
    _isolated()
    assert callable(getattr(bots, "submit", None))
    assert callable(getattr(bots, "step_all", None))
    send = Client.place_order
    clock = Clock()
    calls: list[tuple[str, float]] = []
    _patch_orders(monkeypatch, clock, calls)
    client = Client(base_url, bot_key(0))
    order = {"product_id": "p1", "side": "buy", "quantity": 1, "price_cents": 10}
    for _ in range(7):
        bots.submit(0, client, clock, order)
    assert len(calls) == 6
    calls.clear()
    for _ in range(60):
        bots.step_all(base_url, clock)
        clock.advance(1)
    _window_ok(calls)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA.read_text())
    conn.execute(
        "INSERT INTO products (id, symbol, zone, delivery_hour) "
        "VALUES ('p1', 'LZ_HOUSTON-H', 'LZ_HOUSTON', '2030-01-01T01:00:00Z') "
        "ON CONFLICT(id) DO UPDATE SET delivery_hour=excluded.delivery_hour, status='open'"
    )
    conn.execute(
        "INSERT OR IGNORE INTO accounts (id, display_name, cash_cents) VALUES ('acct-0', 'bot-0', 100000)"
    )
    conn.execute(
        "INSERT OR IGNORE INTO api_keys (id, account_id, key_hash, label) VALUES ('k0', 'acct-0', ?, 'bot')",
        (hashlib.sha256(bot_key(0).encode()).hexdigest(),),
    )
    conn.commit()
    assert conn.execute("SELECT delivery_hour, status FROM products WHERE id='p1'").fetchone() == (
        "2030-01-01T01:00:00Z",
        "open",
    )
    conn.close()
    from gridmarket import GridMarketError

    with pytest.raises(GridMarketError) as caught:
        send(
            Client(base_url, bot_key(0)),
            {"product_id": "p1", "side": "buy", "quantity": 51, "price_cents": 10},
            "risk-too-big",
        )
    assert caught.value.status == 422
    assert caught.value.code == "ORDER_TOO_LARGE"


def test_SEIT_GM_BOT_07_admin_spawn(server) -> None:
    """Admin spawn adds 1-10 sampled bots, rejects the rest, and the loop polls them."""
    base_url, db_path, app = server
    assert callable(getattr(bots, "step_all", None))

    def count() -> int:
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute("SELECT COUNT(*) FROM bots").fetchone()
            return int(row[0])
        finally:
            conn.close()

    def post(body: dict, key: str | None = ADMIN, forwarded: str | None = None) -> httpx.Response:
        headers = {}
        if key is not None:
            headers["Authorization"] = f"Bearer {key}"
        if forwarded is not None:
            headers["CF-Connecting-IP"] = forwarded
        return httpx.post(f"{base_url}/v1/admin/bots", json=body, headers=headers, timeout=5)

    before = count()
    assert post({"count": 1}, key=None).status_code in (401, 403)
    assert post({"count": 1}, key="wrong").status_code in (401, 403)
    assert post({"count": 1}, forwarded="203.0.113.5").status_code == 403
    assert count() == before
    assert post({"count": 0}).status_code == 422
    assert post({"count": 11}).status_code == 422
    assert count() == before
    messages: list[str] = []

    class Grab(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            messages.append(record.getMessage())

    handler = Grab()
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)
    try:
        spawned = post({"count": 1, "seed": "cohort-seed"})
    finally:
        logging.getLogger().removeHandler(handler)
    assert spawned.status_code == 200
    assert count() == before + 1
    assert any("cohort-seed" in message for message in messages)
    conn = sqlite3.connect(db_path)
    try:
        bot_id = conn.execute("SELECT id FROM bots ORDER BY bot_index DESC LIMIT 1").fetchone()[0]
    finally:
        conn.close()
    profile = httpx.get(f"{base_url}/v1/bots/{bot_id}", timeout=5)
    assert profile.status_code == 200
    body = profile.json()
    assert len(body["traits"]) == 7
    assert len(body["household"]["batteries"]) in (1, 2)
    bots.step_all(base_url, Clock())
    assert app.state.bot_reads
    added = post({"count": 10, "seed": "cohort-ten"})
    assert added.status_code == 200
    assert count() == before + 11
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO providers (id, display_name) VALUES ('base_sim', 'Base Simulation')"
        )
        current = int(conn.execute("SELECT COUNT(*) FROM bots").fetchone()[0])
        for n in range(current, 200):
            account_id = f"pad-{n}"
            conn.execute(
                "INSERT OR IGNORE INTO accounts (id, display_name, cash_cents) VALUES (?, ?, 100)",
                (account_id, account_id),
            )
            conn.execute(
                """
                INSERT INTO bots (
                    id, account_id, bot_index, bot_type, provider_id, profile_json, dormant
                ) VALUES (?, ?, ?, 'saver', 'base_sim', '{}', 0)
                """,
                (f"pad-{n}", account_id, 1000 + n),
            )
        conn.commit()
    finally:
        conn.close()
    assert count() == 200
    capped = post({"count": 1, "seed": "over-cap"})
    assert capped.status_code == 409
    assert capped.json()["error"]["code"] == "BOT_CAP"
    assert count() == 200


def test_phase1b_F1_admin_spawn_rejects_non_loopback_peer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-GM-API-07: a non-loopback peer gets 403 and spawns nothing, even with the key."""
    db_path = tmp_path / "gridmarket.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA.read_text())
    conn.commit()
    conn.close()
    monkeypatch.setenv("GRIDMARKET_DB", str(db_path))
    monkeypatch.setenv("GRIDMARKET_NWS", "off")
    monkeypatch.setenv("GRIDMARKET_BOT_MASTER_SEED", "20260926")
    monkeypatch.setenv("GRIDMARKET_ADMIN_KEY", ADMIN)
    app = main.create_app()
    headers = {"Authorization": f"Bearer {ADMIN}"}
    denied = TestClient(app, client=("10.1.2.3", 50000)).post(
        "/v1/admin/bots", json={"count": 1}, headers=headers
    )
    assert denied.status_code == 403
    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM bots").fetchone()[0] == 0
    finally:
        conn.close()
    allowed = TestClient(app).post("/v1/admin/bots", json={"count": 1}, headers=headers)
    assert allowed.status_code == 200


def test_SEIT_GM_UI_03_API_bot_profile(server) -> None:
    """GET /v1/bots and /v1/bots/{id} return the profile fields, P&L excluding deposits."""
    base_url, db_path, _app = server
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR IGNORE INTO providers (id, display_name) VALUES ('base_sim', 'Base Simulation')"
    )
    conn.execute(
        "INSERT INTO accounts (id, display_name, cash_cents) VALUES ('acct-profile', 'profile', 14000)"
    )
    profile = {
        "bot_type": "saver",
        "blend": {"saver": 1.0},
        "traits": {
            "risk appetite": 0.4,
            "patience": 0.5,
            "reaction delay": 0.2,
            "loss aversion": 0.3,
            "herd versus contrarian": 0.6,
            "daily activity pattern": 0.7,
            "wealth": 0.8,
        },
        "household": {
            "batteries": [13.5],
            "zone": "LZ_HOUSTON",
            "reserve_pct": 0.2,
            "schedule": [1.0] * 24,
        },
        "employed": True,
        "pay": 40.0,
        "provider_id": "base_sim",
    }
    conn.execute(
        """
        INSERT INTO bots (
            id, account_id, bot_index, bot_type, provider_id, profile_json, dormant
        ) VALUES ('bot-profile', 'acct-profile', 10000, 'saver', 'base_sim', ?, 0)
        """,
        (json.dumps(profile),),
    )
    conn.execute(
        "INSERT INTO products (id, symbol, zone, delivery_hour) VALUES ('p1', 'LZ_HOUSTON-H', 'LZ_HOUSTON', '2026-09-26T00:00:00Z')"
    )
    conn.execute("INSERT INTO settlements (id, product_id, price_cents) VALUES ('set-1', 'p1', 50)")
    conn.execute(
        """
        INSERT INTO settled_positions (
            id, settlement_id, account_id, product_id, quantity, pnl_cents
        ) VALUES ('sp-loss', 'set-1', 'acct-profile', 'p1', 1, -500)
        """
    )
    conn.execute(
        """
        INSERT INTO settled_positions (
            id, settlement_id, account_id, product_id, quantity, pnl_cents
        ) VALUES ('sp-win', 'set-1', 'acct-profile', 'p1', 1, 200)
        """
    )
    conn.execute(
        "INSERT INTO deposits (id, account_id, amount_cents, reason) VALUES ('dep-profile', 'acct-profile', 4000, 'pay')"
    )
    conn.commit()
    conn.close()
    missing = httpx.get(f"{base_url}/v1/bots/missing", timeout=5)
    assert missing.status_code == 404
    listed = httpx.get(f"{base_url}/v1/bots", timeout=5)
    assert listed.status_code == 200
    rows = listed.json()
    assert isinstance(rows, list)
    assert any(row["id"] == "bot-profile" for row in rows)
    response = httpx.get(f"{base_url}/v1/bots/bot-profile", timeout=5)
    assert response.status_code == 200
    body = response.json()
    for key in (
        "id",
        "bot_type",
        "blend",
        "provider_id",
        "traits",
        "household",
        "employed",
        "pay",
        "cash",
        "net_worth",
        "balance",
        "trades",
        "losses",
        "loss_share",
        "worst_loss",
        "pnl",
        "dormant",
    ):
        assert key in body
    assert body["id"] == "bot-profile"
    assert body["traits"] == profile["traits"]
    assert body["household"] == profile["household"]
    assert body["employed"] is True
    assert body["pay"] == pytest.approx(40.0)
    assert body["balance"][-1] == pytest.approx(140.0)
    assert body["trades"] == 0
    assert body["losses"] == 1
    assert body["loss_share"] == pytest.approx(0.5)
    assert body["worst_loss"] == pytest.approx(-5.0)
    assert body["pnl"] == pytest.approx(-3.0)
    assert body["cash"] == pytest.approx(140.0)
    assert body["net_worth"] == pytest.approx(140.0)
    assert body["dormant"] is False
