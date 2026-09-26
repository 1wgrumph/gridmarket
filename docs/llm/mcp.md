# GridMarket MCP setup

Give your coding agent live market reads plus your own orders through a
local MCP server. Everything runs on your machine over stdio; your sandbox
key never leaves your agent config.

## 1. Get a sandbox key

```sh
curl -s -X POST http://127.0.0.1:8000/v1/sandbox/keys \
  -H 'Content-Type: application/json' \
  -d '{"label": "MyAgent"}'
```

Keep the returned `api_key`: it is shown once.

## 2. Install the server

```sh
uv sync --project mcp-server --frozen
```

## 3. Point your agent at it

```json
{
  "mcpServers": {
    "gridmarket": {
      "command": "uv",
      "args": ["run", "--project", "/path/to/mcp-server", "--frozen",
               "python", "-m", "gridmarket_mcp"],
      "env": {
        "GRIDMARKET_URL": "http://127.0.0.1:8000",
        "GRIDMARKET_API_KEY": "<api_key from step 1>"
      }
    }
  }
}
```

## 4. Tools you get

- Market reads: `market`, `order_book`, `predictions`, `router_checks`,
  `provider_health`, `bot_population`
- Your account only: `my_orders`, `my_positions`, `my_pnl`, `my_losses`
- Trading through the public risk-checked API: `buy`, `sell`, `cancel`
  (max 50 lots per order, 200 position limit)

## Safety notes

- Responses contain market data only: no other user's display names, key
  labels, or free text ever reach your agent.
- Private tools return only rows owned by your key.
- Orders go through the same public API, risk engine, and rate limits as
  every other client. There is no remote MCP server to deploy.
