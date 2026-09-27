# Changelog

## [1.0.0] - 2026-09-27

### Improvements (1)
- GridMarket now provides a simulated flexibility exchange on real ERCOT conditions: replay of real Texas grid days with simulated home batteries, the live market with bots and a judge sandbox, the God's Eye grid map, the Python SDK and MCP server, and real ERCOT responses verified through the parsers.

### Fixes (1)
- Fixed the adversary burst test so it now verifies the rate limit on the limiter's own clock, so the test suite gives the same result on fast and busy machines.

## [0.5.0] - 2026-09-27

### Improvements (6)
- The dashboard Overview now features a live grid chart showing hub prices, system lambda and actual demand with a day-ahead line and CSV export.
- The Replay page now features more real replay days with a day picker.
- The Predictions page now features a forecast track record with Brier calibration, an event table, and history via `GET /v1/router/history`.
- The 3D God's Eye view now features a past range with Actual/Forecast labels and a Now button.
- The dashboard now provides CSV exports for market trades, sandbox orders and bot history.
- `GET /v1/signals/history` now serves snapshot series for hub prices, system lambda and actual demand.

### Fixes (3)
- Fixed dashboard page files spending the API rate limit, so fast reloads no longer blank the app.
- Fixed the first-run checklist's first-order step so it now completes when the order is placed.
- Fixed the judge guide so it now covers Replay.

## [0.4.0] - 2026-09-27

### Improvements (8)
- The dashboard and `POST /v1/replay` now replay a real Texas grid day (26 August 2026) with 1,000 simulated home batteries, three strategies, a scoreboard and a reason for every decision.
- The "Your turn" controls now let users adjust backup reserve, fleet size and provider availability to rerun the replay scenario.
- The dashboard Overview now features a headline, a first-run checklist guiding users across the application, and simplified navigation.
- The 3D grid views now include a "help the grid" layer showing demand now, grid batteries now and help windows, alongside an activity ticker.
- The 3D God's Eye view now features responsive mobile layouts, plain-language grid and price labels, keyboard accessibility, and stale-data indicators during market outages.
- Admin routes are now limited to the host and configured admin networks, rejecting tunnel and non-host traffic with 403 `FORBIDDEN`.
- The replay API now enforces per-client rate limits and validates incoming payload fields, returning 422 `VALIDATION_ERROR` for malformed requests.
- The README and judge guide now provide an end-to-end walkthrough for judges and developers ("Your first 3 minutes"), clarifying simulated versus real elements and the demo path.

### Fixes (5)
- Fixed ERCOT report and snapshot parsers to match real Worker responses, parsing field objects, UTC timestamps and hour-ending formats with batched signal storage.
- Fixed the documented Docker deployment so admin routes are reachable from the host and simulated bots trade as described.
- Fixed settlement accounting to conserve cash, ledger delivery defaults with exact refunds, keep flat futures P&L in net worth, and isolate scheduled background tasks so one failure cannot stop the others.
- Fixed bot summaries displaying blank or $NaN values, repaired market browsing and sandbox feedback, and corrected Python SDK defaults, strategy rejection handling and API abuse limits.
- Fixed predictions to show missing inputs as unavailable instead of computing fabricated scores, and ensured forecast horizons reach predictions.

## [0.3.0] - 2026-09-26

### Improvements (7)
- A second simulated battery provider, LoneStar Storage, now participates across the provider seam, with its own customer accounts, battery assets and capacity reservations.
- The dashboard now has a Providers page showing simulated provider health with customer counts, online assets, heartbeat age and router checks, alongside owner controls to start and end simulated outages with an admin key.
- Capacity reservation SQL now runs inside the provider layer, keeping market order execution independent of provider storage schemas.
- Orders are now capped at $5.00 (500 cents) per Flex Credit via `MAX_PRICE_CENTS`, rejecting orders above the cap with 422 `VALIDATION_ERROR`.
- A rules-based strategy template and an LLM prompt kit now provide reference implementations, SDK snippets and system prompts for building automated trading bots.
- The GridMarket architecture specification and diagram figures are now published, supported by validation and rendering tools for architecture diagrams and requirements traceability.
- The Bot profile page now reserves loading panel height across breakpoints so panels arrive without shifting the page layout.

