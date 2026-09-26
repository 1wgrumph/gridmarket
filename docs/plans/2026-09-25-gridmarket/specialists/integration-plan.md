# Integration plan: GridMarket hackathon MVP (Integration Engineer, planning session)

Lifecycle GM-2026-09-25. Role: `integration_engineer` planning session (Claude
Code, Claude Opus 5.5), scope-reopen delta re-issue for the 51-slice graph
(DEC-GM-027, DEC-GM-029, DEC-GM-038, DEC-GM-039, DEC-GM-040; DEC-GM-043
delegate authority). Method: Bearing Lite `integration-engineer` 1.1.5 and
AlphaZede `integration-engineering` (planning session only: no assembly, no
merge, no product). Standards: ISO/IEC/IEEE 24748-6 cited by metadata only
(SRC-EMV-24748-6); NASA Systems Engineering Handbook Appendix H named, not
copied. Planning cadence (DEC-GM-038): one pass.

Supporting file, not a canonical artifact. The Plan Integrator copies the
`integration_plan` JSON block below mechanically into `implementation.json`.
Slice IDs, phases, lanes, write sets, edges, and assembly order come from
`specialists/slice-graph.md` (authoritative). Command IDs are the slice-graph
proposals; the Planning Test Engineer finalizes them in `seit.json`. When
`seit.json` changes an ID or pass rule, `seit.json` wins and this plan follows
it. `seit.json` read at this pass is still the 25-slice issue (CF-28).

## Return

- **Status:** `GAPS`
- **Verdict:** `PLAN_READY` for the assembly strategy over the current graph
  (51 slices, waves 1-3, phases 1a, 1b, 2, stretch, final; 22 phase-scoped
  lanes plus 5 phase integration branches). CF-01 to CF-23 are dispositioned
  below (resolved or superseded; CF-21 stays open). This pass adds CF-24 to
  CF-34. Two are high: the `rust` and `ml` lanes lack code they read from the
  `backtest` lane because their edges are plain, not lane-sync (CF-24,
  CF-25). They must be fixed in `slice-graph.md` before S17 and S23
  dispatch, not before wave 2 starts.
- **candidate_ref:** none. Planning session; no integrated candidate exists.
  Planning revision read: `e71bd81` on `gridmarket/lifecycle-setup` with
  `design.md`, `slice-graph.md`, and views modified but uncommitted in the
  owner checkout (CF-21). External item read with `git` only:
  `origin/jordaaan` at `4853e51b2a5d8564631946e688e53802f83a7ab8`.
- **changed_paths:** `docs/plans/2026-09-25-gridmarket/specialists/integration-plan.md`
- **tests:** `python3` JSON parse and key check of the `integration_plan`
  block. Mechanical write-set check over the 51 slice rows of
  `slice-graph.md` (prefix-aware path overlap for every pair of slices in
  different lanes, plus reachability over all 71 edges). Result: 4
  cross-lane overlaps, each ordered by a dependency path: S08/S17
  (`deploy/Dockerfile`, `deploy/compose.yaml`), S25/S27
  (`ercot-hackathon/src/index.js`, `wrangler.jsonc`, `README.md`), S08/S45
  (`README.md`), S51/S48 (`dashboard/src/pages/Sandbox.tsx`). Every S01 overlap
  is ordered by an `S01 -->` edge. Every slice reaches its phase assembly slice.
  Read-only git: `origin/main` is `712f63a` (merge of PR #2);
  `gridmarket/lifecycle-setup` is not a descendant of `origin/main` (merge
  base `a63c8d2`), and `git diff --name-only origin/main HEAD` lists only
  `docs/plans/2026-09-25-gridmarket/**`; `git merge-base HEAD
  origin/jordaaan` is `a63c8d2`; PR #3 (`jordaaan`, head `4853e51`) is OPEN.
  No product tests exist. Nothing was assembled.
- **findings:** CF-01 to CF-34 in `concurrency_findings`.
- **blocker:** none for wave 1 dispatch once CF-21 is applied (the planning
  package must be committed and landed before S01 branches). CF-24 blocks S17
  dispatch, CF-25 blocks S23 dispatch, and CF-28 blocks the Planning Test
  Engineer's final command table. No owner decision is required: the open
  items are inside the approved scope and the Orchestrator's delegate
  authority (DEC-GM-043). Owner-only actions (Worker deploy and secrets,
  tunnel, credential `.env`, publication) stay owner-only and appear as
  typed gaps if absent.

## Input drift observed since the last issue

- DEC-GM-027: the owner, not Jordan, builds and deploys the Worker from
  Jordan's code at `4853e51` plus S24-S25 and holds all credentials. There is
  no PR into `jordaaan`. The phase 1a PR carries Jordan's commits to `main`
  with authorship kept (DES-GM-LANES). `HUM-JORDAN-*` dependencies,
  `OD-WORKER-LANDING`, and the old S18-E `origin/main` merge step are removed.
  When the phase 1a PR merges, GitHub will show PR #3 as merged because its
  head `4853e51` becomes reachable from `main`; the Orchestrator records that.
- DEC-GM-038/039/040: one integration branch per phase, from `main` at
  assembly start; each phase lands through its own PR and its merged lanes
  are deleted. There is no fixed lane cap (DEC-GM-025 cap superseded); the
  limit is disjoint write sets plus route capacity (2 concurrent sessions per
  usage-windowed primary route).
- DEC-GM-029: the `views` lane (S26-S27) branches from the S25 exit and
  writes the same three Worker files as S25.

## Items and versions

An item is one lane branch at one recorded **exit commit**: the lane tip after
the named slice passes every slice command. The Coordinator records the SHA
and hands it to the IE. A merge consumes that exact SHA, never a moving branch
name. Commits on the lane after the handoff are ignored until a new exit SHA
is handed over.

| Phase | Item (lane) | Branch base | Exit consumed | Step |
|---|---|---|---|---|
| 1a | foundation | `main` after the CF-21 planning PR | S01 exit | S09-A |
| 1a | worker | `origin/jordaaan` at `4853e51` | S25 exit (contains S24, `bae0a16`, `4853e51`) | S09-B |
| 1a | market | S01 exit | S08 exit (S02, S05, S08) | S09-C |
| 1a | data | S01 exit | S06 exit (S03, S06) | S09-D |
| 1a | ui | S01 exit | S07 exit (S04, S07) | S09-E |
| 1b | bots | S01 exit; merges `main` after 1a landing before S29 exit | S31 exit, or S29 exit if the slip trigger fired | S49-A |
| 1b | router | S01 exit; merges `main` after 1a landing before S33 exit | S33 exit (S32, S33) | S49-B |
| 1b | views | S25 exit (lane-sync from `worker`) | S27 exit (S26, S27) | S49-C |
| 1b | pages | S01 exit; lane-sync S07 exit before S51 | S51 exit (S50, S51) | S49-D |
| 1b | spec | S01 exit | S21 exit (S19-S21), complete-or-defer | S49-E |
| 2 | lonestar | S01 exit; merges `main` after 1b landing before S11 exit | S11 exit (S10, S11) | S12-A |
| 2 | providers-page | S01 exit; lane-sync S07 exit before S35 | S35 exit (S34, S35) | S12-B |
| 2 | kit | S01 exit; merges `main` after 1a landing before S37 exit | S37 exit (S36, S37) | S12-C |
| 2 | bots (slipped) | same lane, continued after S49-A | S31 exit | S12-D (only if slipped) |
| 2 | spec (deferred) | same lane | S21 exit | S12-E (only if deferred) |
| stretch | adversary | S01 exit; merges `main` after 1a landing | S14 exit | S18-A |
| stretch | backtest | S01 exit; merges `main` after 1a landing | S16 exit (S15, S16) | S18-B |
| stretch | jev | S01 exit; merges `main` after 1b landing | S43 exit | S18-C |
| stretch | mcp | S01 exit; merges `main` after 1b landing | S39 exit | S18-D |
| stretch | quant | S01 exit; merges `main` after 1a landing | S41 exit | S18-E |
| stretch | ml | S01 exit; lane-sync S16 exit (CF-25); merges `main` after 1a landing | S23 exit | S18-F |
| stretch | rust | S01 exit; lane-sync `main` after 1a landing; lane-sync S16 exit (CF-24) | S17 exit, only with a benchmark gain | S18-G |
| final | docs | `main` after stretch landing | S45 exit (S44, S45) | S46-A |
| final | onboarding | `main` after stretch landing | S48 exit (S47, S48) | S46-B |
| external | jordan-worker | `origin/jordaaan` `4853e51` | enters only inside the S25 exit | S09-B |
| baseline | CONTRACTS.md + stubs | S01 exit | frozen-contract blob SHAs recorded at S09-A | every step |

**Interface baseline.** `CONTRACTS.md` (CONTRACT-GM-INDEX) plus the frozen
stub files are the interface baseline. At S09-A the IE records the blob SHA of
each frozen file; every later merge compares against that baseline, updated
only by a recorded contract amendment (CF-26).

Frozen files: `CONTRACTS.md`, `backend/gridmarket_server/contracts.py`,
`backend/gridmarket_server/schema.sql`, `backend/gridmarket_server/main.py`,
`backend/pyproject.toml`, `backend/uv.lock`, `dashboard/src/api.ts`,
`dashboard/src/App.tsx`, `dashboard/src/hooks.ts`. `dashboard/package.json`,
`package-lock.json`, and `vite.config.ts` are frozen for every lane except
`ui` at S07, and only when S04 recorded the Astryx+StyleX build red
(DEC-GM-033 fallback); that change is recorded as an amendment at S09-E.

**External item check (S09-B).** `git diff --name-only $(git merge-base
<integration-head> <S25-exit>) <S25-exit>` lists only `ercot-hackathon/**`.
The agent-authored part: `git log --no-merges --name-only --format=
<S25-exit> --not 4853e51` lists only the S24 and S25 write sets.

## Per-merge checks (every step)

1. **Contract conformance.** `git diff --exit-code <baseline-sha> <exit-sha>
   -- <frozen files>` must be empty (amendments excepted, CF-26), and
   CMD-TEST-CONTRACTS passes on the merge commit. A diff is `CONTRACT_STOP`:
   do not merge; route the change as a contract amendment.
2. **Write-set check.** `git log --no-merges --name-only --format= <exit-sha>
   --not <integration-head>` lists only paths in the union of that lane's slice
   write sets. Lane-sync and `main` merges are merge commits, and their parents
   are already on the integration branch or on `main`, so they drop out.
3. **Merge.** `git merge --no-ff <exit-sha>` on `gridmarket/integration-<phase>`.
   Write sets are disjoint, so any non-whitespace conflict is a write-set
   violation: `git merge --abort` and return the lane.
4. **Interface exercise** (part of PROC-ASSEMBLY) against the CMD-SMOKE stack
   `gm-smoke-integration:18000` with no `GRIDMARKET_WORKER_URL` and
   `GRIDMARKET_NWS=off`: `/openapi.json` holds every CONTRACT-GM-API path the
   phase has landed; error body `{"error":{"code","message"}}` on a 401 and a
   400 (`IDEMPOTENCY_KEY_REQUIRED`); `/v1/market/status` answers.
   An interface-completeness-profile pass is structural only, never runtime
   proof.
5. **Post-step V&V.** The step's `post_step_vv` on the merge commit, in the
   integration worktree. AC-GM-LANE-02: backend tests, dashboard tests and
   build, and compose smoke pass before the next merge.

## Phase assurance handoff (DEC-GM-038)

After the last merge step of a phase and its acceptance run, the IE commits
and pushes the phase evidence file and hands the candidate (integration head
SHA, code tree SHA, configuration identity) to one Reviewer pass and one
Assurance Test Engineer pass. A repair round, at most one, lands on the owning
lanes as new exit SHAs. The IE merges them into the same
`gridmarket/integration-<phase>`, re-entering reverted lanes by revert-of-revert.
Deterministic verification then decides: CMD-TEST-ALL, CMD-SMOKE, CMD-SECRETS,
and CMD-RULES. There is no re-review. The Orchestrator then runs the landing
step. The final wave follows the same rule (Planning proposal).

## Landing and cleanup (DEC-GM-040, AC-GM-LAND-01)

The Orchestrator runs these commands from the owner checkout
`/home/spectre/alphazede/Hackathons/Base` or the integration worktree. It never
uses `git switch`, force push, `--admin`, squash or rebase merge, or `gh pr
merge --delete-branch`, which switches branches locally.

```bash
P=<phase>; IW=/home/spectre/alphazede/worktrees/base-gridmarket-integration-$P
git -C "$IW" status --short                      # must print nothing
git -C "$IW" push -u origin gridmarket/integration-$P
gh pr create --repo 1wgrumph/gridmarket --base main --head gridmarket/integration-$P \
  --title "Land GridMarket phase $P" --body-file "$IW/docs/plans/2026-09-25-gridmarket/evidence/assembly-phase-$P.md"
gh pr checks <pr> --repo 1wgrumph/gridmarket --watch   # when required checks exist
gh pr merge <pr> --repo 1wgrumph/gridmarket --merge
git -C /home/spectre/alphazede/Hackathons/Base fetch origin --prune
git -C /home/spectre/alphazede/Hackathons/Base merge-base --is-ancestor "$(git -C "$IW" rev-parse HEAD)" origin/main
# post-merge V&V on the main merge commit (AC-GM-LAND-01)
MW=/home/spectre/alphazede/worktrees/base-gridmarket-main-check
git -C /home/spectre/alphazede/Hackathons/Base worktree add --detach "$MW" origin/main
( cd "$MW" && make test-all && make test-dash && make smoke SMOKE_PROJECT=gm-smoke-main SMOKE_PORT=18003 )
git -C /home/spectre/alphazede/Hackathons/Base worktree remove "$MW"
```

Delete a lane only when all of these hold (CF-27). Git's `--merged` and
`--is-ancestor` also report reverted merges as merged, so they are not enough
on their own.

1. The phase evidence file marks every slice of the lane `merged` and not
   reverted.
2. The recorded exit SHA is the lane tip:
   `test "$(git rev-parse origin/gridmarket/lane-$L)" = "<exit-sha>"`.
3. `main` holds the lane's content:
   `git diff --quiet <exit-sha> origin/main -- <lane write-set union>`.

```bash
for L in <lanes of this phase that pass the three checks>; do
  git -C /home/spectre/alphazede/Hackathons/Base worktree remove /home/spectre/alphazede/worktrees/base-gridmarket-$L   # no --force; dirty => stop and report
  git -C /home/spectre/alphazede/Hackathons/Base branch -d gridmarket/lane-$L    # -d, never -D; upstream is set by the lane push
  git -C /home/spectre/alphazede/Hackathons/Base push origin --delete gridmarket/lane-$L
done
git -C /home/spectre/alphazede/Hackathons/Base worktree remove "$IW"
git -C /home/spectre/alphazede/Hackathons/Base branch -d gridmarket/integration-$P
git -C /home/spectre/alphazede/Hackathons/Base push origin --delete gridmarket/integration-$P
git -C /home/spectre/alphazede/Hackathons/Base worktree prune
git -C /home/spectre/alphazede/Hackathons/Base worktree list   # evidence: no removed path listed
```

Kept after landing: `bots` if S31 slipped to phase 2; `spec` if S21 was
deferred; any lane whose merge was reverted and not re-entered; stretch lanes
recorded dropped. Deleting an unmerged branch is destructive git and belongs
to the owner; the Scribe lists these branches for the owner at the freeze.
`worker` is deleted after the 1a landing: its exit SHA is on `main`, and
`views` has already branched from it.

## Authorized glue

**None in product paths.** The IE may write only:

- `--no-ff` merge commits of recorded exit SHAs on `gridmarket/integration-<phase>`
- revert commits (`git revert -m 1 <merge>`) and revert-of-revert commits
- its evidence file `docs/plans/2026-09-25-gridmarket/evidence/assembly-<phase>.md`
  (`assembly-phase-1a.md`, `assembly-phase-1b.md`, `assembly-phase-2.md`,
  `assembly-stretch.md`, `assembly-final.md`)
- non-force pushes of its phase integration branch

It resolves only whitespace-only conflicts. Every other conflict, or any
product, test, configuration, dependency, or compose edit, returns to the
owning lane. A contract edit is an amendment (CF-26). The Orchestrator, not
the IE, opens and merges the phase PR and deletes branches. Nobody pushes to
`jordaaan` or directly to `main`. Only the owner deploys the Worker.

## Shared runtime resources

- **ERCOT budget:** the owner's Worker owns the upstream budget (25 per 60 s,
  AC-GM-EDGE-03). Market callers share the per-client 30 per 60 s: poller ≤ 12,
  backtest ≤ 5, ML ≤ 5. Only the demo stack (project `gridmarket`, port 8000)
  holds `GRIDMARKET_WORKER_KEY` and polls. PROC-ERCOT-LIVE-CHECK runs with the
  demo poller stopped. Live backtest and ML runs are owner-run and never
  happen during recording. The 3D views draw on the same upstream budget, so
  a live 429 is typed gap `ERCOT_LIVE_UNAVAILABLE`.
