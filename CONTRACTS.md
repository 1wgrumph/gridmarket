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
| Market product: `id`, `symbol`, `zone`, `delivery_hour`, `status` | market | Public product |
| Trade: `id`, `product_id`, `buy_order_id`, `sell_order_id`, `quantity`, `price_cents`, `created_at` | market | Append-only fill |
| Asset: `id`, `account_id`, `provider_id`, `zone`, `capacity_kwh`, `soc_kwh`, `min_reserve_kwh`, `charge_kw`, `discharge_kw` | market | Battery |
| Prediction response: `zone`, `delivery_hour`, `score`, `level`, `confidence`, `expected_value`, `market_price`, `drivers`, `disclaimer`, `generated_at` | data | `drivers` entries have `factor`, `contribution`, `detail` |
| Router response: `checks`, `brier`, `jev_enabled` | router | Latest results, per-check calibration, Jev flag |
| Bot response: `id`, `bot_type`, `blend`, `provider_id`, `cash`, `net_worth`, `pnl`, `trades`, `losses`, `dormant` | bots | Public bot profile |
| Sandbox key request: `label` | market | `^[A-Za-z0-9 _-]{1,24}$` |
| Sandbox key response: `account_id`, `api_key`, `label` | market | Key shown once |
| Spawn request: `count`, `seed` | bots | `count` 1–10; seed optional |
| Outage request: `active` | lonestar | Start/end simulated outage |
| Error response: `error.code`, `error.message` | market | Stable JSON envelope |

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

## Flex core (C2, DEC-GM-113)

`gridmarket_server.flex` exports `Battery`, `StepResult`, `Observation`,
`FeedWindow`, `InformationSet`, `InformationView`, `Decision`, `DecisionInput`,
`FixedSchedule`, `PriceBased`, and `EsrInformed`. This is simulated dispatch,
not ERCOT clearing or a live order executor.

- Amendment 5: stored SoC/reservations are DC kWh; power and household load are
  AC kW. `Battery.transition(...)` is pure; `step(...)` applies its result only
  to the caller-owned battery. Both use `E_next = E + sqrt(eta)*C*h - D*h/sqrt(eta)`.
  Commercial discharge subtracts `reserved_dc_kwh` before computing feasibility.
  The engine owns reservation creation/release; release the reservation being
  delivered before its transition, retaining all other outstanding reservations.
  `forced=True` is diagnostic only: any actual reserve breach invalidates the result.
  Household load affects import/export, never implicitly depletes the battery.
  No solar, standby loss or degradation is modelled. No money or monetary
  rounding is performed in this layer.
- Amendments 3/9: `InformationSet.at(time, feed_interrupts=...)` returns immutable,
  deduplicated observations with known publication and availability and
  `available_at <= time`. Unknown availability and retrospective/settlement-only
  quality are excluded. The latest eligible version wins; conflicting versions
  at identical timestamps are rejected. Active source interruptions suppress new
  arrivals and expire known actuals at 30 minutes from interval end; known DAM
  remains visible. Recovery restores then-available observations. The returned
  view exposes neither the backing dataset nor future disruption windows.
- Amendment 6: each policy exposes keyword-only `decide(battery, information,
  household_load_kw, config, decision_time, feed_interrupts=())`; time must open
  a UTC quarter. `config.zone` defaults to `LZ_HOUSTON` and
  `config.current_commitment_kw` defaults to zero; a current delivery suppresses
  charging. Policies do not mutate battery state or read clocks, RNG, live
  stores or the network. Reasons describe requests, with acceptance/delivery
  pending. `hold` and `preserve_backup` neither dispatch nor cancel commitments.
  Returned config includes a complete `state_snapshot` (including zero load and
  reservations); decision inputs carry all DAM observations used by thresholds.
- FixedSchedule charges 00:00–06:00 Central and offers for next-quarter delivery
  17:00–21:00. PriceBased requires a complete eligible local-day hourly DAM
  vector (23/24/25 hours), uses nearest-rank Q25/Q75, prioritizes offers over
  charging, and holds for overlapping quantiles or unavailable DAM. EsrInformed
  additionally offers on eligible RT >= Q75 and decreasing absolute charging
  across the latest two contiguous complete 15-minute ERCOT ESR bins. Missing
  RT/ESR explicitly falls back to PriceBased. This is a simulated heuristic,
  not an ERCOT scarcity declaration. Offers cannot cross the local day boundary.

S69 owns procurement, accepted commitments, settlement, breach counting, and the
Decimal day-component ledger with HALF_EVEN posting. C2 does not implement those
APIs or claim independent review, real-source qualification, or replay acceptance.

## Replay engine and API (C3, DEC-GM-113)

`gridmarket_server.replay` runs a labelled simulated peak-flex procurement
programme on captured ERCOT observations; it is not ERCOT clearing. One
catalogued day per run, stepped at local-day 15-minute quarters (92/96/100).
Each strategy gets an independently cloned fleet; demand per procurement
quarter is 25% of the fleet's initial rated AC discharge kW, fixed across
strategy copies, zero outside delivery starts 17:00–21:00 Central. Offers
target the next quarter; acceptance is pro rata with deterministic
0.000001-kWh floor and lexicographic residual; accepted energy is reserved
immediately (AC kWh / eta_d) and released exactly once after settlement.
Settlement truth is independent of interrupted agent feeds. Money posts once
per strategy/day ledger component in integer cents (HALF_EVEN); net =
energy − charging + bonus − penalty + terminal mark − opening mark; a
no-action run scores zero. Breaches invalidate the run; shortfalls above
0.000001 kWh are failed commitments with cause. `provider_offline` blocks new
commitments and dispatch while retaining SoC and liabilities;
`feed_interrupt` hides new observations (actuals expire 30 minutes after
interval end; published DAM stays valid) and never erases settled state.

- `POST /v1/replay` (day, 1–3 distinct strategies, 1–1000 assets, 0–20
  disruptions, 2 MiB, 6 runs/minute/client, 2 concurrent computations) returns
  canonical JSON: `run_id` (SHA-256 of the binding), binding, scoreboard and
  timeline. Identical requests return byte-identical bodies without timing
  keys; the latest 20 completed runs are retained. Oversize is 413, invalid
  422, rate/concurrency 429, unknown day or run 404.
- `GET /v1/replay/{run_id}` returns the stored immutable body. Reset clears
  playback state; rerun reuses the same inputs.
- `GET /v1/replay/days` lists catalogued days with quarters, gaps, synthetic
  flags, availability status and `peak_rt_price` (point, interval, value).
- Availability: `strict` when every series carries real `available_at`;
  otherwise labelled `assumed` (DAM 13:30 Central D−1, RT 5 minutes after
  interval end, load 20 minutes after). Every run carries
  `availability_mode` plus the assumption text; the S67 2026-08-26 dataset is
  assumed-mode because ERCOT archives do not record original publication
  times. Datasets use `$/MWh` archive labels normalized to the `USD/MWh`
  policy contract. Every run and day states: "Historical ERCOT observations;
  simulated households, batteries, procurement and outcomes."
