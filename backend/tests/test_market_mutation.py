"""Observable market outcomes missed by the broader exchange tests."""

import sqlite3
from zoneinfo import ZoneInfo

import pytest
import test_market

from gridmarket_server import market

exchange = test_market.exchange


def test_matching_skips_unrelated_orders_and_respects_price_time(exchange):
    path, client = exchange
    for account, product, side, quantity, price, key in (
        ("seller", "spot", "sell", 1, 1, "other-product"),
        ("buyer", "future", "buy", 1, 1, "same-side"),
        ("seller", "future", "sell", 2, 20, "first-at-20"),
        ("second_seller", "future", "sell", 1, 20, "second-at-20"),
        ("second_seller", "future", "sell", 1, 19, "best-price"),
        ("seller", "future", "sell", 1, 21, "over-limit"),
    ):
        assert (
            test_market.place(client, account, product, side, quantity, price, key).status_code
            == 200
        )
    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row
        resting = [dict(row) for row in db.execute("SELECT rowid AS sequence,* FROM orders")]
    by_key = {row["price_cents"]: row["id"] for row in resting if row["price_cents"] in (19, 21)}
    at_20 = [row["id"] for row in resting if row["price_cents"] == 20]
    result = market.MatchingEngine().match(
        resting, {"product_id": "future", "side": "buy", "quantity": 4, "price_cents": 20}
    )
    assert result == market.MatchResult(
        [
            market.Fill(by_key[19], 1, 19),
            market.Fill(at_20[0], 2, 20),
            market.Fill(at_20[1], 1, 20),
        ],
        0,
    )
    assert by_key[21] not in {fill.resting_order_id for fill in result.fills}


def test_future_hour_alias_resolves_only_valid_open_product(exchange):
    _, client = exchange
    alias = f"FLEX-LZ_HOUSTON-{test_market.HOUR.astimezone(ZoneInfo('America/Chicago')):%H}"
    detail = client.get(f"/v1/market/{alias}")
    assert detail.status_code == 200
    assert detail.json()["id"] == "future"
    order = test_market.place(client, "buyer", alias, "buy", 1, 0, "hour-alias")
    assert order.status_code == 200
    assert order.json()["product_id"] == "future"
    for invalid in ("FLEX-LZ_HOUSTON-2", "FLEX-LZ_HOUSTON-XX", "FLEX-LZ_HOUSTON-25"):
        response = client.get(f"/v1/market/{invalid}")
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "UNKNOWN_PRODUCT"


def test_zero_price_exact_cash_and_max_safe_price(exchange):
    path, client = exchange
    zero = test_market.place(client, "buyer", "future", "buy", 1, 0, "zero-price")
    assert zero.status_code == 200
    assert zero.json()["price_cents"] == 0
    with sqlite3.connect(path) as db:
        db.execute("UPDATE accounts SET cash_cents=25000 WHERE id='seller'")
    exact = test_market.place(client, "seller", "future", "buy", 50, 500, "exact-cash")
    assert exact.status_code == 200
    assert exact.json()["status"] == "open"
    over_cash = test_market.place(client, "seller", "future", "buy", 1, 1, "over-cash")
    assert over_cash.status_code == 422
    assert over_cash.json()["error"]["code"] == "INSUFFICIENT_FUNDS"

    with sqlite3.connect(path) as db:
        db.execute("UPDATE accounts SET cash_cents=? WHERE id='buyer'", (2**63 - 1,))
    maximum = market.MAX_PRICE_CENTS
    accepted = test_market.place(client, "buyer", "future", "buy", 1, maximum, "max-price")
    assert accepted.status_code == 200
    rejected = test_market.place(client, "buyer", "future", "buy", 1, maximum + 1, "past-max")
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "VALIDATION_ERROR"


