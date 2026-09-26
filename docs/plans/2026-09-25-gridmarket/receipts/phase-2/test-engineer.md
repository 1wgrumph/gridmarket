---
type: evidence
title: GridMarket phase 2 independent Test Engineer assurance
okf_status: active
tags: [gridmarket, phase-2, assurance, evidence]
freshness: "2026-09-26"
---

# Verdict: REPAIRABLE_FAILURE

Fresh Test Engineer assurance session for Journey GM-2026-09-25. Candidate
`gridmarket/integration-2 @ 1290402ca755b254f1395749e59f344c9a1d7bb5`,
base `e08cf552f73696fcec1c09490533169b4d7adbf1`. This session did not author
product changes. Only this receipt is authorized for writing and committing.
No product, test, contract, plan JSON, persistent service configuration, owner data, or
credential was changed. No push, landing, deployment, issue action, or owner
acceptance was performed.

The candidate is not phase-assurance PASS. Health mutation is **61.2167%**
against 70%, and `make lint` is red. Further evidence/authority and live-contract findings
are distinguished below from product defects. Ordinary functional gates pass, but the live Providers API/page contract fails independent inspection (ATE-P2-05).

## Method and evidence boundary

The Test Engineer skill governs assurance. Existing SEIT procedures were rerun;
Test Engineering method: test for existing suites, analysis for mutation/coverage,
inspection for frozen names, write sets and amendments, browser demonstration
for the dispatched CLS claim. No new product tests were written. Ponytail did
not reduce the required proof cases. No external standard compliance is claimed.

BRAN is unavailable: this repository has no native `.bran/policy.yaml`.
`CONTRACTS.md` is at repository root (not inside the plan directory).
The candidate and clean branch were verified before work. During execution the independently dispatched Reviewer committed only review.md as `017d7fa540cd64b29eb46a00b238e4b6d9420bfc`; the product remained identical to 1290402. This receipt follows that evidence-only commit. Raw evidence,
commands, exit records, JUnit and runnable evidence harnesses are under
`/tmp/gm-evidence/P2/assurance-1290402/` (called E below). Every gate exports
`GRIDMARKET_NWS=off`; live Worker/Jev settings are removed. No owner `.env`
was read. Existing locked installed dependencies were copied; offline frozen
sync exited 0, with no dependency changes or downloads.

Gates that write artifacts ran on `git archive` snapshots, not the protected
integration worktree. `E/candidate/` contains every tracked file byte-for-byte
from 1290402; `E/market-mutation/` is a separate archive of the same commit.
Snapshot equality, frozen blobs, and ancestry inspection exited 0. The snapshots
are exports, not linked worktrees or branches. Build, pytest, mutation and
coverage outputs stay outside the integration worktree. Rules, history scanning,
lint and read-only Git inspections ran against the actual integration worktree;
Ruff's cache was redirected outside it. Git-dependent snapshot gates use the
integration Git metadata with the snapshot as `GIT_WORK_TREE`.

## Deterministic gates

| Gate / exact command | Exit | Independent result |
|---|---:|---|
| CMD-TEST-ALL: `make test-all` | 0 | 178 backend/tools, 61 dashboard, 34 Worker tests passed; dashboard build passed. |
| CMD-TEST-DASH: `make test-dash` | 0 | 61 passed, including 9 S34 and 13 S50; tsc/Vite build passed. |
| CMD-TEST-MARKET: `make test-market` | 0 | 37 passed. Cap tests also rerun explicitly through CMD-RED-GREEN. |
| CMD-TEST-PROVIDERS: `make test-providers` | 0 | 14 passed. |
| CMD-TEST-KIT: `make test-kit` | 0 | 2 passed, real test-local uvicorn and SDK. |
| CMD-SPEC-LINT: `make spec-lint` | 0 | Generated specification unchanged; spec and diagram lints clean. The 33 tools tests also pass in test-all. |
| CMD-SMOKE: `make smoke SMOKE_PROJECT=gm-smoke-assurance-2 SMOKE_PORT=18012` | 0 | Dashboard HTML, status 200, loopback port, UID 10001, read-only root, restart policy, project SQLite volume, healthy bots after 30 s. Own stack/volume/env removed. |
| CMD-SECRETS: `make secrets` | 0 | Full history clean; MIT and empty example-value checks passed. |
| CMD-RULES: `make rules` | 0 | Baseline label, Jev boundary and author-date checks passed. |
| CMD-COVERAGE: `make coverage BASE=e08cf55` | 2 first; 0 repeat | First run: 177 passed, burst timing failed at 1.447 s against 1.0 s. Targeted same test with coverage exited 0. Full bounded repeat: 178 passed; 846/936 changed lines = 90.3846%, exceeding 80%. |
| CMD-MUTATION: `make mutation MUTANTS="gridmarket_server.health.*"` | 0 command; **1 threshold** | **161 killed, 102 survived, 0 timeout, all 263 selected scored; 61.2167% < 70%. ATE-P2-01.** |
| S05-cap: `make mutation MUTANTS="gridmarket_server.market.*"` | 0 command; 0 threshold | 909 killed, 183 survived, 0 timeout, 1092 selected; 83.2418%. |
| CMD-LINT: `make lint` | **2** | Ruff check passes; format check would reformat only `examples/strategy-template/strategy.py`. ATE-P2-02. |

