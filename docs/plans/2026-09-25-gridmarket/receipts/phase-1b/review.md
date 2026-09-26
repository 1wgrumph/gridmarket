---
type: review-receipt
title: Phase 1b independent review
okf_status: active
tags: [gridmarket, phase-1b, review]
---

# Phase 1b review

**Verdict: REPAIR_REQUIRED**

Candidate `8f6818b73c00a19e0d076104b6169aca2d753983` against `origin/main` `44b7f63cac9a35730059a791c7f1aab461f5d245` (merge-base, verified ancestor). Diff `origin/main...candidate`: 45 files, +6421/−306. Reviewer identity is independent of the lane authors. Product, test, and manifest files were not edited.

Reverify: not applicable — no compiled-binary behavior claim. The added `inter-latin-var.woff2` is a font asset; nothing in the gates asserts a disassembly, patch, or native-code property.
BRAN: unavailable (no `.bran/policy.yaml`).
Visual review: not run. The packet did not include a browser run command. UI findings below are from executing the page expressions and `renderFeed` against the live response shapes.

## DIR-P1b-12

Confirmed, same scale. For day-ahead `80` $/MWh and score 50:

- `expected_value = 80/1000 = 0.08` $/credit (`scoring.py:125`)
- account mark `expected_value * 100 = 8` cents (`api.py:299`)
- settlement reference `round(sum(four × 80) / 40) = 8` cents (`market.py:416`), which is $/MWh ÷ 10 = cents per credit
- `market_price = price_cents / 100 = 0.08` when the last trade is that mark (`scoring.py:192`)

`expected_value`, `market_price`, the account mark, and the settlement reference are one number. Not a finding.

## Findings

**F1 — P1.** `backend/gridmarket_server/bots_api.py:196`
`POST /v1/admin/bots` rejects `CF-Connecting-IP` and a wrong key, and does not check the peer. AC-GM-API-07 requires HTTP 403 and no state change for any `/v1/admin/*` request that does not arrive on loopback.
Reproducer: `TestClient(app, client=("10.1.2.3", 50000))` reports `request.client.host == "10.1.2.3"`. The same client, correct admin key, no `CF-Connecting-IP`, `POST /v1/admin/bots {"count": 1}` returned **200** `{"spawned": 1, ...}`.
Repair: use the same peer check as `api.admin_guard` (`127.0.0.1`, `::1`, and the test client).

**F2 — P1.** `backend/gridmarket_server/decision_router.py:24`
`DA_REPORT` / `RT_REPORT` are `np4-190-cd` / `np6-905-cd`. The poller stores `NP4-190-CD` / `NP6-905-CD` (`ercot.py:21`). SQLite `=` does not fold that case, so `market_checks` skips every hour and `_market_outcome` stays `None`. AC-GM-ROUTER-01 never answers on the live store. `test_router.py` uses an in-memory store loaded with the same lowercase ids.
Reproducer: one `NP4-190-CD` row and four `NP6-905-CD` rows for `LZ_HOUSTON` 2026-09-26 14:00Z, `scoring.predict` returning that hour. `market_checks()` length **0**. `series("NP4-190-CD", ...)` length **1**. `series("np4-190-cd", ...)` length **0**. `_market_outcome` **None**.
Repair: query `NP4-190-CD` and `NP6-905-CD`.

**F3 — P1.** `dashboard/src/pages/Bots.tsx:107`
`usd` calls `toLocaleString` on `cash`. `GET /v1/bots` (`bots_api.py:132`) returns `id`, `bot_index`, `bot_type`, `provider_id`, `dormant` only. The first live row throws and there is no error boundary. `phase1b.json` includes `cash` and `pnl`, so the page test does not hit this.
Reproducer: `usd(undefined)` → `TypeError: Cannot read properties of undefined (reading 'toLocaleString')`.
Repair: render the list fields the route returns, or return the economy columns the table reads, and guard the formatter.

**F4 — P1.** `dashboard/src/pages/Bots.tsx:27`
The panel reads `trait_space_coverage`, `behavior_entropy`, and `risk_patience`. `GET /v1/bots/diversity` (`bots_api.py:162`) returns `coverage`, `entropy`, and `points`. `phase1b.json` uses the page names.
Reproducer: `{coverage, entropy, points}.behavior_entropy.toFixed(2)` → `TypeError: Cannot read properties of undefined (reading 'toFixed')`.
Repair: read `coverage`, `entropy`, and `points`.

**F5 — P2.** `dashboard/src/pages/BotProfile.tsx:43`
Traits are stored as `"risk appetite"` (`population.py:24`). The profile reads `traits.risk_appetite`, so a live profile renders an em dash for a trait that is present.
Reproducer: `pct({"risk appetite": 0.8}.risk_appetite)` → `—` while the spaced key is `0.8`.
Repair: read `"risk appetite"`.