### Fixes (1)
- Fixed keyed rate-limit tests flaking under token refills; the test suite now freezes the monotonic clock during burst assertions without stopping the ASGI event loop.

## [0.2.0] - 2026-09-26

### Improvements (9)
- A population of 60 simulated bots across seven trader types now trades through the public API, each with its own strategy blend, household battery, payroll and cash, and goes dormant when it runs out of money.
- `GET /v1/bots` and `GET /v1/bots/{id}` now show each bot's type, blend, cash, net worth, P&L, trades, losses and balance history, and `GET /v1/bots/diversity` measures how varied the population is.
- Operators can now spawn 1 to 10 more bots with `POST /v1/admin/bots`, up to 200 in total; the route answers only the host loopback with the admin key and returns 403 `FORBIDDEN` to any other peer.
- `GET /v1/router` now publishes the decision router's market checks every 60 seconds, each with a probability, a `log`, `review` or `alert` band and its resolved outcome, plus per-check Brier calibration.
- The 3D grid views now show the market's activity strip and alert checks, and keep the ERCOT content working when the market is unset or down.
- The dashboard now uses the design v2 look: a self-hosted Inter typeface, a new palette, a numbered navigation rail with data freshness and an API-key prompt, a single outage banner, and a rebuilt Overview.
- The dashboard now has Market, Predictions, Bots, Bot profile, Judge sandbox and Spec pages; polled panels keep their last-known data with a stale tag instead of going blank.
- The order limits are now the named constants `MAX_ORDER_QUANTITY` (50) and `MAX_POSITION` (200) in `gridmarket_server.market`.
- The design system and a frontend-design skill are now published, with light and dark screenshots of each page at desktop and phone widths.

### Fixes (2)
- Fixed `GET /v1/market/status` always returning an empty `anomalies` list, even after rejected orders were recorded; it now returns the newest 50 anomalies.
- Fixed bursts of concurrent orders being slow, about 1.2 s for 50 orders, caused by a full disk sync on every commit; the database now syncs at the `NORMAL` level and a 50-order burst finishes in under a second with no lost orders.

## [0.1.0] - 2026-09-26

### Improvements (10)
- Traders can now buy and sell simulated Flex Credits for the four ERCOT load zones through one REST API, with `POST /v1/orders`, `GET /v1/orders`, `GET /v1/orders/{id}` and `DELETE /v1/orders/{id}`.
- Orders are now risk-checked before they rest: at most 50 credits per order, 200 per position, and enough cash or battery capacity, with each rejection returned as a stable `error.code` such as `ORDER_TOO_LARGE`, `POSITION_LIMIT` or `INSUFFICIENT_CAPACITY`.
- `POST /v1/orders` now requires an `Idempotency-Key`, so a retried request never places a second order.
- Anyone can now get a sandbox key with $1,000.00 of simulated cash from `POST /v1/sandbox/keys`, limited to three keys per hour.
- Callers can now read their own state from `GET /v1/account`, `GET /v1/portfolio`, `GET /v1/positions`, `GET /v1/trades`, `GET /v1/losses`, `GET /v1/assets` and `GET /v1/assets/{id}`.
- Anyone can now read the product list, product detail, price history, activity feed, open or halted status and provider summary from the public `GET /v1/market`, `GET /v1/market/{symbol}`, `GET /v1/market/history`, `GET /v1/market/activity`, `GET /v1/market/status` and `GET /v1/providers` routes.
- `GET /v1/predictions` and `GET /v1/predictions/{zone}` now score each load zone from live ERCOT and NWS signals, with the drivers behind each score, and `GET /v1/signals` serves those signals; a missing temperature reads as unavailable, never as 0 °F.
- Public and caller `/v1` responses now carry `X-RateLimit-Limit` and `X-RateLimit-Remaining`, with a lower limit for sandbox keys, and a caller over the limit gets 429 `RATE_LIMITED` with `Retry-After`.
- The standard-library Python SDK `Client` and an example trader under 30 lines now let a judge place a first order with nothing but Python 3.10.
- The dashboard Overview now shows ERCOT signals, zone scores, market status and the live activity feed, refreshed every two seconds, in dark and light themes, and links to the ERCOT data service's 3D grid views, including the God's Eye globe; the data service caches ERCOT reports behind a report allowlist, a market key, per-client rate limits and an ERCOT call budget.