Mutation ran in fresh, separate artifact trees. The 1,966 generated mutants
span five configured modules; scores above count only the selected module,
not unchecked mutants or another module's cache. `mutation_score.py` preserves
selected metadata and asserts the threshold independently. The Makefile only
asserts a nonzero denominator, then prints the score; its exit 0 does not prove
70%. Health metadata SHA-256: `df9901502f0c1074faa67fd5382804541aac9fe6e6b1dc3d5542cdb9f12cbb72`.
Market metadata SHA-256: `4712ab6d7af5e0fbc65853b9f99c01202ec0773cf1fa800a322128bfa3da5c2a`.

Coverage's first timing failure is retained as a load/instrumentation-sensitive
observation, not filed as a product defect. The uninstrumented full suite,
targeted instrumented check and full instrumented repeat all passed without
product/test changes. jsdom CSS-parser diagnostics and dependency deprecation
warnings were observed; they did not cause failed tests. Browser demonstration
below had no page errors or failed HTTP responses.

## Red-then-green binding

All XML was produced in this session. `E/red-green-bindings.json` contains
identical test IDs, full baseline/candidate SHAs, exits and XML digests. Green
is always candidate 1290402; lane green receipts alone were not accepted.

| Pair | Fresh red baseline and exit | Fresh candidate green and exit |
|---|---|---|
| S10/S11 | Original test-only commit `701fa217ab0af773b1016432e0a1862c7eb9a234`: 12 failures, exit 1, no collection errors. Replayed **current amended tests** byte-for-byte over that original product baseline: 12 failures plus 2 passing guards, exit 1. | All 12 pass and both guards pass; combined backend red-green command exit 0 and named providers command exit 0. |
| S34/S35 + S35-v2 | `60140c6a1760812f355039e446780d17984d82b7`: 9 failures, exit 1, no collection errors. | Same 9 pass, red-green exit 0; test-dash/build exit 0. |
| S36/S37 + S37-cap | `0805fc2e8779da3ec431c1768796ccdc9610ad03`: 2 failures, exit 1, no collection errors. | Same 2 pass, red-green and test-kit exits 0. |
| S05-cap supplemental check | Product baseline `60b16860e76d1c591b27ccdd2b6d51c487ff9946` with the candidate cap-test file copied unchanged as test input: over-cap rejection test fails; 3 regression guards pass; exit 1. | All 4 cap tests pass, red-green exit 0. |

The supplied `exits/S10` pointer is now `0f371df...`, a fixture repair after
implementation/lane merges. Fresh execution there gives 1 failure and 11 passes
(exit 1), so it is **not** a valid twelve-red baseline. Historical Git inspection
recovered 701fa21 and the reruns above close the binding. Original/current S10
assertion ASTs are identical; the authorized spot-symbol/seeded-row fixture
amendments are preserved. No test was edited in the integration worktree.

## Proof-row results

PASS is bounded to the named proof; owner acceptance and independent review
remain separate. Supplemental slices absent from the older canonical slice
mapping are verified against this session's explicit dispatch and the recorded
P2 directives, without rewriting SEIT or inventing new approved row IDs.

