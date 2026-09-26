---
type: evidence
title: GridMarket phase 1b assembly — S49-A rolled back
okf_status: active
tags: [gridmarket, integration, phase-1b, evidence]
freshness: "2026-09-26"
---

# Phase 1b assembly: REPAIRABLE_FAILURE / ROLLED_BACK

Journey GM-2026-09-25; S49; Integration Engineer execution session. This is an
assembly receipt, not independent review, assurance, owner acceptance, or landing.
The bots lane is returned to the Coordinator with the failing evidence below.
S49-B through S49-E were not entered. Stop before S49-L.

## Identity and authority

- Branch: `gridmarket/integration-1b`.
- Worktree: `/home/spectre/alphazede/worktrees/base-gridmarket-integration-1b`.
- Owner-authorized overlap base: `2c96695a21fe4dc7e960c9e6bab0d510b298727d`.
  `ops/candidates/1a` matched it; `ops/landed/1a` was absent before assembly,
  after the merge, and after rollback verification. No main synchronization applied.
- S49-A bots S31 exit: `5ddc28c35eb0f56195d70151f0090194dc6cf26f`.
- Conflict-free `--no-ff` merge: `d6e05f89743cb4dfb3250bf4fde86c7180b598de`.
- `git revert -m 1 --no-edit` rollback: `b58d6c480a008abfa2e518ecfb09439f763b599f`.
- Tested rollback candidate SHA: `b58d6c480a008abfa2e518ecfb09439f763b599f`;
  tree: `2a5d33968b35aa218c18cd0ffb443a94d59ac4d8`.
  It equals the authorized base tree (`git diff --exit-code BASE HEAD`: 0).
  The subsequent evidence-only commit is the branch handoff HEAD; its parent
  names this exact tested candidate. This is not a phase-1b-ready candidate.
- Sources: `implementation.json` full S49-A..E and S49-L records,
  `seit.json` named commands and PROC-ASSEMBLY, frozen `CONTRACTS.md`, and the
  owner dispatch `ops/packets/P1b/S49-IE.md`. Current dispatch overrides the
  printed landed-base requirement and earlier slip-check time.
- Slip trigger: **NOT fired**; S31 was recorded green before the Saturday
  12:00 CDT check. The rollback is not a slip-trigger decision.

## Entry and assembly checks

All five dispatched exit SHAs matched their `ops/exits/` records. The bots
entry accepted the expressly authorized deviations: missing 1a landing,
BOT_01/BOT_03 baseline reds, and the entropy proof conflict. The S31 lane log
records four diversity tests green and the two baseline bots reds; it is not
represented here as an all-green lane test run.

`make setup` exited 0. Lockfiles remained unchanged (diff exit 0). Existing
S01 dependency admission evidence was reused for identical frozen dependencies,
as recorded in the inherited `evidence/assembly-phase-1a.md`; npm reported the
same two moderate development advisories. No dependency update was made.

PROC-ASSEMBLY write-set inspection used the prescribed non-merge commit history
from S31 excluding the pre-merge integration head. Exactly the eight paths in
the S28/S29/S30/S31 union appeared; exit 0. The twelve frozen files (including
`dashboard/vite.config.ts`) match S01
`4256b221081a0f145524df1da6a5a2aaa2092221`; exit 0. No contract amendment,
conflict resolution, or direct product/test edit was made.

Evidence root for the tables below: `/tmp/gm-evidence/P1b/`.
Commands ran with inherited `GRIDMARKET_NWS` unset; backend tests retain their
existing outbound-socket guard. No live weather retrieval is claimed.

## S49-A post-step V&V at d6e05f8

| Check | Exit | Evidence | Observation |
|---|---:|---|---|
| CMD-LINT: `make lint` | 2 | `S49-A-lint.log` | Ruff check passes; format check rejects bots.py, bots_api.py, population.py. |
| CMD-TEST-CONTRACTS: `make test-contracts` | 0 | `S49-A-test-contracts.log` | 3 passed. |
| CMD-TEST-ALL: `make test-all` | 2 | `S49-A-test-all.log` | Backend 94 passed, 1 failed; dashboard and Worker subcommands not reached by this target. |
| CMD-TEST-BOTS: `make test-bots` | 2 | `S49-A-test-bots.log` | 14 passed, 1 failed, BOT_03 tail. BOT_01 passes on the assembled base. |
| CMD-TEST-DASH: `make test-dash` | 0 | `S49-A-test-dash.log` | 12 passed; TypeScript/Vite build succeeds. |
| CMD-SMOKE: `make smoke SMOKE_PROJECT=gm-smoke-1b SMOKE_PORT=18003` | 0 | `S49-A-smoke.log` | Status open; incomplete smoke proof described below. |
| PROC-ASSEMBLY frozen files / lane write set | 0 / 0 | `S49-A-proc-assembly.log` | No frozen drift or out-of-write-set path. |
| PROC-ASSEMBLY aggregate | FAIL | `S49-A-results.json` | Required test-all is red; no independent aggregate process exit code invented. |

Smoke uses the unique S49 project/port assigned by seit.json CMD-SMOKE rather
than the stale `gm-smoke-integration:18000` annotation in the step record. This
avoids overlap with phase-1a work. The existing smoke recipe forces NWS off,
prints `container gm-smoke-1b-bots-1 has no healthcheck configured`, then obtains
HTTP status open and exits 0. It does not implement all CMD-SMOKE pass-rule
assertions (dashboard HTML, UID, hardening/volume inspection, or bots stability
after 30 seconds). Exit 0 is a command receipt only, not full operational proof.
No Makefile repair or deployment was performed.

