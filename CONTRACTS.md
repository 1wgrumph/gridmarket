# GridMarket frozen shared names (S01, DEC-GM-039)

Each row is a name frozen for the listed owning lane. A change requires a dated contract amendment with name, old value, new value, reason, and affected lanes.

## Modules and files

| Name | Owning lane | Contract |
| --- | --- | --- |
| `backend/pyproject.toml`, `backend/uv.lock` | foundation | Python project and frozen dependency set |
| `backend/gridmarket_server/contracts.py`, `schema.sql`, `main.py` | foundation | Shared Python types, SQLite schema, composition root |
| `backend/gridmarket_server/market.py`, `api.py`, `seed.py` | market | Market engine, REST routes, initial database rows |
| `backend/gridmarket_server/ercot.py`, `nws.py`, `scoring.py` | data | Worker client, weather client, predictions |
| `backend/gridmarket_server/providers/__init__.py`, `base_sim.py` | market | Provider registry and base adapter |
| `backend/gridmarket_server/providers/lonestar.py`, `health.py` | lonestar | Second adapter, provider heartbeat and health |
| `backend/gridmarket_server/population.py`, `economy.py`, `bots.py`, `bots_api.py` | bots | Bot population, economy, loop, routes |
| `backend/gridmarket_server/decision_router.py` | router | Check registry and router results |
| `backend/gridmarket_server/jev.py` | jev | Optional Jev probability bridge |
| `backend/gridmarket_server/keys.py` | market | Sandbox key issuance |
| `backend/gridmarket_server/adversary.py`, `adversary_api.py` | adversary | Halt observer and admin routes |
| `sdk/python/gridmarket/__init__.py` | market | Judge-facing `Client` |
| `dashboard/src/api.ts`, `dashboard/src/App.tsx`, `dashboard/src/hooks.ts` | foundation | Typed browser API, hash routes, data hooks |
| `dashboard/src/components/Shell.tsx`, `dashboard/src/pages/Overview.tsx` | ui | App shell and overview |
| `dashboard/src/pages/Market.tsx`, `Predictions.tsx`, `Bots.tsx`, `BotProfile.tsx`, `Sandbox.tsx`, `Spec.tsx` | pages | Phase 1b pages |
| `dashboard/src/pages/Providers.tsx` | providers-page | Provider page |
| `mcp-server/` | mcp | Local stdio tool server |
| `ercot-hackathon/src/` | worker | ERCOT Worker data edge |

## Python types and dataclasses

| Name | Owning lane | Contract |
| --- | --- | --- |
| `Signal` | data | `report_id`, `zone`, `interval_start`, `interval_minutes`, `value`, `unit`, `published_at`, `fetched_at` |
| `SignalStore` | data | `latest(report_id, zone)`, `series(report_id, zone, start, end)`, `staleness(report_id)` |
| `WorkerStats` | data | `requests`, `errors`, `http_429`, `latencies_ms`, `snapshot_age_s` |
| `ProviderOffline` | lonestar | Capacity rejection exception |
| `ProviderAdapter` | market | `provider_id`, `display_name`, `list_customers`, `list_assets`, `available_capacity`, `reserve_capacity`, `release_capacity`, `verify_delivery`, `asset_status`, `heartbeat` |
| `CheckResult` | router | `check_id`, `family`, `subject`, `horizon_s`, `probability`, `band`, `baseline`, `jev_probability`, `created_at`, `resolves_at`, `outcome` |
| `BotSpec` | bots | `index`, `bot_type`, `blend`, `traits`, `info`, `household`, `employed`, `pay`, `pay_offset_s`, `start_cash`, `learning_rate`, `provider_id` |
| `Prediction` | data | `zone`, `delivery_hour`, `score`, `level`, `confidence`, `expected_value`, `market_price`, `drivers`, `disclaimer`, `generated_at` |
| `Client` | market | `market`, `predictions`, `account`, `orders`, `place_order`, `cancel_order` |

## API routes