| Slice / SEIT proof row | Result and independently reproduced evidence |
|---|---|
| S05-prov; SEIT-GM-PROV-01 | PASS: regex finds no direct assets/reservations SQL in market.py or api.py; both adapters are used; test-market/test-providers/test-all exit 0. Frozen adapter names unchanged. |
| S05-cap; dispatched 500/501/0, exact message and DEC-GM-090 | Behavior PASS: four cap tests, both buy/sell rejection, state unchanged, exact message, floor and generic other-error message. **Authority constraint FAIL: ATE-P2-03**. Market mutation result above. |
| S10/S11; SEIT-GM-PROV-01 | PASS: adapter conformance and capacity-routing assertions; 12-red/green binding above. |
| S10/S11; SEIT-GM-PROV-02 | PASS: >=20 LoneStar customers/public counts and cross-provider fill; providers exit 0. |
| S10/S11; SEIT-GM-PROV-03 | PASS: admin outage authorization, start/end/auto-end and base provider independence in simulated-clock tests; providers exit 0. This is not owner PROC-ACCEPT-P2. |
| S10/S11; SEIT-GM-PROV-04 and SEIT-GM-PROV-04-HEARTBEAT | PASS: offline sells/no state mutation, online recovery, 29/31-second boundary and 10-second loop; market/providers exits 0. |
| S10/S11; SEIT-GM-ROUTER-03 | Functional PASS: worker/provider health inputs, bands and probability bounds; providers exit 0. Required phase health mutation FAIL remains ATE-P2-01. |
| S10; SEIT-GM-API-07 | PASS: outage admin denial tests plus market/API guard suite; named gates exit 0. |
| S34/S35; SEIT-GM-UI-04 and UI part of SEIT-GM-PROV-03 | Test-level PASS (9 red/green, dashboard/build exit 0), but **UI-04 live integration FAIL: ATE-P2-05**. Recorded fixtures supply fields absent from the real API; green component tests do not establish live provider fields. |
| S35-v2; dispatched token rule | PASS inspection: all seven referenced CSS variables are defined in styles.css; no retired gm-* classes; nine S34 tests and build green. Visual assurance gap below. |
| S36/S37; SEIT-GM-KIT-01 | PASS: real uvicorn/SDK cycle and import/order/position constraints; 2-red/green binding and test-kit exit 0. |
| S36/S37; SEIT-GM-KIT-02; S37-cap | PASS: docs match constants 50/200/500, position instruction and OpenAPI URL present; test-kit and inspection exits 0. |
| S53-cls; dispatched CLS <=0.1 and S50 regression | PASS: delayed real browser render of candidate build with repository fixture responses: CLS **0 at 390px**, **0.00244648 at 1280px**; loaded state confirmed, no page errors/failed responses. Screenshots E/cls-*-loading.png and E/cls-*-loaded.png; harness exit 0. S50 13/13 in dashboard suite. |
| S21 / S12-E; SEIT-GM-SPEC-03 | PASS: spec-lint exit 0, generated file unchanged, templates/skills delivered; tools suite 33 passed. |
| SEIT-GM-DATA-04-SCAN | PASS: secrets exit 0; empty env example and ignored/untracked env checked. |
| SEIT-GM-SEC-01 | PASS: full history secret scan and root MIT license; secrets exit 0. |
| SEIT-GM-RISK-04 | PASS for repository secret controls; no live credential use; secrets exit 0. |
| SEIT-GM-RULE-02 | PASS for specified label/Jev/date inspection; rules exit 0. |
| SEIT-GM-OPS-01 | PASS: isolated assurance smoke exit 0 with all native hardening assertions and cleanup. |
| SEIT-GM-LANE-01 | PASS for path write sets: fresh Git inspection reproduces six step unions and merge parents, structure-fixed exit 0. The narrower S05-cap content constraint is separately failed. |
| SEIT-GM-LANE-02 | PASS for assembled-candidate gates and inspected history: all six recorded ordered steps have correct parent/exit identities; new test-all and smoke exit 0. Historical post-step executions are provenance, not misrepresented as fresh reruns. |
| SEIT-GM-CONTRACT-01-AMEND | PASS for phase delta: all twelve frozen files equal e08cf55, inspection exit 0; current contract tests green in test-all. No new amendment or drift. Does not retroactively certify inherited pre-phase changes. |
| SEIT-GM-RISK-19 | PASS for phase delta: frozen comparison and current contract suite green; assembly chronology inspected. |
| SEIT-GM-RISK-05 | Structural checks PASS; assurance/landing condition remains open because this verdict fails. No landing performed. |
| SEIT-GM-RISK-18 | **TYPED_GAP: ATE-P2-04.** Current phase Reviewer browser run exists (exit 1); observer exits 2 and judges no screenshots. Functional fallback is green but the selected observer is not passing evidence. |
| SEIT-GM-ACC-02 / PROC-ACCEPT-P2 | OWNER_RUN / NOT_RUN, explicitly outside this assurance (TE4-F6), including the owner simulated LoneStar outage. |
| SEIT-GM-OPS-01-TUNNEL | OWNER_RUN / NOT_RUN; no tunnel or owner stack operation. |
| SEIT-GM-LAND-01 and SEIT-GM-RISK-11 | ORCHESTRATOR / NOT_RUN; landing and scheduling/cleanup proof are outside this receipt's authority. No future landing PASS inferred. |

