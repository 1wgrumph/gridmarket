---
type: evidence
title: GridMarket phase 2 partial assembly — kit exit identity unresolved
okf_status: active
tags: [gridmarket, integration, phase-2, evidence]
freshness: "2026-09-26"
---

# Phase 2 assembly: OWNER_DECISION_REQUIRED

Journey GM-2026-09-25, slice S12; Integration Engineer execution session.
The flake prerequisite and S12-A LoneStar are assembled and green. The next
ordered merge, kit, is blocked by a nonexistent supplied exit SHA. This is a
verified partial candidate, not a phase-2-ready candidate, independent review,
assurance, owner acceptance, or landing. No lane was reverted or returned red.

## Identity and boundary

- Branch: `gridmarket/integration-2`.
- Worktree: `/home/spectre/alphazede/worktrees/base-gridmarket-integration-2`.
- Base: `origin/main` at `e08cf552f73696fcec1c09490533169b4d7adbf1`, the
  phase-1b plus ops PR merge specified by the owner. `ops/landed/1b` is an
  owner-supplied entry fact; no local ops marker was independently located.
- Tested partial candidate: `9f37f51d8546afa02d323d6744fbacf91413fdd7`.
- Tested tree: `fd11af44321b50137ea880edce564bbbbd302cc6`.
- The evidence-only commit directly following this tested candidate is the
  handoff HEAD; its full SHA is returned after the authorized non-force push.
- Source contracts: `implementation.json` integration_plan S12-A/B/C/E,
  `seit.json` named commands and PROC-ASSEMBLY, and this session's exact owner
  dispatch. The dispatch overrides the printed order: flake, LoneStar, kit,
  providers-page, pages2, spec. It also explicitly assigns
  `gm-smoke-integration:18000`, overriding SEIT's older phase-specific pair.
- S12-D is NOT_APPLICABLE by owner dispatch; no slip trigger is inferred.
- S12-L, PR creation, landing, owner PROC-ACCEPT-P2 (including simulated
  outage), deployments, credentials, and lane writes were not performed.

## Blocking identity discrepancy

The supplied S37 exit is `f1f12e3e5c9a04a1f5ceebfcf09633e8ca7974e6`.
`git cat-file -e <supplied-sha>^{commit}` exits **128**: object absent.
`git rev-parse gridmarket/lane-kit` returns
`f1f12e3a5a98a81771400eca53dc363e135dcc7a` (subject:
`docs(kit): document MAX_PRICE_CENTS cap in system prompt (S37-cap)`).
The matching seven-character prefix does not authorize substituting a different
full commit identity. An asynchronous owner question requested the exact
correction; no correction was received before this handoff. No kit merge was
attempted. Resume with an explicit corrected pin and continue the existing
branch in the original owner order; do not recreate or rewrite it.

## Merge receipts

| Step | Lane exit | Merge SHA | Result |
|---|---|---|---|
| prerequisite, DIR-P2-11 | `be405b309f8f187e592d1cf39a501f143043d961` | `1d6b26315fe8d54ede8263040ff2e9acc862b060` | GREEN |
| S12-A | `848e6a303ebcd7572734a97728a1b82814799ae6` | `9f37f51d8546afa02d323d6744fbacf91413fdd7` | GREEN |
| S12-C kit | supplied absent SHA above | — | NOT_RUN: identity unresolved |
| S12-B providers-page | `6606e76bb3382f673664994be13f87aa7517e524` | — | NOT_RUN: ordered predecessor blocked |
| S12-B pages2 CLS | `51c39c974df6617b9aaef2f194321cc02198647b` | — | NOT_RUN: ordered predecessor blocked |
| S12-E spec | `8989e539e7499dccbcbe49ad06fbfbe4c30ea747` | — | NOT_RUN: ordered predecessor blocked |

Both merges used `git merge --no-ff --no-edit <exact-exit>` and exited 0
without conflicts. The flake exit contains market3 `60b1686` and `5be7051`
(ancestry checks exit 0); market3 was not separately merged. All other supplied
pins except kit exist and match their named local lane tips.