**F6 — P2.** `dashboard/src/pages/BotProfile.tsx:82` and `backend/gridmarket_server/economy.py:149`
AC-GM-UI-03 requires the cash balance after each fill and deposit, in ledger order. `economy.stats` returns `balance` as a two-number tuple `(cash − deposits, cash)` and no `balance_history`. The chart stays on “No balance history served.”
Reproducer: `economy.stats` keys on a funded account are `cash`, `balance`, `trades`, `losses`, `loss_share`, `worst_loss`, `pnl`, `net_worth`, `dormant`. `balance` was `[1000.0, 1000.0]`.
Repair: return the ledger series and point the chart at it.

**F7 — P2.** `backend/gridmarket_server/economy.py:22`
A dormant bot is unemployed, available cash below $1.00, and no battery capacity. Available cash is cash minus cash held for open orders. `_dormant` compares gross `cash_cents` with 100.
Reproducer: cash 150 cents, one open buy holding 100 cents, no assets. Available **50** cents. `_dormant` returned **False**.
Repair: subtract `market.cash_held` before the $1.00 test.

**F8 — P2.** `backend/gridmarket_server/economy.py:132`
Net worth marks an open future at the last trade and values it as `(mark − average trade price) × signed quantity`. The entry query joins only `buy_order_id`, so a short’s sells are ignored and unrealized stays 0.
Reproducer: sell 1 @ 40 cents, later print 80 cents, position quantity −1. Expected net worth **999.60**. `economy.stats` returned **1000.0**.
Repair: average the account’s own opening trades on both sides.

**F9 — P2.** `dashboard/src/pages/Bots.tsx:58`
The spawn form sends `seed` as a JSON number. `SpawnRequest.seed` is `str | None` (`bots_api.py:32`). AC-GM-BOT-07 says a named seed is used.
Reproducer: `SpawnRequest.model_validate({"count": 1, "seed": 123})` → `string_type`. The string `"123"` validates.
Repair: send the seed as a string.

**F10 — P1.** `ercot-hackathon/public/market-feed.js:29`
`GET /v1/market/activity` is a list of `label` / `side` / `quantity` / `price_cents` (`market.py:529`). `GET /v1/router` is `{checks, brier, jev_enabled}` (`decision_router.py:179`). The feed reads `activity[].name` / `text` and `router.results`. `views.test.mjs` stubs `{items:[{name,text}]}` and `{results:[...]}`, so the view test never sees the live shapes. AC-GM-EDGE-05 requires those views to show activity and router alerts.
Reproducer: `renderFeed` on one activity row (`label: "Harbor Desk"`, `side: "buy"`, `quantity: 3`, `price_cents: 8`) and one alert in `checks` produced `<li><b></b> </li>` and `No alert-band checks`.
Repair: render `label`, `side`, `quantity`, and `price_cents`, and read `checks`.

## Security

F1 is the admin-boundary break. Bot keys stay HMAC-SHA256 and are stored as SHA-256 (`bots_api.py:72`). Spawn still rejects a missing key, a wrong key, and `CF-Connecting-IP`. Product SQL added in this diff is parameterized. `market-feed.js` escapes interpolated text; the failure is the wrong fields (F10), not raw HTML. The master seed is logged because DES-GM-BOTS says to log it.

## OCR

Delegation: `ocr delegate preview --from origin/main --to 8f6818b73c00a19e0d076104b6169aca2d753983`, then `ocr delegate rule` on every reviewable path. 28 reviewable, 17 excluded (tests, fixtures, markdown, the font binary, `wrangler.jsonc`, `OFL.txt`). Tests were still read where they hide F2, F3, F4, and F10.

| Rule group | Files | Result |
| --- | --- | --- |
| Python correctness, security, concurrency | `bots.py`, `bots_api.py`, `decision_router.py`, `economy.py`, `market.py`, `population.py` | F1, F2, F7, F8. No `eval`. Router SQL interpolates the constant column list only. Limiter dicts are the documented per-bot window. |
| Default (HTML, CSS) | `dashboard/index.html`, `styles.css`, `godseye/index.html`, `public/index.html` | No separate defect. Both views mount `market-feed.js` (F10). |
| TS/JS security and React | `api.ts`, `hooks.ts`, pages, components, `theme.ts`, `market-feed.js`, worker `index.js`, `views.test.mjs` | F3, F4, F5, F6, F9, F10. No `eval`, no `var`. Feed text is escaped before `innerHTML`. |

## Repair write set

`backend/gridmarket_server/bots_api.py`, `backend/gridmarket_server/decision_router.py`, `backend/gridmarket_server/economy.py`, `dashboard/src/pages/Bots.tsx`, `dashboard/src/pages/BotProfile.tsx`, `ercot-hackathon/public/market-feed.js`, and the tests that currently encode the wrong shapes (`backend/tests/test_router.py`, `dashboard/src/fixtures/phase1b.json`, `dashboard/src/pages/phase1b.test.tsx`, `ercot-hackathon/test/views.test.mjs`).

## Remaining risks

Spec commit `8989e53` is not in this candidate (`SPEC_WRITESET_GAP`, Orchestrator item). Page and view tests pass against fixture shapes that the live routes do not return, which is why F3, F4, and F10 survived the green gates.