CLS demonstration used a 1.5-second delayed bot-profile response, sampled after
loading and at 3.2 seconds, with widths 390 and 1280. It exercises the async
placeholder transition against the candidate build. The fixture has two blend
rows rather than the author's three: the loaded footer differs by about 34px,
but measured CLS remains below 0.1. It does not establish full visual review,
all possible profile shapes, mobile interaction, or owner live acceptance.

## Findings and smallest closure evidence

- **ATE-P2-01 — HEALTH_MUTATION_BELOW_THRESHOLD.** E/mutation-health.log
  prints 61.22%; all 263 health mutants scored, 161 killed and 102 survived,
  zero timeout. E/mutation-health-threshold.log exits 1. The source/tests need
  the authorized owning-lane repair sufficient to reach >=70%; rerun the same
  selected scope. Do not use Makefile exit 0 as a threshold assertion or weaken
  the frozen score rule. This is a measured assurance failure, not a claim that
  each surviving mutant represents a real production defect.
- **ATE-P2-02 — LINT_NOT_GREEN.** E/lint-candidate.log: `make lint` exits 2;
  only strategy.py formatting fails. This reproduces DIR-P2-13, not a new or
  duplicate issue. A format-only authorized repair followed by lint exit 0
  closes this item. No formatting was applied by the Test Engineer.
- **ATE-P2-03 — DATA_ONLY_AUTHORITY_VARIANCE.** Commit 5be7051 changes two
  `assert place(...).status_code < 300` lines in test_market.py from price
  1000 to 400. Comparators, expected status and rejection/state assertions
  remain intact; no weakened behavior claim is made. However DEC-GM-090 and
  its S05-cap-o2 packet explicitly prohibit **any assertion line change**.
  E/cap-rule.log exits 1 and E/cap-assertion-lines.json records the exact four
  diff lines. The Coordinator needs an explicit disposition reconciling this
  literal constraint with the embedded test-data edit; passing tests cannot
  silently amend it. No broader test rewrite is authorized by this receipt.
- **ATE-P2-04 — VISUAL_OBSERVER_UNAVAILABLE.** The fresh phase Reviewer
  receipt at 017d7fa binds candidate 1290402. Its scripted browser run exits 1;
  the selected observer exits 2 (`no_before_image:ratio=None`, 16 selected,
  zero judged). Independent JSON inspection confirms 16 gap pairs and zero batches; observations.json SHA-256 is `2a5885b83d6027e9ccf1d8cfb258e193bebbeefa34322e16e629ae474b534c5a`. This supersedes the initial missing-current-v2-receipt concern.
  Current browser coverage exists, but an unavailable observer is not PASS.
  Preserve the selected route and repair its input/configuration through the
  owning review workflow; do not substitute ordinary test reruns. The Reviewer
  manually read screenshots and separately reports F1/F2/F3; those findings
  remain in that receipt rather than being silently adopted as TE evidence.
- **ATE-P2-05 — LIVE_PROVIDER_CONTRACT_UNPROVEN_BY_FIXTURE_TESTS** (same
  defect as Reviewer F1, not a new issue). Fresh candidate TestClient calls,
  with LoneStar on and a disposable SQLite file, returned 200 for providers,
  health and router. Both base_sim (40 participants) and lonestar (20) have
  no health row matching the page's `provider_id` lookup. Actual health rows
  use `id`, and omit `provider_id`, `customers`, and `online_assets`. The page
  expects those fields; the test fixture supplies them. E/provider-contract.log
  exits 1, with sanitized payload keys/counts in provider-contract-result.json.
  Fix the API/page/fixture agreement through the authorized repair and prove
  the live component boundary. No owner outage was invoked. This is why the
  passing nine UI tests are recorded as test-level evidence only.

