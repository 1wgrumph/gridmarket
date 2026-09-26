# Integration plan: GridMarket hackathon MVP (Integration Engineer, planning session)

Lifecycle GM-2026-09-25. Role: `integration_engineer` planning session (Claude
Code, Claude Opus 5.5), delta re-issue after DEC-GM-021 and DEC-GM-022.
Method: Bearing Lite `integration-engineer` 1.1.5 and AlphaZede
`integration-engineering` (planning session only: no assembly, no merge, no
product). Standards: ISO/IEC/IEEE 24748-6 cited by metadata only
(SRC-EMV-24748-6); NASA Systems Engineering Handbook Appendix H named, not
copied.

Supporting file, not a canonical artifact. The Plan Integrator copies the
`integration_plan` JSON block below mechanically into `implementation.json`.
Command IDs come from `specialists/slice-graph.md`. The Planning Test Engineer
finalizes them in `seit.json`. When `seit.json` changes an ID or pass rule,
`seit.json` wins and this plan follows it.

## Owner changes applied by Planning and Design (DEC-GM-023..026)

The Integration Engineer planning session wrote this plan. Planning and Design
applied the owner changes from the integrated approval gate to the text and the
JSON block below; the IE session did not re-run.

- DEC-GM-025: the cap is 4 lanes. The red-test lanes lonestar (S10),
  adversary (S13), stretch (S15), and ml (S22) branch from the S01 exit in
  wave 2. Before each wave 3 implementation slice, the lane's implementer
  merges the recorded S09 exit (`lane-ml`: the S16 exit) into the lane with
  `--no-ff` (lane sync). That merge commit is the slice's CMD-WRITESET base.
  PROC-ASSEMBLY write-set checks are unchanged (CF-22).
- DEC-GM-023: every slice exits with a commit on its lane branch. Each IE
  slice (S09, S12, S18) ends with a PR `gridmarket/integration` → `main`,
  merged with a merge commit and no review. The Reviewer runs once, at
  Lifecycle cadence, on the integrated candidate at about Sat 2026-09-26
  22:00 CDT. OD-WORKER-LANDING now applies from the S09 phase PR (CF-23).
- DEC-GM-024 (lane profiles) and DEC-GM-026 (LICENSE holders) change no
  assembly rule.

## Return

- **Status:** `GAPS`
- **Verdict:** `PLAN_READY` for the assembly strategy over the current graph
  (S01 to S25, lanes foundation, worker, market, data, ui, spec, lonestar,
  adversary, stretch, rust, ml). CF-01 to CF-12 are resolved as applied by
  Planning and Design. This delta adds CF-13 to CF-21. Four need a
  Planning and Design text correction before the affected wave dispatches:
  CF-13 (the cap of 3 lanes is exceeded across waves), CF-16 (two hard edges
  gate a whole assembly slice), CF-18 (NWS polling from every smoke stack),
  and CF-15 (S18 goal wording). CF-19 is a conditional owner decision at the
  freeze.
- **candidate_ref:** none. This is a planning session and no integrated
  candidate exists. Planning revision read: `0bfa50a300fe79a2b2722854438e7915aec158dc`
  on `gridmarket/lifecycle-setup`, with `design.md` and `specialists/` still
  untracked in the owner checkout (CF-21). External item read with `git show`
  only: `origin/jordaaan` at `4853e51b2a5d8564631946e688e53802f83a7ab8`.
- **changed_paths:** `docs/plans/2026-09-25-gridmarket/specialists/integration-plan.md`
- **tests:** `python3` JSON parse and key check of the `integration_plan`
  block. Read-only observations: `git merge-base HEAD origin/jordaaan` is
  `a63c8d2`; `git diff --name-only a63c8d2 origin/jordaaan` lists only
  `ercot-hackathon/**` (9 paths); the `712f63a` tree equals the `a63c8d2`
  tree; `gitleaks git --log-opts=a63c8d2..origin/jordaaan` scanned 2 commits,
  no leaks (gitleaks 8.30.1); Node v22.23.2 (module syntax detection is on by
  default, so `node --test` can import `ercot-hackathon/src/index.js` without a
  `package.json`). No product tests exist. Nothing was assembled.
- **findings:** CF-01 to CF-21 in `concurrency_findings`.
- **blocker:** none for the plan. Wave 2 dispatch needs the CF-13 cap rule
  (otherwise 4 lanes run while the worker lane is still active). S12 and S09
  dispatch need the CF-16 edge change to keep the cut-offs meaningful.

## Input drift observed

- The ERCOT data edge is now Jordan's Cloudflare Worker (DEC-GM-021). The
  market holds no ERCOT credentials. The owner's `.env` holds
  `GRIDMARKET_WORKER_URL` and `GRIDMARKET_WORKER_KEY`. The earlier
  owner-registered ERCOT key dependency (OWN-ERCOT-KEY) is superseded by
  OWN-WORKER-ENV and the Jordan dependencies below.
