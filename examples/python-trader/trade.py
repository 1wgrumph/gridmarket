"""Print a LZ_HOUSTON prediction, then buy 2 Flex Credits of FLEX-LZ_HOUSTON-18.

GRIDMARKET_API_KEY=gm_... GRIDMARKET_URL=http://127.0.0.1:8000 \
    PYTHONPATH=sdk/python python3 examples/python-trader/trade.py
"""

import os
import sys

from gridmarket import Client, GridMarketError

url = os.getenv("GRIDMARKET_URL", "http://127.0.0.1:8000")
client = Client(url, os.environ["GRIDMARKET_API_KEY"])
try:
    scores = [p for p in client.predictions() if p["zone"] == "LZ_HOUSTON"]
    print("prediction:", scores[0] if scores else "none published yet")
    try:  # from 16:00 to 17:59, hour 18 is a spot product, not a future
        order = client.buy("FLEX-LZ_HOUSTON-18", quantity=2, price_cents=22)
    except GridMarketError as error:
        if error.code not in ("UNKNOWN_PRODUCT", "PRODUCT_CLOSED"):
            raise
        houston = [p for p in client.market() if p["zone"] == "LZ_HOUSTON"]
        order = client.buy(houston[0]["id"], quantity=2, price_cents=22)
    print("order:", order["id"], order["status"])
except GridMarketError as error:
    sys.exit(f"GridMarket rejected the request: {error}")
