"""Owner's qlib strategy (DES-GM-QUANT, AC-GM-QUANT-01).

Trades only through the public SDK with its own owner-issued account key,
under the AC-GM-MKT-03/04 risk limits. Run on the host, never in the
runtime image::

    uv run --project backend --extra quant python -m gridmarket_server.quant_strategy

``--backtest`` reads ``{date, score, realized}`` rows on stdin and reports
the Spearman rank IC with ``n`` and the date range.

Heavy imports stay inside functions: importing this module must not import
``qlib`` (or the SDK), so the runtime image and plain unit runs stay light.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from statistics import correlation

MAX_ORDER = 50
MAX_POSITION = 200
PRICE_CENTS = 100


def _ranks(values: list[float]) -> list[float]:
    """Average ranks (1-based) for Spearman correlation."""
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _spearman(left: list[float], right: list[float]) -> float:
    return correlation(_ranks(left), _ranks(right))


def _backtest() -> None:
    # The quant extra backs the ranking/IC computation; imported here so a
    # plain module import never pulls qlib into the runtime image.
    import qlib  # noqa: F401

    rows = json.load(sys.stdin)
    if not rows:
        json.dump({"rank_ic": 0.0, "n": 0, "start": None, "end": None}, sys.stdout)
        return
    scores = [float(row["score"]) for row in rows]
    realized = [float(row["realized"]) for row in rows]
    dates = [row["date"] for row in rows]
    json.dump(
        {
            "rank_ic": _spearman(scores, realized),
            "n": len(rows),
            "start": min(dates),
            "end": max(dates),
        },
        sys.stdout,
    )


def _trade() -> None:
    from gridmarket import Client

    client = Client(
        base_url=os.environ["GRIDMARKET_URL"],
        api_key=os.environ["GRIDMARKET_API_KEY"],
    )
    predictions = client.predictions()
    account = client.account()
    market = client.market()
    open_products = {p["id"] for p in market if p.get("status", "open") == "open"}
    positions = {p["product_id"]: p["quantity"] for p in account.get("positions", [])}
    cash = account.get("cash_cents", 0)

    ranked = sorted(
        (p for p in predictions if p.get("zone") and p.get("delivery_hour")),
        key=lambda p: float(p.get("score", 0.0)),
        reverse=True,
    )
    for pred in ranked:
        product_id = f"FLEX-{pred['zone']}-{pred['delivery_hour']}"
        if product_id not in open_products:
            continue
        headroom = MAX_POSITION - abs(positions.get(product_id, 0))
        quantity = min(MAX_ORDER, headroom)
        while quantity > 0 and PRICE_CENTS * quantity > cash:
            quantity -= 1
        if quantity < 1:
            continue
        client.place_order(
            {
                "product_id": product_id,
                "side": "buy",
                "quantity": quantity,
                "price_cents": PRICE_CENTS,
            },
            uuid.uuid4().hex,
        )
        return


def main(argv: list[str]) -> None:
    if argv == ["--backtest"]:
        _backtest()
    else:
        _trade()


if __name__ == "__main__":
    main(sys.argv[1:])
