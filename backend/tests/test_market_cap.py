"""S05-cap: order prices are capped at $5.00 per Flex Credit (DEC-GM-082)."""

import sqlite3

import pytest
import test_market

from gridmarket_server import market

exchange = test_market.exchange
CAP_MESSAGE = "price_cents must be between 0 and 500 ($5.00/FC, the ERCOT $5,000/MWh offer cap)"


def state(path):
    with sqlite3.connect(path) as db:
        return [
            db.execute(query).fetchall()
            for query in (
                "SELECT id,cash_cents,flex_credits FROM accounts ORDER BY id",
                "SELECT * FROM positions ORDER BY account_id,product_id",
                "SELECT id,side,remaining_qty,price_cents,status FROM orders ORDER BY id",
                "SELECT COUNT(*) FROM trades",
                "SELECT COUNT(*) FROM reservations",
            )
        ]


def test_price_cap_accepts_the_cap_and_zero(exchange):
    _, client = exchange
    at_cap = test_market.place(client, "buyer", "future", "buy", 1, 500, "at-cap")
    assert at_cap.status_code == 200
    assert at_cap.json()["price_cents"] == 500
    zero = test_market.place(client, "buyer", "future", "buy", 1, 0, "zero")
    assert zero.status_code == 200
    assert zero.json()["price_cents"] == 0


def test_price_above_cap_rejects_with_message_and_changes_nothing(exchange):
    path, client = exchange
    assert (
        test_market.place(client, "seller", "future", "sell", 1, 400, "resting").status_code == 200
    )
    before = state(path)
    for account, side in (("buyer", "buy"), ("seller", "sell")):
        response = test_market.place(client, account, "future", side, 1, 501, f"over-{side}")
        assert response.status_code == 422
        assert response.json()["error"] == {"code": "VALIDATION_ERROR", "message": CAP_MESSAGE}
    assert state(path) == before


def test_negative_price_still_rejects(exchange):
    path, client = exchange
    before = state(path)
    response = test_market.place(client, "buyer", "future", "buy", 1, -1, "negative")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert state(path) == before


def test_quantity_api_error_names_field_and_engine_side_rejection_is_unchanged(exchange):
    _, client = exchange
    response = test_market.place(client, "buyer", "future", "buy", 0, 20, "zero-quantity")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "quantity" in response.json()["error"]["message"]
    assert "greater than or equal to 1" in response.json()["error"]["message"]
    order = {"product_id": "future", "side": "hold", "quantity": 1, "price_cents": 20}
    with market.connection(write=True) as db, pytest.raises(market.HTTPException) as failure:
        market.place_order(db, "buyer", order)
    assert failure.value.status_code == 422
    assert failure.value.detail == {"code": "VALIDATION_ERROR", "message": "Validation error"}
