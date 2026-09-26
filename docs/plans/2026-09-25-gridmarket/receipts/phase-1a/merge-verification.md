---
type: evidence
title: GridMarket Phase 1a deterministic repair closure
okf_status: active
tags: [gridmarket, phase-1a, integration, verification]
freshness: "2026-09-26"
public_boundary: private
---

# DIR-P1a-16 / DEC-GM-061 merge verification

Outcome: **REPAIRABLE_FAILURE — mutation closure gate remains red**. Single aggregate repair round: **1**. No second Reviewer or Assurance Test Engineer dispatch.

Lifecycle GM-2026-09-25; Phase 1a; S09-merge; integration execution session. The current owner dispatch authorizes the three exact merges and deterministic closure, superseding the earlier live-NWS smoke requirement and separate assurance handoff. Stop before S09-L.

Initial HEAD: `663637558681e636bea3f784ce78fb72819bfd60` on `gridmarket/integration-1a`; worktree initially clean. The three ops/exits files matched the approved SHA values.

| Lane | Approved exit | Resulting merge | Exit |
|---|---|---|---:|
| Market | `4c87cdb9ad2275a46881c36c10fb4641a6530a91` | `e0aa8947241a9bf2107239d47d08249308bbccb5` | 0 |
| Data | `a09ab402e626a46cf521654f3688e1a2fb8ae6a5` | `9bbe7b6c2194eb8182e64a2beb614f49a7a6a2be` | 0 |
| UI | `b558a0e00ae3e43775683edf61da5dd8523e69d8` | `021568f83bb8c3377fb459747164998a2e4cc94c` | 0 |

All merges used the dispatched `git merge --no-ff` commands and messages, in order, without conflicts. No direct product/test/configuration edits or dependency changes. No lane was reverted: the mutation failure was not conclusively attributed to an individual lane. The dispatch explicitly permits returning REPAIRABLE_FAILURE instead of editing product/tests or reverting an unidentified offending lane. Market includes the DIR-P1a-17 bots-route removal; F6 is resolved within that scope by the UI's providers-based participants display, rather than adding the out-of-contract bots route.

Tested merge: `021568f83bb8c3377fb459747164998a2e4cc94c`; Git tree: `12d57c38effb9fc0120dc42890eb7ad4b79de2dc`. The final failure checkpoint is the documentation/receipt commit containing this file, with product/test/configuration content identical to the tested merge. It is not a candidate-ready promotion. `ops/candidates/1a` remains unchanged at `2c96695a21fe4dc7e960c9e6bab0d510b298727d` because deterministic closure failed.

## Deterministic gates

Commands ran in this worktree. `GRIDMARKET_NWS` and `GRIDMARKET_WORKER_URL` were unset for test/coverage/mutation and smoke invocations. Backend NWS polling remains enabled under the existing outbound-socket test guard; this is not a claim of successful public weather-service retrieval. The unchanged smoke recipe sets NWS off in its fresh temporary env file, as required by DIR-P1a-09 / DIR-P1a-15.

| Command | Exit | Result |
|---|---:|---|
| `make lint` | 0 | Ruff checks pass; 32 files formatted. |
| `make test-contracts` | 0 | 3 passed. |
| `make test-all` | 0 | 85 backend, 13 dashboard and 25 Worker tests passed; dashboard TypeScript/Vite build passed. |
| `make test-dash` | 0 | 13 passed; TypeScript/Vite build passed, 632 modules. |
| `make smoke SMOKE_PROJECT=gm-smoke-repair-1a SMOKE_PORT=18020` | 0 | All recipe assertions passed, including stable healthy bots after 30 seconds. |
| `make secrets` | 0 | No leaks in 121 commits; MIT and env-example checks pass. |
| `make rules` | 0 | Baseline rules, Jev boundary and author-time checks pass. |
| `make coverage BASE=c6bcb39f3d31eeb28a4a7d416a1b6d0cff00f90c` | 0 | Changed-line coverage 90.47% (1016/1123); diff-cover displays 90%; threshold 80%. All 85 tests passed. |
| `make mutation MUTANTS="gridmarket_server.market.*"` — inherited generated state | 0 | **FAIL threshold:** 65.43% (757/1157), below 70%; 385 survived and 15 timed out. |
| Same mutation command — fresh generated state diagnostic | 2 | Incomplete; forced-failure self-check stopped making progress. No valid complete score; mutmut terminated with 143. |
| `uv run --project backend --frozen python -c "import gridmarket_server.main"` | 0 | Import succeeds from the project environment. |
| `GET http://127.0.0.1:18020/v1/predictions` | 0 | HTTP 200; JSON list from the running merged smoke stack. DIR-P1a-05 lane gap closed. |
| `gitleaks dir --config .gitleaks.toml --redact --exit-code 1 docs/plans/2026-09-25-gridmarket/receipts/phase-1a` | 0 | Original copied assurance transcripts contain no detected secrets. |
| Smoke cleanup inspection | 0 | No containers, volumes or networks with the assigned project label; temporary smoke env file removed. |

Mutation score is killed/(killed+survived+timeout). The completed command reported 1177 total generated mutants but 1157 scored; no-tests, skipped, suspicious, interrupted and segfault counters were zero. Its exit 0 does not satisfy the separate >=0.70 threshold. The completed run took 1232.44 seconds. See [machine-readable mutation receipt](mutation-verification.json).

