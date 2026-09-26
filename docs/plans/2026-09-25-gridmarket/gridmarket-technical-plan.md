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
benchmark, and an ML model compared against the deterministic score, DEC-GM-017) run in parallel lanes and are merged only when green. A Spec lane builds the spec template, the azdiagram generator, the spec skills, and GridMarket's own specification for the judges (DEC-GM-019). All submission code is written during the hackathon (DEC-GM-020). The architecture is hybrid (DEC-GM-021): Jordan Hill's Cloudflare Worker `ercot-hackathon` (PR #3, branch `jordaaan`, directory `ercot-hackathon/`) is the ERCOT data edge and the 3D visualization lane, owned by Jordan; the Python market reads ERCOT data only through that Worker and exposes market activity to his views. The ERCOT Worker rate-limit fix is a first-wave agent slice pair (DEC-GM-022); deploying it is Jordan's action. Feature
freeze is Sun 2026-09-27 07:00 CDT; submission is 11:00 CDT.

## Requirements register

No requirements register exists. The repository is greenfield
(`workspace.md` Observed Systems; `repository-map.md` Anchors) and the
Lifecycle is not a specification Lifecycle. Every requirement below is
Lifecycle-local (`AC-*` / `RISK-*`). Sources are the confirmed decisions
DEC-GM-001..022 in `journey.json` and the owner intent `gridmarket-intent.html`
(§ numbers). Success criteria are cited as SC-n (intent §22).

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
- **Sandbox key**: an API key issued by the owner to a judge or developer,
  bound to a sandbox account with $1,000.00 simulated cash and the sandbox
  rate limit.
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
- **ERCOT Worker**: the Cloudflare Worker in `ercot-hackathon/` (DEC-GM-021),
  reached at the URL in the untracked environment variable
  `GRIDMARKET_WORKER_URL`. It holds the ERCOT credentials as Worker secrets,
  owned by Jordan.
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
| AC-GM-ACCT-01 | When the database is empty at startup, the system shall create at least 50 simulated users, each with $1,000.00 simulated cash, zero Flex Credits, one API key, and at least one simulated battery with provider, zone, capacity in kWh, state of charge in kWh, minimum reserve in kWh, and charge and discharge limits in kW. | intent §4, DEC-GM-012, SC-2 | test |
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
| AC-GM-API-05 | When a GET request to `/v1/market`, `/v1/market/{symbol}`, `/v1/market/history`, `/v1/market/activity`, `/v1/predictions`, or `/v1/predictions/{zone}` carries the `Origin` named in the untracked environment variable `GRIDMARKET_CORS_ORIGIN`, the system shall return `Access-Control-Allow-Origin` set to that origin, and shall return no `Access-Control-Allow-Origin` header for any other origin or for a request to an account or trading endpoint. | DEC-GM-021 | test |
| AC-GM-BOT-01 | While seeded traffic runs, it shall submit at least 10 orders per minute from at least 3 seeded accounts only through the public HTTP API with those accounts' own API keys. | intent §12, §18 P0-14, SC-9 | test, demonstration |
| AC-GM-UI-01 | The dashboard shall show on one page, without login, the ERCOT signals with publish time and staleness, per-zone predictions with their factor contributions, product order books and recent trades, participant counts per provider, market status, and the order activity feed, and shall refresh every 3 seconds or more often. | intent §20, SC-1, SC-11 | test, demonstration |
| AC-GM-UI-02 | The dashboard shall display that future products are simulated forward flexibility contracts and not regulated commodity futures, and that a Flex Credit is not a renewable energy certificate, a cryptocurrency, or a claim on specific electrons. | intent §5, §7 | test, inspection |
| AC-GM-EDGE-01 | The ERCOT Worker shall return HTTP 404 without calling ERCOT for a `/api/report/*` path outside the report allowlist, and shall return HTTP 401 without calling ERCOT for a `/api/report/*` or `/api/products` request, or a `/api/snapshot` request with the `fresh` parameter, that lacks a valid market client key. | DEC-GM-021 required fix, DEC-GM-022 | test, demonstration |
| AC-GM-EDGE-02 | The ERCOT Worker shall return HTTP 429 without calling ERCOT when one client address sends more than 30 requests to `/api/*` in any 60-second window. | DEC-GM-021 required fix, DEC-GM-022 | test |
| AC-GM-EDGE-03 | The ERCOT Worker shall send no more than 25 requests to ERCOT, token requests and retries included, in any 60-second window for any number of clients and requests, and shall return HTTP 429 without calling ERCOT for a request whose ERCOT call would exceed that budget and that no cached response can answer. | DEC-GM-022 | test |
| AC-GM-EDGE-04 | If ERCOT returns HTTP 429 to a call made while building `/api/snapshot`, then the ERCOT Worker shall retry that call at most 4 times, and the wait before retry attempt n shall be the lesser of 4 seconds and the `Retry-After` value in seconds when that header is a positive number, and otherwise the lesser of 4 seconds and 0.9 seconds times n. | DEC-GM-022 | test |
| AC-GM-OPS-01 | The system shall run as Docker Compose services under a non-root user, shall bind its HTTP port only to 127.0.0.1 on the host, and shall be reachable from the internet only through an outbound Cloudflare named tunnel. | DEC-GM-009, DEC-GM-010 | inspection, demonstration |
| AC-GM-ACC-01 | The phase 1 acceptance run shall show SC-1 to SC-5 and SC-7 to SC-11 in one uninterrupted session through the tunnel URL. | DEC-GM-016 | demonstration |

### Phase 2 — second provider

| ID | Statement | Source | Verification |
|---|---|---|---|
| AC-GM-PROV-01 | The market shall read and reserve battery capacity only through the provider adapter interface (list customers, list assets, available capacity, reserve capacity, release capacity, verify delivery, asset status). | intent §10, DEC-GM-006 | test |
| AC-GM-PROV-02 | When the LoneStar Storage adapter is enabled, at least 20 LoneStar Storage customers shall trade on the same order books as Base simulator customers, and the dashboard shall show participant counts for both providers. | DEC-GM-006, SC-6 | test, demonstration |
| AC-GM-ACC-02 | The phase 2 acceptance run shall show SC-1 through SC-11 in one uninterrupted session through the tunnel URL. | DEC-GM-016 | demonstration |

### Stretch — merged only when green

| ID | Statement | Source | Verification |
|---|---|---|---|
| AC-GM-ADV-01 | When the adversarial scenario runs, the system shall reject an over-capacity spot sell and change no balances, shall create no second order when an identical request reuses an Idempotency-Key, and shall return HTTP 429 and change no state once one account exceeds its AC-GM-API-03 rate limit, and shall show each of those three outcomes as an anomaly on the dashboard. | DEC-GM-012, intent §15, §20 step 8 | test, demonstration |
| AC-GM-ADV-02 | When a request authenticated as the admin API key named in the untracked environment file invokes the kill switch for the market or for one account, the system shall reject every later order in that scope with a typed reason and change no balances until a request authenticated as that same admin API key lifts the halt, and shall append the halt and the lift to the append-only trade ledger. | DEC-GM-012, intent §15 | test |
| AC-GM-BT-01 | The backtest command shall compute, over at least 7 days of ERCOT history fetched through the ERCOT Worker's allowlisted report routes, the Spearman rank correlation between zone-hour opportunity scores and realized real-time settlement point prices, and shall report the correlation, the sample size, and the date range. | DEC-GM-012, intent §9.4 | test, demonstration |
| AC-GM-PERF-01 | Where the Rust matching core is enabled, it shall produce the same fills as the Python engine on the shared matching test suite, and a benchmark shall report orders per second for both engines on one identical workload; the Rust core shall be enabled only if its throughput is higher. | DEC-GM-010, DEC-GM-012 | test, analysis |
| AC-GM-ML-01 | The ML command shall train a model on at least 28 days of ERCOT archive data fetched through the ERCOT Worker's allowlisted report routes with the score inputs, Open-Meteo weather history, Census county population estimates, and LEHD LODES8 Texas WAC and RAC job counts as a daytime population weight per zone, and the backtest shall report the Spearman rank correlation of both the model and the deterministic score against realized real-time settlement point prices over the same held-out range of at least 7 days after the training range, together with the model's feature importances. | DEC-GM-017, DEC-GM-012 (partial supersession), intent §9.4 | test, analysis |

### Spec lane — shown to the judges, must not block phase 1

| ID | Statement | Source | Verification |
|---|---|---|---|
| AC-GM-SPEC-01 | When azdiagram renders a per-class YAML figure input, it shall write an SVG file and a draw.io file from one Graphviz layout when the class is F1, F2, F3, F4, F6, or F7, and from the grid renderer when the class is F5 or F8, and its lint shall fail when two node boxes overlap or the figure exceeds the size limit named in that input. | DEC-GM-019, DEC-SPEC-006, DEC-SPEC-007 | test |
| AC-GM-SPEC-02 | The spec lint shall fail a specification section that lacks a BLUF, lacks any of the six Frame fields (Who, What, Why, How, When, Where), binds more than 5 requirements, cites a table or figure class outside T1–T8 and F1–F8, has no table when it lists 3 or more items that share 2 or more attributes, or has no figure when it names 3 or more entities with a relationship, a time order, or states. | DEC-GM-019, DEC-SPEC-005, DEC-SPEC-006 | test |
| AC-GM-SPEC-03 | The repository shall contain the spec template (generated front matter, the DEC-SPEC-004 outline, and the DEC-SPEC-010 additions of the COE-ASA-001 floor elements as subsections plus Stakeholders and their concerns, Model correspondence, and Rationale), the spec-author, spec-diagram, and spec-lint skills, and GridMarket's own specification written in that template with its figures, and the specification shall pass the spec lint and the azdiagram lint. | DEC-GM-019, DEC-SPEC-004 | test, inspection |

### Lifecycle-level requirements

| ID | Statement | Source | Verification |
|---|---|---|---|
| AC-GM-LANE-01 | The implementation shall change, in each slice, only the paths in that slice's write set, and slices of one wave that can run at the same time shall have disjoint write sets. | DEC-GM-006, profile concurrency | inspection (write-set check) |
| AC-GM-LANE-02 | When an assembly step merges a lane, the integrated branch shall pass the backend tests, the dashboard tests and build, and the compose smoke run before the next lane is merged. | DEC-GM-006 | test |
| AC-GM-SEC-01 | When the owner prepares to make the repository public, the repository shall have zero secret-scan findings over its full Git history and an MIT `LICENSE` file at its root. | DEC-GM-011, DEC-GM-015 | test, inspection |
| AC-GM-RULE-02 | The ERCOT Worker views shall label their decision checks as baseline rules and shall call no Jev decision engine unless journey.json records an owner decision that the Jev code was written on or after 2026-09-25 17:00 CDT or has been open source for at least 14 days. | DEC-GM-020, DEC-GM-021 | inspection |
| AC-GM-RULE-01 | The repository shall contain only code written from 2026-09-25 17:00 CDT onward plus open-source dependencies whose release has been public for at least 14 days, and shall contain no code ported from private repositories. | DEC-GM-020 | inspection |

### Risks

| ID | Risk | Control | Recovery |
|---|---|---|---|
| RISK-GM-01 | ERCOT or ERCOT Worker outage, HTTP 429, or token expiry during the demo recording. | AC-GM-DATA-02/03: market request budget and stale display with age; the Worker caches its ID token for 55 minutes and backs off on 429. | Re-record the affected demo step; the dashboard keeps running on last stored values. |
| RISK-GM-02 | The ERCOT Worker is not deployed with the report allowlist and the market client key when phase 1 acceptance runs, so live score inputs cannot flow. | Tests use fixtures shaped like the Worker responses (DEC-GM-014); the security fix (AC-GM-EDGE-01..04) is the first-wave agent slice pair S24–S25 (DEC-GM-022); deployment is Jordan's action on his Cloudflare account, surfaced when it blocks ready work. | Jordan deploys; no market change. |
| RISK-GM-03 | The spectre-dev workstation is a single point of failure (DEC-GM-009). | Compose restart policy `unless-stopped`; SQLite on a named volume. | Restart the stack; re-run the demo from the last good integrated commit. |
| RISK-GM-04 | Credential leak when the repository goes public. | `.env` git-ignored, `.env.example` only; secret scan gate AC-GM-SEC-01 before owner publication. | Owner rotates the market client key, Jordan rotates the ERCOT credentials, and history is rewritten only with owner approval. |
| RISK-GM-05 | Parallel lanes conflict or break the demoable branch. | Contract-first wave 1; disjoint write sets; ordered assembly with post-step V&V (AC-GM-LANE-02). | Revert the failing merge commit on the integration branch and return the lane to its implementer. |
| RISK-GM-06 | The schedule overruns the Sun 07:00 CDT freeze. | Phase checkpoints; stretch lanes merge only when green; stretch cut-off Sun 04:30 CDT. | Drop unfinished stretch lanes; freeze the last integrated green commit. |
| RISK-GM-07 | Abuse of the public tunnel or judge keys. | API keys, sandbox rate limits, maximum order size, tunnel open only from recording through 15:00 CDT Sunday. | Owner revokes keys or stops the tunnel. |
| RISK-GM-08 | A new dependency (Python, npm, Astryx, maturin, PyO3) carries a supply-chain defect. | Dependency admission scan when a dependency is added (wave 1 and the Rust lane). | Pin or remove the dependency; stretch lane dropped if unresolved. |
| RISK-GM-10 | NWS API outage or throttling, or Open-Meteo free-tier terms that do not fit a public repository. | AC-GM-DATA-05 budget and stale marking; Open-Meteo used only by the offline ML lane with CC BY 4.0 attribution; the ML lane checks the terms first and drops Open-Meteo history if they do not allow this use. | Score runs on ERCOT and calendar factors; ML lane falls back to NWS-free features. |
| RISK-GM-11 | Spec, ML, and the Rust lane exceed the 3-lane concurrency limit if they run beside the lanes already in that window. | Slot edges serialize them: Spec runs after the data lane in wave 2; ML runs after LoneStar in wave 3; Rust runs after the adversary lane. | Drop Rust first, then ML, at the Sun 04:30 CDT cut-off. |
| RISK-GM-09 | Fixture shape differs from live ERCOT Worker responses. | Parsers read the documented ERCOT report fields and the snapshot shape of `ercot-hackathon/src/snapshot.js` at `bae0a16` (CONTRACT-GM-WORKER); one live response per Worker route is checked during phase 1 assembly once the Worker fix is deployed. | Fix the parser in the data lane; fixtures stay test-only. |
| RISK-GM-12 | The Worker's open report proxy lets any caller exhaust the shared ERCOT limit of 30 requests per minute during the demo. | AC-GM-EDGE-01..04 built in wave 1 (S24–S25) and deployed by Jordan before the recording. | Jordan disables `/api/report/*` for anonymous callers; the market keeps last stored values. |
| RISK-GM-13 | The Worker lane is run by a human teammate on his own schedule; a snapshot shape change or a missing allowlist entry breaks the market data lane. | CONTRACT-GM-WORKER fixes the routes, the allowlist, and the snapshot shape; agent lanes edit `ercot-hackathon/` only in S24–S25 (DEC-GM-022). | Jordan restores the contract; the market marks the affected signals stale. |

## Exclusions

- Everything in intent §21 (real settlement, billing, money, KYC/AML, QSE,
  blockchain, options, leverage, sophisticated margin).
- All P2 items of intent §18 except item 26 (ML model, now a stretch lane,
  DEC-GM-017): Google OAuth, personal bot, AI trading agent, WebSockets, historical backtesting dashboard, sophisticated clearing)
  — DEC-GM-012.
