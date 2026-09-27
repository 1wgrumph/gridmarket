"""Exchange regressions through a real loopback server and its persisted ledger."""

import asyncio
import json
import random
import sqlite3
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import pytest
import uvicorn

from gridmarket_server import economy, keys, main, market

NOW = datetime(2026, 9, 26, 19, 30, tzinfo=UTC)
CENTRAL = ZoneInfo("America/Chicago")


@pytest.fixture
def exchange(tmp_path, monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW.astimezone(tz)

    monkeypatch.setattr(market, "datetime", Clock)
    monkeypatch.setenv("GRIDMARKET_DB", str(tmp_path / "exchange.db"))
    monkeypatch.setenv("GRIDMARKET_NWS", "off")
    monkeypatch.setenv("GRIDMARKET_BOT_SECRET", "local-regression-secret")
    monkeypatch.delenv("GRIDMARKET_WORKER_URL", raising=False)
    monkeypatch.delenv("GRIDMARKET_LONESTAR", raising=False)
    server = uvicorn.Server(uvicorn.Config(main.create_app(), host="127.0.0.1", port=0))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert server.started
        port = server.servers[0].sockets[0].getsockname()[1]
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False) as client:
            yield client
    finally:
        server.should_exit = True
        thread.join(10)
        assert not thread.is_alive()


def order(client, account, product, side, quantity=1, price=20):
    return client.post(
        "/v1/orders",
        headers={
            "Authorization": "Bearer "
            + keys.bot_key(int(account.removeprefix("bot_")), "local-regression-secret"),
            "Idempotency-Key": uuid.uuid4().hex,
        },
        json={"product_id": product, "side": side, "quantity": quantity, "price_cents": price},
    )


def traders():
    with market.connection() as db:
        return [
            r[0]
            for r in db.execute(
                "SELECT account_id FROM bots WHERE provider_id='base_sim' ORDER BY bot_index"
            )
        ]


def future(client):
    return next(
        p for p in client.get("/v1/market").json() if p["symbol"].startswith("FLEX-LZ_HOUSTON")
    )


def conserved(db):
    """Independent mark-to-market and cash rebuild oracle, including default transfers."""
    initial = sum(
        round(json.loads(r[0])["start_cash"] * 100)
        for r in db.execute("SELECT profile_json FROM bots")
    )
    deposits = db.execute("SELECT COALESCE(SUM(amount_cents),0) FROM deposits").fetchone()[0]
    cash = db.execute("SELECT SUM(cash_cents) FROM accounts").fetchone()[0]
    # A common mark cancels across all long/short positions; keep the explicit terms.
    position_value = 0
    for account, product, quantity in db.execute(
        "SELECT x.* FROM positions x JOIN products p ON p.id=x.product_id WHERE p.symbol LIKE 'FLEX-%' AND p.status!='settled'"
    ):
        position_value += market.trade_value(db, account, product) + quantity * 23
    # Each undelivered reservation backs a buyer claim and a seller obligation.
    pending = {}
    for buyer, seller, value in db.execute(
        "SELECT b.account_id,s.account_id,t.price_cents*t.quantity*r.kwh/"
        "(SELECT SUM(t2.quantity) FROM trades t2 WHERE t2.sell_order_id=s.id) "
        "FROM reservations r JOIN trades t ON t.sell_order_id=r.order_id "
        "JOIN orders b ON b.id=t.buy_order_id JOIN orders s ON s.id=t.sell_order_id "
        "WHERE r.status='committed'"
    ):
        pending[buyer] = pending.get(buyer, 0) + value
        pending[seller] = pending.get(seller, 0) - value
    pending_refunds = sum(pending.values())
    assert cash + position_value + pending_refunds == pytest.approx(
        initial + deposits, abs=1e-7, rel=0
    )
    assert cash == initial + deposits


def test_central_symbols_and_readme_alias(exchange):
    products = exchange.get("/v1/market").json()
    for p in products:
        local = datetime.fromisoformat(p["delivery_hour"]).astimezone(CENTRAL)
        assert p["symbol"] == f"{p['symbol'].split('-')[0]}-{p['zone']}-{local:%Y-%m-%d-%H}"
    p = exchange.get("/v1/market/FLEX-LZ_HOUSTON-18").json()
    assert datetime.fromisoformat(p["delivery_hour"]).astimezone(CENTRAL).hour == 18
    response = order(exchange, traders()[0], "FLEX-LZ_HOUSTON-18", "buy", 2, 22)
    assert response.status_code == 200
    assert response.json()["product_id"] == p["id"]


def test_zero_crossing_and_seeded_thousand_orders_conserve(exchange):
    p = future(exchange)["id"]
    accounts = traders()
    a, b, c = accounts[:3]
    for account, side, price in ((a, "buy", 20), (b, "sell", 20), (a, "sell", 30), (c, "buy", 30)):
        assert order(exchange, account, p, side, price=price).status_code == 200
        with market.connection() as db:
            conserved(db)
    rng = random.Random(78)
    accepted = 0
    for _ in range(1000):
        response = order(
            exchange,
            rng.choice(accounts),
            p,
            rng.choice(("buy", "sell")),
            rng.choice((1, 5, 20)),
            rng.randrange(51),
        )
        assert response.status_code in (200, 422)
        accepted += response.status_code == 200
        with market.connection() as db:
            conserved(db)
    assert accepted > 500
    with market.connection(write=True) as db:
        market.list_products(db, NOW + timedelta(days=1))
        conserved(db)
        assert (
            db.execute(
                "SELECT COUNT(*) FROM trades t JOIN orders b ON b.id=t.buy_order_id JOIN orders s ON s.id=t.sell_order_id WHERE b.account_id=s.account_id"
            ).fetchone()[0]
            == 0
        )