An environment diagnostic preserved that run and moved only the ignored generated `backend/mutants` directory into the ignored worktree scratch area. The identical command then generated fresh state, collected the full test map and passed its clean-test baseline. No product, test, configuration, threshold or NWS setting changed. It stopped emitting output in the forced-failure self-check for 255 seconds; native stack attachment was denied by the environment. SIGINT released that self-check and mutant execution advanced, so the observation alone does not establish the root cause. SIGTERM then stopped this diagnostic; it ended after 353.79 seconds with make exit 2 / mutmut 143. Partial results are not accepted. No owned mutation workers remained after cleanup.

Stale cache, an upstream tool defect, and a specific offending lane are **not established**. The completed below-threshold result and the incomplete diagnostic are separate evidence. No issue was filed, no second independent review/assurance was dispatched, and no code/test workaround was applied. Return for owner/coordinator disposition under the existing single-round budget; do not close Phase 1a or proceed to S09-L.

Coverage uses the integration phase base on main, per CMD-COVERAGE. The missing `tools` coverage-module warning, two backend deprecation warnings, and JSDOM CSS parser diagnostics are non-failing. No test selection or gate threshold was weakened.

Smoke ran the Makefile exactly as written. It proved dashboard HTML, loopback port, UID 10001, read-only root, restart policy, project-scoped SQLite volume, and healthy non-restarting bots after 30 seconds. The additional predictions GET ran during this same stack's lifetime. The recipe removed only its own project and temporary env file.

## Review evidence and capability identity

The original reviewer and tester receipts below concern prior candidate `2c96695a21fe4dc7e960c9e6bab0d510b298727d`. Their original failure verdicts are preserved verbatim. This receipt records deterministic verification of the single repair round; it does not fabricate a second independent review or assurance verdict.

- [Original reviewer log](assurance-reviewer.log): OCR delegation preview/rule execution is recorded there. Its browser visual review remains explicitly `not_run`; no browser-review PASS is inferred here.
- [Original assurance log](assurance-tester.log): original mutation, smoke and scoring findings preserved.
- `review.coverage_assist`: enabled, required=false, OpenCodeReview delegation backend retained; no new review dispatched or substituted.
- `deterministic_verification.reverify`: enabled, conditional Rust ELF selection retained. Reverify: **NOT_APPLICABLE**, no Rust/native binary claim in this phase. Source tests, JS builds and container runtime checks are not binary-analysis evidence.
- Frozen profile digest remains `14d07a1ceffc31954e7be348d0ec32b10140108a2351448d26e500759a8ed721`; no live profile imported, role route switched, or capability selection changed.
- BRAN: **unavailable**, no native policy. Direct plan, exit-file, Git and command evidence used.

Original receipt SHA-256 hashes (byte-for-byte copies):

- `assurance-reviewer.log`: `684a776f3a73395663c1823f535ad4893969734d69e68d91e199bbb271ed16a6`
- `assurance-tester.log`: `149d700c52421162b93b00bb7b6117fe26b0fbb02a0e63353926b0f22d349066`

## Command provenance

Local transcripts and JSON exits remain in `backend/.venv/p1a-closure/` (ignored worktree scratch). The hashes below bind the executed gates; the summaries above and original assurance logs are committed.

| Log | Exit | Seconds | SHA-256 |
|---|---:|---:|---|
| `lint.log` | 0 | 0.15 | `8d84d5f6fc37afdcda2ae72db9725985a2a8eab0b918668aebbb0873010cfbe7` |
| `contracts.log` | 0 | 0.83 | `15759adc2f0b9cc32ffc2d1e2e1ad2470661a30d23f5607d65c112ddcb674d33` |
| `test-all.log` | 0 | 84.27 | `4b3dfc48f6b6683dfa6d62660ca22b39f62a0960b4dcc2914e07e823fd775504` |
| `test-dash.log` | 0 | 6.57 | `174e1abdf0f698f7d6b7a06cfc8c57fbe7729deb6d5e7e08d49d3706816b5abe` |
| `smoke.log` | 0 | 63.26 | `011c4e62fe264bb619381c3bd6931beb009b7e1a7ccd77114bd9dc1c358640ff` |
| `secrets.log` | 0 | 1.03 | `207fbcb1cf3d80aef13d6caead105a9685ea4733c2c22b038b6c1d0666a5092c` |
| `rules.log` | 0 | 0.04 | `4ecf979e4133d8fe403586fa0b1151514e28ff4572a178e3aa716deb6ecc9145` |
| `coverage.log` | 0 | 75.71 | `784c9fc5a7ce8066660ff7884c215f5e21197e87679d89b07f7624ab16ce9856` |
| `import.log` | 0 | 0.48 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `mutation-inherited.log` | 0 | 1232.44 | `b582fa272cc3803e0f4e249f7f5c484db9e892014637c4bf9074d19b021ac22a` |
| `mutation.log` | 2 | 353.79 | `63b962561415610d77516c6b7f453f7449a88af6dd165940e937b9af9fc29e09` |

Tool versions: Python 3.12.3; uv 0.11.6 (x86_64-unknown-linux-gnu); v22.23.2; 11.15.0; Docker version 29.1.3, build 29.1.3-0ubuntu3~24.04.2; Docker Compose version 2.40.3+ds1-0ubuntu1~24.04.1; 8.30.1.

No S09-L, main merge, owner acceptance, deployment, issue closure or new review occurred. The failure-checkpoint SHA and remote push result are reported in the session handoff. The candidate pointer is intentionally not advanced on a red closure gate.
