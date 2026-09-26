---
type: review-receipt
title: Phase 2 independent review
okf_status: active
tags: [gridmarket, phase-2, review]
---

# Phase 2 review

**Verdict: REPAIR_REQUIRED**

Candidate `1290402ca755b254f1395749e59f344c9a1d7bb5` against base `e08cf552f73696fcec1c09490533169b4d7adbf1` (merge-base, verified). Diff `e08cf55..1290402`: 160 files, +9566/−70. Reviewer identity is independent of the lane authors. Product, test, and contract files were not edited.

Reverify: not applicable — no binary artifact in phase 2. The stretch Rust lane is dropped (`exits/S17.dropped-DEC-GM-067`).
BRAN: unavailable (no `.bran/policy.yaml`).

Checked and not findings: reservation SQL is out of `market.py` (provider functions in `base_sim.py`); `MAX_PRICE_CENTS = 500` rejects 501 with `VALIDATION_ERROR` and the stated cap message (`market.py:23`, `market.py:198`); kit prompt lists all three limits (`docs/llm/system-prompt.md:31`); sandbox sample price is 10 cents; LoneStar outage skips heartbeats and the router check reaches the alert band after the heartbeat ages past 30 s (`health.py:122`, `test_health.py:163`). Bot-profile CLS at 390 px is 0 (S53-cls holds).

## Findings

**F1 — P1.** `dashboard/src/pages/Providers.tsx:74`
AC-GM-UI-04 requires customers, online assets, heartbeat age, health probability, band, and outage state. The page binds health rows with `provider_id` and reads `customers` and `online_assets`. `GET /v1/providers/health` returns `id`, `online`, `last_heartbeat`, `heartbeat_age_s`, `outage_active`, `outage_until` (`health.py:231`). It has no `provider_id`, `customers`, or `online_assets`. `GET /v1/providers` does return `participants` (40 and 20 on a seeded book, `api.py:377`) and the page never reads it. The fixture (`dashboard/src/fixtures/providers.json:7`) uses the page's shape, so `Providers.test.tsx` stays green.
Reproducer: `TestClient` with `GRIDMARKET_LONESTAR=on` and `GRIDMARKET_NWS=off`. Health keys were `display_name`, `heartbeat_age_s`, `id`, `last_heartbeat`, `online`, `outage_active`, `outage_until`. Lookup `provider_id == id` was `None` for both providers. The same row matched on `id` had `customers` and `online_assets` missing, with a real `last_heartbeat` and `outage_active: false`. Router checks for `base_sim` and `lonestar` were present (`family=health`). Rendered page at 390 px (`vr/out/providers/step0_390.png`): both providers Unknown; Customers, Online assets, Heartbeat age, and Outage Unavailable; probability 5% and band log (those come from `/v1/router`, which does match).
Repair: bind the page to the live documents (`id`, heartbeat, `outage_active`, `participants`) and serve an online-asset count. Point `providers.json` at that shape.

**F2 — P2.** `spec/gridmarket/04.1.8-providers.md:28` (built copy `spec/GridMarket-Specification.md:944`)
The spec says an admin `POST /v1/admin/providers/lonestar/outage` with action `start` / `end`. The route requires `{"active": true|false}` (`health.py:211`). SEIT-GM-PROV-03 and the page already post that body (`Providers.test.tsx:129`).
Reproducer: same client, loopback, admin key. `{"action":"start"}` returned **422** `VALIDATION_ERROR` / `active must be true or false`. `{"active": true}` returned **200**.
Repair: describe `{"active": true}` and `{"active": false}` in the spec source and regenerate the built spec. Leave the route.

**F3 — P2.** `dashboard/src/pages/Providers.tsx:68`
The new Providers page replaces a one-line loading state with the card grid and does not reserve that height. Scripted visual review, fresh load, 390 px: CLS **0.1987** (limit 0.1). Desktop was ~0.
Reproducer: `vr/out/report.json` flow `providers`, width 390.
Repair: reserve the loaded card stack while `providers.loading` is true, the same way `.profile-reserve .loading` does for the bot profile.

