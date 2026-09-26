# GridMarket

GridMarket is a simulated flexibility market for ERCOT load zones. Batteries
sell spare capacity as Flex Credits, predictions score each zone from live
ERCOT and NWS signals, and every trader — human, rule, algorithm, or AI agent —
uses the same REST API.

## Disclosures

- Future products are simulated forward flexibility contracts, not regulated
  commodity futures.
- A Flex Credit is not a renewable energy certificate, a cryptocurrency, or a
  claim on specific electrons.
- The market, accounts, balances, bots, and batteries are simulated. No real
  money or energy changes hands. Zone scores are informational, not advice.
- Router decisions labelled "baseline rules" come from fixed rules in this
  repository. The optional Jev probability column comes from Jev, a
  pre-existing hosted service linked to the owner. It is off by default
  (`GRIDMARKET_JEV` unset) and makes no call unless the owner turns it on.

## Run

Requirements: Docker with Compose 2.24 or later.

```sh
cp .env.example .env    # fill in GRIDMARKET_BOT_SECRET at minimum
docker compose -f deploy/compose.yaml up -d --build
curl http://127.0.0.1:8000/v1/market/status
```

- Dashboard: <http://127.0.0.1:8000/>. API docs: <http://127.0.0.1:8000/docs>
  (OpenAPI at `/openapi.json`).
- Services: `app` (API and dashboard) and `bots` (simulated population), both
  from one image, non-root (uid 10001), read-only root filesystem, SQLite in
  the project volume `gm-data`.
- The HTTP port binds to `127.0.0.1` only (`GRIDMARKET_PORT`, default 8000).
  Public access goes through an outbound Cloudflare named tunnel; no inbound
  port is opened.
- `GM_ENV_FILE` points compose at another env file (default `../.env`,
  relative to `deploy/`).

Local development without Docker: `make setup`, then
`GRIDMARKET_DB=./gridmarket.db uv run --project backend uvicorn gridmarket_server.main:app`
and `npm --prefix dashboard run dev`. Checks: `make lint`, `make test-all`,
`make smoke SMOKE_PROJECT=<name> SMOKE_PORT=<port>`.

### Public tunnel (owner only)

Tunnel creation and its credentials belong to the owner.

1. `cloudflared tunnel create gridmarket` writes the credentials JSON to
   `~/.cloudflared/`.
2. Copy `deploy/cloudflared.example.yml` to `~/.cloudflared/config.yml` and
   fill in the tunnel UUID and hostname.
3. `GM_TUNNEL_UID=$(id -u) docker compose -f deploy/compose.yaml --profile tunnel up -d`

The `cloudflared` service mounts `${GM_TUNNEL_DIR:-~/.cloudflared}`
read-only and forwards the hostname to `http://app:8000`.

## Judge quickstart

The Python SDK in `sdk/python/gridmarket` uses only the standard library, so
Python 3.10 or later is all you need.

1. Get a sandbox key ($1,000.00 simulated cash; the key is shown once):

   ```sh
   curl -s -X POST http://127.0.0.1:8000/v1/sandbox/keys \
     -H 'Content-Type: application/json' -d '{"label": "judge"}'
   ```

   The dashboard's Judge sandbox page issues the same key.

2. Run the example trader (`examples/python-trader/trade.py`, under 30 lines).
   It prints a LZ_HOUSTON prediction and buys 2 Flex Credits of
   `FLEX-LZ_HOUSTON-18`:

   ```sh
   export GRIDMARKET_URL=http://127.0.0.1:8000 GRIDMARKET_API_KEY=gm_...
   PYTHONPATH=sdk/python python3 examples/python-trader/trade.py
   ```

3. Watch the order appear in the dashboard activity feed within a few seconds.

Use the SDK in your own code:

```python
from gridmarket import Client

client = Client("http://127.0.0.1:8000", api_key="gm_...")
print(client.market("FLEX-LZ_HOUSTON-18"))
client.buy("FLEX-LZ_HOUSTON-18", quantity=2, price_cents=22)
print(client.orders(), client.portfolio())
```

`Client` methods: `market`, `predictions`, `account`, `portfolio`, `orders`,
`place_order`, `buy`, `sell`, `cancel_order` (alias `cancel`). Each order
sends a fresh `Idempotency-Key`. A non-2xx response raises `GridMarketError`
with `status`, `code`, and `message` from the API's error envelope.

## License

MIT. See [LICENSE](LICENSE).