PROC-ASSEMBLY non-merge write-set checks exited 0. Flake has eight paths,
limited to market.py, providers/__init__.py, providers/base_sim.py, the four
market/API test files, and Sandbox.tsx, as authorized by DIR-P2-11. LoneStar
has five paths: api.py, health.py, providers/lonestar.py, test_health.py,
and test_providers.py; the provider-summary repair in api.py is explicitly
included in this dispatch's S11 scope. No direct product or test edit occurred.
DEC-GM-090 data-only fixture repair was not needed.

## Gates and interface evidence

All gates inherit `GRIDMARKET_NWS=off`. Worker URL/key and Jev settings are
unset in the gate harness. `make setup` exited 0 and preserved both lockfiles.
Existing dependency admission evidence in `assembly-phase-1a.md` and
`assembly-phase-1b.md` was reused for unchanged locked dependencies. npm
reported the same two moderate development advisories; no update was made.

Raw logs and runnable harnesses are retained locally in
`/tmp/gm-evidence/P2/assembly-20260926/`; the table below preserves their
commands, exits, tested commits, and digests in this committed evidence.

| Step / tested SHA | Gate | Exit | Log SHA-256 |
|---|---|---:|---|
| pre-A-flake / `1d6b263` | `make lint` | 0 | `cab1c8123745729c7de62a4252c63a0fc11bc5f3b39bbc0f9021b3e3d1a0d8de` |
| pre-A-flake / `1d6b263` | `make test-contracts` | 0 | `4dc99d2fc37b2bbd699ad9df8f7b51c9c568bbb23f9cf80bd4bdb3e4ad54cac3` |
| pre-A-flake / `1d6b263` | `make test-all` | 0 | `ccc3ae2df24b44b7b5e95f2be6c0e367dabbe409e26897245ef8e8c02fe44b22` |
| pre-A-flake / `1d6b263` | `make test-dash` | 0 | `a37183721d683fa660cc9d2169b1c62134f940b0bdd8fe596f4e55376ff691d5` |
| pre-A-flake / `1d6b263` | `make smoke SMOKE_PROJECT=gm-smoke-integration SMOKE_PORT=18000` | 0 | `7eba0f1abf442f5a216ecd284ca984043fa0ffba4da4251b435ae22c36537e9f` |
| S12-A / `9f37f51` | `make lint` | 0 | `27598daa6d0ff8700a251e0c66565e4514f5a30db3b970b6b368fc65e3f6388d` |
| S12-A / `9f37f51` | `make test-contracts` | 0 | `e5a20a03635c1de7c4a76aba58232b00d30151d15817f72a0d7396b25e7005a4` |
| S12-A / `9f37f51` | `make test-all` | 0 | `96b4a6b6b6f223322196e1e725f1e3d6b265a75266079b1784d03f169283acb1` |
| S12-A / `9f37f51` | `make test-providers` | 0 | `9c7229834ad8b68cedd6d68b7ecb9c3e64b3eade27498a4fa92a1e2088681802` |
| S12-A / `9f37f51` | `make test-dash` | 0 | `6096cd6cf4e7fd3dda1e59e7385f18b58498667bf004bc96d7d7e87f2718821e` |
| S12-A / `9f37f51` | `make smoke SMOKE_PROJECT=gm-smoke-integration SMOKE_PORT=18000` | 0 | `6c3a5fd54470483af156c7e7647c68f624e4550db6dde63d49e80f09959918cc` |
| handoff / `9f37f51` | `make secrets` | 0 | `8dc8ce07d06491311491b8c31368e527f4f0e8f9fb43f50efb49f84cf067a426` |
| handoff / `9f37f51` | `make rules` | 0 | `4ecf979e4133d8fe403586fa0b1151514e28ff4572a178e3aa716deb6ecc9145` |