## Security

Outage admin checks the bearer key and loopback, including `testclient` (`health.py:188`). Product SQL added in this diff is parameterized; LoneStar's column list is a constant. No `eval`. Bot and admin secrets are not logged by the new code.

## OCR

Delegation: `ocr delegate preview --from e08cf55 --to 1290402ca755b254f1395749e59f344c9a1d7bb5` (exit 0), then `ocr delegate rule` on every reviewable path (exit 0). 27 reviewable, 133 excluded (tests, fixtures, markdown, drawio, svg). Tests and `providers.json` were still read where they hide F1.

| Rule group | Files | Result |
| --- | --- | --- |
| Default | `Makefile`, `dashboard/src/styles.css` | No separate defect. `.profile-reserve` matches `FeedBody`'s `.loading` (`Market.tsx:40`). |
| Python correctness, security, concurrency | `api.py`, `health.py`, `market.py`, `providers/__init__.py`, `base_sim.py`, `lonestar.py`, `strategy.py`, `tools/azdiagram/*`, `tools/spec_build.py`, `tools/spec_lint.py` | F2 is the spec/route mismatch, not an injection. Price cap and reservation move hold. No `eval`, no shell. |
| TS/JS security and React | `BotProfile.tsx`, `Providers.tsx`, `Sandbox.tsx` | F1, F3. No `eval`, no `var`. |
| YAML | spec `spec.yaml` and figure yaml | No separate defect. |

## Visual review

Scripted driver, widths 1280 and 390, `--cls-max 0.1`, `--serve` on this worktree (LoneStar on, NWS off). Accessible nav names are `01 Overview` … `07 Spec` (the number is its own line, so `01Overview` does not match). Theme controls were not clicked. Each flow is one click at 1280; 390 is a reload of that URL, because the rail is `display:none` until Menu.

`vr.py` exit **1**. `observe.py --observer claude` with no `--baseline` exit **2**. `observations.json`: `/tmp/claude-1000/-home-spectre-alphazede-Hackathons-Base/3f3d16bb-9fd4-4279-8e99-ac29f3675fda/scratchpad/ops/vr/out/observations.json`. The observer selected 16 pairs and judged none: `no_before_image:ratio=None` (no baseline and no design reference). That is a typed gap in the observer, not a pass. The screenshots were read for this review.

| Flow | CLS 1280 | CLS 390 | Console errors | Failed same-origin |
| --- | ---: | ---: | ---: | ---: |
| overview | ~0 | 0.0967 | 0 | 0 |
| market | ~0 | 0.2019 | 0 | 0 |
| predictions | ~0 | 0.3952 | 0 | 0 |
| providers | ~0 | 0.1987 | 2 (429) | 2 |
| bots | ~0 | 0.1052 | 1 (429) | 1 |
| bot-profile | 0.0940 | 0 | 0 | 0 |
| sandbox | 0.0048 | 0 | 0 | 0 |
| spec | ~0 | 0 | 0 | 0 |

The 429s are the unauthenticated bucket (10/s, burst 20) after an overview load and the providers navigation in the same second. A direct providers reload showed no error banner and did render router probability. Not a separate defect. Market, predictions, and bots CLS at 390 are on pages this diff does not change.

## Repair write set

`dashboard/src/pages/Providers.tsx`, `dashboard/src/fixtures/providers.json`, `dashboard/src/pages/Providers.test.tsx`, `backend/gridmarket_server/health.py` (online-asset count on the health document), `spec/gridmarket/04.1.8-providers.md`, and the regenerated `spec/GridMarket-Specification.md`.

## Remaining risks

Market CLS 0.2019, predictions CLS 0.3952, and bots CLS 0.1052 at 390 px are above 0.1 on pages this phase did not edit. A fast click from a polling Overview onto Providers can 429 the new page's first health and router fetches. Observer eye-judgment did not run (`no_before_image`). PROC-ACCEPT-P2 and the simulated outage demonstration remain the owner's.
