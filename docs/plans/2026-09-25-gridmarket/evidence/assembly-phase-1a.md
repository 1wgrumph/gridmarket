---
type: evidence
title: GridMarket phase 1a progressive assembly
okf_status: active
tags: [gridmarket, integration, phase-1a, evidence]
freshness: "2026-09-26"
public_boundary: private
---

# Phase 1a assembly — S09

Outcome: **REPAIRABLE_FAILURE**. S09-A merged without conflicts but failed its required dashboard gates. It was reverted under PROC-ASSEMBLY. No assembly step is complete; S09-B through S09-E were not attempted. S09-L remains with the Orchestrator.

## Authority and input identity

- Lifecycle GM-2026-09-25; execution session; DIR-P1a-02 / DEC-GM-051.
- Branch: `gridmarket/integration-1a`; clean initial base: `c6bcb39f3d31eeb28a4a7d416a1b6d0cff00f90c`.
- Plan: `implementation.json` integration_plan.steps S09-A and anomaly_rollback_recovery; `seit.json` PROC-ASSEMBLY; current owner dispatch overrides stale worktree text.
- Coordinator exit S01: `4256b221081a0f145524df1da6a5a2aaa2092221`.
- Coordinator exit S25: `4ff729401ec87f20f79dfcc7bf5f13e028b08091` (not merged). Planned external worker base: `4853e51b2a5d8564631946e688e53802f83a7ab8` (not assembled).
- Coordinator W1 receipt reports setup, lint, contract tests, dependency scan, secrets and write-set gates passed at S01, and worker gates at S25. S01 log records no known Python vulnerabilities and the locked npm version cutoff passing; two moderate Vitest development advisories remain, below the required high-severity threshold. Existing dependency-scan evidence reused for unchanged lockfile identities; integration setup preserved both lockfiles.
- BRAN: unavailable (no native policy); repository plan, exit files, receipt and Git objects used directly.
- Frozen review.coverage_assist: OCR enabled, required=false. This session performs assembly, not independent code review; OCR not_run here and no review PASS claimed. Phase reviewer must resolve and run its selected OCR backend; runtime availability was not assessed here.
- Frozen deterministic_verification.reverify: enabled, SELECTED_CONDITIONAL for the Rust ELF extension claim. Reverify: NOT_APPLICABLE here — no Rust lane or binary-level claim; Python/TypeScript source checks only. No live profile imported or route switched.

## S09-A attempt

- Merged S01 with `git merge --no-ff`.
- Merge commit: `eb600c0f210e594944aa093788cbdfce068630eb`.
- Merge tree: `55e37bceb9851633a0488e0c906f9d2c0ea8b9a6`.
- No conflicts or product edits outside the merge.
- Write-set inspection: `git log --no-merges --name-only --format= 4256b22 --not c6bcb39` matched S01's 52 authorized paths; no exceptions.
- Frozen-contract comparison is skipped at the initial foundation step by PROC-ASSEMBLY; attempted baseline blobs are recorded below, but are not an accepted green baseline.

| Check | Exit | Result |
|---|---:|---|
| Initial `make setup` before merge | 2 | No Makefile on the planning-only base; rerun after foundation merge. |
| CMD-SETUP: `make setup` on merge | 0 | Backend virtual environment and dashboard node_modules created. |
| Lockfile diff | 0 | backend/uv.lock and dashboard/package-lock.json unchanged. |
| CMD-LINT: `make lint` | 0 | Ruff checks pass; 25 files formatted. |
| CMD-TEST-CONTRACTS: `make test-contracts` | 0 | 3 passed. |
| CMD-TEST-ALL: `make test-all` | 2 | Backend 3 passed; nested dashboard Vitest finds no tests, exits 1; make exits 2. |
| CMD-TEST-DASH: `make test-dash` | 2 | Same no-test failure independently reproduced; build recipe not reached. |
| CMD-SECRETS: `make secrets` | 0 | Gitleaks scanned 50 commits; no leaks; MIT and env-example checks pass. |
| CMD-SMOKE | — | NOT_APPLICABLE: deploy/compose.yaml arrives at S09-C. |