- **Ports and compose projects:** port 8000 and project `gridmarket` belong to
  the demo stack from `main`. Smoke runs: `gm-smoke-integration:18000` (IE,
  every phase; phases never assemble at the same time), `gm-smoke-market:18001`
  (S08), `gm-smoke-rust:18002` (S17), `gm-smoke-main:18003` (Orchestrator
  post-landing check). Each run removes only its own project.
- **Test-local servers:** S02, S36, and S38 start real uvicorn servers, and S42
  starts a stub HTTP server. With up to 18 parallel lanes on one host, these
  must bind `127.0.0.1:0` (CF-29).
- **SQLite:** tests use pytest `tmp_path`; the demo uses the project-scoped
  `gm-data` volume.
- **NWS / Jev:** only the demo stack polls NWS; smoke sets
  `GRIDMARKET_NWS=off`. Jev is called only by the demo stack with
  `GRIDMARKET_JEV=on` (owner action); tests use a stub.
- **Route capacity (DEC-GM-040):** ≤ 2 concurrent sessions per
  usage-windowed primary route; overflow goes to the ordered fallbacks. The
  IE execution session for a phase counts against its route.

## Owner dependencies

| Dependency | Blocks | If absent |
|---|---|---|
| OWN-WORKER-DEPLOY-1: owner sets Worker secrets (`MARKET_KEY`, ERCOT credentials) and bindings (`RATE_LIMITER`, `ERCOT_BUDGET`) and runs `wrangler deploy` from `ercot-hackathon/` at the phase 1a landing commit on `main` (S25 fix); reports source SHA and version ID | PROC-ERCOT-LIVE-CHECK; AC-GM-ACC-01 live data | typed gap `WORKER_FIX_NOT_DEPLOYED`; 1a lands without the live check |
| OWN-WORKER-DEPLOY-2: owner sets `MARKET_URL` and redeploys from the `gridmarket/integration-1b` head after S49-C is green (views, S27) | AC-GM-EDGE-05 live and AC-GM-ACC-01 | typed gap `VIEWS_NOT_DEPLOYED`; AC-GM-ACC-01 is recorded as not run for the views part (CF-30) |
| OWN-WORKER-ENV: untracked `.env` at the integration worktree root with `GRIDMARKET_WORKER_URL`, `GRIDMARKET_WORKER_KEY` (= `MARKET_KEY`), `GRIDMARKET_ADMIN_KEY`, `GRIDMARKET_CORS_ORIGIN` | PROC-ERCOT-LIVE-CHECK; live acceptance; live backtest and ML | typed gap `WORKER_ENV_ABSENT` |
| OWN-TUNNEL (PROC-TUNNEL) | AC-GM-ACC-01, AC-GM-ACC-02 (through the tunnel URL); recording | acceptance is recorded as not run; assembly is unaffected |
| OWN-JUDGE-KEYS | judge quickstart | seeded accounts only |
| OWN-JEV-KEY and flag | S43 live behavior | Jev stays off (default) |
| OWN-PUBLICATION | public flip after the final landing and full-history CMD-SECRETS | IE hands over the AC-GM-SEC-01 result |

The IE and Orchestrator never read, print, or copy `.env` values,
`MARKET_KEY`, or tunnel credentials. AC-GM-ACC-03 (phase 1a) does not need
the tunnel or live data.

## Concurrency proof: independent verification

**Write sets: confirmed, with one wording defect (CF-31).** The mechanical
pairwise check found exactly four cross-lane path overlaps outside S01, all
ordered by a dependency path:

- S08 (market, 1a) and S17 (rust, stretch): `deploy/Dockerfile`,
  `deploy/compose.yaml`. Ordered by S09 --> S17 (lane-sync): the rust lane
  merges `main` after the 1a landing before S17.
- S25 (worker, 1a) and S27 (views, 1b): `ercot-hackathon/src/index.js`,
  `wrangler.jsonc`, `README.md`. Ordered by S25 --> S26 --> S27 and the
  views lane base (S25 exit). The proof text does not list this overlap
  (CF-31).
- S08 and S45 (`README.md`), S51 and S48 (`Sandbox.tsx`): ordered across
  waves by S18 --> S44/S47 and the phase landings.
- S01 overlaps every lane that replaces a stub. All of those lanes branch
  from the S01 exit.

**Hidden read dependencies: two defects.** S17 reads S15's parity suite and
bench script. S23's `ml.py` reuses the backtest harness (DES-GM-ML). Both
edges are plain, so neither file is in those lanes (CF-24, CF-25).

**Shared resources:** ports, compose projects, ERCOT budget, SQLite, NWS, and
Jev are covered. The gap is test-local server ports (CF-29).

## Lifecycle-end integrated technical assessment (execution session)

A fresh IE execution session on the frozen route assesses the final
candidate, the `main` merge commit of the final landing. It has no lane-author
ancestry, and its receipts are diagnostic, not self-certifying. It hands off
to the Assurance Test Engineer. Inputs are in `lifecycle_assessment_inputs`.