def test_cancel_releases_cash_hold_and_spot_capacity(exchange):
    _, client = exchange
    buy = test_market.place(client, "buyer", "future", "buy", 2, 15, "hold-then-cancel")
    assert buy.status_code == 200
    assert buy.json()["status"] == "open"
    headers = {"Authorization": f"Bearer {test_market.api_key('buyer')}"}
    assert client.get("/v1/account", headers=headers).json()["cash_held_cents"] == 30
    denied = client.delete(
        f"/v1/orders/{buy.json()['id']}",
        headers={"Authorization": f"Bearer {test_market.api_key('seller')}"},
    )
    assert denied.status_code == 404
    assert denied.json()["error"]["code"] == "NOT_FOUND"
    cancelled = client.delete(f"/v1/orders/{buy.json()['id']}", headers=headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert client.get("/v1/account", headers=headers).json()["cash_held_cents"] == 0

    sell = test_market.place(client, "seller", "spot", "sell", 10, 20, "reserve-then-cancel")
    assert sell.status_code == 200
    seller_headers = {"Authorization": f"Bearer {test_market.api_key('seller')}"}
    assert (
        client.delete(f"/v1/orders/{sell.json()['id']}", headers=seller_headers).json()["status"]
        == "cancelled"
    )
    replacement = test_market.place(client, "seller", "spot", "sell", 10, 20, "capacity-reused")
    assert replacement.status_code == 200
    assert replacement.json()["status"] == "open"


def test_future_round_trip_realizes_pnl_and_returns_filled_orders(exchange):
    path, client = exchange
    orders = [
        test_market.place(client, account, "future", side, 1, price, key)
        for account, side, price, key in (
            ("seller", "sell", 20, "open-short"),
            ("buyer", "buy", 20, "open-long"),
            ("buyer", "sell", 30, "close-long"),
            ("seller", "buy", 30, "close-short"),
        )
    ]
    assert all(response.status_code == 200 for response in orders)
    assert [response.json()["status"] for response in orders] == [
        "open",
        "filled",
        "open",
        "filled",
    ]
    assert [response.json()["remaining_qty"] for response in orders] == [1, 0, 1, 0]
    with sqlite3.connect(path) as db:
        assert dict(db.execute("SELECT id,cash_cents FROM accounts")) == {
            "buyer": 100000,
            "seller": 100000,
            "second_seller": 100000,
        }
        assert set(
            db.execute("SELECT account_id,quantity FROM positions WHERE product_id='future'")
        ) == {
            ("buyer", 0),
            ("seller", 0),
        }
        # Closing a future defers its cash and ledger realization until expiry.
        assert db.execute("SELECT COUNT(*) FROM settled_positions").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM settlements").fetchone()[0] == 0
    history = client.get("/v1/market/history?product_id=future")
    assert history.status_code == 200
    assert [(trade["quantity"], trade["price_cents"]) for trade in history.json()] == [
        (1, 30),
        (1, 20),
    ]
    detail = client.get("/v1/market/future")
    assert detail.status_code == 200
    assert detail.json()["orders"] == []


def test_settlement_continues_past_missing_signals_and_cancels_open_orders(exchange):
    path, client = exchange
    order = test_market.place(client, "seller", "spot", "sell", 1, 20, "expiring-order")
    assert order.status_code == 200
    with sqlite3.connect(path) as db:
        for offset, value in enumerate((200, 220, 240, 260)):
            db.execute(
                "INSERT INTO signals(id,report_id,zone,interval_start,interval_minutes,value,unit,published_at,fetched_at) "
                "VALUES (?,?,?,?,15,?,'$/MWh',?,?)",
                (
                    f"spot-{offset}",
                    "NP6-905-CD",
                    "LZ_HOUSTON",
                    (
                        test_market.SPOT_HOUR + test_market.timedelta(minutes=15 * offset)
                    ).isoformat(),
                    value,
                    test_market.HOUR.isoformat(),
                    test_market.HOUR.isoformat(),
                ),
            )
        market.settle(db, test_market.HOUR + test_market.timedelta(hours=1))
        assert dict(db.execute("SELECT id,status FROM products WHERE id IN ('future','spot')")) == {
            "future": "open",
            "spot": "settled",
        }
        assert db.execute("SELECT product_id,price_cents FROM settlements").fetchall() == [
            ("spot", 23)
        ]
    response = client.get(
        f"/v1/orders/{order.json()['id']}",
        headers={"Authorization": f"Bearer {test_market.api_key('seller')}"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


@pytest.mark.parametrize(
    "online,status,buyer_cash,seller_cash",
    [(1, "delivered", 99940, 100060), (0, "defaulted", 100000, 100000)],
)
def test_spot_delivery_is_recorded_once_and_default_refunds_buyer(
    exchange, online, status, buyer_cash, seller_cash
):
    path, client = exchange
    assert (
        test_market.place(client, "buyer", "spot", "buy", 3, 20, "delivery-buy").status_code == 200
    )
    sell = test_market.place(client, "seller", "spot", "sell", 3, 20, "delivery-sell")
    assert sell.status_code == 200
    assert sell.json()["status"] == "filled"
    with sqlite3.connect(path) as db:
        db.execute("UPDATE provider_health SET online=? WHERE provider_id='base_sim'", (online,))
        for _ in range(2):
            market.settle(db, test_market.SPOT_HOUR + test_market.timedelta(hours=1))
        assert db.execute("SELECT status,kwh FROM reservations").fetchall() == [(status, 3)]
        assert dict(db.execute("SELECT id,cash_cents FROM accounts")) == {
            "buyer": buyer_cash,
            "seller": seller_cash,
            "second_seller": 100000,
        }
        assert (
            db.execute("SELECT COUNT(*) FROM events WHERE entry_type='settlement'").fetchone()[0]
            == 1
        )