| Name | Owning lane | Contract |
| --- | --- | --- |
| `GET /v1/market` | market | Public product list |
| `GET /v1/market/{symbol}` | market | Public product detail |
| `GET /v1/market/history` | market | Public price history |
| `GET /v1/market/activity` | market | Public activity |
| `GET /v1/market/status` | market | Public open or halted status |
| `GET /v1/predictions` | data | Public zone scores |
| `GET /v1/predictions/{zone}` | data | Public zone detail |
| `GET /v1/signals` | data | Public ERCOT and NWS signals |
| `GET /v1/providers` | market | Public provider summary |
| `GET /v1/providers/health` | lonestar | Public heartbeat and outage state |
| `GET /v1/router` | router | Public checks and calibration |
| `GET /v1/bots` | bots | Public population |
| `GET /v1/bots/{id}` | bots | Public bot profile |
| `GET /v1/bots/diversity` | bots | Public diversity measures |
| `POST /v1/sandbox/keys` | market | Self-service sandbox key |
| `GET /v1/account` | market | Caller account |
| `GET /v1/portfolio` | market | Caller balances and holdings |
| `GET /v1/positions` | market | Caller open positions |
| `GET /v1/trades` | market | Caller trade ledger |
| `GET /v1/losses` | bots | Caller settled losses |
| `GET /v1/assets` | market | Caller batteries |
| `GET /v1/assets/{id}` | market | Caller battery detail |
| `POST /v1/orders` | market | Risk-checked order |
| `GET /v1/orders` | market | Caller orders |
| `GET /v1/orders/{id}` | market | Caller order detail |
| `DELETE /v1/orders/{id}` | market | Cancel caller order |
| `POST /v1/admin/bots` | bots | Spawn 1–10 bots |
| `POST /v1/admin/providers/{id}/outage` | lonestar | Simulated outage |
| `POST /v1/admin/halt` | adversary | Stretch halt |
| `POST /v1/admin/resume` | adversary | Stretch resume |
| `GET /openapi.json`, `GET /docs`, `GET /docs/oauth2-redirect`, `GET /redoc` | foundation | FastAPI metadata |
| `GET /llms.txt`, `GET /guide.md`, `GET /kit/*` | docs | Served only when files exist |
| `GET /` | ui | Built dashboard only |

## Request and response fields

| Name | Owning lane | Contract |
| --- | --- | --- |
| `POST /v1/orders`: `product_id`, `side`, `quantity`, `price_cents` | market | Order input; `side` is `buy` or `sell` |
| Order response: `id`, `account_id`, `product_id`, `side`, `quantity`, `remaining_qty`, `price_cents`, `status`, `created_at` | market | Caller-scoped order |
| Market product: `id`, `symbol`, `zone`, `delivery_hour`, `status` | market | Public product; hour-beginning America/Chicago symbols `FLEX-<zone>-<YYYY-MM-DD>-<HH>` / `SPOT-<zone>-<YYYY-MM-DD>-<HH>`; `delivery_hour` is the UTC start instant. On fall-back, the second occurrence (standard time, UTC-06:00) appends `R`, e.g. `FLEX-LZ_HOUSTON-2026-11-01-01R`; the first keeps the plain symbol. `FLEX-<zone>-<HH>` selects the earliest open matching Central hour by UTC instant, advancing to the repeated hour after the first closes. |
| Trade: `id`, `product_id`, `buy_order_id`, `sell_order_id`, `quantity`, `price_cents`, `created_at` | market | Append-only fill |
| Asset: `id`, `account_id`, `provider_id`, `zone`, `capacity_kwh`, `soc_kwh`, `min_reserve_kwh`, `charge_kw`, `discharge_kw` | market | Battery |
| Prediction response: `zone`, `delivery_hour`, `score`, `level`, `confidence`, `expected_value`, `market_price`, `drivers`, `disclaimer`, `generated_at` | data | `drivers` entries have `factor`, `contribution`, `detail` |
| Router response: `checks`, `brier`, `jev_enabled` | router | Latest results, per-check calibration, Jev flag |
| Bot response: `id`, `bot_type`, `blend`, `provider_id`, `cash`, `net_worth`, `pnl`, `trades`, `losses`, `dormant` | bots | Public bot profile |
| Sandbox key request: `label` | market | `^[A-Za-z0-9 _-]{1,24}$` |
| Sandbox key response: `account_id`, `api_key`, `label` | market | Key shown once |
| Spawn request: `count`, `seed` | bots | `count` 1–10; seed optional |
| Outage request: `active` | lonestar | Start/end simulated outage |
| Error response: `error.code`, `error.message` | market | Stable JSON envelope; request-validation 422 messages identify the field and constraint. `Idempotency-Key` over 128 characters returns 422 `VALIDATION_ERROR`. |

