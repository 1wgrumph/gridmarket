"""Acceptance repairs through HTTP, real provider commitments and SignalStore."""

import json
import random
import time
import uuid
from datetime import UTC, datetime, timedelta
from fractions import Fraction

import pytest
import test_sweep_core
from test_sweep_core import future, order, traders

from gridmarket_server import ercot, keys, market

native_exchange = test_sweep_core.exchange


@pytest.fixture
def exchange(native_exchange, monkeypatch):
    request = native_exchange.request

    def retry(*args, **kwargs):
        response = request(*args, **kwargs)
        if response.status_code == 429:
            time.sleep(int(response.headers["Retry-After"]))
            response = request(*args, **kwargs)
        return response

    monkeypatch.setattr(native_exchange, "request", retry)
    return native_exchange


def account(client, who):
    response = client.get(
        "/v1/account",
        headers={
            "Authorization": "Bearer " + keys.bot_key(int(who[4:]), "local-regression-secret")
        },
    )
    assert response.status_code == 200
    return response.json()


def prices(product, value):
    hour = datetime.fromisoformat(product["delivery_hour"])
    for quarter in range(4):
        stamp = (hour + timedelta(minutes=15 * quarter)).isoformat()
        # Exercise the real stored Signal producer; no external response is fabricated.
        ercot._store("NP6-905-CD", product["zone"], stamp, 15, value, "$/MWh", stamp)
    return hour + timedelta(hours=1)