## Frozen capabilities and remaining risk

Frozen profile digest:
`14d07a1ceffc31954e7be348d0ec32b10140108a2351448d26e500759a8ed721`.
Assurance route remains Codex CLI / GPT-6 Astra / high; no model/harness switch
or live-profile import. The separate Reviewer receipt records OCR delegation
preview and rule calls exiting 0; this is review provenance, not a TE-run review. `review.coverage_assist`: enabled, required=false,
backend **OpenCodeReview delegation**, locally available v1.12.9.
**NOT_RUN in this assurance session**: separate Reviewer responsibility,
never counted as independent review PASS. `deterministic_verification.reverify`:
enabled, backend Reverify locally callable (`--help` exit 0).
**NOT_APPLICABLE: phase 2 asserts Python/TS/JS source behavior, with no native
compiled-binary claim or Rust lane.** Ordinary reruns are not Reverify.
Tech-writing lane capability overrides remain unchanged.

Remaining risks: 102 surviving health mutants; formatting and amendment
constraint; current visual-observer capability and live Providers payload mismatch; the observed timing sensitivity
under coverage; owner acceptance, tunnel and external/live data remain unrun.
There is no authority blocker to completing this receipt. Repair/acceptance
belongs to the owning lanes, Reviewer, Coordinator and owner as specified.
This is the one phase assurance entry, not permission for implementation,
publication, landing, or a second independent assurance round.

## phase_assurance entry

Recorded here because this session authorizes only this receipt; seit.json and
implementation.json are frozen and were not edited.

```json
{
  "phase": "2",
  "candidate": "1290402ca755b254f1395749e59f344c9a1d7bb5",
  "coverage_base": "e08cf552f73696fcec1c09490533169b4d7adbf1",
  "session": "assurance",
  "verdict": "REPAIRABLE_FAILURE",
  "common_required_commands": {
    "CMD-TEST-ALL": "PASS: exit 0; 178 backend/tools, 61 dashboard, 34 Worker",
    "CMD-SMOKE": "PASS: exit 0; gm-smoke-assurance-2:18012, cleanup completed",
    "CMD-SECRETS": "PASS: exit 0",
    "CMD-RULES": "PASS: exit 0",
    "CMD-COVERAGE": "PASS on bounded repeat: exit 0, 846/936 = 90.3846%; first exit 2 retained",
    "CMD-MUTATION": "FAIL: health make exit 0, independent threshold exit 1; 161/263 = 61.216730%, below 70%"
  },
  "extra_commands": {
    "CMD-TEST-DASH": "PASS: exit 0",
    "CMD-SPEC-LINT": "PASS: exit 0; S21 merged at S12-E",
    "CMD-LINT": "FAIL: exit 2; strategy.py formatting",
    "S05-cap-market-mutation": "make exit 0; selected 909/1092 = 83.241758%; threshold exit 0"
  },
  "red_green_pairs": {
    "S10/S11": "PASS: 12 red, 12 green; two guards green in both; current tests replayed over 701fa21 product baseline",
    "S34/S35": "PASS: 9 red at 60140c6, 9 green at candidate",
    "S36/S37": "PASS: 2 red at 0805fc2, 2 green at candidate",
    "S30/S31": "NOT_APPLICABLE: S12-D excluded by owner dispatch; no slip inferred"
  },
  "acceptance": "OWNER_RUN / NOT_RUN: PROC-ACCEPT-P2 including simulated LoneStar outage (TE4-F6); not assurance evidence",
  "findings": [
    "ATE-P2-01",
    "ATE-P2-02",
    "ATE-P2-03",
    "ATE-P2-04",
    "ATE-P2-05"
  ],
  "repair_verification_commands": [
    "CMD-TEST-ALL",
    "CMD-SMOKE",
    "CMD-SECRETS",
    "CMD-RULES",
    "CMD-LINT",
    "CMD-MUTATION health and market with selected-scope >=70% assertions",
    "DEC-GM-090 disposition",
    "current-v2 visual review and observer receipt",
    "live Providers API/page contract and updated fixture proof"
  ],
  "blocker": "No execution-authority blocker; required health threshold, formatting, amendment constraint, visual-observer gap and live provider contract remain open."
}
```

## Evidence integrity and diagnostic runs

