"""SEIT-GM-PERF-01. Python MatchingEngine.match and Rust matching_core.match_order.

Both follow CONTRACT-GM-ENGINE: pure; best price then earliest sequence; fill
price is the resting price. The rust parameter skips when matching_core cannot
be imported, unless GRIDMARKET_REQUIRE_RUST=1, which fails instead.
"""

import copy
import os

import pytest

CASES = {
    "empty": (
        [],
        {"id": "in", "side": "buy", "product_id": "p", "price_cents": 100, "quantity": 4},
    ),
    "best_price": (
        [
            {
                "id": "late-cheap",
                "side": "sell",
                "product_id": "p",
                "price_cents": 100,
                "quantity": 5,
                "remaining_qty": 5,
                "sequence": 2,
            },
            {
                "id": "early-rich",
                "side": "sell",
                "product_id": "p",
                "price_cents": 150,
                "quantity": 5,
                "remaining_qty": 5,
                "sequence": 1,
            },
        ],
        {"id": "in", "side": "buy", "product_id": "p", "price_cents": 160, "quantity": 5},
    ),
    "time_priority": (
        [
            {
                "id": "second",
                "side": "sell",
                "product_id": "p",
                "price_cents": 100,
                "quantity": 1,
                "remaining_qty": 1,
                "sequence": 2,
            },
            {
                "id": "first",
                "side": "sell",
                "product_id": "p",
                "price_cents": 100,
                "quantity": 1,
                "remaining_qty": 1,
                "sequence": 1,
            },
        ],
        {"id": "in", "side": "buy", "product_id": "p", "price_cents": 100, "quantity": 1},
    ),
    "resting_price": (
        [
            {
                "id": "ask",
                "side": "sell",
                "product_id": "p",
                "price_cents": 100,
                "quantity": 2,
                "remaining_qty": 2,
                "sequence": 1,
            },
        ],
        {"id": "in", "side": "buy", "product_id": "p", "price_cents": 150, "quantity": 2},
    ),
    "partial": (
        [
            {
                "id": "ask",
                "side": "sell",
                "product_id": "p",
                "price_cents": 100,
                "quantity": 4,
                "remaining_qty": 4,
                "sequence": 1,
            },
        ],
        {"id": "in", "side": "buy", "product_id": "p", "price_cents": 100, "quantity": 10},
    ),
    "no_cross": (
        [
            {
                "id": "ask",
                "side": "sell",
                "product_id": "p",
                "price_cents": 100,
                "quantity": 1,
                "remaining_qty": 1,
                "sequence": 1,
            },
        ],
        {"id": "in", "side": "buy", "product_id": "p", "price_cents": 99, "quantity": 1},
    ),
    "sell_side": (
        [
            {
                "id": "low-bid",
                "side": "buy",
                "product_id": "p",
                "price_cents": 90,
                "quantity": 1,
                "remaining_qty": 1,
                "sequence": 1,
            },
            {
                "id": "high-bid",
                "side": "buy",
                "product_id": "p",
                "price_cents": 100,
                "quantity": 1,
                "remaining_qty": 1,
                "sequence": 2,
            },
        ],
        {"id": "in", "side": "sell", "product_id": "p", "price_cents": 95, "quantity": 1},
    ),
    "same_side": (
        [
            {
                "id": "bid",
                "side": "buy",
                "product_id": "p",
                "price_cents": 100,
                "quantity": 1,
                "remaining_qty": 1,
                "sequence": 1,
            },
        ],
        {"id": "in", "side": "buy", "product_id": "p", "price_cents": 100, "quantity": 1},
    ),
    "other_product": (
        [
            {
                "id": "ask",
                "side": "sell",
                "product_id": "p",
                "price_cents": 100,
                "quantity": 1,
                "remaining_qty": 1,
                "sequence": 1,
            },
        ],
        {"id": "in", "side": "buy", "product_id": "q", "price_cents": 100, "quantity": 1},
    ),
    "walk_book": (
        [
            {
                "id": "rich",
                "side": "sell",
                "product_id": "p",
                "price_cents": 110,
                "quantity": 5,
                "remaining_qty": 5,
                "sequence": 1,
            },
            {
                "id": "cheap",
                "side": "sell",
                "product_id": "p",
                "price_cents": 100,
                "quantity": 3,
                "remaining_qty": 3,
                "sequence": 2,
            },
        ],
        {"id": "in", "side": "buy", "product_id": "p", "price_cents": 120, "quantity": 10},
    ),
}


def reference_match(resting: list[dict], incoming: dict) -> dict:
    buy = incoming["side"] == "buy"
    remaining = incoming["quantity"]
    fills = []
    for order in sorted(
        resting,
        key=lambda row: (
            row["price_cents"] if buy else -row["price_cents"],
            row.get("sequence", 0),
        ),
    ):
        if remaining <= 0:
            break
        if order["side"] == incoming["side"] or order["product_id"] != incoming["product_id"]:
            continue
        price = order["price_cents"]
        if (buy and price > incoming["price_cents"]) or (
            not buy and price < incoming["price_cents"]
        ):
            continue
        quantity = min(remaining, order["remaining_qty"])
        if quantity > 0:
            fills.append(
                {"resting_order_id": order["id"], "quantity": quantity, "price_cents": price}
            )
            remaining -= quantity
    return {"fills": fills, "remaining_qty": remaining}


def _normalize(result) -> tuple:
    if isinstance(result, dict):
        fills, remaining = result["fills"], result["remaining_qty"]
    else:
        fills, remaining = result.fills, result.remaining_qty
    normalized = []
    for fill in fills:
        if isinstance(fill, dict):
            normalized.append(
                (fill["resting_order_id"], int(fill["quantity"]), int(fill["price_cents"]))
            )
        else:
            normalized.append((fill.resting_order_id, int(fill.quantity), int(fill.price_cents)))
    return tuple(normalized), int(remaining)


def _call(engine: str, resting: list[dict], incoming: dict):
    if engine == "python":
        from gridmarket_server.market import MatchingEngine

        return MatchingEngine().match(resting, incoming)
    try:
        import matching_core
    except ImportError:
        if os.environ.get("GRIDMARKET_REQUIRE_RUST") == "1":
            pytest.fail("matching_core extension is not importable")
        pytest.skip("matching_core extension is not importable")
    return matching_core.match_order(resting, incoming)


@pytest.mark.parametrize("case_name", tuple(CASES))
@pytest.mark.parametrize("engine", ("python", "rust"))
def test_seit_gm_perf_01_match(case_name: str, engine: str) -> None:
    resting, incoming = copy.deepcopy(CASES[case_name])
    snapshot = copy.deepcopy(resting)
    result = _call(engine, resting, incoming)
    assert resting == snapshot
    assert _normalize(result) == _normalize(reference_match(snapshot, incoming))