The failing test is `backend/tests/test_bots.py::test_SEIT_GM_BOT_03_order_limit`.
Its tail expects `httpx.HTTPStatusError`, while the SDK raises
`gridmarket.GridMarketError: 422 PRODUCT_CLOSED: Product closed` for its fixed,
already-expired delivery timestamp. This is the documented test-tail gap,
not a newly classified product defect. Both test-all and test-bots reproduce it.
The independent new gate failure is formatting in the three S31 product files.
No tests were skipped, deselected, weakened, or repaired.

## Rollback verification at b58d6c4

| Check | Exit | Evidence | Observation |
|---|---:|---|---|
| `git revert -m 1 --no-edit d6e05f8` | 0 | Git history | Reverts only S49-A. |
| `git diff --exit-code 2c96695 HEAD` | 0 | Git trees / `S49-identity.json` | Exact base tree restored. |
| `make lint` | 0 | `S49-A-revert-lint.log` | Original formatting restored. |
| `make test-all` | 0 | `S49-A-revert-test-all.log` | 80 backend, 12 dashboard, 25 Worker tests pass; dashboard build passes. |
| `make smoke SMOKE_PROJECT=gm-smoke-1b SMOKE_PORT=18003` | 0 | `S49-A-revert-smoke.log` | Status open; same smoke-proof limitations remain. |

`S49-A-revert-results.json` records actual exits. Rollback follows S49-A's
explicit CMD-TEST-ALL + CMD-SMOKE list; lint additionally confirms removal of
the formatting regression. Bots-only tests no longer exist after the revert.
No later merge was attempted. The only net tracked change from the authorized
base is this evidence file. No review/test receipt placeholders were authored.

## Return to Coordinator / bots lane

Repair request: format the three S31 product files within an authorized bots
repair packet; route the pre-existing BOT_03 test-tail repair to an authorized
test owner. An amended entry decision alone cannot make a red post-step gate
green. Provide a new exact exit SHA and passing required gates before resuming
assembly. Retain the merge and revert history; do not rewrite it. The explicit
stop-on-red rule prevents S49-B..E from proceeding in this session.

| Step | Input exit SHA | Disposition |
|---|---|---|
| S49-A bots | `5ddc28c35eb0f56195d70151f0090194dc6cf26f` | Merged then reverted; returned. |
| S49-B router | `fc8080df50250b564f2e1f858e9c4265a16d740e` | NOT_RUN: S49-A red. |
| S49-C views | `fde33285c721b24d191d3dde36d1177a87050900` | NOT_RUN: S49-A red. |
| S49-D pages | `90921b98c87857f22bf4e64cee6ec0ab59909f0a` | NOT_RUN: S49-A red. |
| S49-E spec | `b0fa857e9f2e7f065b7ad55fde5570069ae982ba` | NOT_RUN: entry not reached. |

Spec-defer status: **not evaluated**. S21 is unmerged because S49-E was not
reached; no complete-or-defer decision or S12-E deferral is asserted.

## Typed gaps and pending actions

- `S31_FORMAT_RED`: new assembly gate failure, returned to bots.
- `BOT_03_PREEXISTING_TEST_TAIL_RED`: reproduced; outside this assembly's repair authority.
- `MAIN_AFTER_1A_ABSENT`: authorized overlap base; no lane yet contains main after landing.
- `BOT_01_LANE_BASELINE_RED`: carried entry gap; clears on the attempted merged candidate.
- `ENTROPY_PROOF_CONFLICT`: S30/S31 bits versus SEIT 0–1 proof conflict remains unresolved.
- `PAGES_APP_ERROR_BOUNDARY_GAP`: supplied lane gap; page-level repair is in S51-repair,
  but pages were not merged here.
- `SMOKE_PROOF_INCOMPLETE`: recipe exit 0 does not prove its full declared pass rule;
  live NWS remains unproven by this recipe.
- `VIEWS_NOT_DEPLOYED`: pending owner action, not yet actionable from a green S49-C
  head. After S49-C passes, owner sets MARKET_URL and redeploys the Worker from
  that integration head (OWN-WORKER-DEPLOY-2). No such green-head notification is claimed.
- Owner `PROC-ERCOT-LIVE-CHECK` and `PROC-ACCEPT-P1`: pending; never performed here.
- `BRAN_UNAVAILABLE`: no native policy; ordinary repository/Git discovery used.
- Independent phase review, browser visual review, and Assurance Test Engineer:
  pending; this receipt does not establish their PASS.

Frozen primary profile digest remains
`14d07a1ceffc31954e7be348d0ec32b10140108a2351448d26e500759a8ed721`;
Integration Engineer execution route remains Codex CLI / GPT-6 Astra / high.
No live profile or fallback route was substituted.
`review.coverage_assist` remains enabled, required=false, backend OpenCodeReview
delegation. `ocr` is on PATH; runtime not exercised (`not_run`), a pending review
capability gap rather than review evidence. This session performs no code review.
`deterministic_verification.reverify` remains enabled, selected conditional Rust
ELF backend retained. Reverify: not applicable — no Rust/native binary claim.
Source tests, JavaScript builds and container startup are not binary-analysis
receipts; ordinary tests do not substitute for Reverify.

Remaining blocker: S49-A required gates are red on the merged lane content.
The rollback has green command exits but cannot certify phase 1b. No PR,
main merge, branch deletion, force operation, owner deployment, credential
access, issue closure, or Co-Authored-By line was introduced.