- TypeScript trading example and TypeScript SDK — DEC-GM-013.
- Wind and solar forecast signals and the renewable-deficit factor: not in
  the confirmed phase 1 signal list (DEC-GM-012, DEC-GM-017).
- Record-and-replay or replay-only data in the live data path — DEC-GM-007.
- Agent edits under `ercot-hackathon/` other than slices S24–S25
  (DEC-GM-022); deploying the ERCOT Worker and setting its
  secrets (Jordan's Cloudflare account); ERCOT credentials in the market
  (DEC-GM-021). Jordan's 3D views consuming market activity are his lane.
- Making the repository public, applying the PR-only ruleset after the flip, creating the Cloudflare tunnel credentials, registering the ERCOT account, and submitting the GitHub link, the project description, and the 3–5 minute Loom video are owner actions (DEC-GM-009, DEC-GM-011, DEC-GM-018, DEC-GM-020). Team size is at most 5 (DEC-GM-020). The private repository
  `github.com/1wgrumph/gridmarket` exists (DEC-GM-018); pushing branches and
  landing PRs to `main` is agent work, never a direct push to `main`.
- A special-events feed and TxDOT traffic data (DEC-GM-017); porting the
  private alphazede-sports weather fetcher (DEC-GM-020); NWS alert history as
  an ML feature (the NWS API serves active alerts only).

## Phases and schedule (America/Chicago)

| Phase | Waves | Target done | Exit |
|---|---|---|---|
| Foundation | Wave 1 | Fri 2026-09-25 23:30 | Contracts, scaffold, tooling green. |
| Phase 1 core | Wave 2 | Sat 2026-09-26 14:00 | Integrated branch demoable; AC-GM-ACC-01 run once the ERCOT Worker fix is deployed. |
| Worker security fix | Wave 1 (S24–S25, agent lane `worker`, DEC-GM-022) | Sat 2026-09-26 01:00 | AC-GM-EDGE-01..04 pass; PR offered into `jordaaan`; Jordan deploys before phase 1 acceptance. |
| Spec lane | Wave 2 (after data lane) | Sat 2026-09-26 18:00 | Spec tooling green; GridMarket spec passes both lints. |
| Phase 2 + stretch | Wave 3 | Sat 2026-09-26 20:00 (phase 2), Sun 2026-09-27 04:30 (stretch cut-off) | Phase 2 merged first; stretch lanes merged only when green. |
| Freeze | — | Sun 2026-09-27 07:00 | Last green integrated commit frozen; video recorded; submission 11:00. |

## Entry criteria

- DEC-GM-001..022 confirmed or recorded in `journey.json` (the Orchestrator
  clears `pending_planning_delta`, which this package incorporates); profile `primary` frozen with
  digest `14d07a1ceffc31954e7be348d0ec32b10140108a2351448d26e500759a8ed721`.
- Integrated owner approval of this five-artifact package (one review gate).
- Checkout lease active on `/home/spectre/alphazede/Hackathons/Base`; lane
  worktrees are created under `/home/spectre/alphazede/worktrees/` per the
  workspace worktree rule.
- Tools present on spectre-dev: Python 3.12, uv, Node/npm, Docker, cargo,
  gitleaks, cloudflared (observed 2026-09-25 20:14 CDT). `maturin` is absent
  and is admitted by the Rust lane only.

## Exit criteria

- Phase 1: AC-GM-ACC-01 demonstrated; all phase 1 SEIT rows pass on the
  integrated candidate.
- Phase 2: AC-GM-ACC-02 demonstrated.
- Stretch: each stretch AC either passes on the integrated candidate or is
  recorded as a dropped lane with its reason.
- Lifecycle: Reviewer (phase cadence), Test Engineer assurance (Lifecycle
  cadence), and Integration Engineer execution assessment (Lifecycle cadence)
  complete; AC-GM-SEC-01 passes before any owner publication; DoD Manifest
  closeout appended.

## Rollback or repair

- A lane slice that fails its commands returns to the same lane's implementer
  inside the one-repair bound; the lane branch never merges red.
- A failed assembly step reverts that merge commit on
  `gridmarket/integration`; earlier merged lanes stay; the integrated branch
  returns to its last green commit.
- A stretch lane that is not green by Sun 04:30 CDT is dropped and recorded,
  never forced in.
- Planning defects found after approval return to Planning and Design as a
  named delta; no silent re-scope.

## Accountable controller

The Bearing Lite Orchestrator (Claude Code, Claude Opus 5.5) holds the
checkout lease (`journey.json` `checkout_lease`, generation 1) and dispatches
waves through the Coordinator route; the owner (William) holds every
owner-only action listed in Exclusions and the integrated plan approval.
Jordan Hill (human teammate) owns the ERCOT Worker lane and its deployment;
the Worker security fix slices S24–S25 are agent work (DEC-GM-022).
