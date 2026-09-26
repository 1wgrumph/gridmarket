"""GridMarket rules strategy template (simulation only; no real money).

Buys a zone's open product when its prediction level is HIGH and the expected
value beats the market price by MARGIN. Every order is clamped to the order
size limit and to the room left under the position limit before it is sent.

    GRIDMARKET_URL=http://127.0.0.1:8000 GRIDMARKET_API_KEY=gm_... \
        python strategy.py --once
"""

import argparse
import math
import os
import time
import uuid

from gridmarket import Client, GridMarketError

MAX_ORDER = 50  # credits per order (engine rejects more with ORDER_TOO_LARGE)
MAX_POSITION = 200  # abs(net credits) per product (POSITION_LIMIT)
MARGIN = float(os.getenv("STRATEGY_MARGIN", "0.10"))  # $/credit EV must beat market by
SIZE = int(os.getenv("STRATEGY_SIZE", str(MAX_ORDER)))  # credits wanted per signal
INTERVAL = float(os.getenv("STRATEGY_INTERVAL", "60"))  # seconds between cycles


def rows(payload, key):
    """Accept either a bare list or an object wrapping the list under key."""
    return payload if isinstance(payload, list) else payload.get(key, [])


def net_positions(payload):
    held = {}
    for row in rows(payload, "positions"):
        field = next(
            f for f in ("net_position", "net_quantity", "quantity") if f in row
        )
        held[row["product_id"]] = held.get(row["product_id"], 0) + int(row[field])
    return held


def cycle(client):
    predictions = rows(client.predictions(), "predictions")
    products = [
        p for p in rows(client.market(), "products") if p["status"].lower() == "open"
    ]
    held = net_positions(client.request("GET", "/v1/positions"))
    for prediction in predictions:
        market_price = prediction.get("market_price")
        if prediction["level"] != "HIGH" or market_price is None:
            continue
        if prediction["expected_value"] < market_price + MARGIN:
            continue
        product = next(
            (
                p
                for p in products
                if p["zone"] == prediction["zone"]
                and str(p["delivery_hour"]) == str(prediction["delivery_hour"])
            ),
            None,
        )
        if product is None:
            continue
        room = MAX_POSITION - held.get(product["id"], 0)
        quantity = min(SIZE, MAX_ORDER, room)
        if quantity < 1:
            print(f"skip {product['id']}: position limit reached")
            continue
        order = {
            "product_id": product["id"],
            "side": "buy",
            "quantity": quantity,
            "price_cents": max(1, math.ceil(market_price * 100)),
        }
        try:
            result = client.place_order(order, idempotency_key=str(uuid.uuid4()))
        except GridMarketError as exc:
            print(f"rejected {product['id']}: {exc.status} {exc.code}: {exc.message}")
            if exc.status == 429:  # RATE_LIMITED: wait for the next cycle
                return
            continue
        held[product["id"]] = held.get(product["id"], 0) + quantity
        print(
            f"order {result.get('id')} buy {quantity} {product['id']} @ {order['price_cents']}c"
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--once", action="store_true", help="run one cycle and exit")
    args = parser.parse_args()
    client = Client(
        os.getenv("GRIDMARKET_URL", "http://127.0.0.1:8000"),
        os.environ["GRIDMARKET_API_KEY"],
    )
    while True:
        try:
            cycle(client)
        except GridMarketError as exc:
            # Reads can also be rate limited; preserve the normal cycle backoff.
            print(f"rejected cycle: {exc.status} {exc.code}: {exc.message}")
        if args.once:
            return
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
