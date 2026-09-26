# Strategy template

A rules strategy on the GridMarket simulation (no real money). Each cycle it
reads `/v1/predictions`, `/v1/market`, and your `/v1/positions`, then buys the
open product for a zone and delivery hour when the prediction level is `HIGH`
and the expected value beats the market price by a margin.

It uses only the Python standard library and the repository SDK.

## Run

```bash
export PYTHONPATH=sdk/python
export GRIDMARKET_URL=http://127.0.0.1:8000
export GRIDMARKET_API_KEY=gm_...   # sandbox key from POST /v1/sandbox/keys
python examples/strategy-template/strategy.py --once   # one cycle
python examples/strategy-template/strategy.py          # loop
```

## Knobs

| Environment variable | Default | Meaning |
| --- | --- | --- |
| `STRATEGY_MARGIN` | `0.10` | $/credit the expected value must exceed the market price by |
| `STRATEGY_SIZE` | `50` | credits wanted per signal |
| `STRATEGY_INTERVAL` | `60` | seconds between cycles in loop mode |

Before sending, every order is clamped to 50 credits (the order size limit)
and to the room left under the 200-credit net position limit per product. The
bid price is the prediction's market price, rounded up to whole cents.
Rejected orders are printed and skipped; a `RATE_LIMITED` rejection ends the
cycle early.

Edit `cycle()` to change the rule; keep the clamps.