## HTTP headers

| Name | Owning lane | Contract |
| --- | --- | --- |
| `Authorization: Bearer <key>` | market | Caller and admin API key |
| `Idempotency-Key` | market | Required on `POST /v1/orders` |
| `X-RateLimit-Limit` | market | Current caller or IP limit |
| `X-RateLimit-Remaining` | market | Remaining requests |
| `Retry-After` | market | Retry delay on 429 |
| `x-gridmarket-key` | worker | Market-to-Worker report key |

## Ledger and event entry types

| Name | Owning lane | Contract |
| --- | --- | --- |
| `fill` | market | Trade fill event |
| `settlement` | market | Delivery settlement event |
| `deposit` | bots | Simulated payroll deposit |
| `settled_position` | market | Settled P&L row |
| `halt`, `lift` | adversary | Halt state transitions |
| `reject` | market | Rejected order |
| `alert` | router | Raised check alert |

## Bot profile fields and schema

| Name | Owning lane | Contract |
| --- | --- | --- |
| `BotSpec.index`, `bot_type`, `blend`, `traits` | bots | Identity, one of seven types, weighted strategy blend, latent traits |
| `BotSpec.info.families`, `delay_s`, `ev_bias`, `noise` | bots | Visible information and reaction behavior |
| `BotSpec.household.batteries`, `zone`, `reserve_pct`, `schedule` | bots | Battery capacities in kWh and 24 hourly weights |
| `BotSpec.employed`, `pay`, `pay_offset_s`, `start_cash`, `learning_rate`, `provider_id` | bots | Economy and provider selection |
| `population.sample(master, start_index, n, seed=None)` | bots | Default 60: market maker 4, score follower 12, DART trader 8, heat seller 14, saver 12, alert reactor 6, noise trader 4; $1,000 and 13.5 kWh battery in S01 |
| `population.digest(specs)` | bots | SHA-256 hex |
| `economy.tick(tx, now)`, `economy.stats(account_id)` | bots | Stats: `losses`, `loss_share`, `worst_loss`, `pnl`, `net_worth`, `dormant` |

## Check and router fields and schema

| Name | Owning lane | Contract |
| --- | --- | --- |
| `CheckResult.check_id`, `family`, `subject`, `horizon_s` | router | `family` is `market` or `health` |
| `CheckResult.probability`, `band`, `baseline`, `jev_probability` | router | `band` is `log`, `review`, or `alert`; optional Jev probability |
| `CheckResult.created_at`, `resolves_at`, `outcome` | router | UTC timing and eventual Boolean outcome |
| `decision_router.register(family, fn)`, `decision_router.tick()` | router | Registry and 60 s evaluation |
| `health.heartbeat(provider_id)`, `health.is_online(provider_id)` | lonestar | 10 s heartbeat loop, 30 s offline rule |
| `jev.enabled()`, `jev.probability(check)` | jev | Off by default |
| `adversary.halted(tx, account_id)`, `adversary.observe(event)` | adversary | Order halt and observer seams |

## gridmarket-mcp tool names and arguments

