---
type: technical-plan
status: complete
lifecycle: GM-2026-09-25
title: GridMarket hackathon MVP
plan_dir: docs/plans/2026-09-25-gridmarket/
---

# GridMarket hackathon MVP — Technical Plan

## Outcome

A provider-neutral, API-first simulated exchange for battery flexibility,
driven by live ERCOT Public API data, that completes the demo story of
`gridmarket-intent.html` §20 without crashing. It is entered in the Open Grid
Data and Most Commercializable tracks (DEC-GM-003). Delivery is phased
(DEC-GM-005): phase 1 is the core and must be demoable first; phase 2 adds the
LoneStar Storage provider adapter (DEC-GM-006); stretch items (adversarial
scenario with kill switch, score backtest, Rust PyO3 matching core with
benchmark, an ML model compared against the deterministic score, DEC-GM-017, the local gridmarket-mcp, the owner's qlib strategy, and the Jev flag, CONF-GM-PHASE-PLACEMENT) run in parallel lanes and are merged only when green. A Spec lane builds the spec template, the azdiagram generator, the spec skills, and GridMarket's own specification for the judges (DEC-GM-019). All submission code is written during the hackathon (DEC-GM-020). The architecture is hybrid (DEC-GM-021, amended by DEC-GM-027): the owner's own Cloudflare Worker, built from Jordan Hill's `ercot-hackathon` code at `4853e51` plus the S24–S25 security fix and deployed on the owner's Cloudflare account with owner-held ERCOT credentials, is the ERCOT data edge and serves the 3D views; the Python market reads ERCOT data only through that Worker, and the two surfaces link to each other (DEC-GM-029). Jordan is no longer on the critical path. Phase 1 adds a decision router with baseline market checks (DEC-GM-028), a 7-type bot population with layered diversity and a bot economy (DEC-GM-030..032), and a multi-page Astryx dashboard (DEC-GM-033, CONF-GM-PAGES) with quick sandbox onboarding (DEC-GM-037). Phase 2 adds router health checks, a simulated LoneStar outage, the Providers page, the strategy template, and the LLM prompt kit. Phase 1 is delivered as phase 1a, a walking skeleton, and phase 1b, the rich core (DEC-GM-038). The build is contract-first (DEC-GM-039): wave 1 freezes every shared name as code stubs plus `CONTRACTS.md`, then one wide wave builds phases 1a, 1b, 2, and stretch in parallel lanes against those contracts; each phase gets one review, at most one repair, and lands on `main` through a merged PR (DEC-GM-038, DEC-GM-040). A short final wave writes the agent-readable user guide and onboarding skill and finishes quick website onboarding (DEC-GM-036, DEC-GM-037). Feature
freeze is Sun 2026-09-27 07:00 CDT; submission is 11:00 CDT.

## Requirements register

No requirements register exists. The repository is greenfield
(`workspace.md` Observed Systems; `repository-map.md` Anchors) and the
Lifecycle is not a specification Lifecycle. Every requirement below is
Lifecycle-local (`AC-*` / `RISK-*`). Sources are the confirmed decisions
DEC-GM-001..040 and DEC-GM-042 (DEC-GM-041 is revoked by DEC-GM-042),
SC-2-AMENDMENT, and CONF-GM-PAGES, CONF-GM-VISUAL-REVIEW,
CONF-GM-JORDAN-DISCLAIMER, and CONF-GM-PHASE-PLACEMENT in `journey.json`, and
the owner intent `gridmarket-intent.html` (§ numbers). Success criteria are
cited as SC-n (intent §22); SC-2 is read as amended by SC-2-AMENDMENT.

## Definitions

- **Zone**: one of the four ERCOT load zones `LZ_HOUSTON`, `LZ_NORTH`,
  `LZ_SOUTH`, `LZ_WEST`.
- **Delivery hour**: a one-hour interval starting on the hour, America/Chicago.
- **Flex Credit (credit)**: 1 kWh of battery flexibility for one delivery hour
  (intent §5). Price unit is $/credit; $/MWh ÷ 1000 = $/credit (DEC-GM-008).
- **Spot product**: `SPOT-<zone>-<YYYY-MM-DD>-<HH>`, delivery hour starting 1
  or 2 hours after the current hour; a sell is backed by a battery capacity
  reservation.
- **Future product**: `FLEX-<zone>-<YYYY-MM-DD>-<HH>`, delivery hour starting
  3 to 24 hours after the current hour; cash-settled at expiry (DEC-GM-008).
- **Available capacity** (per battery, per delivery hour): state of charge
  minus minimum reserve, minus quantities already reserved for that hour, never
  below zero.
- **Sandbox key**: an API key bound to one sandbox account with $1,000.00 simulated cash and a limit of 5 requests per second, created by `POST /v1/sandbox/keys` or by `python -m gridmarket_server.keys issue --sandbox` (AC-GM-API-06).
- **Admin request**: a request that carries the admin API key named in the
  untracked environment file and arrives on the host's loopback interface
  without a `CF-Connecting-IP` header, that is, not through the tunnel.
- **Bot**: a seeded or owner-spawned simulated trader with its own account and
  API key (DEC-GM-030). **Master seed**: the integer logged at startup that is the default seed for bot parameters (DEC-GM-031). A spawned cohort uses this integer unless its request names a seed (AC-GM-BOT-07).
- **Decision router**: the component that answers checks. A **check** is one
  question with a fixed horizon that returns a probability. Its **band** is
  calibration-log below 0.50, review from 0.50 to below 0.80, and alert at
  0.80 or above (DEC-GM-028). A **baseline rule** is the deterministic rule
  that always answers a check.
- **Deposit**: a ledger entry that adds income to a bot's cash; it is not a
  trade and is excluded from P&L (DEC-GM-032).
- **Settled position**: one account's holding in one product, recorded at the product's expiry or when the holding quantity returns to zero. If the product expires with a non-zero holding, realized P&L is (reference price − average trade price) × signed quantity, using the reference price of AC-GM-MKT-05. If the holding returns to zero before expiry, realized P&L is (average closing trade price − average opening trade price) × signed opened quantity. For a spot product that realized P&L changes no cash and feeds only the loss statistics, because cash moved at the fill.
- **Dormant bot**: an unemployed bot whose available cash is below $1.00 and that has no available battery capacity for any listed spot product. Available cash is the account's cash minus cash held for that account's open orders. The dormant rate is the number of dormant bots divided by the number of bots.
- **Net worth**: cash plus the unrealized value of open future positions. Each open future position is marked at the last trade price of that product, otherwise the mid of the best bid and best ask, otherwise the prediction's expected value for that zone and delivery hour. Unrealized value is (mark − average trade price) × signed quantity. Spot Flex Credit inventory adds nothing further, because cash moved at the fill.
- **Append-only trade ledger**: the stored records of fills, settlements,
  market or account halts, and halt lifts; the system never updates or deletes
  them.
- **Representative point**: the NWS forecast location of a zone: Houston
  (29.76, −95.37) for LZ_HOUSTON, Dallas (32.78, −96.80) for LZ_NORTH, San
  Antonio (29.42, −98.49) for LZ_SOUTH, Midland (31.99, −102.08) for LZ_WEST.
- **On-peak hour**: an hour ending 07:00 through 22:00 Central Prevailing Time
  on Monday to Friday, except the six NERC holidays (New Year's Day, Memorial
  Day, Independence Day, Labor Day, Thanksgiving Day, Christmas Day; a Sunday
  holiday is observed on Monday).
- **ERCOT Worker**: the owner's Cloudflare Worker built from `ercot-hackathon/` at commit `4853e51` plus the S24–S25 security fix (DEC-GM-021, DEC-GM-027), deployed on the owner's Cloudflare account and reached at the URL in the untracked environment variable `GRIDMARKET_WORKER_URL`. It holds the owner's ERCOT credentials as Worker secrets.
- **Report allowlist**: the fixed set of `/api/report/<emil-id>/<report>` paths
  the ERCOT Worker serves. The set contains one path for each of the five
  reports named in AC-GM-DATA-01 and no other path.
- **Market client key**: a secret shared by the market and the ERCOT Worker,
  sent by the market in the `x-gridmarket-key` header, stored in the untracked
  environment file and as a Worker secret.
- **Live data path**: the running application, its seeded traffic, and the
  demo. Test code is outside the live data path (DEC-GM-014).

## Requirements (Lifecycle-local)

### Phase 1 — core

Phase 1 is delivered in two declared phases (DEC-GM-038). A phase demonstrates only the rows listed for it. **Phase 1a** (walking skeleton): AC-GM-DATA-01, AC-GM-DATA-02, AC-GM-DATA-03, AC-GM-DATA-04, AC-GM-DATA-05, AC-GM-SCORE-01, AC-GM-SCORE-02, AC-GM-SCORE-03, AC-GM-SCORE-04, AC-GM-SCORE-05, AC-GM-MKT-01, AC-GM-MKT-02, AC-GM-MKT-03, AC-GM-MKT-04, AC-GM-MKT-05, AC-GM-MKT-06, AC-GM-API-01, AC-GM-API-02, AC-GM-API-03, AC-GM-API-04, AC-GM-API-06, AC-GM-API-07, AC-GM-EDGE-01, AC-GM-EDGE-02, AC-GM-EDGE-03, AC-GM-EDGE-04, AC-GM-OPS-01, AC-GM-UI-02, AC-GM-UI-06, AC-GM-ACC-03, and AC-GM-UI-01 for the Overview page and the app shell only. **Phase 1b** (rich core): AC-GM-ACCT-01, AC-GM-BOT-01, AC-GM-BOT-02, AC-GM-BOT-03, AC-GM-BOT-04, AC-GM-BOT-07, AC-GM-BOT-08, AC-GM-ECON-01, AC-GM-ECON-02, AC-GM-ECON-03, AC-GM-ECON-04, AC-GM-ROUTER-01, AC-GM-ROUTER-02, AC-GM-API-05, AC-GM-EDGE-05, AC-GM-UI-03, AC-GM-ACC-01, AC-GM-UI-01 for the Market page, the Predictions and router page (market checks), the Bots page including the dormant rate and `/bots/:id`, the Judge sandbox route, and the Spec link when the specification has landed, and AC-GM-UI-07 for the dormant rate. AC-GM-BOT-05, AC-GM-BOT-06, and the AC-GM-UI-07 coverage, entropy, and scatter are phase 1b unless the Sat 14:00 CDT slip trigger moves them to phase 2. The spec lane (AC-GM-SPEC-01, AC-GM-SPEC-02, AC-GM-SPEC-03) is phase 1b and does not block the phase 1b landing. AC-GM-UI-05 is built in the final wave. No phase 1 row is listed in both phase 1a and phase 1b.

| ID | Statement | Source | Verification |
|---|---|---|---|
| AC-GM-DATA-01 | While the ERCOT Worker is reachable, the system shall poll `/api/snapshot` and shall store that response's demand, hub real-time prices, HB_NORTH day-ahead price, and SCED lambda with the snapshot `asOf` and the fetch time, and shall poll allowlisted `/api/report/<emil-id>/<report>` routes for real-time settlement point prices (NP6-905-CD), day-ahead settlement point prices (NP4-190-CD), the seven-day load forecast by weather zone (NP3-565-CD), hourly resource outage capacity (NP3-233-CD), and SCED shadow prices and binding constraints (NP6-86-CD), and shall store each settlement-point price with its settlement-point name, each load-forecast value with its ERCOT weather-zone name, each outage-capacity value with its load zone, and each shadow price with its constraint identity, and shall store each of those report values with its interval, ERCOT publish time, and fetch time. | DEC-GM-007, DEC-GM-012, DEC-GM-021, intent §8, SC-1 | test (fixtures), demonstration (live) |
| AC-GM-DATA-02 | The market's ERCOT Worker client shall send no more than 12 requests in any rolling 60-second window, and shall never send the `fresh` query parameter. | DEC-GM-007, DEC-GM-021 | test |
| AC-GM-DATA-03 | If an ERCOT Worker request returns HTTP 401, HTTP 404, HTTP 429, or a 5xx status, or the connection fails before a complete HTTP response, then the system shall retry that request with exponential backoff whose delay is at most 5 minutes, shall keep serving the last stored values marked stale with their age in seconds, and shall keep every API endpoint able to return an HTTP response. | DEC-GM-007 recorded risk | test |
| AC-GM-DATA-04 | The live data path shall read ERCOT signals only through the ERCOT Worker, shall hold no ERCOT credentials, and shall read the Worker URL and the market client key only from an untracked environment file whose values never appear in the repository, in logs, or in API responses. | DEC-GM-007, DEC-GM-014, DEC-GM-011, DEC-GM-021 | inspection, test |
| AC-GM-DATA-05 | While the application runs, the system shall poll the NWS API (api.weather.gov) for the hourly temperature forecast and the active alerts at each zone's representative point, sending a User-Agent header, no more than 6 requests in any rolling 60-second window, and applying the retry and stale-marking rule of AC-GM-DATA-03 to NWS failures. | DEC-GM-017 | test |
| AC-GM-SCORE-01 | The system shall publish, for each zone and each future delivery hour, an opportunity score from 0 to 100, a scarcity level (LOW below 40, MEDIUM from 40 to below 70, HIGH at 70 or above), a confidence from 0 to 1, an expected flexibility value in $/credit, and a signed point contribution with a one-line explanation for each of the price-spread, load-pressure, outage-pressure, congestion-pressure, heat-stress, peak-period, and weather-alert factors. | DEC-GM-012, intent §9, SC-4, SC-5 | test |
| AC-GM-SCORE-02 | When the hourly resource outage capacity stored for a load zone increases while every other input to that zone's opportunity score is unchanged, the opportunity score for that zone shall not decrease. When a shadow price cited by that zone's congestion-pressure explanation increases while every other input to that zone's opportunity score is unchanged, the opportunity score for that zone shall not decrease. | intent §8, §9.2, SC-4 | test |
| AC-GM-SCORE-03 | The system shall state in every prediction API response and every dashboard prediction view that the score is a simulation estimate and not guaranteed profit. | intent §9.2 | test, inspection |
| AC-GM-SCORE-04 | The system shall give the peak-period factor a positive signed point contribution when the delivery hour is an on-peak hour, and a negative signed point contribution otherwise, using the standard library calendar and no added dependency. | DEC-GM-017 | test |
| AC-GM-SCORE-05 | When the NWS forecast temperature at a zone's representative point for the delivery hour increases and the higher temperature is at or above 85 °F, or the number of active NWS alerts at that point increases, while every other input to that zone's opportunity score is unchanged, the opportunity score for that zone shall not decrease. | DEC-GM-017 | test |
| AC-GM-ACCT-01 | When the database is empty at startup, the system shall create the seeded bot population of AC-GM-BOT-02, each bot account with the starting cash of AC-GM-ECON-01, zero Flex Credits, one API key, and the batteries of AC-GM-BOT-04, each battery with provider, zone, capacity in kWh, state of charge in kWh, minimum reserve in kWh, and a charge limit and a discharge limit that are determined by that battery's capacity and each lie in 2 through 10 kW; every human or judge sandbox account shall start with $1,000.00 simulated cash and zero Flex Credits. | intent §4, DEC-GM-012, DEC-GM-032, SC-2 as amended (SC-2-AMENDMENT) | test |
| AC-GM-MKT-01 | The system shall list one spot product for every zone for each delivery hour starting 1 or 2 hours after the current hour and one future product for every zone for each delivery hour starting 3 to 24 hours after the current hour, and shall trade both product types through one matching engine. | DEC-GM-012, intent §6, §7, SC-3 | test |
| AC-GM-MKT-02 | When an incoming limit order crosses resting orders, the matching engine shall fill it in price-time priority at each resting order's price, and the system shall record each fill exactly once in an append-only trade ledger. | intent §6, SC-3 | test |
| AC-GM-MKT-03 | If a spot sell order's quantity exceeds the seller's available capacity for the delivery hour, then the system shall reject the order, and concurrent sell orders shall never reserve more than the available capacity of any battery. | intent §4.2, §15, DEC-GM-012, SC-10 | test |
| AC-GM-MKT-04 | If an order exceeds 50 credits, would raise the account's absolute net position in the product above 200 credits, or requires more cash than the account's cash minus cash held for that account's open orders, then the system shall reject it with a typed reason and change no balances. | intent §7, §15, DEC-GM-012, SC-10 | test |
| AC-GM-MKT-05 | When all four 15-minute real-time settlement point prices of a future product's delivery hour are stored, the system shall settle every open position in that product at the reference price (their average in $/MWh ÷ 1000) with cash P&L equal to (reference − trade price) × signed quantity, and shall report realized and unrealized P&L per account. | DEC-GM-008, intent §7 | test |
| AC-GM-MKT-06 | When a spot fill occurs, the system shall transfer simulated cash from the buyer to the seller of that fill in the amount fill price × filled quantity and shall increase the buyer's Flex Credit inventory by that filled quantity. | intent §6, DEC-GM-012, SC-2, SC-3 | test |
| AC-GM-API-01 | If a request to an account or trading endpoint carries no valid API key, then the system shall return HTTP 401 and change no state; the system shall store API keys only as SHA-256 hashes. | DEC-GM-012, intent §14, §15 | test |
| AC-GM-API-02 | When an order is submitted with an Idempotency-Key already used by the same account, the system shall return the original result without creating a second order if the request body is identical, and shall return HTTP 409 if the body differs; an order without an Idempotency-Key shall be rejected with HTTP 400. | DEC-GM-012, intent §15 | test |
| AC-GM-API-03 | If a client exceeds its request rate limit (standard keys 20 requests per second, sandbox keys 5 requests per second, unauthenticated reads 10 requests per second per client address), then the system shall return HTTP 429 and change no state. | DEC-GM-009, DEC-GM-012, intent §15 | test |
| AC-GM-API-04 | The system shall serve the REST endpoints of intent §11 except the WebSocket streams, with a generated OpenAPI document, and a Python example of at most 30 lines using the repository SDK and a sandbox key shall submit an order that the dashboard activity feed shows within 5 seconds. | intent §11, §13, DEC-GM-013, SC-7, SC-8 | test, demonstration |
| AC-GM-API-05 | When a GET request to `/v1/market`, `/v1/market/{symbol}`, `/v1/market/history`, `/v1/market/activity`, `/v1/predictions`, `/v1/predictions/{zone}`, or `/v1/router` carries the `Origin` named in the untracked environment variable `GRIDMARKET_CORS_ORIGIN`, the system shall return `Access-Control-Allow-Origin` set to that origin, and shall return no `Access-Control-Allow-Origin` header for any other origin or for a request to an account, trading, sandbox, or admin endpoint. | DEC-GM-021, DEC-GM-029 | test |
| AC-GM-BOT-01 | While seeded traffic runs, it shall submit at least 10 orders per minute from at least 3 seeded accounts only through the public HTTP API with those accounts' own API keys. | intent §12, §18 P0-14, SC-9 | test, demonstration |
| AC-GM-UI-01 | The dashboard shall serve, without login, as a single-page app and shall refresh displayed data by REST polling every 2 seconds. The Overview page shall show ERCOT signals with publish time and staleness, zone scores, participant counts per provider, market status, the order activity feed, and a link to the 3D views. The app shell shall show navigation, the disclosures of AC-GM-UI-02, and the theme control. The Market page shall show products, order book depth, and recent trades. The Predictions and router page shall show factor contributions per zone and the market-check family, shall show the health-check family only when that family is in the landed candidate, and shall show no Jev column while `GRIDMARKET_JEV` is unset or is not `on`. The Bots page shall show the population table, the dormant rate, the `/bots/:id` profile page, and the spawn form of AC-GM-BOT-07. The Judge sandbox route shall be served. The Spec page shall link to the GridMarket specification when that specification is in the landed candidate and shall be omitted when it is not. | intent §20, SC-1, SC-11, CONF-GM-PAGES | test, demonstration |
| AC-GM-UI-02 | The dashboard shall display that future products are simulated forward flexibility contracts and not regulated commodity futures, and that a Flex Credit is not a renewable energy certificate, a cryptocurrency, or a claim on specific electrons. | intent §5, §7 | test, inspection |
| AC-GM-UI-03 | The bot profile page shall show the bot's traits, strategy blend, household, job and pay, the cash balance after each of that bot's fills and deposits in ledger order, trade count, losing positions as count, share of settled positions, and worst loss, P&L excluding deposits, and dormant status. | DEC-GM-032, CONF-GM-PAGES | test |
| AC-GM-UI-06 | The dashboard shall use `@astryxdesign/core` 0.6.0 with Recharts 3.10.1 on React 19 in a dark control-room theme with cyan accent and the colors #5fdd91, #ff7a45, and #f2c14e, plus a light mode; if the Astryx and StyleX Vite build is not green at the S04 exit, the dashboard shall instead use shadcn/ui with Tailwind 4 and Recharts in the same palette. | DEC-GM-033 | inspection, demonstration |
| AC-GM-API-06 | When a client requests a sandbox key from `POST /v1/sandbox/keys`, the client address is the `CF-Connecting-IP` value when that header is present and otherwise the socket peer address. The system shall create a sandbox account with $1,000.00 simulated cash and a limit of 5 requests per second, and shall return its API key once. It shall return HTTP 429 and create no account when that client address has received 3 sandbox keys in the preceding 60 minutes. It shall return HTTP 503 with code `SANDBOX_CAP` and create no account once 300 sandbox accounts exist. It shall return HTTP 422 and create no account when a label is present and does not match `^[A-Za-z0-9 _-]{1,24}$`. A missing label shall be accepted. The owner command `python -m gridmarket_server.keys issue --sandbox` shall create one sandbox account with the same cash and rate limit and shall print its API key once. | DEC-GM-037, intent §15 | test |
| AC-GM-API-07 | If a request to any `/v1/admin/*` path carries a `CF-Connecting-IP` header or does not arrive on the host's loopback interface, the system shall return HTTP 403 and change no state. If a request to any `/v1/admin/*` path arrives on the host's loopback interface without a `CF-Connecting-IP` header and the admin API key is missing or wrong, the system shall return HTTP 401 and change no state. | DEC-GM-030, DEC-GM-028, intent §15 | test |
| AC-GM-BOT-02 | When the database is empty at startup, the system shall seed 60 bot accounts of 7 types: market maker 4, score follower 12, DART trader 8, heat seller 14, saver 12, alert reactor 6, and noise trader 4; while the LoneStar Storage adapter is enabled, at least 20 of them shall be LoneStar Storage customers. | DEC-GM-030 | test |
| AC-GM-BOT-03 | Each bot shall trade only through the public HTTP API with its own API key under the risk controls of AC-GM-MKT-03 and AC-GM-MKT-04, and shall submit no more than 6 orders in any rolling 60-second window. | DEC-GM-030, SC-9 | test |
| AC-GM-BOT-07 | When an admin request to `POST /v1/admin/bots` asks for a cohort of 1 to 10 bots with an optional seed, the system shall add that many bots sampled as in AC-GM-BOT-04 and log the seed used, using the master seed when the request names none. It shall return HTTP 422 and add no bot when the count is outside 1 to 10, and HTTP 409 with code `BOT_CAP` and add no bot when the cohort would raise the bot total above 200. The Bots page shall include a form that submits this request with an admin API key the operator types into the form, and the page shall not store that key. The request succeeds only when it is an admin request. | DEC-GM-030 | test |
| AC-GM-BOT-04 | The bot sampler shall use only the Python standard library. It shall seed each bot's generator as `random.Random(f"{master}:{index}")`. It shall draw the seven latent traits (risk appetite, patience, reaction delay, loss aversion, herd versus contrarian, daily activity pattern, wealth) with a Gaussian copula whose target correlation matrix is a fixed constant in the sampler, using a pure-Python Cholesky factor and `statistics.NormalDist`, and logistic-normal marginals on (0, 1) for risk appetite, patience, loss aversion, and herd versus contrarian. It shall give each bot 1 or 2 batteries whose capacity is lognormal with median 13.5 kWh and clamped to 5 through 40 kWh, a charge limit and a discharge limit determined by that capacity and each in 2 through 10 kW, a load zone drawn from fixed zone weights that are constants in the sampler and sum to 1, a reserve habit of 15% to 50% of capacity, and an hour-of-day activity schedule of 24 non-negative weights. | DEC-GM-031 layers 1 and 4 | test |
| AC-GM-BOT-08 | Two populations sampled from the same master seed shall have the same SHA-256 digest, the hex SHA-256 of the UTF-8 JSON array of bot records in ascending index order with object keys sorted. Over 2,000 sampled bots, the sample median battery capacity shall lie within 10% of 13.5 kWh, each zone's share shall lie within 0.05 of that zone's fixed weight, and each off-diagonal Spearman rank correlation of the seven latent traits shall lie within 0.10 of the sampler's fixed target correlation for that pair. The target matrix shall include at least one off-diagonal entry with absolute value at least 0.2. | DEC-GM-031 | test |
| AC-GM-BOT-05 | Each bot shall blend its main type with 2 other types using weights from a Dirichlet draw with alpha (6, 1.5, 1.5) produced with `random.Random.gammavariate`. Each bot shall be assigned a subset of these signal families: price-spread, load-pressure, outage-pressure, congestion-pressure, heat-stress, peak-period, weather-alert, and DART. The seeded population shall contain at least two different subsets. The bot shall use only its subset, delayed by its own delay of 0 through 15 minutes, shifted by its expected-value bias of −10% to +10%, and the value it acts on shall differ from the un-noised signal by no more than its observation-noise rate of 2% to 10%. | DEC-GM-031 layers 2 and 3; phase 2 if the slip trigger fires (CONF-GM-PHASE-PLACEMENT) | test |
| AC-GM-BOT-06 | Each bot shall store one or more decision thresholds, each with a declared numeric range. After each settled position, the bot shall move each threshold by no more than its learning rate, drawn once from 0.01 through 0.05, times that range's width, and shall clamp the result to the range. After a restart of the bot service, every threshold shall equal the value produced by replaying that bot's settled positions from the ledger in order, starting from the thresholds derived from the master seed. | DEC-GM-031 layer 5a; phase 2 if the slip trigger fires | test |
| AC-GM-UI-07 | The Bots page shall show the dormant rate. When diversity layers 2, 3, 5a, and 6 are in the landed candidate, the diversity panel shall also show trait-space coverage, behavior entropy, and a scatter of risk appetite against patience. Coverage is the fraction of the seven latent traits whose sample standard deviation over the seeded bots is at least 0.05. Behavior entropy is the Shannon entropy in bits of the main-type shares and shall be within 0.01 of the value computed from those shares. The scatter shall have one point per bot at that bot's risk appetite and patience. When those layers are not in the landed candidate, the page shall show the dormant rate and shall mark coverage, entropy, and the scatter as not enabled. | DEC-GM-031 layer 6, DEC-GM-032; the panel falls to phase 2 if the slip trigger fires, except the dormant rate | test |
| AC-GM-ECON-01 | Each bot shall start with cash drawn lognormal (median $1,000, sigma 0.8), clamped to $100 through $10,000. Each employed bot's pay shall be drawn lognormal (median $40, sigma 0.5), clamped to $10 through $150. The seeded population of 60 shall contain 39 employed bots. Over 2,000 sampled bots the median cash shall lie within 10% of $1,000, the median pay within 10% of $40, the employed share within 0.03 of 0.65, the Spearman rank correlation of starting cash with employment (1 employed, 0 unemployed) within 0.10 of +0.3, and the Spearman rank correlation of starting cash with risk appetite within 0.10 of +0.2. An employed bot's hour-of-day activity weight summed over 06:00–08:59 and 17:00–19:59 America/Chicago shall exceed its weight summed over 09:00–16:59. An unemployed bot's weight summed over 09:00–16:59 shall exceed its weight summed over 06:00–08:59 and 17:00–19:59. | DEC-GM-032 | test |
| AC-GM-ECON-02 | Every 30 minutes of real time, at an offset drawn once per bot uniformly from 0 minutes inclusive to 30 minutes exclusive and then held fixed, the system shall add each employed bot's pay to its cash as a deposit ledger entry, which is not a trade and which changes no P&L. Unemployed bots shall receive no deposit. | DEC-GM-032 | test |
| AC-GM-ECON-03 | The system shall count one loss for each settled position with negative realized P&L, shall report net worth, shall mark a bot dormant when it meets the dormant-bot definition, shall add no cash to a dormant bot, and shall show the dormant rate on the Bots page. | DEC-GM-032 | test |
| AC-GM-ECON-04 | After a restart of the bot service, each bot's parameters, cash, positions, and dormant status shall equal the values rebuilt from the ledger and the master seed. | DEC-GM-032 | test |
| AC-GM-ROUTER-01 | The decision router shall answer the DART spread check for each zone and each future delivery hour: the probability that the zone's real-time settlement point price averaged over that delivery hour exceeds its day-ahead price for that hour. The horizon ends at the end of that delivery hour. The router shall answer with a baseline-rule probability and that probability's band, shall record the realized outcome when the horizon ends (1 when the inequality holds, otherwise 0), and shall report at `GET /v1/router` each check's Brier score, the mean of (probability − outcome) squared over its resolved results. | DEC-GM-028 | test |
| AC-GM-ROUTER-02 | The decision router shall submit no orders and shall hold no account API key. No router output shall change market state except the baseline rule of AC-GM-PROV-04 that marks a provider offline or online. | DEC-GM-028 | test, inspection |
| AC-GM-EDGE-05 | The ERCOT Worker's `/`, `/diagram/`, and `/godseye/` views shall each link to the dashboard. The `/` and `/godseye/` views shall show market activity read by cross-origin GET of `/v1/market/activity` and router results read by cross-origin GET of `/v1/router`. Those views shall keep rendering their ERCOT content when a request to the market fails to complete. The dashboard Overview shall link to the views. | DEC-GM-029 | test, demonstration |
| AC-GM-EDGE-01 | The ERCOT Worker shall return HTTP 404 without calling ERCOT for a `/api/report/*` path outside the report allowlist, and shall return HTTP 401 without calling ERCOT for a `/api/report/*` or `/api/products` request, or a `/api/snapshot` request with the `fresh` parameter, that lacks a valid market client key. | DEC-GM-021 required fix, DEC-GM-022 | test, demonstration |
| AC-GM-EDGE-02 | The ERCOT Worker shall return HTTP 429 without calling ERCOT when one client address sends more than 30 requests to `/api/*` in any 60-second window. | DEC-GM-021 required fix, DEC-GM-022 | test |
| AC-GM-EDGE-03 | The ERCOT Worker shall send no more than 25 requests to ERCOT, token requests and retries included, in any 60-second window for any number of clients and requests, and shall return HTTP 429 without calling ERCOT for a request whose ERCOT call would exceed that budget and that no cached response can answer. | DEC-GM-022 | test |
| AC-GM-EDGE-04 | If ERCOT returns HTTP 429 to a call made while building `/api/snapshot`, then the ERCOT Worker shall retry that call at most 4 times, and the wait before retry attempt n shall be the lesser of 4 seconds and the `Retry-After` value in seconds when that header is a positive number, and otherwise the lesser of 4 seconds and 0.9 seconds times n. | DEC-GM-022 | test |
| AC-GM-OPS-01 | The system shall run as Docker Compose services under a non-root user, shall bind its HTTP port only to 127.0.0.1 on the host, and shall be reachable from the internet only through an outbound Cloudflare named tunnel. | DEC-GM-009, DEC-GM-010 | inspection, demonstration |
| AC-GM-ACC-03 | The phase 1a acceptance run shall show SC-1, SC-3, SC-4, SC-5, SC-7, SC-8, and SC-10 in one uninterrupted session against the phase 1a integrated candidate. | DEC-GM-038, DEC-GM-016 | demonstration |
| AC-GM-ACC-01 | The phase 1b acceptance run shall show SC-1 to SC-5 and SC-7 to SC-11 in one uninterrupted session against the phase 1b integrated candidate. | DEC-GM-016 | demonstration |

### Phase 2 — second provider

| ID | Statement | Source | Verification |
|---|---|---|---|
| AC-GM-PROV-01 | The market shall read and reserve battery capacity only through the provider adapter interface (list customers, list assets, available capacity, reserve capacity, release capacity, verify delivery, asset status). | intent §10, DEC-GM-006 | test |
| AC-GM-PROV-02 | When the LoneStar Storage adapter is enabled, at least 20 LoneStar Storage customers shall trade on the same order books as Base simulator customers, and the dashboard shall show participant counts for both providers. | DEC-GM-006, SC-6 | test, demonstration |
| AC-GM-ROUTER-03 | The decision router shall compute, for the ERCOT Worker and for each provider, the probability of becoming unavailable within 15 minutes from in-process latency, error rate, HTTP 429 rate, snapshot staleness, and adapter heartbeat age, with the bands of AC-GM-ROUTER-01. | DEC-GM-028 | test |
| AC-GM-PROV-04 | When a provider adapter's last heartbeat is older than 30 seconds, the baseline rule shall mark that provider offline, and the system shall reject every new sell order from that provider's customers with typed reason `PROVIDER_OFFLINE` and change no balances until the next heartbeat marks it online. | DEC-GM-028 | test |
| AC-GM-PROV-03 | When an admin request to `POST /v1/admin/providers/lonestar/outage` with action `start` starts the simulated LoneStar Storage outage, the LoneStar adapter shall send no heartbeat until an admin request to that same path with action `end` ends the outage or 10 minutes pass, whichever comes first. Within 60 seconds of the start, `GET /v1/router` shall show the LoneStar health check offline with its probability in the alert band. | DEC-GM-028 | test, demonstration |
| AC-GM-UI-04 | The Providers page shall show, for Base simulator and LoneStar Storage, the customer count, the online asset count, the heartbeat age, the health-check probability and band, and the outage state. | CONF-GM-PAGES, DEC-GM-028 | test |
| AC-GM-KIT-01 | The strategy template in `examples/strategy-template/` shall use only the Python standard library and the repository SDK, shall read predictions and submit orders with a sandbox key through the public API, and shall submit no order that exceeds the order-size or position limits of AC-GM-MKT-04. | DEC-GM-035 | test |
| AC-GM-KIT-02 | The file `docs/llm/system-prompt.md` shall state that trading is simulated, that an order shall not exceed 50 credits, that an account's absolute net position in a product shall not exceed 200 credits, and that the agent shall not exceed the position limit. It shall include the `/openapi.json` URL and at least one Python SDK snippet. Every numeric limit the prompt states shall equal the value the risk engine enforces. | DEC-GM-035 | test, inspection |
| AC-GM-ACC-02 | The phase 2 acceptance run shall show SC-1 through SC-11 and the simulated LoneStar Storage outage of AC-GM-PROV-03 in one uninterrupted session against the phase 2 integrated candidate. | DEC-GM-016, DEC-GM-028 | demonstration |

### Stretch — merged only when green

| ID | Statement | Source | Verification |
|---|---|---|---|
| AC-GM-ADV-01 | When the adversarial scenario runs, the system shall reject an over-capacity spot sell and change no balances, shall create no second order when an identical request reuses an Idempotency-Key, and shall return HTTP 429 and change no state once one account exceeds its AC-GM-API-03 rate limit, and shall show each of those three outcomes as an anomaly on the dashboard. | DEC-GM-012, intent §15, §20 step 8 | test, demonstration |
| AC-GM-ADV-02 | When a request authenticated as the admin API key named in the untracked environment file invokes the kill switch for the market or for one account, the system shall reject every later order in that scope with a typed reason and change no balances until a request authenticated as that same admin API key lifts the halt, and shall append the halt and the lift to the append-only trade ledger. | DEC-GM-012, intent §15 | test |
| AC-GM-BT-01 | The backtest command shall compute, over at least 7 days of ERCOT history fetched through the ERCOT Worker's allowlisted report routes, the Spearman rank correlation between zone-hour opportunity scores and realized real-time settlement point prices, and shall report the correlation, the sample size, and the date range. | DEC-GM-012, intent §9.4 | test, demonstration |
| AC-GM-PERF-01 | Where the Rust matching core is enabled, it shall produce the same fills as the Python engine on the shared matching test suite, and a benchmark shall report orders per second for both engines on one identical workload; the Rust core shall be enabled only if its throughput is higher. | DEC-GM-010, DEC-GM-012 | test, analysis |
| AC-GM-MCP-01 | gridmarket-mcp shall run on the user's machine over stdio with the user's own sandbox key, shall expose read tools for the market and order books, predictions and router checks, provider health, and the bot population, and caller-scoped tools for the caller's own orders, positions, P&L, and loss history, shall place orders only through the public API, and shall return no free text entered by another user. | DEC-GM-035, DEC-GM-012 (partial supersession, item 25) | test |
| AC-GM-MCP-02 | gridmarket-mcp shall depend on an `mcp` package release that has been public for at least 14 days, and the Lifecycle shall deploy no remote MCP server. | DEC-GM-035, DEC-GM-020 | inspection |
| AC-GM-QUANT-01 | The qlib strategy shall use pyqlib 0.9.7, shall be written in this repository during the hackathon, and shall trade only through the public API with its own account key under AC-GM-MKT-03 and AC-GM-MKT-04. qlib and its dependencies shall install only through the optional `quant` extra and shall be absent from the runtime image unless the qlib lane is merged. Its backtest shall report the Spearman rank IC together with the sample size and the date range. When that lane is merged, `examples/strategy-template/` shall link to the strategy as an optional example. | DEC-GM-034 | test, inspection |
| AC-GM-ROUTER-04 | Where the environment variable `GRIDMARKET_JEV` equals `on`, the decision router shall add the hosted Jev service's probability for each check as a separate column that changes no market state. Where that variable is unset or equals any other value, the system shall make no call to the Jev service. | DEC-GM-028 | test |
| AC-GM-ML-01 | The ML command shall train a model on at least 28 days of ERCOT archive data fetched through the ERCOT Worker's allowlisted report routes with the score inputs, Open-Meteo weather history, Census county population estimates, and LEHD LODES8 Texas WAC and RAC job counts as a daytime population weight per zone, and the backtest shall report the Spearman rank correlation of both the model and the deterministic score against realized real-time settlement point prices over the same held-out range of at least 7 days after the training range, together with the model's feature importances. | DEC-GM-017, DEC-GM-012 (partial supersession), intent §9.4 | test, analysis |

### Spec lane — shown to the judges, must not block phase 1

| ID | Statement | Source | Verification |
|---|---|---|---|
| AC-GM-SPEC-01 | When azdiagram renders a per-class YAML figure input, it shall write an SVG file and a draw.io file from one Graphviz layout when the class is F1, F2, F3, F4, F6, or F7, and from the grid renderer when the class is F5 or F8, and its lint shall fail when two node boxes overlap or the figure exceeds the size limit named in that input. | DEC-GM-019, DEC-SPEC-006, DEC-SPEC-007 | test |
| AC-GM-SPEC-02 | The spec lint shall fail a specification section that lacks a BLUF, lacks any of the six Frame fields (Who, What, Why, How, When, Where), binds more than 5 requirements, cites a table or figure class outside T1–T8 and F1–F8, has no table when it lists 3 or more items that share 2 or more attributes, or has no figure when it names 3 or more entities with a relationship, a time order, or states. | DEC-GM-019, DEC-SPEC-005, DEC-SPEC-006 | test |
| AC-GM-SPEC-03 | The repository shall contain the spec template (generated front matter, the DEC-SPEC-004 outline, and the DEC-SPEC-010 additions of the COE-ASA-001 floor elements as subsections plus Stakeholders and their concerns, Model correspondence, and Rationale), the spec-author, spec-diagram, and spec-lint skills, and GridMarket's own specification written in that template with its figures, and the specification shall pass the spec lint and the azdiagram lint. | DEC-GM-019, DEC-SPEC-004 | test, inspection |

### Final wave — agent-readable documentation (DEC-GM-036, DEC-GM-037)

| ID | Statement | Source | Verification |
|---|---|---|---|
| AC-GM-DOC-01 | Before the owner makes the repository public, `docs/USER_GUIDE.md` and its index `docs/llms.txt`, which the application serves at `/llms.txt`, shall give numbered steps for each of the following that is in the landed candidate, and shall omit any that is not: getting a sandbox key; reading market data, predictions, and router checks; using the Python SDK; using the strategy template; using the LLM prompt kit; using gridmarket-mcp; monitoring one's own orders, positions, P&L, and losses; the order-size, position, and rate limits the landed candidate enforces; and every error code in the landed OpenAPI document. The guide shall describe no feature that is absent from the landed candidate. | DEC-GM-036 | test, inspection |
| AC-GM-DOC-02 | An agent that follows only `docs/USER_GUIDE.md`, from a clean machine with a sandbox key or the Judge sandbox page, shall obtain a sandbox key, read market data, place an order, and see that order among its own orders. | DEC-GM-036 | demonstration |
| AC-GM-DOC-03 | The repository shall contain the onboarding skill `skills/gridmarket-onboarding/SKILL.md`, which takes a user's agent through the steps of AC-GM-DOC-01 and states how to handle each limit and error code. | DEC-GM-037 | test, inspection |
| AC-GM-UI-05 | The Judge sandbox page shall give a visitor a working sandbox key in at most 2 clicks, shall offer copy buttons for the SDK snippet and for each prompt-kit and MCP snippet that the application serves, and shall show the visitor's first order under "your orders", labelled with the key label, within 5 seconds of its submission. | DEC-GM-037, CONF-GM-PAGES | test, demonstration |
| AC-GM-DOC-04 | The README shall contain a Contributors section stating that work Jordan Hill contributes may be produced with a different agent or tool profile than the owner's frozen Bearing profile and is integrated through the same lanes, tests, and review gates. | CONF-GM-JORDAN-DISCLAIMER | inspection |

### Lifecycle-level requirements

| ID | Statement | Source | Verification |
|---|---|---|---|
| AC-GM-LANE-01 | The implementation shall change, in each slice, only the paths in that slice's write set, and slices of one wave that can run at the same time shall have disjoint write sets. | DEC-GM-006, profile concurrency | inspection (write-set check) |
| AC-GM-LANE-02 | When an assembly step merges a lane, the integrated branch shall pass the backend tests, the dashboard tests and build, and the compose smoke run before the next lane is merged. | DEC-GM-006 | test |
| AC-GM-SEC-01 | When the owner prepares to make the repository public, the repository shall have zero secret-scan findings over its full Git history and an MIT `LICENSE` file at its root. | DEC-GM-011, DEC-GM-015 | test, inspection |
| AC-GM-RULE-02 | The ERCOT Worker views and the dashboard shall label router decisions from baseline rules as baseline rules; the system shall call the hosted Jev service only as AC-GM-ROUTER-04 permits, and the README shall disclose Jev as a pre-existing hosted service linked to the owner. | DEC-GM-020, DEC-GM-028 (amends the earlier bar on all Jev calls) | inspection, test |
| AC-GM-CONTRACT-01 | Before any wave 2 slice starts, the wave 1 exit commit shall contain `CONTRACTS.md` and code stubs that name every shared module and file, Python type, API route, request and response field, the HTTP headers `Authorization`, `Idempotency-Key`, `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `Retry-After`, and `x-gridmarket-key`, every ledger and event entry type, bot profile field, check and router field, gridmarket-mcp tool name and argument, ERCOT Worker snapshot field, and dashboard page route and data hook, and the contract tests shall pass against the stubs. A later change to any of those names shall be made only as an amendment recorded in `CONTRACTS.md`. | DEC-GM-039 | test, inspection |
| AC-GM-LAND-01 | When a phase has passed its assurance, that phase shall be merged to `main` through a pull request whose merge commit passes the backend tests, the dashboard tests and build, and the compose smoke run, and every lane branch, local and remote, and every worktree whose slices were all merged by that phase shall no longer exist. | DEC-GM-040, DEC-GM-038 | inspection, test |
| AC-GM-RULE-01 | The repository shall contain only code written from 2026-09-25 17:00 CDT onward plus open-source dependencies whose release has been public for at least 14 days, and shall contain no code ported from private repositories. | DEC-GM-020 | inspection |

### Risks

| ID | Risk | Control | Recovery |
|---|---|---|---|
| RISK-GM-01 | ERCOT or ERCOT Worker outage, HTTP 429, or token expiry during the demo recording. | AC-GM-DATA-02/03: market request budget and stale display with age; the Worker caches its ID token for 55 minutes and backs off on 429. | Re-record the affected demo step; the dashboard keeps running on last stored values. |
| RISK-GM-02 | The owner's ERCOT Worker is not deployed with the report allowlist and the market client key when phase 1 acceptance runs, so live score inputs cannot flow. | Tests use fixtures shaped like the Worker responses (DEC-GM-014); the security fix (AC-GM-EDGE-01..04) is the first-wave agent slice pair S24–S25 (DEC-GM-022); registering the owner's ERCOT credentials, setting the Worker secrets, and deploying on the owner's Cloudflare account are owner-only actions (DEC-GM-027), surfaced when they block ready work. | The owner deploys; no market change. |
| RISK-GM-03 | The spectre-dev workstation is a single point of failure (DEC-GM-009). | Compose restart policy `unless-stopped`; SQLite on a named volume. | Restart the stack; re-run the demo from the last good integrated commit. |
| RISK-GM-04 | Credential leak when the repository goes public. | `.env` git-ignored, `.env.example` only; secret scan gate AC-GM-SEC-01 before owner publication; the ERCOT, Cloudflare, and Jev credentials are owner-held and never enter the repository (DEC-GM-027, DEC-GM-028). | The owner rotates the market client key, the ERCOT credentials, the Jev key, and the bot secret; history is rewritten only with owner approval. |
| RISK-GM-05 | Parallel lanes conflict or break the demoable branch. | Contract-first wave 1 with `CONTRACTS.md` (AC-GM-CONTRACT-01); disjoint write sets; ordered assembly with post-step V&V (AC-GM-LANE-02); each phase lands on `main` only after its assurance (AC-GM-LAND-01). | Revert the failing merge commit on the integration branch and return the lane to its implementer. |
| RISK-GM-06 | The schedule overruns the Sun 07:00 CDT freeze; the reopened scope (router, 7-type bots with an estimated 11-hour diversity lane, bot economy, six phase 1 pages) enlarges phase 1. | Contract-first parallel build (DEC-GM-039). Phase targets: 1a about Sat 10:00 CDT, 1b about Sat 16:00 CDT (DEC-GM-038). Slip trigger: if S31 is not green on the bots lane by Sat 2026-09-26 14:00 CDT, diversity layers 2, 3, 5a, and 6 move to phase 2, which are AC-GM-BOT-05, AC-GM-BOT-06, and the AC-GM-UI-07 coverage, entropy, and scatter. The dormant rate stays in phase 1b. The stretch assembly starts at the latest at Sat 22:00 CDT and records every lane not green then as dropped. | Drop unfinished stretch lanes; freeze the last green `main` commit. |
| RISK-GM-07 | Abuse of the public tunnel or judge keys. | API keys, sandbox rate limits, maximum order size, tunnel open only from recording through 15:00 CDT Sunday. | Owner revokes keys or stops the tunnel. |
| RISK-GM-08 | A new dependency (Python, npm, Astryx, maturin, PyO3) carries a supply-chain defect. | Dependency admission scan when a dependency is added (wave 1 and the Rust lane). | Pin or remove the dependency; stretch lane dropped if unresolved. |
| RISK-GM-10 | NWS API outage or throttling, or Open-Meteo free-tier terms that do not fit a public repository. | AC-GM-DATA-05 budget and stale marking; Open-Meteo used only by the offline ML lane with CC BY 4.0 attribution; the ML lane checks the terms first and drops Open-Meteo history if they do not allow this use. | Score runs on ERCOT and calendar factors; ML lane falls back to NWS-free features. |
| RISK-GM-11 | The wide parallel wave exceeds route capacity, or a usage-windowed route (AGY, 5-hour window) runs out mid-wave. | Route load split (DEC-GM-040): wave 2 lanes run concurrently. At most 2 concurrent sessions on each usage-windowed primary route; further concurrent sessions go on the ordered fallbacks, chosen before exhaustion; every placement is recorded in a route receipt. When fewer primary slots are free than lanes that are ready, a phase 1a session takes a free primary slot before a phase 1b session, then phase 2, then stretch. A later phase's lane is not held until an earlier phase lands. | On verified exhaustion all new sessions move down the fallback order; drop Rust first, then ML, at the stretch assembly start. |
| RISK-GM-09 | Fixture shape differs from live ERCOT Worker responses. | Parsers read the documented ERCOT report fields and the snapshot shape of `ercot-hackathon/src/snapshot.js` at `bae0a16` (CONTRACT-GM-WORKER); one live response per Worker route is checked during phase 1 assembly once the Worker fix is deployed. | Fix the parser in the data lane; fixtures stay test-only. |
| RISK-GM-12 | The Worker's open report proxy lets any caller exhaust the shared ERCOT limit of 30 requests per minute during the demo. | AC-GM-EDGE-01..04 built in wave 1 (S24–S25) and deployed by the owner before the recording (DEC-GM-027). | The owner disables `/api/report/*` for anonymous callers; the market keeps last stored values. |
| RISK-GM-13 | Later commits on Jordan's branch `jordaaan`, or a merge of PR #3, change the Worker files that the owner's Worker lane also changes. | The owner's Worker lane branches from `4853e51`; it and the views lane that branches from it are the only lanes that edit `ercot-hackathon/` (S24–S27); the phase 1a and 1b PRs carry them to `main`; Jordan is not on the critical path (DEC-GM-027). | The Integration Engineer resolves or returns the conflict to the worker lane when a phase integration branch is created from `main`. |
| RISK-GM-14 | Self-served sandbox keys are farmed to flood the market or the activity feed. | AC-GM-API-06 per-address and total caps, sandbox rate limit (AC-GM-API-03), risk controls on every order, label pattern; tunnel open only from the recording through Sun 15:00 CDT. | The owner revokes keys or sets the sandbox cap to the current count. |
| RISK-GM-15 | A user's LLM agent is steered by text another user entered (prompt injection) through gridmarket-mcp or the prompt kit. | AC-GM-MCP-01: tool responses carry market data only and no free text from other users; private data is scoped to the caller's key; no remote MCP server. | Remove the offending field from the tool response. |
| RISK-GM-16 | The Astryx 0.6.0 and StyleX Vite build is not green in time. | Timebox at the S04 exit: switch the ui lane to shadcn/ui, Tailwind 4, and Recharts in the same palette (AC-GM-UI-06, DEC-GM-033). | The ui lane rebuilds on the fallback stack. |
| RISK-GM-17 | The qlib dependency tree (mlflow, redis, pymongo, cvxpy, gym, jupyter, matplotlib, lightgbm, pyarrow) fails admission or locking, or bloats the runtime image. | Only in the optional `quant` extra, never in the runtime image unless the qlib lane is merged (DEC-GM-034); dependency admission scan. | Drop the qlib lane; the strategy template stays. |
| RISK-GM-19 | A lane needs a shared name that `CONTRACTS.md` does not define or defines differently, so parallel lanes diverge. | AC-GM-CONTRACT-01: contract tests on every lane; any change is a recorded amendment merged into every lane that uses the name. | The lane stops at that name; the Orchestrator dispatches the amendment to the foundation write set and the affected lanes merge it. |
| RISK-GM-18 | The AZHQ visual-review skill is not ready when the ui lane needs it. | Its absence is a typed capability gap; vitest render tests are the fallback and block nothing (CONF-GM-VISUAL-REVIEW). | Use the vitest evidence; record the gap. |

## Exclusions

- Everything in intent §21 (real settlement, billing, money, KYC/AML, QSE,
  blockchain, options, leverage, sophisticated margin).
- All P2 items of intent §18 except item 26 (ML model, a stretch lane,
  DEC-GM-017, DEC-GM-034) and item 25 in the limited form of agents that
  users bring themselves through the prompt kit and the local gridmarket-mcp
  (DEC-GM-035): Google OAuth, personal bot, a first-party AI trading agent,
  WebSockets, historical backtesting dashboard, sophisticated clearing
  — DEC-GM-012 as partially superseded.
- A remote MCP server; bot evolution (diversity layer 5b); retiring bots;
  judges spawning bots; Loki or another log stack (DEC-GM-031, DEC-GM-034,
  DEC-GM-035).
- TypeScript trading example and TypeScript SDK — DEC-GM-013.
- Wind and solar forecast signals and the renewable-deficit factor: not in
  the confirmed phase 1 signal list (DEC-GM-012, DEC-GM-017).
- Record-and-replay or replay-only data in the live data path — DEC-GM-007.
- Agent edits under `ercot-hackathon/` other than the worker and views lane slices S24–S27; ERCOT credentials in the market (DEC-GM-021). Registering the owner's ERCOT credentials, setting Worker secrets, and deploying the owner's Worker on the owner's Cloudflare account are owner-only actions (DEC-GM-027); so are setting the Jev key and turning the Jev flag on for the demo (DEC-GM-028). The owner discloses Jev in the submission video as a pre-existing hosted service linked to the owner (DEC-GM-028). The submission video cuts from the 3D views to the dashboard during the simulated LoneStar Storage outage (DEC-GM-029).
- Making the repository public, applying the PR-only ruleset after the flip, creating the Cloudflare tunnel credentials, registering the ERCOT account, and submitting the GitHub link, the project description, and the 3–5 minute Loom video are owner actions (DEC-GM-009, DEC-GM-011, DEC-GM-018, DEC-GM-020). Team size is at most 5 (DEC-GM-020). The private repository
  `github.com/1wgrumph/gridmarket` exists (DEC-GM-018); pushing branches and
  landing PRs to `main` is agent work, never a direct push to `main`.
- A special-events feed and TxDOT traffic data (DEC-GM-017); porting the
  private alphazede-sports weather fetcher (DEC-GM-020); NWS alert history as
  an ML feature (the NWS API serves active alerts only).

## Phases and schedule (America/Chicago)

| Phase | Waves and slices | Target done (landed on `main`) | Exit |
|---|---|---|---|
| Skeleton | Wave 1: S01 (contract-first skeleton, `CONTRACTS.md`), S24–S25 (owner's Worker security fix) | Sat 2026-09-26 01:30 | AC-GM-CONTRACT-01 and AC-GM-EDGE-01..04 tests pass; every wave 2 lane can branch. Lands with phase 1a. |
| Phase 1a (walking skeleton) | Wave 2: S02–S08 (market, data, SDK, Overview page); assembly S09 | Sat 2026-09-26 10:00 | AC-GM-ACC-03 run; phase assurance; landed (AC-GM-LAND-01). |
| Phase 1b (rich core) | Wave 2: S26–S33, S50–S51, spec lane S19–S21; assembly S49 | Sat 2026-09-26 16:00; slip check Sat 14:00 | AC-GM-ACC-01 run once the owner's Worker is deployed; phase assurance; landed. If S31 is not green by Sat 2026-09-26 14:00 CDT, diversity layers 2, 3, 5a, and 6 (AC-GM-BOT-05, AC-GM-BOT-06, and the AC-GM-UI-07 coverage, entropy, and scatter) move to phase 2. The dormant rate stays in phase 1b. The spec lane lands with phase 1b when it is green and does not block that landing when it is not. |
| Phase 2 | Wave 2: S10–S11, S34–S37; assembly S12 | Sat 2026-09-26 19:00 | AC-GM-ACC-02 run; phase assurance; landed. |
| Stretch | Wave 2: S13–S17, S22–S23, S38–S43; assembly S18 starts at the later of the phase 2 landing and the earlier of all stretch lanes green or Sat 22:00 | Sun 2026-09-27 00:30; at the latest 03:00 | Each stretch AC passes or its lane is recorded dropped; phase assurance; landed. |
| Final | Wave 3: S44–S45 (user guide, `llms.txt`, onboarding skill, README Contributors), S47–S48 (quick website onboarding); assembly S46 | Sun 2026-09-27 05:00 | AC-GM-DOC-01..04 and AC-GM-UI-05 pass; AC-GM-DOC-02 demonstrated; phase assurance; landed before the freeze. |
| Freeze | — | Sun 2026-09-27 07:00 | Last green `main` commit frozen; video recorded; submission 11:00. After the freeze only documentation corrections to the guide land, before the owner's public flip. |

All wave 2 lanes run concurrently, limited only by disjoint write sets and route capacity (DEC-GM-039, DEC-GM-040). Every declared phase (1a, 1b, 2, stretch, and the final wave) runs Integration Engineer execution (its assembly slice), one Reviewer pass, one Test Engineer assurance pass, at most one repair round, and deterministic verification of that repair, with no re-review (DEC-GM-038). The Orchestrator then lands the phase and removes its merged lane branches and worktrees (DEC-GM-040).

## Entry criteria

- DEC-GM-001..040 and DEC-GM-042, SC-2-AMENDMENT, and the CONF-GM-*
  confirmations recorded in `journey.json` (this package incorporates the
  scope-reopen delta and DEC-GM-038..040; DEC-GM-041 is revoked, so the
  frozen snapshot reasoning levels stand, Muse at max);
  profile `primary` frozen with
  digest `14d07a1ceffc31954e7be348d0ec32b10140108a2351448d26e500759a8ed721`;
  lane profiles `tech-writing` (spec lane) and `frontend` (ui lane) frozen with
  digest `d83b583369a7bf7ce522b32572f78534ffbce41a135b2b84c0087368ec7129ae`
  (DEC-GM-024).
- Integrated owner approval of this five-artifact package (one review gate).
- Checkout lease active on `/home/spectre/alphazede/Hackathons/Base`; lane
  worktrees are created under `/home/spectre/alphazede/worktrees/` per the
  workspace worktree rule.
- Tools present on spectre-dev: Python 3.12, uv, Node/npm, Docker, cargo,
  gitleaks, cloudflared (observed 2026-09-25 20:14 CDT). `maturin` is absent
  and is admitted by the Rust lane only.

## Exit criteria

- Skeleton, landed with phase 1a: AC-GM-CONTRACT-01 and AC-GM-EDGE-01 through AC-GM-EDGE-04 pass on that `main`.
- Phase 1a: AC-GM-ACC-03 demonstrated; phase assurance passed; landed (AC-GM-LAND-01).
- Phase 1b: AC-GM-ACC-01 demonstrated for the requirements that remain in phase 1b. Rows the slip trigger moved are not part of this exit. Phase assurance passed; landed (AC-GM-LAND-01).
- Phase 2: AC-GM-ACC-02 demonstrated, including any diversity rows the slip trigger moved; landed (AC-GM-LAND-01).
- Stretch: each stretch requirement either passes on the landed `main` or is recorded as a dropped lane with its reason.
- Final: AC-GM-DOC-01 through AC-GM-DOC-04 and AC-GM-UI-05 pass, and AC-GM-DOC-02 is demonstrated, before the freeze and before the owner makes the repository public.
- Freeze: the submission recording reaches the landed candidate through the tunnel URL while the tunnel is open.
- Every phase: one Reviewer pass, one Test Engineer assurance pass, and Integration Engineer execution (DEC-GM-038); at most one repair; deterministic verification of that repair; no re-review. AC-GM-LAND-01 holds after the landing. AC-GM-SEC-01 passes before any owner publication. DoD Manifest closeout is appended.

## Rollback or repair

- A lane slice that fails its commands returns to the same lane's implementer inside the one-repair bound. The lane branch never merges red.
- A failed assembly step reverts that merge commit on the phase integration branch. Earlier merged lanes stay. The branch returns to its last green commit.
- Phase review is one review, at most one repair round that fixes every finding, then deterministic verification, with no re-review. If verification of the repair fails, revert the failing lane from the phase integration branch. If the phase acceptance then passes, land the remaining lanes. If it does not pass, the phase does not land, and the owner decides (owner-stops class C).
- `main` changes only by merged phase PRs. A landed phase that breaks `main` is reverted by a PR, never by force-push.
- A stretch lane that is not green when S18 starts, at the latest Sat 22:00 CDT, is dropped and recorded, never forced in.
- Diversity layers 2, 3, 5a, and 6 move to phase 2 when the Sat 14:00 CDT slip trigger fires (RISK-GM-06). That move is not a failed repair.
- Planning defects found after approval return to Planning and Design as a named delta. No silent re-scope.

## Accountable controller

The Bearing Lite Orchestrator (Claude Code, Claude Opus 5.5) holds the
checkout lease (`journey.json` `checkout_lease`, generation 1) and dispatches
waves through the Coordinator route under the route load split of DEC-GM-040
(at most 2 concurrent sessions per usage-windowed primary route, further
sessions on ordered fallbacks, each placement recorded), and lands each
phase (DEC-GM-040); the owner (William) holds every
owner-only action listed in Exclusions and the integrated plan approval.
The owner owns the Worker and 3D-view lanes and holds the ERCOT, Cloudflare,
and Jev credentials (DEC-GM-027); the worker and views lane slices S24–S27 are agent
work. Jordan Hill is no longer on the critical path; work he contributes may
be produced with a different agent or tool profile than the owner's frozen
Bearing profile and enters through the same lanes, tests, and review gates
(CONF-GM-JORDAN-DISCLAIMER, AC-GM-DOC-04).
