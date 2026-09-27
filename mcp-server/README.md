# gridmarket-mcp

Local stdio MCP server for GridMarket. It runs on your machine, uses your
own sandbox key, and talks only to the public REST API. There is no remote
MCP server.

## Install

```sh
uv sync --project mcp-server --frozen
```

Requires an `mcp` release public for at least 14 days (see `uv.lock`).

## Configure

```sh
export GRIDMARKET_URL=http://127.0.0.1:8000
export GRIDMARKET_API_KEY=<your sandbox key from POST /v1/sandbox/keys>
```

Example client config (Claude Desktop style):

```json
{
  "mcpServers": {
    "gridmarket": {
      "command": "uv",
      "args": ["run", "--project", "/path/to/mcp-server", "--frozen",
               "python", "-m", "gridmarket_mcp"],
      "env": {
        "GRIDMARKET_URL": "http://127.0.0.1:8000",
        "GRIDMARKET_API_KEY": "<your sandbox key>"
      }
    }
  }
}
```

## Tools

Reads (mirror the dashboard): `market`, `order_book(symbol)`,
`predictions(zone=None)`, `router_checks(family=None)`, `provider_health`,
`bot_population(bot_type=None)`.

Caller-scoped: `my_orders`, `my_positions`, `my_pnl`, `my_losses`.

Orders (public API, risk engine and key limits apply):
`buy(product_id, quantity, price_cents, idempotency_key)`,
`sell(...)`, `cancel(order_id)`.

## Privacy

Tool responses carry market data only. Display names, key labels, and any
other user-entered text from other accounts are removed before responding
(RISK-GM-15). Private tools return only the caller's own rows.