```json integration_plan
{
  "branches": {
    "integration": {"name": "gridmarket/integration-<phase> for phase in 1a, 1b, 2, stretch, final", "created_from": "origin/main at assembly start of that phase (1a: main after the CF-21 planning PR; 1b: main after the 1a landing; 2: after 1b; stretch: after 2; final: after stretch)", "writers": ["Integration Engineer (execution route) only; one phase at a time"], "remote": "origin https://github.com/1wgrumph/gridmarket.git; non-force push after every green step and every revert; deleted local and remote after its phase lands (DEC-GM-040)"},
    "lanes": [
      {"lane": "foundation", "phase": "1a", "branch": "gridmarket/lane-foundation", "slices": ["S01"], "created_from": "origin/main after the CF-21 planning PR", "exit_commits": {"S01": "recorded by Coordinator at S01 green; base of every wave 2 lane except worker"}, "delete_after": "1a landing"},
      {"lane": "worker", "phase": "1a", "branch": "gridmarket/lane-worker", "slices": ["S24", "S25"], "created_from": "origin/jordaaan at 4853e51b2a5d8564631946e688e53802f83a7ab8 (DEC-GM-022, DEC-GM-027); no PR into jordaaan", "exit_commits": {"S25": "recorded by Coordinator at S25 green; base of lane views"}, "delete_after": "1a landing"},
      {"lane": "market", "phase": "1a", "branch": "gridmarket/lane-market", "slices": ["S02", "S05", "S08"], "created_from": "S01 exit", "exit_commits": {"S08": "recorded at S08 green"}, "delete_after": "1a landing"},
      {"lane": "data", "phase": "1a", "branch": "gridmarket/lane-data", "slices": ["S03", "S06"], "created_from": "S01 exit", "exit_commits": {"S06": "recorded at S06 green"}, "delete_after": "1a landing"},
      {"lane": "ui", "phase": "1a", "branch": "gridmarket/lane-ui", "slices": ["S04", "S07"], "created_from": "S01 exit", "exit_commits": {"S07": "recorded at S07 green; lane-sync source for pages (S51) and providers-page (S35)"}, "delete_after": "1a landing"},
      {"lane": "bots", "phase": "1b", "branch": "gridmarket/lane-bots", "slices": ["S28", "S29", "S30", "S31"], "created_from": "S01 exit; merges main after the 1a landing before the S29 exit", "exit_commits": {"S29": "recorded at S29 green (merged at S49-A only if the slip trigger fired)", "S31": "recorded at S31 green (merged at S49-A, or at S12-D if slipped)"}, "delete_after": "the landing of the phase that merged S31"},
      {"lane": "router", "phase": "1b", "branch": "gridmarket/lane-router", "slices": ["S32", "S33"], "created_from": "S01 exit; merges main after the 1a landing before the S33 exit", "exit_commits": {"S33": "recorded at S33 green"}, "delete_after": "1b landing"},
      {"lane": "views", "phase": "1b", "branch": "gridmarket/lane-views", "slices": ["S26", "S27"], "created_from": "S25 exit (DEC-GM-029); merges main after the 1a landing before the S27 exit (CF-30)", "exit_commits": {"S27": "recorded at S27 green"}, "delete_after": "1b landing"},
      {"lane": "pages", "phase": "1b", "branch": "gridmarket/lane-pages", "slices": ["S50", "S51"], "created_from": "S01 exit; lane-sync merge of the S07 exit (--no-ff) before S51; merges main after the 1a landing before the S51 exit (CF-30)", "exit_commits": {"S51": "recorded at S51 green"}, "delete_after": "1b landing"},
      {"lane": "spec", "phase": "1b", "branch": "gridmarket/lane-spec", "slices": ["S19", "S20", "S21"], "created_from": "S01 exit", "exit_commits": {"S21": "recorded at S21 green (complete-or-defer: S49-E, else S12-E, else S18)"}, "delete_after": "the landing of the phase that merged S21"},
      {"lane": "lonestar", "phase": "2", "branch": "gridmarket/lane-lonestar", "slices": ["S10", "S11"], "created_from": "S01 exit; merges main after the 1b landing before the S11 exit", "exit_commits": {"S11": "recorded at S11 green"}, "delete_after": "2 landing"},
      {"lane": "providers-page", "phase": "2", "branch": "gridmarket/lane-providers-page", "slices": ["S34", "S35"], "created_from": "S01 exit; lane-sync merge of the S07 exit before S35", "exit_commits": {"S35": "recorded at S35 green"}, "delete_after": "2 landing"},
      {"lane": "kit", "phase": "2", "branch": "gridmarket/lane-kit", "slices": ["S36", "S37"], "created_from": "S01 exit; merges main after the 1a landing before the S37 exit", "exit_commits": {"S37": "recorded at S37 green"}, "delete_after": "2 landing"},
      {"lane": "adversary", "phase": "stretch", "branch": "gridmarket/lane-adversary", "slices": ["S13", "S14"], "created_from": "S01 exit; merges main after the 1a landing before the S14 exit", "exit_commits": {"S14": "recorded at S14 green"}, "delete_after": "stretch landing if merged"},
      {"lane": "backtest", "phase": "stretch", "branch": "gridmarket/lane-backtest", "slices": ["S15", "S16"], "created_from": "S01 exit; merges main after the 1a landing before the S16 exit", "exit_commits": {"S16": "recorded at S16 green; lane-sync source for ml and rust (CF-24, CF-25)"}, "delete_after": "stretch landing if merged"},
      {"lane": "jev", "phase": "stretch", "branch": "gridmarket/lane-jev", "slices": ["S42", "S43"], "created_from": "S01 exit; merges main after the 1b landing before the S43 exit", "exit_commits": {"S43": "recorded at S43 green"}, "delete_after": "stretch landing if merged"},
      {"lane": "mcp", "phase": "stretch", "branch": "gridmarket/lane-mcp", "slices": ["S38", "S39"], "created_from": "S01 exit; merges main after the 1b landing before the S39 exit", "exit_commits": {"S39": "recorded at S39 green"}, "delete_after": "stretch landing if merged"},
      {"lane": "quant", "phase": "stretch", "branch": "gridmarket/lane-quant", "slices": ["S40", "S41"], "created_from": "S01 exit; merges main after the 1a landing before the S41 exit", "exit_commits": {"S41": "recorded at S41 green"}, "delete_after": "stretch landing if merged"},
      {"lane": "ml", "phase": "stretch", "branch": "gridmarket/lane-ml", "slices": ["S22", "S23"], "created_from": "S01 exit; lane-sync merge of the S16 exit before S23 (CF-25); merges main after the 1a landing before the S23 exit", "exit_commits": {"S23": "recorded at S23 green"}, "delete_after": "stretch landing if merged"},
      {"lane": "rust", "phase": "stretch", "branch": "gridmarket/lane-rust", "slices": ["S17"], "created_from": "S01 exit; lane-sync merge of main after the 1a landing (S09 --> S17) and of the S16 exit (CF-24) before S17", "exit_commits": {"S17": "recorded at S17 green with bench/results.md"}, "delete_after": "stretch landing if merged"},
      {"lane": "docs", "phase": "final", "branch": "gridmarket/lane-docs", "slices": ["S44", "S45"], "created_from": "origin/main after the stretch landing", "exit_commits": {"S45": "recorded at S45 green"}, "delete_after": "final landing"},
      {"lane": "onboarding", "phase": "final", "branch": "gridmarket/lane-onboarding", "slices": ["S47", "S48"], "created_from": "origin/main after the stretch landing", "exit_commits": {"S48": "recorded at S48 green"}, "delete_after": "final landing"}
    ],
    "external": [
      {"item": "jordan-worker", "ref": "origin/jordaaan", "sha": "4853e51b2a5d8564631946e688e53802f83a7ab8", "contains": ["bae0a16 Add ercot-hackathon Worker", "4853e51 Add God's Eye ERCOT globe view"], "merge_base_with_main": "a63c8d2e286c8b9bfe686552af6b430cbfc2a07e", "paths": "ercot-hackathon/** only", "owner": "Jordan wrote it; the owner deploys the Worker built from it (DEC-GM-027)", "enters_via": ["S09-B inside the S25 exit; main receives it at the 1a landing with authorship kept; PR #3 then shows as merged (recorded, not acted on)"]},
      {"item": "contracts-baseline", "ref": "S01 exit", "sha": "recorded at S09-A", "paths": "CONTRACTS.md, backend/gridmarket_server/contracts.py, schema.sql, main.py, backend/pyproject.toml, backend/uv.lock, dashboard/src/api.ts, dashboard/src/App.tsx, dashboard/src/hooks.ts (dashboard/package.json, package-lock.json, vite.config.ts frozen except the S07 DEC-GM-033 fallback)", "enters_via": ["S09-A; updated only by recorded amendments (CF-26)"]}
    ],
    "rule": "A merge consumes the recorded exit SHA, never a moving tip. No force-push, no history rewrite, no git switch in the owner checkout. main changes only through the phase PRs, opened and merged by the Orchestrator with a merge commit (DEC-GM-040). Lane-sync and merge-main commits are made by the lane implementer in the lane worktree, never on an integration branch. Nobody pushes to jordaaan."
  },
  "worktrees": {
    "rule": "Every linked worktree is /home/spectre/alphazede/worktrees/base-gridmarket-<name>; never hidden directories or /tmp. Agents create them at lane start (git worktree add -b gridmarket/lane-<lane> <path> <base-sha>) and the Orchestrator removes them at landing (git worktree remove, then git worktree prune). The owner checkout /home/spectre/alphazede/Hackathons/Base keeps branch gridmarket/lifecycle-setup.",
    "integration": "/home/spectre/alphazede/worktrees/base-gridmarket-integration-<phase> (one at a time)",
    "lanes": {
      "foundation": "/home/spectre/alphazede/worktrees/base-gridmarket-foundation",
      "worker": "/home/spectre/alphazede/worktrees/base-gridmarket-worker",
      "market": "/home/spectre/alphazede/worktrees/base-gridmarket-market",
      "data": "/home/spectre/alphazede/worktrees/base-gridmarket-data",
      "ui": "/home/spectre/alphazede/worktrees/base-gridmarket-ui",
      "bots": "/home/spectre/alphazede/worktrees/base-gridmarket-bots",
      "router": "/home/spectre/alphazede/worktrees/base-gridmarket-router",
      "views": "/home/spectre/alphazede/worktrees/base-gridmarket-views",
      "pages": "/home/spectre/alphazede/worktrees/base-gridmarket-pages",
      "spec": "/home/spectre/alphazede/worktrees/base-gridmarket-spec",
      "lonestar": "/home/spectre/alphazede/worktrees/base-gridmarket-lonestar",
      "providers-page": "/home/spectre/alphazede/worktrees/base-gridmarket-providers-page",
      "kit": "/home/spectre/alphazede/worktrees/base-gridmarket-kit",
      "adversary": "/home/spectre/alphazede/worktrees/base-gridmarket-adversary",
      "backtest": "/home/spectre/alphazede/worktrees/base-gridmarket-backtest",
      "jev": "/home/spectre/alphazede/worktrees/base-gridmarket-jev",
      "mcp": "/home/spectre/alphazede/worktrees/base-gridmarket-mcp",
      "quant": "/home/spectre/alphazede/worktrees/base-gridmarket-quant",
      "ml": "/home/spectre/alphazede/worktrees/base-gridmarket-ml",
      "rust": "/home/spectre/alphazede/worktrees/base-gridmarket-rust",
      "docs": "/home/spectre/alphazede/worktrees/base-gridmarket-docs",
      "onboarding": "/home/spectre/alphazede/worktrees/base-gridmarket-onboarding",
      "main-check": "/home/spectre/alphazede/worktrees/base-gridmarket-main-check (detached, Orchestrator post-landing V&V, removed after use)"
    },
    "env_file": "Only the phase integration worktree root holds the owner's real .env (owner-placed, re-placed per phase). Lane worktrees have no .env; compose tolerates its absence (env_file required: false). Worker and views worktrees hold no Worker secrets; S24 and S26 tests use stub env values."
  },
  "steps": [
    {"id": "S09-A", "slice": "S09", "phase": "1a", "order": 1, "merges": {"lane": "foundation", "exit_commit_of": "S01"}, "entry_criteria": ["gridmarket/integration-1a created from origin/main after the CF-21 planning PR; worktree clean", "S01 exit SHA recorded; CMD-SETUP, CMD-LINT, CMD-TEST-CONTRACTS, CMD-DEPSCAN, CMD-SECRETS, CMD-WRITESET passed on it"], "post_step_vv": ["CMD-SETUP", "CMD-LINT", "CMD-TEST-CONTRACTS", "CMD-TEST-ALL", "CMD-TEST-DASH", "CMD-SECRETS", "PROC-ASSEMBLY (CMD-SMOKE NOT_APPLICABLE: deploy/compose.yaml arrives with market at S09-C)"], "rollback": "git revert -m 1 <S09-A merge>; CMD-TEST-ALL on the revert; return S01; no later 1a step runs until S09-A is green", "exit": "Green; contract baseline (blob SHAs of the frozen files) recorded in evidence/assembly-phase-1a.md"},
    {"id": "S09-B", "slice": "S09", "phase": "1a", "order": 2, "merges": {"lane": "worker", "exit_commit_of": "S25"}, "entry_criteria": ["S09-A green", "S25 exit SHA recorded; CMD-RED-GREEN-WORKER (S24 red, S25 green), CMD-TEST-WORKER incl. the burst case, CMD-WRITESET passed", "external-item check: diff from merge-base lists only ercot-hackathon/**; agent commits (--not 4853e51) only in the S24 and S25 write sets"], "post_step_vv": ["CMD-TEST-WORKER", "CMD-TEST-CONTRACTS", "CMD-TEST-ALL", "CMD-TEST-DASH", "CMD-SECRETS (Jordan's history now scanned)", "CMD-RULES", "PROC-ASSEMBLY"], "rollback": "git revert -m 1 <S09-B merge>; CMD-TEST-ALL on the revert; return the worker lane; re-entry by revert-of-revert then the new S25 exit; views (S26) must not start from a reverted S25 exit", "exit": "Green; jordaaan SHA 4853e51 and S25 exit recorded in the configuration identity"},
    {"id": "S09-C", "slice": "S09", "phase": "1a", "order": 3, "merges": {"lane": "market", "exit_commit_of": "S08"}, "entry_criteria": ["S09-B green (or worker recorded returned; S09-C does not depend on worker content)", "S08 exit SHA recorded; CMD-RED-GREEN, CMD-TEST-MARKET, CMD-COVERAGE, CMD-SMOKE gm-smoke-market:18001, CMD-LINT, CMD-WRITESET passed", "contract diff empty; write-set union S02, S05, S08"], "post_step_vv": ["CMD-LINT", "CMD-TEST-CONTRACTS", "CMD-TEST-ALL", "CMD-TEST-DASH", "CMD-SMOKE (gm-smoke-integration:18000)", "PROC-ASSEMBLY"], "rollback": "git revert -m 1 <S09-C merge>; CMD-TEST-ALL on the revert (CMD-SMOKE not applicable: compose leaves with market); return the market lane", "exit": "Green; /v1/market/status healthy, openapi matches the landed CONTRACT-GM-API paths, bots from population.sample submit orders, /v1/providers lists base_sim"},
    {"id": "S09-D", "slice": "S09", "phase": "1a", "order": 4, "merges": {"lane": "data", "exit_commit_of": "S06"}, "entry_criteria": ["S09-C green", "S06 exit SHA recorded; CMD-RED-GREEN, CMD-TEST-DATA, CMD-COVERAGE, CMD-LINT, CMD-WRITESET passed", "contract diff empty; write-set union S03, S06"], "post_step_vv": ["CMD-LINT", "CMD-TEST-CONTRACTS", "CMD-TEST-ALL", "CMD-TEST-DASH", "CMD-SMOKE (gm-smoke-integration:18000)", "PROC-ASSEMBLY"], "rollback": "git revert -m 1 <S09-D merge>; CMD-TEST-ALL and CMD-SMOKE on the revert; return the data lane", "exit": "Green; with no GRIDMARKET_WORKER_URL the poller is not started and /v1/signals, /v1/predictions answer empty or stale with age_s and the disclaimer"},
    {"id": "S09-E", "slice": "S09", "phase": "1a", "order": 5, "merges": {"lane": "ui", "exit_commit_of": "S07"}, "entry_criteria": ["S09-D green", "S07 exit SHA recorded; CMD-RED-GREEN, CMD-TEST-DASH incl. production build, CMD-WRITESET passed; S04 Astryx build state recorded", "contract diff empty, except package.json, package-lock.json, vite.config.ts when S04 recorded red (recorded as amendment, CMD-DEPSCAN passed)"], "post_step_vv": ["CMD-LINT", "CMD-TEST-CONTRACTS", "CMD-TEST-ALL", "CMD-TEST-DASH", "CMD-SMOKE (gm-smoke-integration:18000)", "CMD-SECRETS", "CMD-RULES", "PROC-ASSEMBLY", "AC-GM-ACC-03 acceptance run (seit ID pending CF-28; no tunnel, no live data needed)"], "rollback": "git revert -m 1 <S09-E merge>; CMD-TEST-DASH and CMD-SMOKE on the revert; return the ui lane; pages and providers-page lanes must re-sync to the repaired S07 exit (CF-30)", "exit": "Phase 1a candidate recorded (head SHA, tree SHA, configuration identity); evidence committed and pushed; handed to one Reviewer and one Assurance TE pass (DEC-GM-038); repair exits merged here; deterministic verification CMD-TEST-ALL, CMD-SMOKE, CMD-SECRETS, CMD-RULES decides"},
    {"id": "S09-L", "slice": "S09", "phase": "1a", "order": 6, "merges": {"lane": "landing", "exit_commit_of": "phase 1a candidate after assurance"}, "entry_criteria": ["phase 1a assurance passed (review, at most one repair, deterministic verification green)"], "post_step_vv": ["Orchestrator landing commands (PR --merge to main, post-merge CMD-TEST-ALL, CMD-TEST-DASH, CMD-SMOKE gm-smoke-main:18003 on origin/main)", "cleanup: foundation, worker, market, data, ui, integration-1a per the three-check deletion rule"], "rollback": "Post-merge V&V red on main: Orchestrator opens a revert PR of the phase merge commit (git revert -m 1 on a branch from main, merge commit, no force) and re-lands after repair; branches are not deleted until main is green", "exit": "main holds phase 1a; AC-GM-LAND-01 inspected; owner notified that OWN-WORKER-DEPLOY-1 can deploy from this main commit, then the owner runs PROC-ERCOT-LIVE-CHECK (Scribe records); all 1b+ lanes that wait on the 1a landing may merge main"},
    {"id": "S49-A", "slice": "S49", "phase": "1b", "order": 7, "merges": {"lane": "bots", "exit_commit_of": "S31, or S29 if the Sat 14:00 CDT slip trigger fired"}, "entry_criteria": ["S09-L landed; gridmarket/integration-1b created from origin/main", "exit SHA recorded; CMD-RED-GREEN, CMD-TEST-BOTS, CMD-COVERAGE, CMD-LINT, CMD-WRITESET passed; lane contains main after the 1a landing", "slip decision recorded by the Scribe"], "post_step_vv": ["CMD-LINT", "CMD-TEST-CONTRACTS", "CMD-TEST-ALL", "CMD-TEST-BOTS", "CMD-TEST-DASH", "CMD-SMOKE (gm-smoke-integration:18000)", "PROC-ASSEMBLY"], "rollback": "git revert -m 1; CMD-TEST-ALL and CMD-SMOKE on the revert; return the bots lane", "exit": "Green; /v1/bots lists 60 bots of the AC-GM-BOT-02 type counts; /v1/bots/diversity present only if S31 merged"},
    {"id": "S49-B", "slice": "S49", "phase": "1b", "order": 8, "merges": {"lane": "router", "exit_commit_of": "S33"}, "entry_criteria": ["S49-A green", "S33 exit recorded; CMD-RED-GREEN, CMD-TEST-ROUTER, CMD-COVERAGE, CMD-LINT, CMD-WRITESET passed; lane contains main after the 1a landing"], "post_step_vv": ["CMD-LINT", "CMD-TEST-CONTRACTS", "CMD-TEST-ALL", "CMD-TEST-ROUTER", "CMD-TEST-DASH", "CMD-SMOKE (gm-smoke-integration:18000)", "PROC-ASSEMBLY"], "rollback": "git revert -m 1; rerun on the revert; return the router lane", "exit": "Green; /v1/router answers with Jev flag off and CORS for GRIDMARKET_CORS_ORIGIN"},
    {"id": "S49-C", "slice": "S49", "phase": "1b", "order": 9, "merges": {"lane": "views", "exit_commit_of": "S27"}, "entry_criteria": ["S49-B green", "S27 exit recorded; CMD-RED-GREEN-WORKER, CMD-TEST-WORKER, CMD-WRITESET passed; lane based on the S25 exit that main holds and contains main after the 1a landing (CF-30)"], "post_step_vv": ["CMD-TEST-WORKER", "CMD-TEST-ALL", "CMD-TEST-DASH", "CMD-SMOKE (gm-smoke-integration:18000)", "CMD-RULES", "PROC-ASSEMBLY"], "rollback": "git revert -m 1; CMD-TEST-WORKER on the revert; return the views lane; the deployed Worker stays on OWN-WORKER-DEPLOY-1", "exit": "Green; owner notified for OWN-WORKER-DEPLOY-2 from this integration head (typed gap VIEWS_NOT_DEPLOYED if not done)"},
    {"id": "S49-D", "slice": "S49", "phase": "1b", "order": 10, "merges": {"lane": "pages", "exit_commit_of": "S51"}, "entry_criteria": ["S49-C green or views returned (pages do not depend on views)", "S51 exit recorded; CMD-RED-GREEN, CMD-TEST-DASH incl. build, CMD-WRITESET passed; lane contains the S07 exit that main holds"], "post_step_vv": ["CMD-TEST-CONTRACTS", "CMD-TEST-ALL", "CMD-TEST-DASH", "CMD-SMOKE (gm-smoke-integration:18000)", "PROC-ASSEMBLY"], "rollback": "git revert -m 1; CMD-TEST-DASH and CMD-SMOKE on the revert; return the pages lane", "exit": "Green; every App.tsx route renders its page"},
    {"id": "S49-E", "slice": "S49", "phase": "1b", "order": 11, "merges": {"lane": "spec", "exit_commit_of": "S21 (complete-or-defer: only if green at S49-E entry)"}, "entry_criteria": ["S49-D green", "S21 exit recorded; CMD-RED-GREEN, CMD-TEST-SPEC, CMD-SPEC-LINT, CMD-WRITESET passed; Graphviz and draw.io versions recorded; else record deferred to S12-E"], "post_step_vv": ["CMD-TEST-SPEC", "CMD-SPEC-LINT", "CMD-TEST-ALL", "CMD-TEST-DASH", "CMD-SMOKE (gm-smoke-integration:18000)", "CMD-SECRETS", "CMD-RULES", "PROC-ASSEMBLY", "PROC-ERCOT-LIVE-CHECK (owner-run, after OWN-WORKER-DEPLOY-1 and OWN-WORKER-ENV, demo poller stopped; Scribe records)", "AC-GM-ACC-01 acceptance run (owner, tunnel, after OWN-WORKER-DEPLOY-2)"], "rollback": "git revert -m 1; rerun on the revert; spec deferred to S12-E", "exit": "Phase 1b candidate recorded incl. slip-trigger and spec-defer outcome; assurance handoff as in S09-E; deterministic verification decides"},
    {"id": "S49-L", "slice": "S49", "phase": "1b", "order": 12, "merges": {"lane": "landing", "exit_commit_of": "phase 1b candidate after assurance"}, "entry_criteria": ["phase 1b assurance passed"], "post_step_vv": ["Orchestrator landing commands (PR --merge, post-merge V&V on origin/main)", "cleanup: router, views, pages, integration-1b; bots only if S31 merged; spec only if S21 merged"], "rollback": "revert PR of the phase merge commit on main; branches kept until main is green", "exit": "main holds phase 1b; target Sat 16:00 CDT"},
    {"id": "S12-A", "slice": "S12", "phase": "2", "order": 13, "merges": {"lane": "lonestar", "exit_commit_of": "S11"}, "entry_criteria": ["S49-L landed; gridmarket/integration-2 created from origin/main", "S11 exit recorded; CMD-RED-GREEN, CMD-TEST-PROVIDERS, CMD-TEST-ALL, CMD-WRITESET passed; lane contains main after the 1b landing"], "post_step_vv": ["CMD-LINT", "CMD-TEST-CONTRACTS", "CMD-TEST-ALL", "CMD-TEST-PROVIDERS", "CMD-TEST-DASH", "CMD-SMOKE (gm-smoke-integration:18000)", "PROC-ASSEMBLY"], "rollback": "git revert -m 1; rerun on the revert; return the lonestar lane", "exit": "Green; /v1/providers lists base_sim and lonestar with >= 20 LoneStar customers; /v1/providers/health answers"},
    {"id": "S12-B", "slice": "S12", "phase": "2", "order": 14, "merges": {"lane": "providers-page", "exit_commit_of": "S35"}, "entry_criteria": ["S12-A green or lonestar returned", "S35 exit recorded; CMD-RED-GREEN, CMD-TEST-DASH incl. build, CMD-WRITESET passed"], "post_step_vv": ["CMD-TEST-CONTRACTS", "CMD-TEST-ALL", "CMD-TEST-DASH", "CMD-SMOKE (gm-smoke-integration:18000)", "PROC-ASSEMBLY"], "rollback": "git revert -m 1; rerun on the revert; return the lane", "exit": "Green"},
    {"id": "S12-C", "slice": "S12", "phase": "2", "order": 15, "merges": {"lane": "kit", "exit_commit_of": "S37"}, "entry_criteria": ["S12-B green or returned", "S37 exit recorded; CMD-RED-GREEN, CMD-TEST-KIT, CMD-WRITESET passed"], "post_step_vv": ["CMD-TEST-KIT", "CMD-TEST-ALL", "CMD-TEST-DASH", "CMD-SMOKE (gm-smoke-integration:18000)", "PROC-ASSEMBLY (/kit/ served when docs/llm/ present)"], "rollback": "git revert -m 1; rerun on the revert; return the lane", "exit": "Green"},
    {"id": "S12-D", "slice": "S12", "phase": "2", "order": 16, "merges": {"lane": "bots", "exit_commit_of": "S31 (only if the slip trigger fired)"}, "entry_criteria": ["S12-C green or returned", "S31 exit recorded; CMD-RED-GREEN, CMD-TEST-BOTS, CMD-WRITESET passed; write-set check over <S29 exit>..<S31 exit>"], "post_step_vv": ["CMD-TEST-BOTS", "CMD-TEST-ALL", "CMD-TEST-DASH", "CMD-SMOKE (gm-smoke-integration:18000)", "PROC-ASSEMBLY"], "rollback": "git revert -m 1; rerun on the revert; diversity recorded dropped", "exit": "Green; /v1/bots/diversity answers"},
    {"id": "S12-E", "slice": "S12", "phase": "2", "order": 17, "merges": {"lane": "spec", "exit_commit_of": "S21 (only if deferred from S49-E and green now; else deferred to S18)"}, "entry_criteria": ["S12-D green, returned, or not applicable", "S21 exit recorded with CMD-TEST-SPEC, CMD-SPEC-LINT passed"], "post_step_vv": ["CMD-TEST-SPEC", "CMD-SPEC-LINT", "CMD-TEST-ALL", "CMD-TEST-DASH", "CMD-SMOKE (gm-smoke-integration:18000)", "CMD-SECRETS", "CMD-RULES", "PROC-ASSEMBLY", "AC-GM-ACC-02 acceptance run incl. the simulated LoneStar outage (owner, tunnel)"], "rollback": "git revert -m 1; rerun on the revert; spec deferred to S18", "exit": "Phase 2 candidate recorded; assurance handoff; deterministic verification decides"},
    {"id": "S12-L", "slice": "S12", "phase": "2", "order": 18, "merges": {"lane": "landing", "exit_commit_of": "phase 2 candidate after assurance"}, "entry_criteria": ["phase 2 assurance passed"], "post_step_vv": ["Orchestrator landing commands", "cleanup: lonestar, providers-page, kit, integration-2; bots if S31 merged here; spec if S21 merged here"], "rollback": "revert PR on main; branches kept", "exit": "main holds phase 2; target Sat 19:00 CDT"},
    {"id": "S18-A", "slice": "S18", "phase": "stretch", "order": 19, "merges": {"lane": "adversary", "exit_commit_of": "S14"}, "entry_criteria": ["S12-L landed; S18 starts at the later of the phase 2 landing and the earlier of (all stretch lanes green, Sat 22:00 CDT) (CF-32); gridmarket/integration-stretch created from origin/main", "every stretch lane not green at S18 start is recorded dropped (complete-or-drop); S21 merged here if still deferred and green", "S14 exit recorded; CMD-RED-GREEN, CMD-TEST-ADVERSARY, CMD-TEST-ALL, CMD-WRITESET passed"], "post_step_vv": ["CMD-TEST-CONTRACTS", "CMD-TEST-ALL", "CMD-TEST-ADVERSARY", "CMD-TEST-DASH", "CMD-SMOKE (gm-smoke-integration:18000)", "PROC-ASSEMBLY (admin halt/resume in openapi)"], "rollback": "git revert -m 1; rerun on the revert; record adversary dropped", "exit": "Green"},
    {"id": "S18-B", "slice": "S18", "phase": "stretch", "order": 20, "merges": {"lane": "backtest", "exit_commit_of": "S16"}, "entry_criteria": ["S18-A closed (green, reverted, or dropped)", "S16 exit recorded; CMD-RED-GREEN, CMD-TEST-BACKTEST, CMD-WRITESET passed; full backend suite green without the Rust extension (parity Rust case skips)"], "post_step_vv": ["CMD-TEST-ALL", "CMD-TEST-BACKTEST", "CMD-SMOKE (gm-smoke-integration:18000)", "PROC-ASSEMBLY"], "rollback": "git revert -m 1; rerun on the revert; S18-F (ml) and S18-G (rust) are then skipped because both carry the S16 exit (CF-24, CF-25)", "exit": "Green"},
    {"id": "S18-C", "slice": "S18", "phase": "stretch", "order": 21, "merges": {"lane": "jev", "exit_commit_of": "S43"}, "entry_criteria": ["S18-B closed", "S43 exit recorded; CMD-RED-GREEN, CMD-TEST-JEV, CMD-WRITESET passed; lane contains main after the 1b landing"], "post_step_vv": ["CMD-TEST-JEV", "CMD-TEST-ROUTER", "CMD-TEST-ALL", "CMD-SMOKE (gm-smoke-integration:18000; GRIDMARKET_JEV unset)", "PROC-ASSEMBLY"], "rollback": "git revert -m 1; rerun on the revert; record jev dropped", "exit": "Green; Jev off by default"},
    {"id": "S18-D", "slice": "S18", "phase": "stretch", "order": 22, "merges": {"lane": "mcp", "exit_commit_of": "S39"}, "entry_criteria": ["S18-C closed", "S39 exit recorded; CMD-RED-GREEN, CMD-TEST-MCP, CMD-DEPSCAN, CMD-WRITESET passed"], "post_step_vv": ["CMD-TEST-MCP", "CMD-TEST-ALL", "CMD-SMOKE (gm-smoke-integration:18000)", "CMD-DEPSCAN", "PROC-ASSEMBLY"], "rollback": "git revert -m 1; rerun on the revert; record mcp dropped", "exit": "Green"},
    {"id": "S18-E", "slice": "S18", "phase": "stretch", "order": 23, "merges": {"lane": "quant", "exit_commit_of": "S41"}, "entry_criteria": ["S18-D closed", "S41 exit recorded; CMD-RED-GREEN, CMD-TEST-QUANT (quant extra installed), CMD-WRITESET passed; quant extra still locked in S01 pyproject (else lane dropped, RISK-GM-17)"], "post_step_vv": ["CMD-TEST-QUANT", "CMD-TEST-ALL", "CMD-SMOKE (gm-smoke-integration:18000; image never references the quant extra)", "PROC-ASSEMBLY"], "rollback": "git revert -m 1; rerun on the revert; record quant dropped", "exit": "Green"},
    {"id": "S18-F", "slice": "S18", "phase": "stretch", "order": 24, "merges": {"lane": "ml", "exit_commit_of": "S23"}, "entry_criteria": ["S18-B merged green and not reverted (CF-25)", "S23 exit recorded; CMD-RED-GREEN, CMD-TEST-ML, CMD-WRITESET passed"], "post_step_vv": ["CMD-TEST-ML", "CMD-TEST-ALL", "CMD-SMOKE (gm-smoke-integration:18000)", "PROC-ASSEMBLY"], "rollback": "git revert -m 1; rerun on the revert; record ml dropped", "exit": "Green; docs/ml-report.md from one owner-run live run or marked fixture-only"},
    {"id": "S18-G", "slice": "S18", "phase": "stretch", "order": 25, "merges": {"lane": "rust", "exit_commit_of": "S17"}, "entry_criteria": ["S18-B merged green and not reverted (CF-24)", "S17 exit recorded; CMD-RED-GREEN, CMD-TEST-PARITY (extension built), CMD-BENCH, CMD-DEPSCAN, CMD-SMOKE gm-smoke-rust:18002, CMD-WRITESET passed", "bench/results.md shows Rust orders/s strictly higher than Python on the identical workload; else skipped and recorded"], "post_step_vv": ["CMD-TEST-ALL", "CMD-TEST-PARITY (in the built image)", "CMD-SMOKE (gm-smoke-integration:18000)", "CMD-SECRETS", "CMD-RULES", "CMD-REVERIFY-RUST (binary claim; handed to Assurance TE)", "PROC-ASSEMBLY"], "rollback": "git revert -m 1; rerun on the revert (image without Rust stage); record rust dropped", "exit": "Stretch candidate recorded with dropped-lane list; assurance handoff; deterministic verification decides. If S18-G does not run, CMD-SECRETS and CMD-RULES run on the last stretch step, and Reverify is recorded not applicable: no binary artifact"},
    {"id": "S18-L", "slice": "S18", "phase": "stretch", "order": 26, "merges": {"lane": "landing", "exit_commit_of": "stretch candidate after assurance"}, "entry_criteria": ["stretch assurance passed", "no later than Sun 03:00 CDT (CF-32)"], "post_step_vv": ["Orchestrator landing commands", "cleanup: merged stretch lanes, integration-stretch; dropped lanes kept and listed"], "rollback": "revert PR on main; branches kept", "exit": "main holds stretch; target Sun 00:30 CDT; wave 3 lanes branch from this main commit"},
    {"id": "S46-A", "slice": "S46", "phase": "final", "order": 27, "merges": {"lane": "docs", "exit_commit_of": "S45"}, "entry_criteria": ["S18-L landed; gridmarket/integration-final created from origin/main", "S45 exit recorded; CMD-RED-GREEN, CMD-TEST-DOCS, CMD-WRITESET passed"], "post_step_vv": ["CMD-TEST-DOCS", "CMD-TEST-ALL", "CMD-TEST-DASH", "CMD-SMOKE (gm-smoke-integration:18000; /llms.txt and /guide.md served)", "PROC-ASSEMBLY"], "rollback": "git revert -m 1; rerun on the revert; return the docs lane", "exit": "Green"},
    {"id": "S46-B", "slice": "S46", "phase": "final", "order": 28, "merges": {"lane": "onboarding", "exit_commit_of": "S48"}, "entry_criteria": ["S46-A closed", "S48 exit recorded; CMD-RED-GREEN, CMD-TEST-DASH incl. build, CMD-WRITESET passed"], "post_step_vv": ["CMD-TEST-DASH", "CMD-TEST-DOCS", "CMD-TEST-ALL", "CMD-SMOKE (gm-smoke-integration:18000)", "CMD-SECRETS (full history, AC-GM-SEC-01)", "CMD-RULES", "PROC-ASSEMBLY", "AC-GM-DOC-02 guide demonstration (clean agent session, sandbox key)"], "rollback": "git revert -m 1; rerun on the revert; return the lane", "exit": "Final candidate recorded; assurance handoff; deterministic verification decides"},
    {"id": "S46-L", "slice": "S46", "phase": "final", "order": 29, "merges": {"lane": "landing", "exit_commit_of": "final candidate after assurance"}, "entry_criteria": ["final assurance passed", "before Sun 07:00 CDT freeze"], "post_step_vv": ["Orchestrator landing commands", "cleanup: docs, onboarding, integration-final; Scribe lists kept (unmerged or dropped) branches for the owner"], "rollback": "after the freeze only a revert PR to the last green main commit", "exit": "main is the submission candidate; handed to the Lifecycle-end IE assessment and Assurance TE"}
  ],
  "configuration_identity": {
    "record_at": "every step exit, in that phase's evidence file",
    "fields": {
      "integration_head_sha": "git rev-parse gridmarket/integration-<phase>",
      "code_tree_sha": "git rev-parse <merge-or-revert-sha>^{tree}",
      "main_landing_sha": "origin/main merge commit SHA of each phase PR and its PR number",
      "lane_exit_shas": "every exit SHA merged, reverted, skipped, deferred, slipped, or dropped, with status",
      "external_shas": "jordaaan 4853e51 (worker lane base); PR #3 state after the 1a landing",
      "contract_baseline": "blob SHAs of the frozen files at S09-A and after every recorded amendment (CF-26)",
      "worker_delivery": "deployed Worker source SHA and Cloudflare version ID as reported by the owner for OWN-WORKER-DEPLOY-1 and -2, or typed gaps",
      "compose_file": "deploy/compose.yaml blob SHA; compose project used",
      "dockerfile": "deploy/Dockerfile blob SHA",
      "image": "docker image inspect --format '{{.Id}}' of the smoke image built from code_tree_sha",
      "engine": "GRIDMARKET_ENGINE effective value: python unless S18-G merged with a benchmark gain",
      "provider_registry": "[base_sim] after 1a, [base_sim, lonestar] after S12-A",
      "slip_and_defer": "slip trigger fired or not (Scribe); spec merged at S49-E, S12-E, S18, or dropped",
      "env_var_names_only": "names in .env.example at code_tree_sha, names only",
      "toolchain": "python, uv, node, npm, docker, docker compose, gitleaks, graphviz, draw.io, cargo and maturin (if S18-G) versions"
    },
    "never_record": "credential values, .env contents, MARKET_KEY or GRIDMARKET_WORKER_KEY values, Jev key, tokens, API key plaintext, tunnel credential contents"
  },
  "authorized_glue": {
    "product_paths": "none",
    "allowed_writes": ["IE: git merge --no-ff <recorded exit SHA> on gridmarket/integration-<phase>", "IE: git revert -m 1 <merge> and revert-of-revert", "IE: evidence file docs/plans/2026-09-25-gridmarket/evidence/assembly-<phase>.md committed on the phase integration branch", "IE: non-force git push origin gridmarket/integration-<phase>", "Orchestrator (DEC-GM-040): phase PR open and merge with --merge; revert PR of a phase merge commit; git worktree remove, git branch -d, git push origin --delete, git worktree prune for lanes that pass the three-check deletion rule"],
    "conflicts": "Resolve only whitespace-only hunks. Any other conflict: git merge --abort and return the owning lane.",
    "forbidden": ["editing product, test, configuration, dependency, compose, or contract files", "weakening, skipping, or deselecting tests", "force-push, reset --hard, history rewrite, git switch, git branch -D, worktree remove --force", "reading or printing .env, MARKET_KEY, Jev key, or tunnel credentials", "pushing to jordaaan or directly to main, squash or rebase merge, gh pr merge --admin or --delete-branch", "deploying the Worker, tunnel start, public flip"]
  },
  "stubs": [
    {"id": "STUB-S01-CONTRACTS", "what": "S01 placeholder modules and dashboard page stubs satisfying contracts.py, CONTRACTS.md, App.tsx, hooks.ts with empty behavior (incl. keys, bots, adversary.halted/observe, adversary_api, providers/lonestar disabled, health.is_online True, jev off, SDK Client signatures)", "scope": "every wave 2 lane codes against them (DEC-GM-039)", "removed_by": "the owning lane's product slice replaces the behavior; the names never change without an amendment"},
    {"id": "STUB-WORKER-FIXTURES", "what": "backend/tests/fixtures/ercot/, nws/, ercot_history/, ml/", "scope": "tests only", "removed_by": "never in the live path"},
    {"id": "STUB-WORKER-ENV", "what": "S24 and S26 stub env (in-memory CACHE, RATE_LIMITER, ERCOT_BUDGET) and stub fetch", "scope": "CMD-TEST-WORKER only", "removed_by": "never; deployed Worker uses real bindings (owner)"},
    {"id": "STUB-DASH-FIXTURES", "what": "dashboard/src/fixtures/overview.json, phase1b.json, providers.json, onboarding.json", "scope": "vitest only", "removed_by": "never"},
    {"id": "STUB-JEV-SERVER", "what": "local stub HTTP server in test_jev.py", "scope": "tests only", "removed_by": "never; live Jev is owner-enabled"},
    {"id": "SIM-NO-WORKER", "what": "app with no GRIDMARKET_WORKER_URL and GRIDMARKET_NWS=off", "scope": "every CMD-SMOKE run", "removed_by": "owner .env for the demo stack and PROC-ERCOT-LIVE-CHECK"},
    {"id": "SIM-ENGINE-FALLBACK", "what": "Python engine when the Rust extension is absent", "scope": "all steps before S18-G", "removed_by": "S18-G only with a benchmark gain"}
  ],
  "anomaly_rollback_recovery": {
    "anomaly_classes": [
      {"id": "AN-CONTRACT", "trigger": "frozen-file diff against the current baseline, or CMD-TEST-CONTRACTS red", "action": "CONTRACT_STOP; do not merge; route as a contract amendment (CF-26)"},
      {"id": "AN-WRITESET", "trigger": "non-merge commits of the lane touch a path outside the lane write-set union", "action": "do not merge; return the lane"},
      {"id": "AN-CONFLICT", "trigger": "non-whitespace merge conflict", "action": "git merge --abort; return the lane"},
      {"id": "AN-PRODUCT-RED", "trigger": "post-step V&V fails on the merge commit", "action": "revert the merge; confirm the revert is green; return the lane with the failing output"},
      {"id": "AN-FLAKE", "trigger": "same command passes and fails on the same SHA", "action": "rerun once; if still inconsistent treat as AN-PRODUCT-RED; never skip or deselect"},
      {"id": "AN-ENV", "trigger": "Docker, disk, port-in-use, Node, Graphviz, draw.io, cargo failure not caused by the merged code", "action": "fix local tooling (agent work); never touch project gridmarket; rerun the same SHA"},
      {"id": "AN-WORKER-LIVE", "trigger": "PROC-ERCOT-LIVE-CHECK keyed call 401/404, 503 secrets missing, or keyless call not 401", "action": "no revert; typed gap WORKER_FIX_NOT_DEPLOYED or WORKER_KEY_MISMATCH; tell the owner"},
      {"id": "AN-ERCOT", "trigger": "Worker 429, 502, or timeout during the live check", "action": "typed gap ERCOT_LIVE_UNAVAILABLE; one retry after 60 s; no revert"},
      {"id": "AN-SECRET", "trigger": "CMD-SECRETS finding", "action": "stop; do not push or land; revert the merge that introduced it; notify the owner; rotation and history rewrite are owner-only"},
      {"id": "AN-LAND-RED", "trigger": "post-merge V&V red on origin/main after a phase PR", "action": "Orchestrator opens a revert PR of the phase merge commit; branches kept; re-land after repair"},
      {"id": "AN-DEMO-CRASH", "trigger": "demo stack crashes after a landing", "action": "Orchestrator restarts the demo from the last green main commit; revert PR if the crash reproduces"}
    ],
    "corrections_bound": "at most three evidence-driven corrections per step, then BLOCKED with evidence",
    "rollback": "git revert -m 1 <merge-sha> on the phase integration branch, rerun the step's post_step_vv on the revert commit, push non-force",
    "re_entry_after_repair": "For a new exit SHA of a reverted lane: git revert <revert-sha>, git merge --no-ff <new exit SHA>, full post_step_vv; if red, revert both and record the lane returned or dropped. If a reverted merge has already landed on main, the lane's original commits are ancestors of main, so any later phase must re-enter the lane the same way (revert-of-revert first). A lane that lane-synced a reverted exit (views from S25; pages and providers-page from S07) merges main after the landing and the repaired exit before its own exit (CF-30).",
    "recovery": ["Workstation failure: integration branches are pushed after every green step; recreate the worktree from origin at the last green SHA", "Demo SQLite volume loss: restart the demo stack; seed.py reseeds", "Lane session loss: the lane branch at its last commit is the state; re-dispatch the same slice on the same or fallback route", "Worker regression after an owner redeploy: market serves stale with age_s; owner rolls back the deployment", "IE execution route exhausted: ordered fallback as a fresh session with no author ancestry (DEC-GM-040 load split)"]
  },
  "cutoffs": {
    "timezone": "America/Chicago",
    "wave_1": "S01 and S25 exits target Sat 2026-09-26 01:30 after the CF-21 planning PR lands; no wave 2 slice starts before the S01 exit is recorded (AC-GM-CONTRACT-01)",
    "phase_1a": "landed on main about Sat 2026-09-26 10:00",
    "slip_check": "Sat 2026-09-26 14:00: S31 not green on lane bots => S49-A merges the S29 exit, S12-D merges S31 (Scribe records)",
    "phase_1b": "landed about Sat 2026-09-26 16:00; spec not green at S49-E => deferred to S12-E",
    "phase_2": "landed about Sat 2026-09-26 19:00",
    "stretch": "S18 starts at the later of the phase 2 landing and the earlier of (all stretch lanes green, Sat 2026-09-26 22:00); lanes not green at start are dropped; landed target Sun 2026-09-27 00:30, no later than Sun 03:00 (CF-32)",
    "final": "wave 3 lanes branch from main after the stretch landing; S46 landed target Sun 2026-09-27 05:00",
    "freeze": "Sun 2026-09-27 07:00: no phase PR after the freeze; only a revert PR to the last green main commit if the demo breaks, and guide corrections before the owner's public flip",
    "submission": "Sun 2026-09-27 11:00; public flip is owner-only"
  },
  "final_candidate": {
    "definition": "The origin/main merge commit of the final phase PR (S46-L), whose tree equals the gridmarket/integration-final head that passed assurance, with every lane merged, reverted, skipped, deferred, or dropped with a recorded reason",
    "must_contain": ["phase 1a: foundation, worker, market, data, ui", "phase 1b: bots (S29, S31 unless slipped), router, views, pages, spec unless deferred", "phase 2: lonestar, providers-page, kit, plus slipped bots and deferred spec", "each stretch lane only if its step closed green", "final: docs, onboarding"],
    "must_pass": ["CMD-TEST-CONTRACTS", "CMD-TEST-ALL", "CMD-TEST-DASH", "CMD-TEST-WORKER", "CMD-TEST-DOCS", "CMD-SMOKE", "CMD-SECRETS full history (AC-GM-SEC-01)", "CMD-RULES", "CMD-TEST-SPEC and CMD-SPEC-LINT if spec merged", "frozen-contract blobs equal to the last recorded baseline", "LICENSE (MIT) at the root"],
    "identity": "configuration_identity fields at S46-B plus main_landing_sha of S46-L",
    "fallbacks": ["main after the stretch landing", "main after the phase 2 landing", "main after the phase 1b landing", "main after the phase 1a landing"],
    "handoff": "Assurance Test Engineer and the IE Lifecycle-end assessment; the IE does not self-certify"
  },
  "lifecycle_assessment_inputs": {
    "session": "fresh integration_engineer.execution session on the frozen route with profile fallbacks, no ancestry from any lane author session",
    "inputs": ["final candidate main SHA and tree SHA", "evidence/assembly-phase-1a.md, assembly-phase-1b.md, assembly-phase-2.md, assembly-stretch.md, assembly-final.md with per-step command exits and identities", "per-phase Reviewer receipts and repair rounds, Assurance TE receipts, deterministic-verification outputs, and review.coverage_assist and deterministic_verification.reverify status (presence only)", "landing receipts: PR numbers, main merge SHAs, post-merge V&V, deleted and kept branch lists (AC-GM-LAND-01)", "contract baseline and amendment log (CONTRACTS.md)", "PROC-ERCOT-LIVE-CHECK result or typed gap; deployed Worker identities from the owner", "AC-GM-ACC-03, AC-GM-ACC-01, AC-GM-ACC-02, AC-GM-DOC-02 run results or not-run typed gaps", "anomaly log with typed gaps and dropped lanes", "CMD-REVERIFY-RUST result if S18-G merged, else Reverify: not applicable - no binary artifact", "gridmarket-technical-plan.md Outcome and demo story"],
    "assessment_questions": ["Does the candidate run the demo story end to end, reading ERCOT data only through the owner's deployed Worker?", "Is every CONTRACTS.md interface exercised at its final state, with no unrecorded name change?", "Does the configuration identity match the image, compose file, and deployed Worker used for acceptance and recording?"]
  },
  "owner_dependencies": [
    {"id": "OWN-WORKER-DEPLOY-1", "what": "owner sets Worker secrets and bindings and deploys ercot-hackathon/ from the phase 1a landing commit on main; reports source SHA and version ID", "blocks": ["PROC-ERCOT-LIVE-CHECK", "AC-GM-ACC-01 live data"], "blocks_when": "after S09-L, before S49-E", "if_absent": "typed gap WORKER_FIX_NOT_DEPLOYED"},
    {"id": "OWN-WORKER-DEPLOY-2", "what": "owner sets MARKET_URL and redeploys from the gridmarket/integration-1b head after S49-C (views)", "blocks": ["AC-GM-EDGE-05 live", "AC-GM-ACC-01 views part"], "blocks_when": "after S49-C, before AC-GM-ACC-01", "if_absent": "typed gap VIEWS_NOT_DEPLOYED"},
    {"id": "OWN-WORKER-ENV", "what": "untracked .env at the phase integration worktree root (GRIDMARKET_WORKER_URL, GRIDMARKET_WORKER_KEY, GRIDMARKET_ADMIN_KEY, GRIDMARKET_CORS_ORIGIN)", "blocks": ["PROC-ERCOT-LIVE-CHECK", "live acceptance", "live backtest and ML runs"], "blocks_when": "from S49-E", "if_absent": "typed gap WORKER_ENV_ABSENT"},
    {"id": "OWN-TUNNEL", "what": "Cloudflare named tunnel (PROC-TUNNEL)", "blocks": ["AC-GM-ACC-01", "AC-GM-ACC-02", "recording"], "blocks_when": "S49-E, S12-E, Sunday recording", "if_absent": "acceptance recorded not run; assembly unaffected"},
    {"id": "OWN-JUDGE-KEYS", "what": "python -m gridmarket_server.keys issue --sandbox (owner-run)", "blocks": ["judge quickstart"], "blocks_when": "acceptance", "if_absent": "seeded accounts only"},
    {"id": "OWN-JEV", "what": "Jev key in .env and GRIDMARKET_JEV=on", "blocks": ["live Jev column"], "blocks_when": "after S18-L", "if_absent": "Jev off (default, AC-GM-RULE-02 label stays)"},
    {"id": "OWN-PUBLICATION", "what": "public flip after the final landing, zero secret findings over full history, MIT LICENSE", "blocks": ["public codebase link"], "blocks_when": "after S46-L, before Sun 11:00", "if_absent": "IE hands over the AC-GM-SEC-01 result"},
    {"id": "OWN-BRANCH-PRUNE", "what": "owner decides deletion of unmerged or dropped lane branches listed by the Scribe", "blocks": [], "blocks_when": "after the freeze", "if_absent": "branches remain; no effect on the candidate"}
  ],
  "concurrency_findings": [
    {"id": "CF-01", "severity": "high", "kind": "defect", "status": "resolved", "where": "foundation assembly", "problem": "No step assembled the foundation lane.", "corrected_text": "Applied: S09-A merges foundation first; wave 2 lanes branch from the S01 exit."},
    {"id": "CF-02", "severity": "high", "kind": "defect (hidden read dependency)", "status": "resolved", "where": "S01 row", "problem": "main.py imported modules created later.", "corrected_text": "Applied and widened by DEC-GM-039: S01 stubs every shared module and page."},
    {"id": "CF-03", "severity": "high", "kind": "defect (shared resource)", "status": "resolved", "where": "Concurrency proof ERCOT bullet", "problem": "Multiple pollers could exceed the ERCOT limit.", "corrected_text": "Applied: Worker owns the budget; poller 12, backtest 5, ML 5; smoke without GRIDMARKET_WORKER_URL."},
    {"id": "CF-04", "severity": "medium", "kind": "defect (shared resource)", "status": "resolved", "where": "Docker/port bullet", "problem": "Smoke stacks collided with the demo.", "corrected_text": "Applied: per-run project and port; no fixed image, container_name, or volume name."},
    {"id": "CF-05", "severity": "medium", "kind": "defect (shared resource)", "status": "resolved", "where": "SQLite bullet", "problem": "SQLite paths not covered.", "corrected_text": "Applied: tmp_path in tests; project-scoped gm-data volume."},
    {"id": "CF-06", "severity": "high", "kind": "defect", "status": "resolved", "where": "S15 row", "problem": "Red Rust parity tests in a merged exit.", "corrected_text": "Applied: Rust parametrization skips without the extension."},
    {"id": "CF-07", "severity": "medium", "kind": "defect", "status": "resolved", "where": "Dependencies", "problem": "Stretch lanes hard-blocked S18.", "corrected_text": "Applied: complete-or-drop edges into S18."},
    {"id": "CF-08", "severity": "medium", "kind": "defect", "status": "resolved", "where": "DES-GM-OPS", "problem": "Mandatory env_file broke lane smoke.", "corrected_text": "Applied: env_file required: false."},
    {"id": "CF-09", "severity": "medium", "kind": "gap", "status": "superseded", "where": "old spec, ML, Rust lanes", "problem": "Planning delta lacked steps.", "corrected_text": "Superseded by the 51-slice graph; every lane now has a step (S49-E, S18-F, S18-G)."},
    {"id": "CF-10", "severity": "low", "kind": "defect", "status": "resolved", "where": "S01 .gitignore", "problem": "Build outputs flagged by CMD-WRITESET.", "corrected_text": "Applied."},
    {"id": "CF-11", "severity": "low", "kind": "note", "status": "resolved", "where": "S05, S06", "problem": "Cross-lane reads.", "corrected_text": "Applied: registry-derived /v1/providers; budget-parameter limiter."},
    {"id": "CF-12", "severity": "info", "kind": "verified", "status": "resolved (re-verified for the 51-slice graph)", "where": "slice-graph.md Concurrency proof", "problem": "none", "corrected_text": "Mechanical check: 4 cross-lane overlaps outside S01 (S08/S17, S25/S27, S08/S45, S51/S48), each ordered by a dependency path; every S01 overlap ordered by an S01 edge; every slice reaches its assembly slice."},
    {"id": "CF-13", "severity": "medium", "kind": "defect", "status": "superseded", "where": "lane cap", "problem": "Cap counted per wave.", "corrected_text": "Superseded by DEC-GM-039/040: no lane cap; route capacity and disjoint write sets limit concurrency."},
    {"id": "CF-14", "severity": "medium", "kind": "defect", "status": "superseded", "where": "jordaaan edits", "problem": "Concurrent Jordan edits vs the lane PR.", "corrected_text": "Superseded by DEC-GM-027: no PR into jordaaan; the lane is pinned to 4853e51; later jordaaan commits do not enter."},
    {"id": "CF-15", "severity": "medium", "kind": "defect", "status": "superseded by CF-24 and CF-25", "where": "S18 order", "problem": "Rust and ML depend on the backtest merge.", "corrected_text": "See CF-24, CF-25; S18-F and S18-G require S18-B merged and not reverted."},
    {"id": "CF-16", "severity": "medium", "kind": "defect", "status": "resolved", "where": "S25 --> S09, S21 --> S12", "problem": "Hard edges gated whole assembly slices.", "corrected_text": "Worker is phase 1a core (S09-B); spec is complete-or-defer into S49."},
    {"id": "CF-17", "severity": "low", "kind": "defect", "status": "resolved (generalized in re_entry_after_repair)", "where": "revert of a merge", "problem": "Reverted content does not return through later merges.", "corrected_text": "Revert-of-revert before re-entry, in any later phase too."},
    {"id": "CF-18", "severity": "low", "kind": "defect", "status": "resolved", "where": "S01 row, CMD-SMOKE", "problem": "Smoke stacks polled NWS.", "corrected_text": "Applied: GRIDMARKET_NWS=off in smoke; S01 main.py gate."},
    {"id": "CF-19", "severity": "medium", "kind": "owner decision", "status": "resolved", "where": "DES-GM-LANES worker bullet", "problem": "Landing Jordan's commits while PR #3 is open.", "corrected_text": "Resolved by DEC-GM-027 and DES-GM-LANES: the phase 1a PR carries Jordan's commits with authorship; PR #3 then shows merged; recorded."},
    {"id": "CF-20", "severity": "low", "kind": "defect", "status": "resolved", "where": "S23 row", "problem": "Stale ERCOT key wording.", "corrected_text": "Applied: live run through the Worker, owner-loaded env."},
    {"id": "CF-21", "severity": "high", "kind": "read dependency (planning inputs uncommitted, branch diverged)", "status": "open", "where": "owner checkout gridmarket/lifecycle-setup at e71bd81: design.md, slice-graph.md, views modified and uncommitted; lifecycle-setup is not a descendant of origin/main (merge base a63c8d2; main 712f63a is the PR #2 merge)", "problem": "The phase integration branches are created from main, and S21 and the Reviewer read design.md and the technical plan. If S01 branches from main before the approved package is on main, lanes lack the design; if foundation branches from lifecycle-setup, the 1a PR drags 16+ planning commits into main through a product PR.", "corrected_text": "Add to DES-GM-LANES: 'Before S01 dispatch, the Orchestrator commits the approved planning package on gridmarket/lifecycle-setup, pushes it, and lands it on main through a PR with a merge commit; lane foundation and gridmarket/integration-1a branch from that main commit.'"},
    {"id": "CF-22", "severity": "info", "kind": "owner change", "status": "superseded", "where": "DEC-GM-025", "problem": "4-lane cap and red-test lanes.", "corrected_text": "Superseded by DEC-GM-039 (one wide wave, phase-scoped lanes)."},
    {"id": "CF-23", "severity": "medium", "kind": "owner change", "status": "superseded", "where": "DEC-GM-023 phase PRs", "problem": "OD-WORKER-LANDING at S09.", "corrected_text": "Superseded by DEC-GM-027/040: phase PRs land after assurance; no OD-WORKER-LANDING."},
    {"id": "CF-24", "severity": "high", "kind": "defect (hidden read dependency)", "status": "open", "where": "slice-graph.md Dependencies 'S15 --> S17, S16 --> S17' and S17 row", "problem": "S17 runs CMD-TEST-PARITY and CMD-BENCH, which need backend/tests/test_matching_parity.py and bench/bench_matching.py from S15 on lane backtest. The edges are plain, so lane rust (from the S01 exit plus main after 1a) does not contain them and S17 cannot pass. Merging only the S15 exit would carry red test_backtest.py (CMD-TEST-ALL red).", "corrected_text": "Replace 'S15 --> S17, S16 --> S17' with 'S16 --> S17 (lane-sync)'. S17 goal: '...; before S17 the lane merges main after the phase 1a landing and the S16 exit (--no-ff).' S18 goal: 'merge Rust (S17) only after backtest (S16) merged green and not reverted.'"},
    {"id": "CF-25", "severity": "high", "kind": "defect (hidden read dependency)", "status": "open", "where": "slice-graph.md Dependencies 'S16 --> S23'; design.md DES-GM-ML ('reuses the backtest harness')", "problem": "ml.py imports backtest.py, but the edge is plain, so lane ml does not contain backtest.py and S23 cannot pass. Its 'merge main after the phase 1a landing' does not help, because backtest lands only in stretch.", "corrected_text": "Replace 'S16 --> S23' with 'S16 --> S23 (lane-sync)'. S23 goal: '...; before S23 the lane merges the S16 exit (--no-ff).' S18 goal already orders ML after backtest; add 'only if backtest merged green and not reverted.'"},
    {"id": "CF-26", "severity": "medium", "kind": "gap (no writer for contract amendments)", "status": "open", "where": "slice-graph.md Build strategy 'A later name change is a contract amendment recorded in CONTRACTS.md'; DES-GM-LANES; CONTRACT-GM-INDEX", "problem": "No slice owns CONTRACTS.md or the frozen stubs after S01, and lane foundation is deleted at the 1a landing. An amendment by a feature lane fails the write-set check and the frozen-contract check (CONTRACT_STOP) with no route to land it.", "corrected_text": "Add to CONTRACT-GM-INDEX: 'An amendment is made on branch gridmarket/contract-<n> from main (or from the S01 exit before the 1a landing) by the S01 route, writing only CONTRACTS.md and the named frozen files; CMD-TEST-CONTRACTS passes; the Orchestrator records it as a dated DEC-GM entry (DEC-GM-043 delegate authority); every affected lane merges its exit SHA (--no-ff) before its own exit; the IE merges it as the first step of the next assembly and updates the contract baseline.'"},
    {"id": "CF-27", "severity": "medium", "kind": "defect (unsafe deletion criterion)", "status": "open (applied in this plan; needs design text)", "where": "design.md DES-GM-LANES landing bullet ('every lane branch ... whose slices are all merged')", "problem": "git branch --merged, git branch -d, and merge-base --is-ancestor report a lane as merged even when its merge was reverted, or when later commits sit on the lane after the exit. Under DEC-GM-040 cleanup, reverted, slipped (bots), or deferred (spec) lanes would be deleted with unlanded work.", "corrected_text": "DES-GM-LANES landing bullet: 'A lane is deleted only when the phase evidence marks every slice merged and not reverted, the remote lane tip equals the recorded exit SHA, and git diff --quiet <exit> origin/main -- <lane write-set union> passes; otherwise it is kept and listed for the owner.'"},
    {"id": "CF-28", "severity": "medium", "kind": "gap (command table stale)", "status": "open (Planning Test Engineer re-issue in progress)", "where": "seit.json procedures_and_commands (25-slice issue)", "problem": "The graph's commands CMD-TEST-BOTS, CMD-TEST-ROUTER, CMD-TEST-KIT, CMD-TEST-MCP, CMD-TEST-QUANT, CMD-TEST-JEV, and CMD-TEST-DOCS are absent. PROC-ASSEMBLY names S09-A..E, S12-A..B, S18-A..E on one gridmarket/integration and omits CONTRACTS.md, App.tsx, and hooks.ts from the frozen list. CMD-SMOKE assigns gm-smoke-stretch:18002, not gm-smoke-rust, and has no main-check pair. Acceptance is PROC-ACCEPT-P1/P2, not AC-GM-ACC-03, 01, and 02.", "corrected_text": "seit.json: add the seven CMD-TEST-* IDs (make test-bots, test-router, test-kit, test-mcp, test-quant, test-jev, test-docs); PROC-ASSEMBLY steps S09-A..E, S49-A..E, S12-A..E, S18-A..G, S46-A..B on gridmarket/integration-<phase>, frozen list per this plan's contracts-baseline item plus CMD-TEST-CONTRACTS per merge; CMD-SMOKE pairs gm-smoke-integration:18000, gm-smoke-market:18001, gm-smoke-rust:18002, gm-smoke-main:18003; acceptance procedures for AC-GM-ACC-03 (1a, no tunnel), AC-GM-ACC-01 (1b), AC-GM-ACC-02 (2)."},
    {"id": "CF-29", "severity": "medium", "kind": "defect (shared resource missing)", "status": "open", "where": "slice-graph.md Concurrency proof; S02, S36, S38, S42 rows", "problem": "Up to 18 wave 2 lanes run on one host. S02 (SDK round trip), S36 (kit), and S38 (mcp) start real uvicorn servers, and S42 starts a stub HTTP server. A fixed port makes parallel CMD-TEST-ALL runs in different lanes, and the IE run beside them, fail intermittently (AN-FLAKE).", "corrected_text": "Add to the Concurrency proof: '- Test-local servers (S02, S36, S38, S42) bind 127.0.0.1 port 0 and read the bound port; no test uses a fixed port.'"},
    {"id": "CF-30", "severity": "medium", "kind": "defect (lane-sync to a revertible exit)", "status": "open", "where": "slice-graph.md views branch base (S25 exit), S07 --> S51 and S07 --> S35 (lane-sync); S27, S35, S51 goals", "problem": "views, pages, and providers-page carry phase 1a exits (S25, S07) made before S09. If S09 reverts and repairs that lane, these lanes still hold the old commits, and their merges either conflict or silently lack the repaired content (the reverted commits are already ancestors of main). The graph also has one owner deploy, but AC-GM-EDGE-05 needs the S27 views deployed.", "corrected_text": "S27, S35, S51 goals: 'before exit merge main after the phase 1a landing.' S49 goal: 'after S49-C is green, the owner sets MARKET_URL and redeploys the Worker from the integration-1b head before AC-GM-ACC-01 (typed gap VIEWS_NOT_DEPLOYED otherwise).'"},
    {"id": "CF-31", "severity": "low", "kind": "defect (proof wording)", "status": "open", "where": "slice-graph.md Concurrency proof Wave 2 bullet ('with one exception ... S17 and S08')", "problem": "S25 (worker) and S27 (views) both write ercot-hackathon/src/index.js, wrangler.jsonc, and README.md. The overlap is safe but unlisted.", "corrected_text": "Append: 'Second exception: S25 (worker) and S27 (views) share ercot-hackathon/src/index.js, wrangler.jsonc, and README.md; serialized by S25 --> S26 --> S27 and the views lane base (S25 exit).'"},
    {"id": "CF-32", "severity": "low", "kind": "defect (start rule contradicts base)", "status": "open", "where": "slice-graph.md S18 row ('start at the earlier of all stretch lanes green or Sat 22:00') vs 'create gridmarket/integration-stretch from main after the phase 2 landing'", "problem": "If phase 2 has not landed by Sat 22:00, S18 cannot start from main after the phase 2 landing. There is also no latest stretch landing time that protects the final wave before the Sun 07:00 freeze.", "corrected_text": "S18 goal: 'start at the later of the phase 2 landing and the earlier of (all stretch lanes green, Sat 22:00 CDT); if the stretch has not landed by Sun 03:00 CDT, revert the unfinished step, land what is green, and record the rest dropped.'"},
    {"id": "CF-33", "severity": "info", "kind": "verified", "status": "resolved", "where": "S08/S17 deploy/* overlap", "problem": "none", "corrected_text": "Verified: S09 --> S17 (lane-sync) makes lane rust contain S08 through main after the 1a landing; S17's own write-set check excludes S08 commits (ancestors on main)."},
    {"id": "CF-34", "severity": "info", "kind": "note (owner-visible side effect)", "status": "resolved (recorded)", "where": "PR #3 (jordaaan, head 4853e51, OPEN)", "problem": "When the phase 1a PR merges, main contains 4853e51 and GitHub marks PR #3 merged without anyone merging it.", "corrected_text": "The Scribe records PR #3's state after S09-L; no action on PR #3 (DEC-GM-027)."}
  ]
}
```