- `origin/jordaaan` is at `4853e51` (`bae0a16` plus the God's Eye view). PR #3
  (`jordaaan` into `main`) is open. `origin/main` is at `712f63a`.
- The S23 goal still says "when ERCOT key exists" (CF-20).

## Items and versions

An item is one lane branch at one recorded **exit commit**. The exit commit is
the lane tip after the named slice passes every slice command. The Coordinator
records it and hands it to the IE. A merge consumes that exact SHA, never a
moving branch name. If the lane tip moves after handoff, the IE ignores the new
commits until a new exit SHA is handed over.

| Item | Branch | Base | Exit commit consumed | Merged by step |
|---|---|---|---|---|
| foundation | `gridmarket/lane-foundation` | planning revision | S01 exit | S09-A |
| market | `gridmarket/lane-market` | S01 exit | S08 exit (contains S02, S05) | S09-B |
| data | `gridmarket/lane-data` | S01 exit | S06 exit (contains S03) | S09-C |
| ui | `gridmarket/lane-ui` | S01 exit | S07 exit (contains S04) | S09-D |
| worker | `gridmarket/lane-worker` | `origin/jordaaan` at `4853e51` | S25 exit (contains S24 and Jordan's `bae0a16`, `4853e51`) | S09-E |
| jordan-worker (external) | `origin/jordaaan` | merge-base `a63c8d2` | `4853e51` (not authored by any slice; enters only through the worker item and through `origin/main` after PR #3) | S09-E, S18-E |
| lonestar | `gridmarket/lane-lonestar` | S01 exit; S09 exit merged before S11 | S11 exit (contains S10) | S12-A |
| spec | `gridmarket/lane-spec` | S01 exit | S21 exit (contains S19, S20) | S12-B |
| adversary | `gridmarket/lane-adversary` | S01 exit; S09 exit merged before S14 | S14 exit (contains S13) | S18-A |
| backtest | `gridmarket/lane-stretch` | S01 exit; S09 exit merged before S16 | S16 exit (contains S15) | S18-B |
| ml | `gridmarket/lane-ml` | S01 exit; S16 exit merged before S23 | S23 exit (contains S15, S16, S22) | S18-C |
| rust | `gridmarket/lane-rust` | S15 exit; S09 exit merged before S17 | S17 exit (contains S15) | S18-D |
| main | `origin/main` | — | SHA recorded at S18-E entry (contains PR #3 if merged) | S18-E |

The external item is identified by SHA only. Its identity check at S09-E:
`git diff --name-only $(git merge-base <integration-head> <S25-exit>) <S25-exit>`
lists only `ercot-hackathon/**`. The write-set check for the agent-authored
part is `git log --name-only --format= <S25-exit> --not <jordaaan-sha-at-lane-base>`
against the S24 and S25 union (`ercot-hackathon/src/index.js`,
`ercot-hackathon/wrangler.jsonc`, `ercot-hackathon/README.md`,
`ercot-hackathon/test/security.test.mjs`).

## Compatibility and interface checks (every merge step)

1. **Frozen-contract check.** Run `git diff --name-only <integration-head>...<exit-sha> --
   backend/gridmarket_server/contracts.py backend/gridmarket_server/schema.sql
   backend/gridmarket_server/main.py backend/pyproject.toml backend/uv.lock
   dashboard/package.json dashboard/package-lock.json dashboard/src/api.ts`.
   The output must be empty for every lane after foundation. A non-empty diff
   is `CONTRACT_STOP`: do not merge, and return it to Planning and Design as a
   named delta.
2. **Write-set check.** Run CMD-WRITESET over `<lane-base>..<exit-sha>`
   against the union of that lane's slice write sets. For the worker lane,
   exclude commits reachable from the recorded `jordaaan` SHA (see Items). A
   path outside the union returns the lane to its implementer.
3. **Merge.** Run `git merge --no-ff <exit-sha>` on `gridmarket/integration`.
   The write sets are disjoint, so any non-whitespace conflict means a
   write-set violation: run `git merge --abort` and return the lane.
4. **Interface exercise.** This is part of PROC-ASSEMBLY, against the CMD-SMOKE
   stack (no `GRIDMARKET_WORKER_URL`). Check that `/openapi.json` contains
   every CONTRACT-GM-API path available at that phase (admin paths only from
   S18-A). Check the error body shape `{"error":{"code","message"}}` on a 401
   and a 400 (IDEMPOTENCY_KEY_REQUIRED). Check `/v1/providers` against the
   expected registry and that `/v1/market/status` answers. From S09-B, bots
   produce orders. From S09-C, `/v1/signals` answers empty or `stale` with
   `age_s` and the poller has not started. From S09-D, `/` serves the
   dashboard. From S09-E, CMD-TEST-WORKER exercises CONTRACT-GM-WORKER
   behavior against stubs (401, 404, 429, upstream budget, snapshot retry).
   An interface-completeness-profile pass is structural completeness only,
   never compatibility or runtime proof.
5. **Post-step V&V.** Run the commands in the step's `post_step_vv`, on the
   merge commit, in the integration worktree. AC-GM-LANE-02 requires the
   backend tests, the dashboard tests and build, and the compose smoke to pass
   before the next merge.

## Authorized glue

**None in product paths.** The IE may write only:

- `--no-ff` merge commits of recorded exit SHAs, and at S18-E of the recorded
  `origin/main` SHA, into `gridmarket/integration`
- revert commits (`git revert -m 1 <merge>`) and revert-of-revert commits
  during recovery
- its evidence files `docs/plans/2026-09-25-gridmarket/evidence/assembly-phase-1.md`,
  `assembly-phase-2.md`, and `assembly-stretch.md`, committed on the
  integration branch
- non-force pushes of `gridmarket/integration` to `origin`
- at the S09, S12, and S18 exits, a PR `gridmarket/integration` → `main`,
  merged with a merge commit once any required checks are green, with no
  review (DEC-GM-023); held while OD-WORKER-LANDING is open

It may resolve a conflict only when both sides differ in whitespace alone.
Every other conflict, code edit, configuration edit (including setting
`GRIDMARKET_ENGINE`), test edit, or dependency edit returns to the owning lane.
A contract edit returns to Planning and Design. The IE never pushes to
`jordaaan` or directly to `main`, never comments on or merges PR #3, and never
deploys the Worker.

## Stubs and simulators

- ERCOT Worker and NWS fixtures (`backend/tests/fixtures/ercot/`,
  `fixtures/nws/`, `fixtures/ercot_history/`, `fixtures/ml/`) are test-only
  (DEC-GM-014). The live data path has no fixture loader. With no
  `GRIDMARKET_WORKER_URL`, the poller does not start and signals are served
  empty or stale. That is product behavior, not a stub.
- The S24 tests stub the Worker `env` (in-memory `CACHE`, sliding-window
  `RATE_LIMITER` and `ERCOT_BUDGET`) and `globalThis.fetch`. They never call
  ERCOT or the deployed Worker.
- The S01 placeholder modules (including `nws.py`) let `main.py` import in
  every lane before the owning lane lands. S05 and S06 replace them.
- The dashboard vitest tests use `dashboard/src/test-fixtures.json`.
- The engine falls back to Python when the Rust extension is absent.
- `base_sim` and `lonestar` are product simulators, not integration stubs.

## Shared runtime resources (assembly rules)

- **ERCOT Worker budget:** the Worker owns the ERCOT account budget
  (upstream guard 25 per 60 s, AC-GM-EDGE-03). Market callers share the
  Worker's per-client limit of 30 per 60 s under one market key: poller ≤ 12,
  backtest ≤ 5, ML ≤ 5. The demo stack (project `gridmarket`, port 8000,
  integration worktree, owner `.env`) is the only process that holds
  `GRIDMARKET_WORKER_KEY` and runs the poller. PROC-ERCOT-LIVE-CHECK runs only
  while the demo poller is stopped. Backtest and ML live runs never run during
  recording. Jordan's public views draw on the same upstream budget, so a
  live 429 is a typed gap, not a product defect.
- **Smoke stacks:** CMD-SMOKE always runs without `GRIDMARKET_WORKER_URL`,
  with a unique project and port: `gm-smoke-integration`:18000 (IE),
  `gm-smoke-market`:18001 (S08), `gm-smoke-stretch`:18002 (S17, lane rust).
  A smoke run removes only its own project and never touches `gridmarket`.
  NWS polling from smoke stacks is open (CF-18).
- **SQLite:** the demo uses the project-scoped `gm-data` volume. Tests use
  pytest `tmp_path`. Nothing writes a fixed absolute DB path.
- **Integration branch:** only IE steps write it, one step at a time.
- **`jordaaan` and PR #3:** written by Jordan and by the S25 PR merge only.

## Owner and human dependencies

| Dependency | Holder | Blocks | If absent |
|---|---|---|---|
| OWN-WORKER-ENV: `.env` at the integration worktree root with `GRIDMARKET_WORKER_URL`, `GRIDMARKET_WORKER_KEY` (equal to Jordan's `MARKET_KEY`, exchanged owner-to-Jordan out of band), `GRIDMARKET_ADMIN_KEY`, `GRIDMARKET_CORS_ORIGIN` | owner | PROC-ERCOT-LIVE-CHECK, live data in PROC-ACCEPT-P1/P2, backtest and ML live runs | typed gap `WORKER_ENV_ABSENT`; phase 1 checkpoint stands without live data |
| HUM-JORDAN-PR: merge or decline the lane-worker PR into `jordaaan`, with a merge commit (not squash or rebase) | Jordan | phase PRs to `main` (first at S09); S18-E clean merge; PR #3 content | declined or open when a phase PR is ready: OD-WORKER-LANDING holds the phase PRs (CF-19, CF-23) |
| HUM-JORDAN-DEPLOY: `wrangler secret put MARKET_KEY`, create the rate-limit bindings, `wrangler deploy` the fixed Worker, report the deployed source SHA and version ID | Jordan | PROC-ERCOT-LIVE-CHECK and PROC-ACCEPT-P1 (target Sat 14:00) | typed gap `WORKER_FIX_NOT_DEPLOYED`; S09 closes without the live check; acceptance waits (running acceptance on the unfixed Worker is OD-WORKER-UNFIXED, owner) |
| HUM-JORDAN-EDITS: no edits to `ercot-hackathon/src/index.js`, `wrangler.jsonc`, `README.md` on `jordaaan` until the lane PR merges, or tell the Coordinator | Jordan | S25 PR merge, S18-E | CF-14 procedure |
| PR #3 merged into `main` | Jordan or owner | S18-E content | S18-E merges `origin/main` as it is; CF-19 |
| OWN-TUNNEL | owner | PROC-ACCEPT-P1/P2, recording | acceptance recorded not run |
| OWN-PUBLICATION (public flip after CMD-SECRETS full history and LICENSE) | owner | public codebase link by Sun 11:00 | IE hands over the AC-GM-SEC-01 result |
| OWN-JUDGE-KEYS | owner | judge quickstart | seeded accounts only |
| OD-ORDER | owner | S18-A..D ahead of an unclosed S12-A | strict order |

The IE never reads, prints, or copies `.env` values, `MARKET_KEY`, or tunnel
credential files. It only runs processes that consume them.

## Concurrency proof: independent verification

**Pairwise write-set disjointness: confirmed.**

- Wave 1: foundation {S01} and worker {S24, S25}. The worker writes only four
  `ercot-hackathon/` paths; S01 writes none (its `.gitignore` is the root
  file, not `ercot-hackathon/.gitignore`). The two lanes also have different
  bases (planning revision vs `4853e51`); the merge-base of the two is
  `a63c8d2`, and Jordan's side changes only `ercot-hackathon/**`. 2 lanes.
- Wave 2: market {S02, S05, S08}, data {S03, S06} then spec {S19, S20, S21}
  (slot S06 --> S19), ui {S04, S07}, and the red-test lanes lonestar {S10},
  adversary {S13}, stretch {S15}, ml {S22} (DEC-GM-025). `README.md` (S08,
  root) and `ercot-hackathon/README.md` (S25) are different paths. `tools/`,
  `spec/`, `skills/spec-*` are spec-only. The red-test write sets
  (`test_providers.py`, `test_adversarial.py`, `test_backtest.py`,
  `test_matching_parity.py`, `fixtures/ercot_history/`,
  `bench/bench_matching.py`, `test_ml.py`, `fixtures/ml/`) appear in no other
  lane. At most 4 running lanes.
- Wave 3: lonestar {S11} then ml {S23} (slot S11 --> S23), adversary {S14}
  then rust {S17} (slot S14 --> S17), stretch {S16}; the spec lane may still
  run. S11 owns `seed.py` and `providers/*`; S14 owns `market.py`, `api.py`,
  `adversary.py`; S17 owns `deploy/*`, `rust/*`, `bench/results.md`; S23 owns
  `ml.py`, `ml_data.py`, `docs/ml-report.md`. At most 4 running lanes.
- Shared lineage: rust contains S15 and ml contains S15 and S16. The same
  commits reach the integration branch more than once, which merges cleanly,
  but it creates merge-order dependencies (CF-15). Every wave 3 lane also
  contains the S09 exit through its lane sync merge; those commits are already
  on the integration branch.

**Defect:** the proof counts lanes per wave. Dependencies let the worker lane
overlap wave 2 and the spec lane overlap wave 3, so 4 lanes can run (CF-13).
Resolved: the cap counts running lanes across waves (CF-13), and DEC-GM-025
raises it to 4.

## Lifecycle-end integrated technical assessment (execution session)

A fresh IE execution session runs the assessment on the frozen
`integration_engineer.execution` route with its fallbacks. It must not descend
from any lane author, and it assesses the final candidate at Lifecycle
cadence. Its receipts are diagnostic and do not self-certify. It hands the
candidate to the Assurance Test Engineer. Inputs are in
`lifecycle_assessment_inputs`.

```json integration_plan
{
  "branches": {
    "integration": {"name": "gridmarket/integration", "created_from": "the owner-approved planning revision commit on gridmarket/lifecycle-setup (containing the approved five-artifact package, design.md, and gridmarket-technical-plan.md; CF-21)", "writers": ["Integration Engineer (execution route) only"], "remote": "origin https://github.com/1wgrumph/gridmarket.git; non-force push after every green step and after every revert"},
    "lanes": [
      {"lane": "foundation", "branch": "gridmarket/lane-foundation", "slices": ["S01"], "created_from": "gridmarket/integration at creation (planning revision)", "exit_commits": {"S01": "recorded by Coordinator at S01 green"}},
      {"lane": "worker", "branch": "gridmarket/lane-worker", "slices": ["S24", "S25"], "created_from": "origin/jordaaan at 4853e51b2a5d8564631946e688e53802f83a7ab8 (DEC-GM-022); read with git show, never checked out in the owner checkout", "exit_commits": {"S25": "recorded by Coordinator at S25 green, with the PR URL into jordaaan and the jordaaan SHA the lane is based on"}},
      {"lane": "market", "branch": "gridmarket/lane-market", "slices": ["S02", "S05", "S08"], "created_from": "S01 exit commit", "exit_commits": {"S08": "recorded by Coordinator at S08 green"}},
      {"lane": "data", "branch": "gridmarket/lane-data", "slices": ["S03", "S06"], "created_from": "S01 exit commit", "exit_commits": {"S06": "recorded by Coordinator at S06 green"}},
      {"lane": "ui", "branch": "gridmarket/lane-ui", "slices": ["S04", "S07"], "created_from": "S01 exit commit", "exit_commits": {"S07": "recorded by Coordinator at S07 green"}},
      {"lane": "spec", "branch": "gridmarket/lane-spec", "slices": ["S19", "S20", "S21"], "created_from": "S01 exit commit (wave 2 lane; starts after S06 by slot edge)", "exit_commits": {"S21": "recorded by Coordinator at S21 green"}},
      {"lane": "lonestar", "branch": "gridmarket/lane-lonestar", "slices": ["S10", "S11"], "created_from": "S01 exit commit (wave 2 red-test lane, DEC-GM-025); before S11 the lane merges the recorded S09 exit SHA (--no-ff, lane sync)", "exit_commits": {"S10": "recorded by Coordinator at S10 red-verified", "S11": "recorded by Coordinator at S11 green"}},
      {"lane": "adversary", "branch": "gridmarket/lane-adversary", "slices": ["S13", "S14"], "created_from": "S01 exit commit (wave 2 red-test lane, DEC-GM-025); before S14 the lane merges the recorded S09 exit SHA (--no-ff, lane sync)", "exit_commits": {"S13": "recorded by Coordinator at S13 red-verified", "S14": "recorded by Coordinator at S14 green"}},
      {"lane": "stretch", "branch": "gridmarket/lane-stretch", "slices": ["S15", "S16"], "created_from": "S01 exit commit (wave 2 red-test lane, DEC-GM-025); before S16 the lane merges the recorded S09 exit SHA (--no-ff, lane sync)", "exit_commits": {"S15": "recorded by Coordinator at S15 red-verified (base of lane-rust)", "S16": "recorded by Coordinator at S16 green (backtest item; base of lane-ml)"}},
      {"lane": "rust", "branch": "gridmarket/lane-rust", "slices": ["S17"], "created_from": "S15 exit commit on gridmarket/lane-stretch; before S17 the lane merges the recorded S09 exit SHA (--no-ff, lane sync, DEC-GM-025)", "exit_commits": {"S17": "recorded by Coordinator at S17 green (Rust item)"}},
      {"lane": "ml", "branch": "gridmarket/lane-ml", "slices": ["S22", "S23"], "created_from": "S01 exit commit (wave 2 red-test lane, DEC-GM-025); before S23 the lane merges the recorded S16 exit SHA (contains the S09 exit; --no-ff, lane sync)", "exit_commits": {"S22": "recorded by Coordinator at S22 red-verified", "S23": "recorded by Coordinator at S23 green (ML item)"}}
    ],
    "external": [
      {"item": "jordan-worker", "ref": "origin/jordaaan", "sha": "4853e51b2a5d8564631946e688e53802f83a7ab8", "contains": ["bae0a16 Add ercot-hackathon Worker", "4853e51 Add God's Eye ERCOT globe view"], "merge_base_with_planning": "a63c8d2e286c8b9bfe686552af6b430cbfc2a07e", "paths": "ercot-hackathon/** only (9 paths, verified with git diff --name-only a63c8d2 4853e51)", "secrets_precheck": "gitleaks 8.30.1 over a63c8d2..4853e51: 2 commits, no leaks", "owner": "Jordan (human lane, not a Bearing role)", "enters_via": ["S09-E (inside the S25 exit)", "S18-E (origin/main after PR #3)"]},
      {"item": "main", "ref": "origin/main", "sha": "712f63a4252ee9db5db7f9d403e64564ab44dca6 at planning time; the SHA merged is recorded at S18-E entry", "enters_via": ["S18-E"]}
    ],
    "rule": "A merge consumes the recorded exit SHA (or recorded origin/main SHA), never a moving branch tip. No force-push, no history rewrite, no git switch in the owner checkout. The IE never pushes to jordaaan or directly to main and never merges PR #3; main changes through the phase PRs at the S09, S12 and S18 exits (DEC-GM-023). Lane sync merges (DEC-GM-025) are made by the lane's implementer in the lane worktree, never on gridmarket/integration."
  },
  "worktrees": {
    "rule": "Every linked worktree is /home/spectre/alphazede/worktrees/base-gridmarket-<lane>; never hidden directories or /tmp. Agents create them without asking at the lane's start. The owner checkout /home/spectre/alphazede/Hackathons/Base keeps branch gridmarket/lifecycle-setup.",
    "integration": "/home/spectre/alphazede/worktrees/base-gridmarket-integration",
    "lanes": {
      "foundation": "/home/spectre/alphazede/worktrees/base-gridmarket-foundation",
      "worker": "/home/spectre/alphazede/worktrees/base-gridmarket-worker",
      "market": "/home/spectre/alphazede/worktrees/base-gridmarket-market",
      "data": "/home/spectre/alphazede/worktrees/base-gridmarket-data",
      "ui": "/home/spectre/alphazede/worktrees/base-gridmarket-ui",
      "spec": "/home/spectre/alphazede/worktrees/base-gridmarket-spec",
      "lonestar": "/home/spectre/alphazede/worktrees/base-gridmarket-lonestar",
      "adversary": "/home/spectre/alphazede/worktrees/base-gridmarket-adversary",
      "stretch": "/home/spectre/alphazede/worktrees/base-gridmarket-stretch",
      "rust": "/home/spectre/alphazede/worktrees/base-gridmarket-rust",
      "ml": "/home/spectre/alphazede/worktrees/base-gridmarket-ml"
    },
    "env_file": "Only the integration worktree root holds the owner's real .env (owner-placed). Lane worktrees have no .env; compose tolerates its absence (env_file required: false). The worker worktree holds no Worker secrets; S24 tests use stub env values."
  },
  "steps": [
    {
      "id": "S09-A", "slice": "S09", "order": 1,
      "merges": {"lane": "foundation", "branch": "gridmarket/lane-foundation", "exit_commit_of": "S01"},
      "entry_criteria": ["S01 exit SHA recorded; S01 commands CMD-SETUP, CMD-LINT, CMD-TEST-CONTRACTS, CMD-DEPSCAN, CMD-SECRETS, CMD-WRITESET passed in the lane on that SHA", "gridmarket/integration exists at the approved planning revision; integration worktree clean"],
      "post_step_vv": ["CMD-SETUP", "CMD-LINT", "CMD-TEST-CONTRACTS", "CMD-TEST-DASH", "CMD-SECRETS", "PROC-ASSEMBLY"],
      "rollback": "git revert -m 1 <S09-A merge>; rerun CMD-TEST-CONTRACTS on the revert commit; return S01 to the foundation lane; wave 2 lanes are unaffected (they branch from the S01 exit SHA) but every later S09 merge waits for a green S09-A",
      "exit": "Merge commit green on every listed command; frozen-file blob SHAs (contracts.py, schema.sql, main.py, pyproject.toml, uv.lock, package.json, package-lock.json, api.ts) recorded as the contract baseline in assembly-phase-1.md"
    },
    {
      "id": "S09-B", "slice": "S09", "order": 2,
      "merges": {"lane": "market", "branch": "gridmarket/lane-market", "exit_commit_of": "S08"},
      "entry_criteria": ["S09-A closed green", "S08 exit SHA recorded; the S02, S05, S08 commands passed in the lane (CMD-RED-GREEN, CMD-TEST-MARKET, CMD-COVERAGE, CMD-SMOKE on gm-smoke-market:18001, CMD-LINT, CMD-WRITESET)", "frozen-contract diff empty against the S09-A baseline", "lane write-set check passes against the union of S02, S05, S08"],
      "post_step_vv": ["CMD-SETUP", "CMD-LINT", "CMD-TEST-ALL", "CMD-TEST-DASH", "CMD-SMOKE (project gm-smoke-integration, port 18000, no GRIDMARKET_WORKER_URL)", "CMD-SECRETS", "PROC-ASSEMBLY"],
      "rollback": "git revert -m 1 <S09-B merge>; rerun CMD-TEST-ALL and CMD-SMOKE on the revert commit to confirm the S09-A state; return the market lane with the failing command output",
      "exit": "Green; smoke shows /v1/market/status healthy, openapi paths match the phase 1 CONTRACT-GM-API, bots submit orders, /v1/providers lists base_sim, CORS allows only GRIDMARKET_CORS_ORIGIN on public reads"
    },
    {
      "id": "S09-C", "slice": "S09", "order": 3,
      "merges": {"lane": "data", "branch": "gridmarket/lane-data", "exit_commit_of": "S06"},
      "entry_criteria": ["S09-B closed green", "S06 exit SHA recorded; the S03 and S06 commands passed in the lane (CMD-RED-GREEN, CMD-TEST-DATA, CMD-COVERAGE, CMD-LINT, CMD-WRITESET)", "frozen-contract diff empty", "lane write-set check passes against the union of S03, S06"],
      "post_step_vv": ["CMD-LINT", "CMD-TEST-ALL", "CMD-TEST-DASH", "CMD-SMOKE (gm-smoke-integration:18000, no GRIDMARKET_WORKER_URL)", "CMD-SECRETS", "PROC-ASSEMBLY"],
      "rollback": "git revert -m 1 <S09-C merge>; rerun CMD-TEST-ALL and CMD-SMOKE on the revert commit; return the data lane",
      "exit": "Green; with no GRIDMARKET_WORKER_URL the smoke shows the Worker poller not started and /v1/signals and /v1/predictions answer (empty or stale with age_s) with the disclaimer and no key text in any response or log"
    },
    {
      "id": "S09-D", "slice": "S09", "order": 4,
      "merges": {"lane": "ui", "branch": "gridmarket/lane-ui", "exit_commit_of": "S07"},
      "entry_criteria": ["S09-C closed green", "S07 exit SHA recorded; the S04 and S07 commands passed in the lane (CMD-TEST-DASH incl. production build, CMD-WRITESET)", "frozen-contract diff empty (dashboard/src/api.ts, package.json, package-lock.json unchanged)"],
      "post_step_vv": ["CMD-LINT", "CMD-TEST-ALL", "CMD-TEST-DASH", "CMD-SMOKE (gm-smoke-integration:18000)", "CMD-SECRETS", "PROC-ASSEMBLY"],
      "rollback": "git revert -m 1 <S09-D merge>; rerun CMD-TEST-DASH and CMD-SMOKE on the revert commit; return the ui lane",
      "exit": "Green; smoke serves the dashboard at / from the image and the page polls the API"
    },
    {
      "id": "S09-E", "slice": "S09", "order": 5,
      "merges": {"lane": "worker", "branch": "gridmarket/lane-worker", "exit_commit_of": "S25"},
      "entry_criteria": ["S09-D closed green", "S25 exit SHA recorded with the jordaaan SHA it is based on and the PR URL into jordaaan; the S24 and S25 commands passed in the lane (CMD-RED-GREEN-WORKER with S24 red baseline and S25 green, CMD-TEST-WORKER incl. the burst case, CMD-WRITESET)", "external-item check: git diff --name-only $(git merge-base <integration-head> <S25-exit>) <S25-exit> lists only ercot-hackathon/**", "agent write-set check: git log --name-only --format= <S25-exit> --not <jordaaan-sha-at-lane-base> lists only ercot-hackathon/src/index.js, ercot-hackathon/wrangler.jsonc, ercot-hackathon/README.md, ercot-hackathon/test/security.test.mjs", "frozen-contract diff empty"],
      "post_step_vv": ["CMD-TEST-WORKER (node --test ercot-hackathon/test/, from the integration worktree root)", "CMD-TEST-ALL", "CMD-TEST-DASH", "CMD-SMOKE (gm-smoke-integration:18000)", "CMD-SECRETS (the merge brings Jordan's commits into scanned history)", "PROC-ASSEMBLY (AC-GM-RULE-02: the merged views under ercot-hackathon/public keep the label 'baseline rules · Jev gateway pending' and call no Jev engine)", "PROC-ERCOT-LIVE-CHECK only after HUM-JORDAN-DEPLOY and OWN-WORKER-ENV, with the demo poller stopped: one call per Worker route of DES-GM-ERCOT with the market key, one keyless /api/report call expecting 401, one non-allowlisted report expecting 404, no fresh parameter"],
      "rollback": "Red merge V&V: git revert -m 1 <S09-E merge>; rerun CMD-TEST-ALL and CMD-SMOKE on the revert commit; return the worker lane. The revert also removes Jordan's ercot-hackathon/ source; a later S18-E merge of origin/main will not restore it because the commits are already ancestors (CF-17), so re-entry uses revert-of-revert. Live-check failures do not revert: 401/404 on keyed calls is a key or allowlist mismatch returned to the worker lane (and Jordan for the deployed version); ERCOT outage or 429 is typed gap ERCOT_LIVE_UNAVAILABLE; a parser mismatch (RISK-GM-09) returns to the data lane via the re-entry procedure.",
      "exit": "Phase 1 demoable checkpoint recorded in evidence/assembly-phase-1.md: integration head SHA, code tree SHA, configuration identity (incl. jordaaan base SHA, S25 exit, PR URL and state, deployed Worker source SHA and version ID as reported by Jordan, or typed gap WORKER_FIX_NOT_DEPLOYED / WORKER_ENV_ABSENT); evidence committed and pushed; phase 1 PR gridmarket/integration -> main opened and merged with a merge commit, no review (DEC-GM-023; held while OD-WORKER-LANDING is open); wave 3 implementation lanes merge this commit (lane sync, DEC-GM-025); owner notified that PROC-ACCEPT-P1 is ready once the live check passed. If the live check is deferred, it reruns on this checkpoint when Jordan reports the deploy, before PROC-ACCEPT-P1, with no merge."
    },
    {
      "id": "S12-A", "slice": "S12", "order": 6,
      "merges": {"lane": "lonestar", "branch": "gridmarket/lane-lonestar", "exit_commit_of": "S11"},
      "entry_criteria": ["S09 closed (S09-E evidence committed)", "S11 exit SHA recorded by Sun 04:30 CDT; the S10 and S11 commands passed (CMD-RED-GREEN, CMD-TEST-PROVIDERS, CMD-TEST-ALL, CMD-WRITESET)", "frozen-contract diff empty", "lane write-set check passes against the union of S10, S11 (no api.py or market.py edits)", "does not wait for S21 (CF-16)"],
      "post_step_vv": ["CMD-LINT", "CMD-TEST-ALL", "CMD-TEST-PROVIDERS", "CMD-TEST-DASH", "CMD-SMOKE (gm-smoke-integration:18000)", "CMD-SECRETS", "PROC-ASSEMBLY"],
      "rollback": "git revert -m 1 <S12-A merge>; rerun CMD-TEST-ALL and CMD-SMOKE on the revert commit; the phase 1 checkpoint stays the demo candidate; return the lonestar lane",
      "exit": "Green; /v1/providers lists base_sim and lonestar with >= 20 LoneStar customers; phase 2 demoable checkpoint recorded in evidence/assembly-phase-2.md, committed and pushed; owner notified that PROC-ACCEPT-P2 is ready"
    },
    {
      "id": "S12-B", "slice": "S12", "order": 7,
      "merges": {"lane": "spec", "branch": "gridmarket/lane-spec", "exit_commit_of": "S21"},
      "entry_criteria": ["S12-A closed green, or lonestar dropped at cut-off (the spec merge does not need lonestar)", "S21 exit SHA recorded by Sun 04:30 CDT; the S19, S20, S21 commands passed (CMD-RED-GREEN, CMD-TEST-SPEC, CMD-SPEC-LINT, CMD-WRITESET)", "frozen-contract diff empty", "lane write-set check passes against the union of S19, S20, S21 (tools/tests/, tools/azdiagram/, tools/spec_build.py, tools/spec_lint.py, spec/template/, spec/gridmarket/, spec/GridMarket-Specification.md, skills/spec-*/)", "Graphviz and draw.io present on the host (version recorded)"],
      "post_step_vv": ["CMD-TEST-SPEC", "CMD-SPEC-LINT", "CMD-LINT", "CMD-TEST-ALL", "CMD-TEST-DASH", "CMD-SMOKE (gm-smoke-integration:18000)", "CMD-SECRETS", "PROC-ASSEMBLY"],
      "rollback": "git revert -m 1 <S12-B merge>; rerun CMD-TEST-ALL and CMD-SMOKE on the revert commit; the phase 2 checkpoint (S12-A) stays; return the spec lane or record it dropped at cut-off",
      "exit": "Green; the built specification and its figures are present at the merge commit; result appended to evidence/assembly-phase-2.md and pushed; then the phase 2 PR gridmarket/integration -> main is opened and merged with a merge commit, no review (DEC-GM-023; also after S12-B is reverted or the spec lane dropped)"
    },
    {
      "id": "S18-A", "slice": "S18", "order": 8,
      "merges": {"lane": "adversary", "branch": "gridmarket/lane-adversary", "exit_commit_of": "S14"},
      "entry_criteria": ["S12-A closed, or lonestar dropped at cut-off, or OD-ORDER allows merging ahead", "S14 exit SHA recorded by Sun 04:30 CDT; the S13 and S14 commands passed (CMD-RED-GREEN, CMD-TEST-ADVERSARY, CMD-TEST-ALL, CMD-WRITESET)", "frozen-contract diff empty", "lane write-set check passes against the union of S13, S14"],
      "post_step_vv": ["CMD-LINT", "CMD-TEST-ALL", "CMD-TEST-ADVERSARY", "CMD-TEST-DASH", "CMD-SMOKE (gm-smoke-integration:18000)", "CMD-SECRETS", "PROC-ASSEMBLY (admin halt/resume paths now present in openapi)"],
      "rollback": "git revert -m 1 <S18-A merge>; rerun CMD-TEST-ALL and CMD-SMOKE on the revert commit; record the adversary lane dropped if no green re-entry before Sun 04:30",
      "exit": "Green; anomalies appear at /v1/market/status; results appended to evidence/assembly-stretch.md and pushed"
    },
    {
      "id": "S18-B", "slice": "S18", "order": 9,
      "merges": {"lane": "stretch", "branch": "gridmarket/lane-stretch", "exit_commit_of": "S16"},
      "entry_criteria": ["Same S12 condition as S18-A; independent of S18-A (preferred order adversary then backtest when both are ready)", "S16 exit SHA recorded by Sun 04:30 CDT; the S15 and S16 commands passed (CMD-RED-GREEN, CMD-TEST-BACKTEST, CMD-WRITESET)", "At the S16 exit SHA the full backend suite is green without the Rust extension (parity Rust case skips, CF-06)", "frozen-contract diff empty"],
      "post_step_vv": ["CMD-LINT", "CMD-TEST-ALL", "CMD-TEST-BACKTEST", "CMD-SMOKE (gm-smoke-integration:18000)", "CMD-SECRETS", "PROC-ASSEMBLY"],
      "rollback": "git revert -m 1 <S18-B merge>; rerun CMD-TEST-ALL and CMD-SMOKE on the revert commit; S18-C (ML) is then skipped because ml.py needs backtest.py (CF-15)",
      "exit": "Green; backtest merged with fixture tests; any live backtest run needs OWN-WORKER-ENV, stays within 5 requests/min, and never runs during recording"
    },
    {
      "id": "S18-C", "slice": "S18", "order": 10,
      "merges": {"lane": "ml", "branch": "gridmarket/lane-ml", "exit_commit_of": "S23"},
      "entry_criteria": ["S18-B closed green and not reverted (lane-ml contains S16; after a backtest revert the ML merge would not restore backtest.py, CF-15)", "S23 exit SHA recorded by Sun 04:30 CDT; the S22 and S23 commands passed (CMD-RED-GREEN, CMD-TEST-ML, CMD-WRITESET)", "frozen-contract diff empty (the optional ml extra is already in S01's pyproject.toml and uv.lock)", "lane write-set check over <S16-exit>..<S23-exit> against the union of S22, S23"],
      "post_step_vv": ["CMD-TEST-ML", "CMD-LINT", "CMD-TEST-ALL", "CMD-TEST-DASH", "CMD-SMOKE (gm-smoke-integration:18000)", "CMD-SECRETS", "PROC-ASSEMBLY"],
      "rollback": "git revert -m 1 <S18-C merge>; rerun CMD-TEST-ALL and CMD-SMOKE on the revert commit; record the ML item dropped",
      "exit": "Green; docs/ml-report.md present (from one live run through the Worker, or marked fixture-only with typed gap WORKER_ENV_ABSENT); appended to evidence/assembly-stretch.md and pushed"
    },
    {
      "id": "S18-D", "slice": "S18", "order": 11,
      "merges": {"lane": "rust", "branch": "gridmarket/lane-rust", "exit_commit_of": "S17"},
      "entry_criteria": ["S18-B merged (green, even if later reverted); if backtest was never merged, S18-D is skipped because lane-rust carries S15's test_backtest.py without backtest.py, which turns CMD-TEST-ALL red (CF-15)", "S17 exit SHA recorded by Sun 04:30 CDT; S17 commands passed (CMD-RED-GREEN, CMD-TEST-PARITY with the extension built, CMD-BENCH, CMD-DEPSCAN for maturin/PyO3, CMD-SMOKE on gm-smoke-stretch:18002, CMD-WRITESET from the S17 lane sync merge commit)", "bench/results.md at the S17 exit SHA shows Rust orders/second strictly higher than Python on the identical workload; otherwise S18-D is skipped and recorded, not merged", "frozen-contract diff empty"],
      "post_step_vv": ["CMD-LINT", "CMD-TEST-ALL", "CMD-TEST-PARITY (inside the built image, extension present)", "CMD-SMOKE (gm-smoke-integration:18000; the engine is rust only if compose sets GRIDMARKET_ENGINE=rust)", "CMD-SECRETS", "PROC-ASSEMBLY"],
      "rollback": "git revert -m 1 <S18-D merge>; rerun CMD-TEST-ALL and CMD-SMOKE on the revert commit (image rebuilt without the Rust stage); record the Rust item dropped",
      "exit": "Green; configuration identity records GRIDMARKET_ENGINE and the extension build; Reverify handoff to the Assurance Test Engineer for the built PyO3 extension (the only binary artifact)"
    },
    {
      "id": "S18-E", "slice": "S18", "order": 12,
      "merges": {"lane": "main", "branch": "origin/main", "exit_commit_of": "origin/main SHA recorded at entry (PR #3 merged or not, recorded)"},
      "entry_criteria": ["Every earlier step is closed green, reverted, skipped, or dropped with a recorded reason", "Not later than Sun 06:00 CDT", "git fetch origin; record origin/main SHA, PR #3 state, and the lane-worker PR state (merged with merge commit, merged by squash or rebase, open, or declined)", "git diff --name-only <integration-head>...<main-sha> lists only ercot-hackathon/** and docs/plans/** (anything else is AN-CONTRACT or AN-WRITESET)", "frozen-contract diff empty"],
      "post_step_vv": ["CMD-TEST-WORKER", "CMD-TEST-ALL", "CMD-TEST-DASH", "CMD-SMOKE (gm-smoke-integration:18000)", "CMD-SECRETS (full Git history; AC-GM-SEC-01)", "PROC-ASSEMBLY (LICENSE present at the root; .env untracked; views label per AC-GM-RULE-02)"],
      "rollback": "Non-whitespace conflict in ercot-hackathon/ (Jordan's later edits vs S25, CF-14): git merge --abort; the candidate is the pre-merge head; return the conflict to the worker lane Product Implementer as a repair on gridmarket/lane-worker (new exit SHA, re-entered at S18-E) and tell Jordan; unresolved by the freeze is CF-19. Red after merge: revert the merge and repeat S18-E without it. If the final V&V is red for another reason: revert the most recent merge step and repeat; the fallback candidate is the last green checkpoint (phase 2, else phase 1).",
      "exit": "Final integrated candidate declared in evidence/assembly-stretch.md with its configuration identity, dropped-lane list, origin/main SHA, and PR #3 state; committed and pushed; handed to the Assurance Test Engineer (CANDIDATE_READY from the execution session). The S18 phase PR gridmarket/integration -> main (the landing PR) is opened and merged with a merge commit, no review, before the Sun 07:00 CDT freeze (DEC-GM-023), unless OD-WORKER-LANDING holds it."
    }
  ],
  "configuration_identity": {
    "record_at": "every step exit, in that step's evidence file",
    "fields": {
      "integration_head_sha": "git rev-parse gridmarket/integration",
      "code_tree_sha": "git rev-parse <merge-or-revert-sha>^{tree} (evidence commits touch only docs/plans/**)",
      "lane_exit_shas": "every exit SHA merged so far, and every exit SHA reverted, skipped, or dropped",
      "external_shas": "jordaaan base SHA of the worker lane (4853e51 unless CF-14 moved it), origin/main SHA merged at S18-E",
      "worker_delivery": "lane-worker PR URL and state into jordaaan; PR #3 state; deployed Worker source SHA and Cloudflare version ID as reported by Jordan (the IE has no Cloudflare access; the live check's 401/404 probes are the behavioral evidence)",
      "frozen_contract_blobs": "git rev-parse <sha>:<path> for backend/gridmarket_server/contracts.py, schema.sql, main.py, backend/pyproject.toml, backend/uv.lock, dashboard/package.json, dashboard/package-lock.json, dashboard/src/api.ts",
      "compose_file": "deploy/compose.yaml and its blob SHA; compose project name used (gridmarket for the demo, gm-smoke-integration for V&V)",
      "dockerfile": "deploy/Dockerfile blob SHA",
      "image": "docker image inspect --format '{{.Id}}' <project>-app for the image built from code_tree_sha",
      "engine": "GRIDMARKET_ENGINE effective value: python unless S18-D merged with a benchmark gain",
      "provider_registry": "the adapter list from providers/__init__.py and GET /v1/providers: [base_sim] after S09, [base_sim, lonestar] after S12-A",
      "env_var_names_only": ["GRIDMARKET_WORKER_URL", "GRIDMARKET_WORKER_KEY", "GRIDMARKET_ADMIN_KEY", "GRIDMARKET_CORS_ORIGIN", "GRIDMARKET_ENGINE", "GRIDMARKET_PORT", "GRIDMARKET_API_KEY", "GRIDMARKET_URL", "COMPOSE_PROJECT_NAME", "plus every other name listed in .env.example at code_tree_sha, recorded by name only"],
      "external_credentials_names_only": ["Cloudflare named-tunnel credential file (outside the repository, owner-held)", "Worker secrets MARKET_KEY, ERCOT_USERNAME, ERCOT_PASSWORD, ERCOT_SUBSCRIPTION_KEY (Jordan-held on Cloudflare)"],
      "toolchain": "python, uv, node, npm, docker, docker compose, gitleaks, graphviz, draw.io (if S12-B), cargo and maturin (if S18-D) versions"
    },
    "never_record": "credential values, .env contents, MARKET_KEY or GRIDMARKET_WORKER_KEY values, tokens, API key plaintext, tunnel credential contents"
  },
  "authorized_glue": {
    "product_paths": "none",
    "allowed_writes": ["git merge --no-ff <recorded exit SHA> merge commits on gridmarket/integration", "git merge --no-ff <recorded origin/main SHA> at S18-E", "git revert -m 1 <merge> revert commits and revert-of-revert commits during recovery", "evidence files docs/plans/2026-09-25-gridmarket/evidence/assembly-phase-1.md, assembly-phase-2.md, assembly-stretch.md (S09, S12, S18 write sets) committed on gridmarket/integration", "non-force git push origin gridmarket/integration", "at the S09, S12 and S18 exits: open a PR gridmarket/integration -> main and merge it with a merge commit once any required checks are green; no review on phase PRs (DEC-GM-023); not while OD-WORKER-LANDING is open"],
    "conflicts": "Resolve only hunks whose sides differ in whitespace alone. Any other conflict: git merge --abort and return it to the owning lane (write sets are disjoint, so a lane conflict signals a write-set violation; an S18-E conflict in ercot-hackathon/ goes to the worker lane).",
    "forbidden": ["editing product, test, configuration, dependency, or contract files", "setting GRIDMARKET_ENGINE or any compose value", "weakening, skipping, or deselecting tests", "force-push, reset --hard, history rewrite, git switch in the owner checkout", "reading or printing .env, MARKET_KEY, or tunnel credentials", "pushing to jordaaan or directly to main, squash or rebase merge of a phase PR, merging or commenting on PR #3, deploying the Worker", "tunnel start, public flip"]
  },
  "stubs": [
    {"id": "STUB-WORKER-FIXTURES", "what": "backend/tests/fixtures/ercot/ (Worker snapshot and report-route shapes), fixtures/nws/, fixtures/ercot_history/, fixtures/ml/", "scope": "tests only (DEC-GM-014)", "removed_by": "never in the live path; the live path has no fixture loader"},
    {"id": "STUB-WORKER-ENV", "what": "ercot-hackathon/test/security.test.mjs stub env (in-memory CACHE, sliding-window RATE_LIMITER and ERCOT_BUDGET, test secrets) and stub globalThis.fetch counting ERCOT calls", "scope": "CMD-TEST-WORKER only", "removed_by": "never; the deployed Worker uses real bindings (Jordan)"},
    {"id": "STUB-S01-PLACEHOLDERS", "what": "placeholder market.py, api.py, ercot.py, nws.py, scoring.py, seed.py, providers/__init__.py, providers/base_sim.py that satisfy contracts.py with empty behavior", "scope": "wave 1 foundation, so main.py imports in every lane", "removed_by": "S05 (market, api, seed, providers) and S06 (ercot, nws, scoring)"},
    {"id": "STUB-DASH-FIXTURES", "what": "dashboard/src/test-fixtures.json", "scope": "vitest only", "removed_by": "never; the live page uses api.ts"},
    {"id": "SIM-NO-WORKER", "what": "app with no GRIDMARKET_WORKER_URL: Worker poller not started, signals empty or stale", "scope": "every CMD-SMOKE run and every lane", "removed_by": "owner .env in the integration worktree for the demo stack and PROC-ERCOT-LIVE-CHECK"},
    {"id": "SIM-ENGINE-FALLBACK", "what": "Python engine when the Rust extension is absent or GRIDMARKET_ENGINE is unset", "scope": "all steps before S18-D", "removed_by": "S18-D only with a benchmark gain"}
  ],
  "anomaly_rollback_recovery": {
    "anomaly_classes": [
      {"id": "AN-CONTRACT", "trigger": "frozen-contract diff non-empty, or an S18-E main diff outside ercot-hackathon/** and docs/plans/**", "action": "CONTRACT_STOP; do not merge; return to Planning and Design as a named delta"},
      {"id": "AN-WRITESET", "trigger": "lane diff outside the lane write-set union (worker: agent commits outside the four paths, or external-item diff outside ercot-hackathon/**)", "action": "do not merge; return the lane to its implementer"},
      {"id": "AN-CONFLICT", "trigger": "non-whitespace merge conflict", "action": "git merge --abort; return the lane (S18-E: the worker lane and tell Jordan)"},
      {"id": "AN-PRODUCT-RED", "trigger": "post-step V&V fails, reproducible on the merge commit", "action": "revert the merge; confirm the revert commit is green; return the lane with the failing command output (one repair bound per lane)"},
      {"id": "AN-FLAKE", "trigger": "same command passes and fails on the same SHA", "action": "rerun once; if inconsistent, treat as AN-PRODUCT-RED and report the flake to the lane; never skip or deselect"},
      {"id": "AN-ENV", "trigger": "Docker daemon, disk, port-in-use, image-pull, Node, Graphviz, or draw.io failure not caused by the merged code", "action": "fix the local environment (local dev tooling is agent work; never stop the demo project gridmarket without the Orchestrator); rerun the same SHA; no revert"},
      {"id": "AN-WORKER-LIVE", "trigger": "Worker 401/404 on a keyed allowlisted call, 503 secrets missing, or a keyless /api/report call that is not 401 during PROC-ERCOT-LIVE-CHECK", "action": "no revert; typed gap WORKER_FIX_NOT_DEPLOYED or WORKER_KEY_MISMATCH; tell the owner and Jordan; phase 1 acceptance waits"},
      {"id": "AN-ERCOT", "trigger": "Worker 429, 502, or timeout during PROC-ERCOT-LIVE-CHECK", "action": "typed gap ERCOT_LIVE_UNAVAILABLE; retry once after backoff inside the 12 per minute poller budget; fixture tests decide product correctness; no revert"},
      {"id": "AN-SECRET", "trigger": "CMD-SECRETS finding (including in Jordan's history after S09-E or S18-E)", "action": "stop; do not push; revert the merge that introduced it; notify the owner (and Jordan for his commits); rotation and history rewrite are owner-only"},
      {"id": "AN-DEMO-CRASH", "trigger": "the demo stack crashes after a merge", "action": "revert the latest merge step; rerun CMD-SMOKE; the Orchestrator restarts the demo from the last green checkpoint SHA"}
    ],
    "corrections_bound": "at most three evidence-driven corrections per step, then BLOCKED with evidence",
    "rollback": "git revert -m 1 <merge-sha> on gridmarket/integration, then rerun the step's post_step_vv on the revert commit to prove the last green state; earlier merged lanes stay; push non-force",
    "re_entry_after_repair": "When a reverted lane hands a new exit SHA: (1) git revert <revert-sha> (restores the lane's reverted content), (2) git merge --no-ff <new exit SHA>, (3) run the full post_step_vv on the result; if red, revert both commits and record the lane as returned or dropped. The same revert-of-revert is required before S18-E if S09-E was reverted, because origin/main's Jordan commits are already ancestors (CF-17).",
    "recovery": ["Workstation failure (RISK-GM-03): gridmarket/integration is pushed after every green step; recreate /home/spectre/alphazede/worktrees/base-gridmarket-integration from origin at the last checkpoint SHA", "Demo SQLite volume loss: restart the demo stack; seed.py reseeds an empty DB; the poller refetches from the Worker", "Lane session loss: the lane branch at its last commit is the state; the Coordinator re-dispatches the same slice", "Worker regression after Jordan redeploys: market serves stale with age_s; the phase 1 checkpoint stays; Jordan rolls back his deployment (his action)", "IE execution route unavailable: ordered fallbacks per the frozen profile, as a fresh session with no author ancestry"]
  },
  "cutoffs": {
    "timezone": "America/Chicago",
    "foundation": "S01 target Fri 2026-09-25 23:30; S09-A runs as soon as the S01 exit SHA is recorded",
    "worker": "S25 exit and PR into jordaaan target Sat 2026-09-26 10:00, so Jordan can deploy before PROC-ERCOT-LIVE-CHECK; S09-A..D do not wait for it (CF-16)",
    "phase_1": "S09 target Sat 2026-09-26 14:00; no wave 3 merge before S09-E closes",
    "phase_2": "S12-A target Sat 2026-09-26 20:00. If S12-A is not closed by Sun 2026-09-27 02:00, raise OWNER_DECISION_REQUIRED OD-ORDER. Default until answered: strict order. S12-B (spec) merges when green, up to the stretch cut-off.",
    "review": "Sat 2026-09-26 22:00: the Reviewer's one Lifecycle review of the integrated candidate (gridmarket/integration head SHA recorded then); its one repair round lands through the owning lanes and assembly before the Sun 07:00 freeze (DEC-GM-023)",
    "stretch": "A lane (including lonestar and spec) whose exit SHA is not recorded green by Sun 2026-09-27 04:30 is dropped and recorded, never forced in. A merge step may start up to 04:30. A step not green by 05:30 is reverted.",
    "final_candidate": "S18-E declared by Sun 2026-09-27 06:00",
    "freeze": "Sun 2026-09-27 07:00: no merges after the freeze; only a revert to the last green checkpoint if the demo breaks. OD-WORKER-LANDING is raised at the freeze if CF-19 applies.",
    "submission": "Sun 2026-09-27 11:00; main holds the S18 phase PR merged before the freeze (DEC-GM-023; PR-only by convention, DEC-GM-018); after the freeze only a revert PR to the last green checkpoint; the public flip is owner-only"
  },
  "final_candidate": {
    "definition": "The commit on gridmarket/integration recorded at S18-E exit: the last green merge (or revert) commit's code tree plus evidence commits, with every step closed green, reverted, skipped, or dropped with a reason",
    "must_contain": ["phase 1 lanes foundation, market, data, ui, worker", "phase 2 lonestar and spec unless dropped at cut-off", "each stretch item (adversary, backtest, ML, Rust) only if its step closed green", "origin/main at the recorded SHA"],
    "must_pass": ["CMD-TEST-ALL", "CMD-TEST-DASH", "CMD-TEST-WORKER", "CMD-SMOKE", "CMD-SECRETS full history (AC-GM-SEC-01)", "CMD-TEST-SPEC and CMD-SPEC-LINT if spec merged", "CMD-TEST-ML if ML merged", "LICENSE (MIT) at the root", "frozen-contract blobs equal to the S09-A baseline"],
    "identity": "configuration_identity fields recorded at S18-E",
    "fallbacks": ["phase 2 checkpoint (S12-A exit)", "phase 1 checkpoint (S09-E exit)"],
    "handoff": "Assurance Test Engineer (Lifecycle cadence) and the IE Lifecycle-end assessment; the IE does not self-certify"
  },
  "lifecycle_assessment_inputs": {
    "session": "fresh integration_engineer.execution session on the frozen route with profile fallbacks, no ancestry from any lane author session, Lifecycle cadence",
    "inputs": ["final candidate SHA and code tree SHA on gridmarket/integration", "evidence/assembly-phase-1.md, assembly-phase-2.md, assembly-stretch.md with per-step command outputs and identities", "configuration_identity at S18-E, incl. jordaaan base SHA, origin/main SHA, PR #3 and lane-worker PR states, and the deployed Worker identity as reported by Jordan", "seit.json rows for post-step V&V, acceptance, and gates (red-then-green incl. CMD-RED-GREEN-WORKER, changed-line coverage, mutation, Reverify on the PyO3 extension if S18-D merged, otherwise Reverify: not applicable because no binary artifact)", "anomaly log with typed gaps (WORKER_ENV_ABSENT, WORKER_FIX_NOT_DEPLOYED, WORKER_KEY_MISMATCH, ERCOT_LIVE_UNAVAILABLE, dropped lanes with reasons)", "PROC-ERCOT-LIVE-CHECK result against the deployed Worker, or its typed gap", "owner-run PROC-ACCEPT-P1 and PROC-ACCEPT-P2 results with the SC-1..SC-11 checklist, or not-run typed gaps", "AC disposition table: phase 1 incl. AC-GM-EDGE-01..04, phase 2 incl. AC-GM-SPEC-01..03, stretch incl. AC-GM-ML-01 (passed on the candidate or dropped with reason)", "CMD-SECRETS full-history result and LICENSE check (AC-GM-SEC-01)", "Reviewer Lifecycle review receipt (candidate recorded at about Sat 2026-09-26 22:00 CDT) with its repair round, and review.coverage_assist status (presence only; the IE does not adjudicate defects)", "the approved user-facing outcome: gridmarket-technical-plan.md Outcome and intent section 20 demo story"],
    "assessment_questions": ["Does the candidate run the section 20 demo story end to end without a crash, reading ERCOT data only through the deployed Worker?", "Is every interface in CONTRACT-GM-API, ENGINE, PROVIDER, SIGNALS, PREDICTION, SCHEMA, WORKER exercised at its final state?", "Does the configuration identity match the image, compose file, and deployed Worker actually used for acceptance and recording?"]
  },
  "owner_dependencies": [
    {"id": "OWN-WORKER-ENV", "what": "untracked .env at the integration worktree root with GRIDMARKET_WORKER_URL, GRIDMARKET_WORKER_KEY (value equal to Jordan's MARKET_KEY, exchanged owner-to-Jordan out of band), GRIDMARKET_ADMIN_KEY, GRIDMARKET_CORS_ORIGIN; supersedes the former OWN-ERCOT-KEY (DEC-GM-021)", "blocks": ["PROC-ERCOT-LIVE-CHECK (S09-E)", "PROC-ACCEPT-P1/P2 live data", "AC-GM-BT-01 and AC-GM-ML-01 live runs"], "blocks_when": "S09-E, target Sat 14:00; it blocks no lane slice", "if_absent": "typed gap WORKER_ENV_ABSENT; phase 1 checkpoint stands without live data"},
    {"id": "HUM-JORDAN-DEPLOY", "what": "Jordan sets MARKET_KEY (wrangler secret put MARKET_KEY), creates the RATE_LIMITER and ERCOT_BUDGET bindings, deploys the fixed Worker (wrangler deploy), and reports the deployed source SHA and version ID", "blocks": ["PROC-ERCOT-LIVE-CHECK", "PROC-ACCEPT-P1", "PROC-ACCEPT-P2"], "blocks_when": "after the S25 PR exists, before S09-E live check (target Sat 14:00)", "if_absent": "typed gap WORKER_FIX_NOT_DEPLOYED; S09 closes without the live check; acceptance waits; running acceptance on the unfixed Worker is owner decision OD-WORKER-UNFIXED"},
    {"id": "HUM-JORDAN-PR", "what": "Jordan merges or declines the lane-worker PR into jordaaan, using a merge commit (not squash or rebase); Jordan or the owner merges PR #3 into main", "blocks": ["phase PRs to main without OD-WORKER-LANDING (first at S09)", "S18-E clean merge", "OD-WORKER-LANDING avoidance"], "blocks_when": "before the S09 phase PR (target Sat 14:00) to avoid OD-WORKER-LANDING; before S18-E (Sun 06:00) for a clean merge", "if_absent": "OD-WORKER-LANDING holds the phase PRs (CF-19, CF-23); S18-E merges origin/main as it is and records the PR states"},
    {"id": "HUM-JORDAN-EDITS", "what": "Jordan does not edit ercot-hackathon/src/index.js, wrangler.jsonc, or README.md on jordaaan until the lane PR merges, or tells the Coordinator first", "blocks": ["S25 PR merge", "S18-E"], "blocks_when": "wave 1 through S18-E", "if_absent": "CF-14 procedure: the worker lane merges the new jordaaan SHA and repairs (Implementer), the IE re-bases its checks on the new jordaaan SHA"},
    {"id": "OWN-TUNNEL", "what": "Cloudflare named-tunnel credentials and docker compose --profile tunnel up (PROC-TUNNEL)", "blocks": ["PROC-ACCEPT-P1", "PROC-ACCEPT-P2", "video recording"], "blocks_when": "after S09-E for acceptance; Sunday recording", "if_absent": "acceptance not run (typed gap); assembly unaffected"},
    {"id": "OWN-GITHUB-REMOTE", "what": "private repository origin https://github.com/1wgrumph/gridmarket.git", "blocks": [], "blocks_when": "does not block: exists per DEC-GM-018", "if_absent": "n/a"},
    {"id": "OWN-PUBLICATION", "what": "making the repository public after zero secret findings over full history (including Jordan's commits; pre-check a63c8d2..4853e51 clean) and the MIT LICENSE", "blocks": ["public codebase link for submission"], "blocks_when": "after S18-E, before Sun 11:00", "if_absent": "the IE hands over the AC-GM-SEC-01 result; the owner decides"},
    {"id": "OWN-JUDGE-KEYS", "what": "python -m gridmarket_server.keys issue --sandbox (owner-run)", "blocks": ["judge quickstart step of acceptance and demo"], "blocks_when": "acceptance runs", "if_absent": "demo uses seeded accounts only"},
    {"id": "OD-ORDER", "what": "owner decision whether green stretch lanes may merge ahead of an unclosed S12-A", "blocks": ["S18-A, S18-B, S18-C, S18-D entry"], "blocks_when": "only if S12-A is not closed by Sun 02:00 CDT", "if_absent": "strict order: phase 2 first"},
    {"id": "OD-WORKER-LANDING", "what": "owner decision (with Jordan) when a phase PR would carry ercot-hackathon/ into main (first at S09, DEC-GM-023) while PR #3 is unmerged or Jordan declined the lane-worker PR: land ercot-hackathon/ in main as integrated (GitHub then counts PR #3's contained commits as merged), or revert the S09-E merge before the phase PR (the market still reads the deployed Worker over HTTP)", "blocks": ["phase PRs gridmarket/integration -> main (S09, S12, S18)"], "blocks_when": "only if CF-19 applies when a phase PR is ready (first at S09, target Sat 14:00); decided before the Sun 07:00 CDT freeze", "if_absent": "the phase PRs are held; assembly on gridmarket/integration, the final candidate and assurance proceed"}
  ],
  "concurrency_findings": [
    {"id": "CF-01", "severity": "high", "kind": "defect", "status": "resolved", "where": "slice-graph.md header lines 14-19; design.md DES-GM-LANES bullet 2", "problem": "No step assembled the foundation lane; wave 2 lanes lacked S01.", "corrected_text": "Applied: wave 2 lanes branch from the S01 exit commit; wave 3 from the S09 exit; S09 merges foundation, market, data, ui, worker."},
    {"id": "CF-02", "severity": "high", "kind": "defect (hidden read dependency)", "status": "resolved", "where": "slice-graph.md S01 row; design.md DES-GM-ARCH composition-root bullet", "problem": "main.py imported modules that did not exist until S05 or S06.", "corrected_text": "Applied: S01 owns placeholder market.py, api.py, ercot.py, nws.py, scoring.py, seed.py, providers/__init__.py, providers/base_sim.py; main.py mounts the dashboard only if built."},
    {"id": "CF-03", "severity": "high", "kind": "defect (shared resource incomplete)", "status": "resolved", "where": "slice-graph.md Concurrency proof, Shared mutable resources bullet", "problem": "More than one credentialed poller could exceed the ERCOT limit.", "corrected_text": "Applied and superseded by DEC-GM-021: the Worker owns the ERCOT budget (upstream 25 per 60 s); market callers share its 30 per 60 s client limit (poller 12, backtest 5, ML 5); CMD-SMOKE runs without GRIDMARKET_WORKER_URL."},
    {"id": "CF-04", "severity": "medium", "kind": "defect (shared resource incomplete)", "status": "resolved", "where": "slice-graph.md Docker/port bullet; design.md DES-GM-OPS line 357", "problem": "Smoke stacks collided with the demo stack.", "corrected_text": "Applied: unique project and port per smoke run; ports 127.0.0.1:${GRIDMARKET_PORT:-8000}:8000; no fixed image, container_name, or volume name."},
    {"id": "CF-05", "severity": "medium", "kind": "defect (shared resource missing)", "status": "resolved", "where": "slice-graph.md SQLite bullet", "problem": "SQLite paths not covered.", "corrected_text": "Applied: tmp_path for tests, project-scoped gm-data volume for the demo."},
    {"id": "CF-06", "severity": "high", "kind": "defect (red tests carried into a merge)", "status": "resolved", "where": "slice-graph.md S15 row", "problem": "Red Rust parity tests in the S16 exit.", "corrected_text": "Applied: the Rust parity parametrization skips without the extension; CMD-TEST-PARITY fails without it."},
    {"id": "CF-07", "severity": "medium", "kind": "defect (dependency contradicts cut-off)", "status": "resolved", "where": "slice-graph.md Dependencies", "problem": "S14 and S17 blocked S18.", "corrected_text": "Applied: S14, S16, S17, S23 --> S18 are completion-or-drop edges."},
    {"id": "CF-08", "severity": "medium", "kind": "defect (environment interface)", "status": "resolved", "where": "design.md DES-GM-OPS line 358", "problem": "Mandatory env_file broke lane smoke runs.", "corrected_text": "Applied: env_file {path: ../.env, required: false}."},
    {"id": "CF-09", "severity": "medium", "kind": "gap (pending planning delta)", "status": "resolved (residual cap issue moved to CF-13)", "where": "slice-graph.md S03/S06 (nws.py), S19-S21, S22-S23, lane-rust; design.md DES-GM-LANES", "problem": "The planning delta had no slices or steps.", "corrected_text": "Applied: phase 1 drivers in the data lane; spec lane S19-S21 on gridmarket/lane-spec after S06 (slot edge); ML lane S22-S23 on gridmarket/lane-ml from the S16 exit (slot S11 --> S22); Rust on gridmarket/lane-rust from the S15 exit (slot S14 --> S17). This plan adds S12-B, S18-C (ML), S18-D (Rust)."},
    {"id": "CF-10", "severity": "low", "kind": "defect (write-set check noise)", "status": "resolved", "where": "slice-graph.md S01 row", "problem": "Build outputs flagged by CMD-WRITESET.", "corrected_text": "Applied: .gitignore entries in S01."},
    {"id": "CF-11", "severity": "low", "kind": "note (read/write dependency to guard)", "status": "resolved", "where": "slice-graph.md S05 and S06 rows", "problem": "S10 read /v1/providers owned by S14; S16 needed its own limiter.", "corrected_text": "Applied: /v1/providers derived only from the registry (S05); limiter takes a requests-per-minute budget parameter (S06)."},
    {"id": "CF-12", "severity": "info", "kind": "verified", "status": "resolved (re-verified for the current graph)", "where": "slice-graph.md Concurrency proof", "problem": "none", "corrected_text": "Pairwise write-set disjointness re-verified: wave 1 foundation {S01} and worker {S24, S25} (worker writes only four ercot-hackathon/ paths, S01 none; Jordan's base changes only ercot-hackathon/** from merge-base a63c8d2); wave 2 market, data then spec, ui; wave 3 lonestar then ml, adversary then rust, stretch; cross-wave reuse of seed.py, providers/*, market.py, api.py, deploy/* ordered by S09 --> S10, S13, S15 and S15 --> S17; integration branch written only by IE slices. Within each wave at most 3 lanes."},
    {"id": "CF-13", "severity": "medium", "kind": "defect (concurrency cap exceeded across waves)", "status": "open", "where": "slice-graph.md Concurrency proof (per-wave slot bullets) and header line 11; design.md DES-GM-LANES cap bullet", "problem": "The cap of 3 is proved per wave, but dependencies let waves overlap. Wave 2 lanes need only S01, so market, data, ui start while the worker lane (S24-S25) is still active: 4 lanes. Wave 3 lanes need only S09, and S09 does not wait for S21, so lonestar, adversary, stretch start while the spec lane is still active: 4 lanes. Write sets stay disjoint, so this is a cap breach, not a write conflict.", "corrected_text": "Add to the Concurrency proof: '- The cap of 3 counts active lanes across waves. The Coordinator starts a ready slice in a new lane only when fewer than 3 lanes are active. When several lanes are ready, priority is: foundation, worker, market, data, ui, spec, lonestar, adversary, stretch, rust, ml. Slot edges below make the common cases deterministic.' Add slot edges: 'S25 --> S04 (slot edge: ui starts after the worker lane)' and 'S21 --> S15 (slot edge: stretch starts after the spec lane)'. Planning and Design may choose other lanes for the two slot edges; the cross-wave rule is required either way."},
    {"id": "CF-14", "severity": "medium", "kind": "defect (concurrent external edits)", "status": "open (procedure in this plan; needs Jordan's agreement, HUM-JORDAN-EDITS)", "where": "slice-graph.md S25 row; design.md DES-GM-EDGE delivery bullet; external branch origin/jordaaan", "problem": "Jordan owns jordaaan and may edit ercot-hackathon/src/index.js, wrangler.jsonc, or README.md while S24-S25 run or before S18-E. The lane PR into jordaaan then conflicts, and S18-E (origin/main with PR #3) conflicts with the S25 changes already in gridmarket/integration. Also, a squash or rebase merge of the lane PR puts different SHAs in main than the integration branch holds, so the same hunks meet again at S18-E.", "corrected_text": "Add to the S25 goal: 'Before opening the PR, fetch origin/jordaaan; if it moved past the lane base, merge it into gridmarket/lane-worker (no rebase), resolve conflicts in the S25 write set, rerun CMD-TEST-WORKER, and record the new jordaaan SHA as the lane base for the write-set check.' Add to DES-GM-EDGE delivery: 'Ask Jordan to merge the lane PR with a merge commit and to tell the Coordinator before editing index.js, wrangler.jsonc, or README.md. An S18-E conflict in ercot-hackathon/ returns to the worker lane Product Implementer as a repair slice.'"},
    {"id": "CF-15", "severity": "medium", "kind": "defect (merge-order dependency from shared lineage)", "status": "resolved in this plan's entry criteria; S18 goal wording open", "where": "slice-graph.md S18 row goal ('each as soon as green'); lane-rust from the S15 exit; lane-ml from the S16 exit", "problem": "lane-rust carries S15's test_backtest.py without backtest.py, so merging Rust before or without backtest turns CMD-TEST-ALL red. lane-ml carries S16; if the backtest merge was reverted, the ML merge does not restore backtest.py and ml.py fails. So Rust and ML are not independent of the backtest merge.", "corrected_text": "S18 goal: 'Assemble stretch: merge adversary (S14 exit) and backtest (S16 exit) each as soon as green; merge ML (S23 exit) only after backtest merged green and not reverted; merge Rust (S17 exit, only with benchmark gain) only after backtest merged; drop any lane not green by Sun 04:30 CDT; merge origin/main; produce the final integrated candidate.'"},
    {"id": "CF-16", "severity": "medium", "kind": "defect (hard edge gates a whole assembly slice)", "status": "open", "where": "slice-graph.md Dependencies: S25 --> S09 and S21 --> S12", "problem": "S09 and S12 are single slices with several merge steps. S25 --> S09 blocks S09-A..D (foundation to ui) behind the worker lane, although the worker merges last. S21 --> S12 blocks the lonestar merge and the phase 2 checkpoint behind the spec lane, although DEC-GM-019 says the spec lane must not block the demo and the spec merge comes second. Both edges contradict the per-step cut-offs.", "corrected_text": "Replace with: 'S25 --> S09 and S21 --> S12 are completion-or-drop edges gating only the step that merges that lane (S09-E, S12-B): S09 starts when S06, S07, S08 are done; S12 starts when S11 is done; a worker or spec lane not green by its cut-off is recorded dropped (worker: phase 1 checkpoint recorded without it and the Worker merge moves to S18-E through origin/main; spec: Sun 04:30 CDT).'"},
    {"id": "CF-17", "severity": "low", "kind": "defect (revert-of-merge hides external commits)", "status": "resolved in this plan (re_entry_after_repair, S09-E rollback)", "where": "S09-E rollback and S18-E", "problem": "Reverting the S09-E merge also removes Jordan's ercot-hackathon/ source. His commits stay ancestors of gridmarket/integration, so the later S18-E merge of origin/main (with PR #3) does not bring the source back and the final candidate silently lacks the Worker.", "corrected_text": "Before S18-E, if S09-E was reverted and not re-entered, revert the revert first (or re-enter a repaired S25 exit); the S18-E diff check then shows ercot-hackathon/ present."},
    {"id": "CF-18", "severity": "low", "kind": "defect (shared external resource in smoke)", "status": "open", "where": "slice-graph.md Concurrency proof NWS bullet; design.md DES-GM-NWS and DES-GM-ARCH composition-root bullet", "problem": "The proof says only the running app polls NWS, but every CMD-SMOKE stack is a running app. No start condition gates the NWS poller, so the demo stack and up to three smoke stacks each poll api.weather.gov (up to 4 x 6 requests/min), and smoke results depend on the public network.", "corrected_text": "DES-GM-ARCH composition root: 'starts the NWS poller unless GRIDMARKET_NWS=off'; CMD-SMOKE sets GRIDMARKET_NWS=off; add GRIDMARKET_NWS to .env.example names. Concurrency proof NWS bullet: 'NWS API: only the demo stack polls it (<= 6 requests/min); smoke stacks run with GRIDMARKET_NWS=off; tests use fixtures.' This touches S01's frozen main.py, so it must land before S01 exits."},
    {"id": "CF-19", "severity": "medium", "kind": "owner decision (landing through the integration PR)", "status": "open (conditional; OD-WORKER-LANDING at the freeze)", "where": "design.md DES-GM-LANES worker bullet ('jordaaan lands on main through PR #3'); landing PR gridmarket/integration -> main", "problem": "gridmarket/integration contains Jordan's commits (from S09-E). If PR #3 is not merged by the freeze, the landing PR lands them in main anyway, and GitHub counts PR #3's contained commits as merged. If Jordan declined the lane-worker PR, main receives a Worker fix that is not deployed, so main's ercot-hackathon/ differs from the running Worker.", "corrected_text": "Add to DES-GM-LANES: 'If PR #3 is unmerged, or the lane-worker PR is declined, at the freeze, the owner decides with Jordan (OD-WORKER-LANDING): land ercot-hackathon/ as integrated, or revert the S09-E merge before the landing PR. The landing PR is held until the decision.'"},
    {"id": "CF-20", "severity": "low", "kind": "defect (stale wording after DEC-GM-021)", "status": "open", "where": "slice-graph.md S23 row goal", "problem": "S23 writes docs/ml-report.md 'from one live run when ERCOT key exists'; the market no longer holds an ERCOT key.", "corrected_text": "'...write docs/ml-report.md from one live run through the ERCOT Worker (GRIDMARKET_WORKER_URL and GRIDMARKET_WORKER_KEY set, <= 5 requests/min, never during recording); otherwise mark it fixture-only.'"},
    {"id": "CF-21", "severity": "low", "kind": "read dependency (planning inputs untracked)", "status": "open", "where": "owner checkout gridmarket/lifecycle-setup at 0bfa50a: design.md, gridmarket-technical-plan.md, specialists/, views/ untracked", "problem": "gridmarket/integration and the S01 base are created from the approved planning revision commit. S21 writes the GridMarket specification from design.md and the technical plan, and the Reviewer and IE assessment cite them. If the approval commit omits them, lane-spec cannot read them from its own branch.", "corrected_text": "Planning and Design (or the Plan Integrator) commits design.md, gridmarket-technical-plan.md, and views/ in the approved planning revision before gridmarket/integration is created."},
    {"id": "CF-22", "severity": "info", "kind": "owner change (DEC-GM-025)", "status": "applied by Planning and Design", "where": "implementation.json waves, dependencies, S10/S13/S15/S22 and S11/S14/S16/S17/S23 branch bases; slice-graph.md; design.md DES-GM-LANES", "problem": "The cap rises from 3 to 4 lanes and the red-test slices S10, S13, S15, S22 move to wave 2 on the S01 exit; their implementation slices stay after S09.", "corrected_text": "Edges S01 --> S10, S13, S15, S22 (data) and S09 --> S11, S14, S16, S17 (data: lane sync merge) replace S09 --> S10, S13, S15; slot S11 --> S23 replaces slot S11 --> S22; slot S21 --> S15 is removed (the stretch red tests run in wave 2, and with 4 slots the spec lane fits beside lonestar, adversary and stretch in wave 3). Wave 2 red-test write sets (test_providers.py, test_adversarial.py, test_backtest.py, test_matching_parity.py, fixtures/ercot_history/, bench/bench_matching.py, test_ml.py, fixtures/ml/) are disjoint from foundation, worker, market, data, ui and spec. A lane holds a slot only while one of its slices runs. PROC-ASSEMBLY write-set sub-checks are unchanged: lane sync merge commits are excluded by --no-merges and their parents are already on the integration branch."},
    {"id": "CF-23", "severity": "medium", "kind": "owner change (DEC-GM-023) moves a conditional owner decision earlier", "status": "applied by Planning and Design", "where": "S09, S12, S18 exits; OD-WORKER-LANDING; authorized_glue; branches.rule", "problem": "Phase PRs merge gridmarket/integration into main after S09, S12 and S18. The S09 PR is the first to carry Jordan's commits and the S25 Worker fix into main, so CF-19 can apply at S09 (target Sat 14:00), not only at the freeze.", "corrected_text": "OD-WORKER-LANDING triggers when a phase PR is ready while PR #3 is unmerged or the lane-worker PR is declined; the phase PRs are held (assembly continues) until the owner decides with Jordan, before the Sun 07:00 CDT freeze. The IE opens and merges phase PRs (merge commit, no review); it still never pushes directly to main or jordaaan."}
  ]
}
```