def test_no_self_trade(exchange):
    p = future(exchange)["id"]
    account = traders()[0]
    assert order(exchange, account, p, "buy").status_code == 200
    assert order(exchange, account, p, "sell").status_code == 200
    with market.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 0


def test_exact_reference_and_closed_positions_settle(exchange):
    p = future(exchange)
    a, b, c = traders()[:3]
    # Sweep's fractional $/MWh case, expressed in the stored Signal contract.
    for account, side, price in ((a, "buy", 20), (b, "sell", 20), (a, "sell", 30), (c, "buy", 30)):
        assert order(exchange, account, p["id"], side, 20, price).status_code == 200
    hour = datetime.fromisoformat(p["delivery_hour"])
    with market.connection(write=True) as db:
        for i in range(4):
            stamp = (hour + timedelta(minutes=15 * i)).isoformat()
            db.execute(
                "INSERT INTO signals VALUES (?,?,?,?,?,?,?,?,?)",
                (str(i), "NP6-905-CD", p["zone"], stamp, 15, 23.45, "$/MWh", stamp, stamp),
            )
        before = dict(db.execute("SELECT id,cash_cents FROM accounts"))
        market.settle(db, hour + timedelta(hours=1))
        after = dict(db.execute("SELECT id,cash_cents FROM accounts"))
        assert (
            db.execute(
                "SELECT price_cents FROM settlements WHERE product_id=? ORDER BY rowid DESC LIMIT 1",
                (p["id"],),
            ).fetchone()[0]
            == 2.345
        )
        assert after[a] - before[a] == 200
        assert after[b] - before[b] == 353
        assert after[c] - before[c] == -553
        conserved(db)
        market.settle(db, hour + timedelta(hours=1))
        assert dict(db.execute("SELECT id,cash_cents FROM accounts")) == after


def test_default_reverses_credits_and_has_rebuildable_ledger(exchange):
    with market.connection() as db:
        seller, zone = db.execute(
            "SELECT account_id,zone FROM assets WHERE provider_id='base_sim' AND soc_kwh-min_reserve_kwh>=2 LIMIT 1"
        ).fetchone()
    buyer = next(a for a in traders() if a != seller)
    p = next(p for p in exchange.get("/v1/market").json() if p["symbol"].startswith(f"SPOT-{zone}"))
    assert order(exchange, seller, p["id"], "sell", 2, 23).status_code == 200
    assert order(exchange, buyer, p["id"], "buy", 2, 23).status_code == 200
    with market.connection(write=True) as db:
        before = dict(db.execute("SELECT id,cash_cents FROM accounts"))
        db.execute("UPDATE provider_health SET online=0,last_heartbeat='2000-01-01T00:00:00+00:00'")
        market.settle(db, datetime.fromisoformat(p["delivery_hour"]) + timedelta(hours=1))
        assert (
            db.execute("SELECT flex_credits FROM accounts WHERE id=?", (buyer,)).fetchone()[0] == 0
        )
        deltas = {}
        for account, payload in db.execute(
            "SELECT account_id,payload_json FROM events WHERE entry_type='delivery_refund'"
        ):
            deltas[account] = deltas.get(account, 0) + json.loads(payload)["cash_delta_cents"]
        assert deltas == {buyer: 46, seller: -46}
        for account, cash in db.execute("SELECT id,cash_cents FROM accounts"):
            assert cash == before[account] + deltas.get(account, 0)
        conserved(db)


def test_scheduler_survives_one_failed_tick(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("GRIDMARKET_DB", str(tmp_path / "loops.db"))
    monkeypatch.setenv("GRIDMARKET_NWS", "off")
    monkeypatch.delenv("GRIDMARKET_WORKER_URL", raising=False)
    calls = {"market": 0, "economy": 0}
    real_sleep = asyncio.sleep

    def flaky(name, real):
        def run():
            calls[name] += 1
            if calls[name] == 1:
                raise sqlite3.OperationalError("database is locked")
            return real()

        return run

    async def fast_sleep(seconds):
        await real_sleep(0.01)

    monkeypatch.setattr(market, "tick", flaky("market", market.tick))
    monkeypatch.setattr(economy, "tick", flaky("economy", economy.tick))
    monkeypatch.setattr(asyncio, "sleep", fast_sleep)

    async def run():
        app = main.create_app()
        async with app.router.lifespan_context(app):
            for _ in range(100):
                if min(calls.values()) >= 2:
                    break
                await real_sleep(0.01)
            assert min(calls.values()) >= 2

    asyncio.run(run())
    assert "database is locked" in caplog.text