Each merged step also passed PROC-ASSEMBLY (exit 0): frozen-file comparison,
write-set inspection, and real HTTP interface exercise against the disposable
Compose app on port 18000. The interface check starts the already-built smoke
image with a new project-scoped volume, fresh throwaway env, no Worker URL,
and NWS off; it removes its own container, network, volume, and env afterward.
LoneStar is enabled only in that step's disposable interface stack.

- Flake: 129 backend, 52 dashboard, and 34 Worker tests passed; dashboard
  build passed. Live OpenAPI held 26 applicable contract operations.
- LoneStar: 143 backend, 14 provider/health, 52 dashboard, and 34 Worker
  tests passed; dashboard build passed. Live OpenAPI held 28 applicable
  contract operations, including health and outage route presence.
- Both steps: `/v1/market/status` returned 200. Unauthenticated `/v1/account`
  returned 401 `UNAUTHENTICATED`; an order with a disposable sandbox key and
  no idempotency key returned 400 `IDEMPOTENCY_KEY_REQUIRED`. Both error
  bodies contained nonempty `error.code` and `error.message`.
- S12-A live `/v1/providers`: `base_sim` had 40 participants and `lonestar`
  had **20**, both online. `/v1/providers/health` returned 200 with both
  providers online, heartbeat ages about 4.7 seconds, and no active outage.
  The outage control was not invoked; PROC-ACCEPT-P2 remains owner-run.
- Both smoke gates verified dashboard HTML, loopback binding, UID 10001,
  read-only root, restart policy, project-scoped SQLite volume, and healthy
  bots after 30 seconds. Cleanup completed. The kit files are not present
  yet; `/kit/*` checks remain pending S12-C.
- Handoff secrets: 229 commits scanned, no leaks found; MIT/env checks pass.
  Rules gate exits 0. These are partial-candidate gates, not substitutes for
  the pending S12-E gates.

PROC-ASSEMBLY `pre-A-flake-proc.log` SHA-256: `8449ca8e354482e8b4377c21fa299af82a2b2191061186aaf5b23027494edd2f`.

PROC-ASSEMBLY `S12-A-proc.log` SHA-256: `95814aff66748a82bd15224961b33f84cebb5383b2fe1e7bebb8d6242299ffa6`.

## Frozen configuration and remaining evidence

The twelve frozen files (including vite.config.ts) match the landed base
`e08cf55` after each merge (diff exit 0). Relative to original S01, inherited
changes already on main exist in backend/pyproject.toml, dashboard/src/api.ts,
and dashboard/src/hooks.ts; this assembly adds no frozen-file drift and does
not retroactively certify those historical amendments. Exact baseline blob
identities are in local `frozen-baseline.json`.

Frozen profile digest remains
`14d07a1ceffc31954e7be348d0ec32b10140108a2351448d26e500759a8ed721`.
The local `frozen-binding.json` preserves every role route and both selected
capabilities. Integration Engineer execution remains Codex CLI / GPT-6 Astra /
high; no fallback or live profile substitution occurred.

`review.coverage_assist`: enabled, required=false; backend OpenCodeReview
**delegation**, available CLI v1.12.9. Review execution is **NOT_RUN**, a
pending independent-review evidence gap, not PASS. No extra review was run
by the assembly author. `deterministic_verification.reverify`: enabled;
Reverify CLI is installed and callable (`--version` is unsupported, exit 2).
**NOT_APPLICABLE: no compiled-binary claim**; phase 2 contains Python,
TypeScript, and JavaScript, and does not merge the Rust lane. Ordinary gate
reruns are not represented as Reverify. Tech-writing lane overrides remain
preserved in the frozen binding. **BRAN_UNAVAILABLE:** no native policy;
repository discovery and Git evidence were used.

Remaining: resolve kit identity, finish S12-C/B/E in owner order with all
post-step gates, then separate phase review/visual review and assurance,
owner PROC-ACCEPT-P2, and Orchestrator S12-L. No whole-phase PASS is claimed.