Exact relevant diagnostic from both failing invocations:

```text
RUN v3.2.7
No test files found, exiting with code 1
make: *** [Makefile:26: test-dash] Error 1
```

The exact S01 tree contains no dashboard test files. Its required integration `test-dash` target invokes Vitest without a no-tests allowance; `test-all` invokes the same target. This is a reproducible foundation/assembly-gate mismatch, not evidence of failing implemented dashboard behavior or a tool defect. No test was skipped, no gate weakened, and no issue filed. Return to the Coordinator/foundation owner for an authorized correction to the foundation or assembly contract before redispatch.

## Rollback and recovery

- Ran `git revert -m 1 --no-edit eb600c0f210e594944aa093788cbdfce068630eb`.
- Revert commit: `c55ede73209fdbd24e6fbd8665949c8f3a0c0222`.
- Revert tree: `681a5f1fd05a26d5b8ecbc5dcf8d124179ed8429`.
- `git diff --exit-code c6bcb39 HEAD` at the revert exited 0: tracked tree exactly restored to the original base.
- Post-revert `make setup`, `make lint`, `make test-contracts`, `make test-all`, `make test-dash`, and `make secrets` each exit 2 with `No rule to make target`: the reverted foundation removes the Makefile. This is a typed rollback-verification gap, not a green test result. Structural restoration passed; executable rollback V&V could not run.
- Generated dependencies and caches were preserved outside the worktree after rollback; no source or branch was deleted.
- Re-entry requires reverting the revert, then merging the repaired recorded S01 exit with `--no-ff`, and running all S09-A checks. Merging the old exit alone will not restore reverted content.
- Evidence-only commit follows this revert and is pushed non-force to `origin/gridmarket/integration-1a`; its SHA is the branch HEAD receipt. No main merge, deployment, acceptance or independent assurance is claimed.

## Attempted contract baseline at S09-A

These blobs describe the reverted attempt only; do not adopt them as a green baseline.

| Frozen file | Blob SHA |
|---|---|
| `CONTRACTS.md` | `43905b3627e1c9104095ce2efac3d33b076011c3` |
| `backend/gridmarket_server/contracts.py` | `2fee6acc527794a886879ad5f15f03985100ea05` |
| `backend/gridmarket_server/schema.sql` | `a63c044b8a4f2c4ebb9594961de4f8247d4a6f19` |
| `backend/gridmarket_server/main.py` | `cacf2536fd50f480f04280f12c39007ef405dcd6` |
| `backend/pyproject.toml` | `5fcfab9d25392bf9be51c655d3f8758d1791910d` |
| `backend/uv.lock` | `dbfe56e12d175769480d6151f642342a7b03ee14` |
| `dashboard/package.json` | `96a15af55503fd04a6fca02b9a1d6076ebff78f4` |
| `dashboard/package-lock.json` | `ddc93c03d444dc4d324e50cc615064d0cea0f520` |
| `dashboard/vite.config.ts` | `c6b177b5751c54d5b6ed5334edddef15ebcb2552` |
| `dashboard/src/api.ts` | `1bf01ac57389adeb3fb59a6ff326a3f814f2eb2b` |
| `dashboard/src/App.tsx` | `ed64096c48890c42ddc3a79e9aa97eba8065391d` |
| `dashboard/src/hooks.ts` | `28e869174ea49af2b2b4e4fdfde6e3149189067d` |

## Configuration and unexecuted steps

Toolchain observed: Python 3.12.3; uv 0.11.6; Node v22.23.2; npm 11.15.0; gitleaks 8.30.1. Vitest reported v3.2.7. Docker, compose, graphviz, draw.io, cargo and maturin were not exercised because assembly stopped at S09-A.

No compose file, Dockerfile or smoke image exists at this step. Engine/provider runtime not exercised; no deployed Worker identity or credential access. Owner deployment and acceptance remain pending. S09-B/C/D/E are blocked by failed S09-A; later exit availability was not used to bypass the failed step.