| Name | Owning lane | Contract |
| --- | --- | --- |
| `market()` | mcp | Read products |
| `order_book(symbol)` | mcp | Read product book |
| `predictions(zone=None)` | mcp | Read zone scores |
| `router_checks(family=None)` | mcp | Read checks |
| `provider_health()` | mcp | Read provider status |
| `bot_population(bot_type=None)` | mcp | Read bots |
| `my_orders()` | mcp | Caller-scoped orders |
| `my_positions()` | mcp | Caller-scoped positions |
| `my_pnl()` | mcp | Caller-scoped P&L |
| `my_losses()` | mcp | Caller-scoped losses |
| `buy(product_id, quantity, price_cents, idempotency_key)` | mcp | Public API order |
| `sell(product_id, quantity, price_cents, idempotency_key)` | mcp | Public API order |
| `cancel(order_id)` | mcp | Public API cancel |

## ERCOT Worker snapshot fields

| Name | Owning lane | Contract |
| --- | --- | --- |
| `GET /api/snapshot`: `asOf`, `ct`, `heNow`, `errors`, `demand`, `hubs`, `dam`, `sced`, `wind`, `solar`, `weather`, `checks` | worker | Five-minute cached JSON snapshot |
| `GET /api/report/np6-905-cd/spp_node_zone_hub` | worker | ERCOT `{fields, data, _meta}` |
| `GET /api/report/np4-190-cd/dam_stlmnt_pnt_prices` | worker | ERCOT `{fields, data, _meta}` |
| `GET /api/report/np3-565-cd/lf_by_model_weather_zone` | worker | ERCOT `{fields, data, _meta}` |
| `GET /api/report/np3-233-cd/hourly_res_outage_cap` | worker | ERCOT `{fields, data, _meta}` |
| `GET /api/report/np6-86-cd/shdw_prices_bnd_trns_const` | worker | ERCOT `{fields, data, _meta}` |
| `GRIDMARKET_WORKER_URL`, `GRIDMARKET_WORKER_KEY` | data | Market Worker client settings |
| `GRIDMARKET_DB` | foundation | SQLite path; default `/data/gridmarket.db` |

## Dashboard page routes and data hooks

| Name | Owning lane | Contract |
| --- | --- | --- |
| `#/` Overview, `useMarketStatus`, `useMarketActivity`, `useSignals` | ui | Overview shell and feed |
| `#/market` Market, `useMarket` | pages | Products and book |
| `#/predictions` Predictions, `usePredictions`, `useRouterChecks` | pages | Scores and checks |
| `#/providers` Providers, `useProviders`, `useProviderHealth` | providers-page | Provider health |
| `#/bots` Bots, `useBots`, `useBotDiversity` | pages | Population and diversity |
| `#/bots/:id` BotProfile, `useBotProfile` | pages | Public profile |
| `#/sandbox` Sandbox | pages | Judge key onboarding |
| `#/spec` Spec | pages | Specification link |
| `useResource` | foundation | Two-second polling, loading and error state |

## Error codes

| Name | Owning lane | Contract |
| --- | --- | --- |
| `UNAUTHENTICATED`, `RATE_LIMITED` | market | 401 / 429 |
| `IDEMPOTENCY_KEY_REQUIRED`, `IDEMPOTENCY_CONFLICT` | market | 400 / 409 |
| `MARKET_HALTED` | adversary | 423 |
| `ORDER_TOO_LARGE`, `POSITION_LIMIT`, `INSUFFICIENT_FUNDS`, `INSUFFICIENT_CAPACITY` | market | Risk and balance rejection |
| `UNKNOWN_PRODUCT`, `PRODUCT_CLOSED` | market | Product rejection |
| `PROVIDER_OFFLINE` | lonestar | Offline sell rejection |
| `FORBIDDEN` | market | 403 admin guard |
| `NOT_FOUND`, `BAD_REQUEST`, `INTERNAL_ERROR` | market | General HTTP errors |
| `VALIDATION_ERROR`, `SANDBOX_CAP` | market | 422 / 503 sandbox rejection |
| `BOT_CAP` | bots | 200-bot cap |
