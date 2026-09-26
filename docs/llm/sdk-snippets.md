# GridMarket Python SDK snippets

The SDK lives in `sdk/python/gridmarket`. Every call returns parsed JSON and
raises on a non-2xx response; the error body is `{"error": {"code", "message"}}`.
GridMarket is a simulation: no real money moves.

## Connect

```python
import os

from gridmarket import Client

client = Client(os.environ["GRIDMARKET_URL"], os.environ["GRIDMARKET_API_KEY"])
```

A sandbox key: `POST /v1/sandbox/keys` with `{"label": "my-bot"}`, or the
Sandbox page in the dashboard.

## Read the market and predictions

```python
from gridmarket import Client

client = Client("http://127.0.0.1:8000")  # public reads need no key
products = client.market()
predictions = client.predictions()
```

## Place and cancel an order

```python
import uuid

from gridmarket import Client

client = Client("http://127.0.0.1:8000", "gm_...")
order = client.place_order(
    {"product_id": "<product id>", "side": "buy", "quantity": 10, "price_cents": 5},
    idempotency_key=str(uuid.uuid4()),
)
client.cancel_order(order["id"])
```

Limits: 1 to 50 credits per order (`ORDER_TOO_LARGE`) and ±200 credits net per
product (`POSITION_LIMIT`). Reuse an idempotency key only to retry the same order.

## Account, positions, and orders

```python
from gridmarket import Client

client = Client("http://127.0.0.1:8000", "gm_...")
account = client.account()
orders = client.orders()
positions = client.request("GET", "/v1/positions")
```

## Handle rate limits

```python
import time

import httpx
from gridmarket import Client

client = Client("http://127.0.0.1:8000", "gm_...")
try:
    client.market()
except httpx.HTTPStatusError as exc:
    if exc.response.status_code == 429:  # RATE_LIMITED
        time.sleep(float(exc.response.headers.get("Retry-After", "1")))
```

A complete loop: `examples/strategy-template/strategy.py`.