def refund_case(client, monkeypatch, capacities, quantities, price, failed):
    """Audit's two 5-kWh assets / 2.5-kWh reserves, generalized to partial defaults."""
    seller, buyer, sentinel = traders()[0], traders()[1], traders()[-1]
    monkeypatch.setenv("GRIDMARKET_LONESTAR", "on")
    product = next(
        p for p in client.get("/v1/market").json() if p["symbol"].startswith("SPOT-LZ_HOUSTON")
    )
    with market.connection(write=True) as db:
        db.execute(
            "INSERT OR IGNORE INTO providers(id,display_name) VALUES ('lonestar','LoneStar Storage')"
        )
        db.execute("INSERT OR IGNORE INTO provider_health(provider_id) VALUES ('lonestar')")
        db.execute("UPDATE provider_health SET online=1,last_heartbeat=CURRENT_TIMESTAMP")
        db.execute("UPDATE assets SET soc_kwh=min_reserve_kwh WHERE account_id=?", (seller,))
        # The provider's documented offline sentinel belongs to a different customer.
        db.execute(
            "INSERT OR IGNORE INTO assets VALUES ('sentinel',?,'lonestar','LZ_HOUSTON',5,5,0,2,2)",
            (sentinel,),
        )
        for i, capacity in enumerate(capacities):
            db.execute(
                "INSERT INTO assets VALUES (?,?,?,'LZ_HOUSTON',?,?,?,2,2)",
                (
                    f"refund-{uuid.uuid4().hex}-{i}",
                    seller,
                    "base_sim" if i in failed else "lonestar",
                    capacity * 2,
                    capacity * 2,
                    capacity,
                ),
            )
    before = {who: account(client, who) for who in (buyer, seller)}
    sell = order(client, seller, product["id"], "sell", sum(quantities), price)
    assert sell.status_code == 200, sell.text
    for quantity in quantities:
        buy = order(client, buyer, product["id"], "buy", quantity, price)
        assert buy.status_code == 200, buy.text
    with market.connection(write=True) as db:
        db.execute("UPDATE provider_health SET online=0 WHERE provider_id='base_sim'")
        end = datetime.fromisoformat(product["delivery_hour"]) + timedelta(hours=1)
        market.settle(db, end)
        refunds = [
            json.loads(row[0])
            for row in db.execute(
                "SELECT e.payload_json FROM events e JOIN trades t ON t.id=e.subject_id WHERE e.entry_type='delivery_refund' AND e.account_id=? AND t.sell_order_id=? ORDER BY e.rowid",
                (buyer, sell.json()["id"]),
            )
        ]
        expected = round(sum(Fraction(str(capacities[i])) for i in failed) * price)
        assert sum(row["cash_delta_cents"] for row in refunds) == expected
        fills = list(
            db.execute(
                "SELECT id,quantity,price_cents FROM trades WHERE sell_order_id=? ORDER BY rowid",
                (sell.json()["id"],),
            )
        )
        allocations = [
            db.execute(
                "SELECT SUM(json_extract(payload_json,'$.cash_delta_cents')) FROM events WHERE entry_type='delivery_refund' AND account_id=? AND subject_id=?",
                (buyer, trade_id),
            ).fetchone()[0]
            for trade_id, _, _ in fills
        ]
        for allocation, (_, quantity, fill_price) in zip(allocations, fills, strict=True):
            quota = (
                sum(Fraction(str(capacities[i])) for i in failed)
                * quantity
                * fill_price
                / sum(quantities)
            )
            assert (
                quota.numerator // quota.denominator
                <= allocation
                <= -(-quota.numerator // quota.denominator)
            )
        if capacities == [1, 1] and quantities == [1, 1] and failed == {0}:
            assert allocations == ([1, 0] if price == 1 else [2, 1])
        balances = dict(db.execute("SELECT id,cash_cents FROM accounts"))
        event_count = db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        market.settle(db, end)
        assert dict(db.execute("SELECT id,cash_cents FROM accounts")) == balances
        assert db.execute("SELECT COUNT(*) FROM events").fetchone()[0] == event_count
    paid = sum(quantities) * price
    assert account(client, buyer)["cash_cents"] == before[buyer]["cash_cents"] - paid + expected
    assert account(client, seller)["cash_cents"] == before[seller]["cash_cents"] + paid - expected
    assert account(client, buyer)["flex_credits"] == pytest.approx(
        before[buyer]["flex_credits"] + sum(quantities) - sum(capacities[i] for i in failed)
    )


@pytest.mark.parametrize("price", [1, 3])
def test_two_fractional_commitments_refund_exactly(exchange, monkeypatch, price):
    refund_case(exchange, monkeypatch, [2.5, 2.5], [5], price, {0, 1})


@pytest.mark.parametrize("price", [1, 3])
def test_order_refund_residuals_and_seeded_partial_defaults(exchange, monkeypatch, price):
    # Two fills with half-cent shares: independent rounding underpays at 1, overpays at 3.
    refund_case(exchange, monkeypatch, [1, 1], [1, 1], price, {0})
    rng = random.Random(78)
    for _ in range(30):
        total = rng.randrange(2, 10)
        default = rng.randrange(1, total * 4) / 4
        cut = rng.randrange(1, total)
        refund_case(
            exchange,
            monkeypatch,
            [default, total - default],
            [cut, total - cut],
            rng.randrange(1, 51),
            {0},
        )


def test_repeated_central_hour_lists_trades_and_settles_separately(exchange):
    now = datetime(2026, 11, 1, tzinfo=UTC)
    with market.connection(write=True) as db:
        market.list_products(db, now)
    listed = exchange.get("/v1/market").json()
    symbols = [f"FLEX-LZ_HOUSTON-2026-11-01-01{suffix}" for suffix in ("", "R")]
    products = [next(p for p in listed if p["symbol"] == symbol) for symbol in symbols]
    assert [p["delivery_hour"] for p in products] == [
        f"2026-11-01T0{hour}:00:00+00:00" for hour in (6, 7)
    ]
    assert exchange.get("/v1/market/FLEX-LZ_HOUSTON-01").json()["id"] == products[0]["id"]
    a, b = traders()[:2]
    before = account(exchange, a)["cash_cents"]
    for p in products:
        assert order(exchange, a, p["symbol"], "buy", price=10).status_code == 200
        assert order(exchange, b, p["symbol"], "sell", price=10).status_code == 200
    ends = [prices(p, value) for p, value in zip(products, (200, 300), strict=True)]
    with market.connection(write=True) as db:
        market.list_products(db, datetime(2026, 11, 1, 6, tzinfo=UTC))
        market.settle(db, ends[0])
    assert exchange.get("/v1/market/FLEX-LZ_HOUSTON-01").json()["id"] == products[1]["id"]
    assert account(exchange, a)["cash_cents"] == before + 10
    assert exchange.get(f"/v1/market/{symbols[1]}").json()["status"] == "open"
    with market.connection(write=True) as db:
        market.settle(db, ends[1])
    assert account(exchange, a)["cash_cents"] == before + 30
    assert all(
        exchange.get(f"/v1/market/{symbol}").json()["status"] == "settled" for symbol in symbols
    )


def test_flat_future_pnl_visible_until_paid(exchange):
    p = future(exchange)
    a, b, c = traders()[:3]
    before = account(exchange, a)
    for who, side, price in ((a, "buy", 20), (b, "sell", 20), (a, "sell", 30), (c, "buy", 30)):
        assert order(exchange, who, p["id"], side, price=price).status_code == 200
    flat = account(exchange, a)
    assert flat["cash_cents"] == before["cash_cents"]
    assert flat["realized_pnl_cents"] == 0
    assert flat["unrealized_pnl_cents"] == 10
    end = prices(p, 250)
    with market.connection(write=True) as db:
        market.settle(db, end)
        market.settle(db, end)
    paid = account(exchange, a)
    assert paid["cash_cents"] == before["cash_cents"] + 10
    assert paid["realized_pnl_cents"] == 10
    assert paid["unrealized_pnl_cents"] == 0