Every row below names `E/<name>.log` and the corresponding JSON command/exit
record. The command table above gives the native command IDs. JUnit binding
hashes are in E/red-green-bindings.json. All are fresh assurance evidence.

| Evidence name | Exit | Log SHA-256 |
|---|---:|---|
| `test-all` | `0` | `5870e02b06e3772794690258c27e96f4a36283890bcaf211178fa0b2acd7bb1b` |
| `test-dash` | `0` | `dcfcf3263bf29418f9383403a8c53e358ff64c7e3734a14f3586bf3154d4b801` |
| `test-market` | `0` | `0fc8ff523b548a0aac52a034d3ea087a5d3a1fa68462116bd82834f1050303b2` |
| `test-providers` | `0` | `a1f71a134350c5d3aa89172d22abbe71f5b1b760b436cf784e736e0a25f91d9f` |
| `test-kit` | `0` | `e47f7d4b48d7c81e76126c52bba6b784e242f0d1f64581c525078249dc4d28d8` |
| `spec-lint` | `0` | `015dc839135e66332a17d9d492dac34349c26350855d64db6bf3809382d3f412` |
| `smoke` | `0` | `c23e98f657fd56b79a489234564500460e1f7890c6b72801e2e7b613f1dbab41` |
| `secrets` | `0` | `ebe4e05bee2bc2c3e48513915abbd4887b82db6b7961262304ff41993ea75166` |
| `rules` | `0` | `4ecf979e4133d8fe403586fa0b1151514e28ff4572a178e3aa716deb6ecc9145` |
| `coverage` | `2` | `90a3c7138203384ba3fcce054291a5d69123dca15307cee42d3e9f6183a9b4ac` |
| `burst-coverage` | `0` | `e213f32b5398384aeadad5aac11cc965cc6a4c2aacc8f3e41491321d552e5222` |
| `coverage-repeat` | `0` | `8380fdb8c995077ad5ef16b62e678d04a6ad4afb386b2e7296df92809be70566` |
| `mutation-health` | `0` | `159d5b7342cac2e4c4f59638c1f9053f8930a78ce30e2e1dd95d480733db6666` |
| `mutation-health-threshold` | `1` | `2e02814dd365bb2c96e4484b7dfa28697b0a3d2f0ce8385dca90023a70f405d9` |
| `mutation-market` | `0` | `ea084291462fe3245a3c18cd4d54d3fa5834abb06ab5740771b1f5bb2f2488b9` |
| `mutation-market-threshold` | `0` | `ae5cf3cf39b72d421ea3bfc8a4b65c7924f4c7eac615b34faa27a9039b74ee88` |
| `lint-candidate` | `2` | `37ead8e539273018b2b94926d6622cf843ba69218bab9182e3252ed3dd087bb3` |
| `inspection` | `0` | `240044d25c56d966268677f3bf4df58607046171a14595657e227b9ed442ef2f` |
| `structure-fixed` | `0` | `ebc3be465605c34647e2b49f92f969a1159ccbdb43ed9a5465aaf9f56e291b59` |
| `bind-pairs` | `0` | `af6bed35c2c5c3ac5cdc91d44428928e88156b9b2c6d9b247035eac941b6ae1f` |
| `cap-rule` | `1` | `28599b917caf6975c4afd0f1dd3d5a1d867fb39e571b173ea8f5df0b0c85e9c0` |
| `cls` | `0` | `50f93d1917e334352ab9e94f30005561585fff1d7c4a133ae880ca50f34292c3` |
| `env-controls` | `0` | `790ba1830dd8b7a4fca82485745b8d847a0a0b07789318c38b26bca7872bb883` |
| `provider-contract` | `1` | `a3449c6bbde91ad1ab35132120d688129d696b1842e249dfe80644b50c26445f` |

Harness-only observations are retained rather than attributed to the product:
initial snapshot lint included generated mutants because the export has no
`.git` ignore discovery (exit 2); direct clean-worktree lint isolated the real
formatting failure. Initial structure harness assumed a uniform receipt shape
(exit 1, KeyError); it was corrected to handle the older prerequisite record,
then reproduced all six unions with exit 0. The first S10 pin run was a
post-implementation pointer (1 failed/11 passed); recovered/rebound baselines
are detailed above. No such diagnostic is counted as proof of a product bug.

Receipt commit contains only this file. Its commit SHA is returned after commit
rather than embedded self-referentially. The tested product remains 1290402.
