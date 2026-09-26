# Implementation graph draft (Planning and Design node, input to TE, IE, PI)

Supporting file, not a canonical artifact. `implementation.json` (Plan
Integrator) is the authority once generated. Slice IDs, waves, roles, write
sets, and dependencies below are fixed by Planning and Design; command IDs are
proposed and finalized by the Planning Test Engineer in `seit.json`.

Development strategy: `tdd` (frozen profile); the spec lane (S19-S21) is
`single_implementer` on the tech-writing profile, and the ui lane (S04, S07)
uses the frontend profile; every other lane uses primary (DEC-GM-024). Roles: `Test Implementer`
(route test_implementer), `Product Implementer` (route implementer),
`Integration Engineer` (route integration_engineer.execution, assembly steps).
Coordinator dispatches waves; max 4 concurrent slices (one per lane;
DEC-GM-025).
Worktrees: `/home/spectre/alphazede/worktrees/base-gridmarket-<lane>`;
branches `gridmarket/lane-<lane>`; integration branch `gridmarket/integration`.
Wave 2 lanes, including the red-test lanes lonestar, adversary, stretch and ml
(DEC-GM-025), branch from the S01 exit commit (`lane-rust` from the S15 exit).
Before a wave 3 implementation slice, its lane merges the S09 exit commit of
`gridmarket/integration` (`lane-ml`: the S16 exit) with `--no-ff` (lane sync);
that merge commit is the slice base and the CMD-WRITESET base. Every slice
exits with a commit on its lane branch; S09, S12, and S18 each end with a PR
`gridmarket/integration` → `main` merged with a merge commit and no review
(DEC-GM-023). The Reviewer runs once, at Lifecycle cadence, on the integrated
candidate at about Sat 2026-09-26 22:00 CDT. Wave 1 lane `worker` branches from
`origin/jordaaan` at `4853e51` (DEC-GM-022) and opens a PR into `jordaaan`. Remote `origin` exists (DEC-GM-018); branches are
pushed without force; `main` changes only through PRs.

## Waves

- Wave 1 (foundation + Worker security, DEC-GM-022): S01, S24, S25
- Wave 2 (phase 1 + spec lane + red tests, DEC-GM-025): S02, S03, S04, S05, S06, S07, S08, S09, S10, S13, S15, S19, S20, S21, S22
- Wave 3 (phase 2 + stretch): S11, S12, S14, S16, S17, S18, S23

## Dependencies

S01 --> S02, S01 --> S03, S01 --> S04, S01 --> S19,
S01 --> S10, S01 --> S13, S01 --> S15, S01 --> S22 (red tests against S01's
frozen contracts, DEC-GM-025),
S02 --> S05, S03 --> S06, S04 --> S07,
S05 --> S08, S08 --> S09, S06 --> S09, S07 --> S09,
S06 --> S19 (slot edge: concurrency cap, not a data dependency),
S19 --> S20, S20 --> S21,
S24 --> S25,
S25 --> S04 (slot edge: ui starts after the worker lane, CF-13),
S09 --> S11, S09 --> S14, S09 --> S16, S09 --> S17 (lane sync merge of the
S09 exit before each wave 3 implementation slice, DEC-GM-025),
S10 --> S11, S11 --> S12,
S11 --> S23 (slot edge), S22 --> S23, S16 --> S23 (lane-ml merges the S16 exit),
S13 --> S14,
S14 --> S17 (slot edge), S15 --> S17,
S15 --> S16,
S12 --> S18,
S14 --> S18, S16 --> S18, S17 --> S18, S23 --> S18 (completion-or-drop edges:
S18 merges each of adversary S14, backtest S16, Rust S17, ML S23 as soon as it
is green; at Sun 04:30 CDT an unfinished lane is recorded dropped and no
longer blocks S18),
S25 --> S09 and S21 --> S12 (completion-or-drop edges gating only the step
that merges that lane, S09-E and S12-B, CF-16): S09 starts when S06, S07,
S08 are done; S12 starts when S11 is done; a worker or spec lane not green by
its cut-off is recorded dropped (worker: phase 1 checkpoint recorded without
it and the Worker merge moves to S18-E through origin/main; spec: Sun 04:30
CDT)

## Slices

| ID | Wave | Lane | Role | Type | Goal | Requirements | Design | Lenses | Write set | Proposed commands |
|---|---|---|---|---|---|---|---|---|---|---|
| S01 | 1 | foundation | Product Implementer | scaffold | Create the repo scaffold and frozen contracts: backend uv project with all phase-1 deps, contracts.py, schema.sql (with append-only triggers), main.py composition root (mounts dashboard only if built), main.py composition root starts the NWS poller unless GRIDMARKET_NWS=off (CF-18); placeholder modules market.py, api.py, ercot.py, nws.py, scoring.py, seed.py, providers/__init__.py, providers/base_sim.py satisfying contracts.py with empty behavior (only GET /v1/market/status, empty registry, empty signal store, predict returns []), contract tests, dashboard Vite+React+Astryx+vitest scaffold with typed api.ts, Makefile targets for every CMD, .gitignore (.env, *.db, node_modules/, dashboard/dist/, backend/.venv/, rust/matching_core/target/, __pycache__/, .pytest_cache/), .env.example (names only incl. GRIDMARKET_ADMIN_KEY, GRIDMARKET_PORT, GRIDMARKET_WORKER_URL, GRIDMARKET_WORKER_KEY, GRIDMARKET_CORS_ORIGIN, GRIDMARKET_NWS; no ERCOT credentials), MIT LICENSE (copyright holders: the owner (GitHub 1wgrumph) and Jordan Hill, DEC-GM-026), gitleaks config. Deps: runtime, dev (pytest, pytest-cov, diff-cover, mutmut, ruff, PyYAML), optional ml (numpy, scikit-learn); admission scan incl. release age >= 14 days. Makefile targets setup, lint, test-contracts, test-market, test-data, test-dash, test-providers, test-adversary, test-backtest, test-parity, test-ml, test-spec, spec-lint, test-all, red-green, coverage, mutation, bench, smoke, secrets, depscan, rules exactly as seit.json procedures_and_commands describes; backend/pyproject.toml [tool.mutmut] paths_to_mutate = ["gridmarket_server/market.py"]; .gitignore adds backend/mutants/ and .coverage; backend/tests/conftest.py blocks outbound sockets except 127.0.0.1 and registers no network fixture (TE-F2). | AC-GM-DATA-04, AC-GM-LANE-01, AC-GM-SEC-01, AC-GM-OPS-01, AC-GM-SCORE-04, AC-GM-RULE-01 | DES-GM-ARCH, DES-GM-LANES, CONTRACT-GM-SCHEMA, CONTRACT-GM-ENGINE, CONTRACT-GM-PROVIDER, CONTRACT-GM-SIGNALS, CONTRACT-GM-PREDICTION, CONTRACT-GM-API, CONTRACT-GM-WORKER | Integration, Security controls, API contract | backend/pyproject.toml, backend/uv.lock, backend/gridmarket_server/__init__.py, backend/gridmarket_server/contracts.py, backend/gridmarket_server/schema.sql, backend/gridmarket_server/main.py, backend/gridmarket_server/market.py, backend/gridmarket_server/api.py, backend/gridmarket_server/ercot.py, backend/gridmarket_server/nws.py, backend/gridmarket_server/scoring.py, backend/gridmarket_server/seed.py, backend/gridmarket_server/providers/__init__.py, backend/gridmarket_server/providers/base_sim.py, backend/tests/conftest.py, backend/tests/test_contracts.py, dashboard/package.json, dashboard/package-lock.json, dashboard/vite.config.ts, dashboard/tsconfig.json, dashboard/index.html, dashboard/src/main.tsx, dashboard/src/api.ts, Makefile, .gitignore, .env.example, .gitleaks.toml, LICENSE | CMD-SETUP, CMD-LINT, CMD-TEST-CONTRACTS, CMD-DEPSCAN, CMD-SECRETS, CMD-WRITESET |
| S02 | 2 | market | Test Implementer | test | Author red tests for matching, risk controls, capacity reservation race, ledger/settlement (DEC-GM-008), seed, auth, idempotency, rate limits, CORS for the Worker origin only, API surface, SDK round trip and bots against a real uvicorn server. | AC-GM-MKT-01..06, AC-GM-ACCT-01, AC-GM-API-01..05, AC-GM-BOT-01 | DES-GM-MARKET, DES-GM-RISK, DES-GM-SETTLE, DES-GM-SDK, CONTRACT-GM-API, CONTRACT-GM-ENGINE, CONTRACT-GM-WORKER | Market integrity, Security controls, API contract | backend/tests/test_market.py, backend/tests/test_api.py, backend/tests/test_sdk_bots.py | CMD-RED-GREEN, CMD-LINT, CMD-WRITESET |
| S03 | 2 | data | Test Implementer | test | Red tests, NWS and Worker fixtures (/api/snapshot, /api/report/np6-905-cd/spp_node_zone_hub, /api/report/np4-190-cd/dam_stlmnt_pnt_prices, /api/report/np3-565-cd/lf_by_model_weather_zone, /api/report/np3-233-cd/hourly_res_outage_cap, /api/report/np6-86-cd/shdw_prices_bnd_trns_const): 12/min budget, no `fresh`, key header, backoff/stale on 401/404/429/5xx, no ERCOT credentials, parsing, zone mapping, NWS forecast/alerts, 5x16 NERC-holiday calendar, seven factors, monotonicity, levels, confidence, disclaimer. | AC-GM-DATA-01..05, AC-GM-SCORE-01..05 | DES-GM-ERCOT, DES-GM-NWS, DES-GM-SCORE, CONTRACT-GM-SIGNALS, CONTRACT-GM-PREDICTION, CONTRACT-GM-WORKER | Data ingestion, Explainability, Security controls | backend/tests/test_ercot.py, backend/tests/test_nws.py, backend/tests/test_scoring.py, backend/tests/fixtures/ercot/, backend/tests/fixtures/nws/ | CMD-RED-GREEN, CMD-LINT, CMD-WRITESET |
| S04 | 2 | ui | Test Implementer | test | Author red vitest tests rendering the dashboard from fixture API responses: all panels, factor contributions, stale badge, disclosures, activity feed shows a judge-labelled order, status/anomalies panel, 2 s polling. | AC-GM-UI-01, AC-GM-UI-02, AC-GM-SCORE-03 | DES-GM-UI, CONTRACT-GM-API | API contract, Explainability | dashboard/src/App.test.tsx, dashboard/src/test-fixtures.json | CMD-RED-GREEN, CMD-TEST-DASH, CMD-WRITESET |
| S05 | 2 | market | Product Implementer | product | Implement market.py (Python engine, risk, ledger, settlement, product listing tick), api.py (/v1/providers derived only from the adapter registry), keys.py, seed.py, base-sim provider until S02 tests are green. | AC-GM-MKT-01..06, AC-GM-ACCT-01, AC-GM-API-01..05, AC-GM-PROV-01 | DES-GM-MARKET, DES-GM-RISK, DES-GM-SETTLE, DES-GM-PROV, CONTRACT-GM-API, CONTRACT-GM-ENGINE, CONTRACT-GM-PROVIDER | Market integrity, Security controls, Provider seam | backend/gridmarket_server/market.py, backend/gridmarket_server/api.py, backend/gridmarket_server/keys.py, backend/gridmarket_server/seed.py, backend/gridmarket_server/providers/__init__.py, backend/gridmarket_server/providers/base_sim.py | CMD-RED-GREEN, CMD-TEST-MARKET, CMD-LINT, CMD-COVERAGE, CMD-WRITESET |
| S06 | 2 | data | Product Implementer | product | Implement ercot.py (Worker client of /api/snapshot, /api/report/np6-905-cd/spp_node_zone_hub, /api/report/np4-190-cd/dam_stlmnt_pnt_prices, /api/report/np3-565-cd/lf_by_model_weather_zone, /api/report/np3-233-cd/hourly_res_outage_cap, /api/report/np6-86-cd/shdw_prices_bnd_trns_const; limiter with a requests-per-minute budget parameter, backoff, parsers, poller, signal store; no ERCOT credentials), nws.py, and scoring.py (seven factors, stdlib peak calendar) until S03 tests are green. | AC-GM-DATA-01..05, AC-GM-SCORE-01..05 | DES-GM-ERCOT, DES-GM-NWS, DES-GM-SCORE, CONTRACT-GM-SIGNALS, CONTRACT-GM-PREDICTION, CONTRACT-GM-WORKER | Data ingestion, Explainability | backend/gridmarket_server/ercot.py, backend/gridmarket_server/nws.py, backend/gridmarket_server/scoring.py | CMD-RED-GREEN, CMD-TEST-DATA, CMD-LINT, CMD-COVERAGE, CMD-WRITESET |
| S07 | 2 | ui | Product Implementer | product | Implement the Astryx dashboard page and components until S04 tests are green and the production build succeeds. | AC-GM-UI-01, AC-GM-UI-02, AC-GM-SCORE-03 | DES-GM-UI | API contract, Explainability | dashboard/src/App.tsx, dashboard/src/components/, dashboard/src/styles.css | CMD-RED-GREEN, CMD-TEST-DASH, CMD-WRITESET |
| S08 | 2 | market | Product Implementer | product | Implement the stdlib SDK, the ≤30-line example, bots.py, Dockerfile, compose.yaml (app, bots, cloudflared profile), cloudflared example config, README (run, judge quickstart, disclosures) until test_sdk_bots.py is green and the compose smoke passes. | AC-GM-API-04, AC-GM-BOT-01, AC-GM-OPS-01 | DES-GM-SDK, DES-GM-OPS | API contract, Operability | sdk/python/, examples/python-trader/, backend/gridmarket_server/bots.py, deploy/Dockerfile, deploy/compose.yaml, deploy/cloudflared.example.yml, README.md | CMD-RED-GREEN, CMD-TEST-MARKET, CMD-SMOKE, CMD-LINT, CMD-WRITESET |
| S09 | 2 | integration | Integration Engineer | integration | Assemble phase 1: merge lanes foundation, market, data, ui, worker into gridmarket/integration in that order with post-step V&V; after Jordan has deployed the Worker fix, the owner runs PROC-ERCOT-LIVE-CHECK (it loads the market client key, owner-only credential access, TE-F6) and the Scribe records it; record the phase-1 demoable checkpoint; inspect that the merged views keep the baseline-rules label. | AC-GM-LANE-02, AC-GM-ACC-01, AC-GM-RULE-02 | DES-GM-LANES | Integration, Operability | docs/plans/2026-09-25-gridmarket/evidence/assembly-phase-1.md | PROC-ASSEMBLY, CMD-TEST-ALL, CMD-SMOKE, CMD-SECRETS, CMD-RULES |
| S10 | 2 | lonestar | Test Implementer | test | Author red tests: adapter protocol conformance for base-sim and LoneStar, capacity only via adapter, ≥20 LoneStar customers, cross-provider fills on one book, offline asset handling, /v1/providers shows both fleets. Written against S01's frozen contracts (DEC-GM-025): at the S01 exit baseline base-sim is a placeholder, so the LoneStar ids and the base-sim conformance ids it fails are red-expected; ids passing there are regression guards (TE-F8). | AC-GM-PROV-01, AC-GM-PROV-02 | DES-GM-PROV, CONTRACT-GM-PROVIDER | Provider seam | backend/tests/test_providers.py | CMD-RED-GREEN, CMD-WRITESET |
| S11 | 3 | lonestar | Product Implementer | product | Implement the LoneStar Storage adapter, register it, and seed its customers until S10 tests are green. | AC-GM-PROV-01, AC-GM-PROV-02 | DES-GM-PROV, CONTRACT-GM-PROVIDER | Provider seam | backend/gridmarket_server/providers/lonestar.py, backend/gridmarket_server/providers/__init__.py, backend/gridmarket_server/seed.py | CMD-RED-GREEN, CMD-TEST-PROVIDERS, CMD-TEST-ALL, CMD-WRITESET |
| S12 | 3 | integration | Integration Engineer | integration | Assemble phase 2: merge lane lonestar, then lane spec, with post-step V&V; record the phase-2 demoable checkpoint. | AC-GM-LANE-02, AC-GM-ACC-02, AC-GM-SPEC-03 | DES-GM-LANES | Integration | docs/plans/2026-09-25-gridmarket/evidence/assembly-phase-2.md | PROC-ASSEMBLY, CMD-TEST-ALL, CMD-SMOKE |
| S13 | 2 | adversary | Test Implementer | test | Author red tests: over-capacity sell rejected with no balance change, identical Idempotency-Key reuse creates no second order, 50-orders-in-1-s burst gets HTTP 429 with no state change, each shown as an anomaly, GRIDMARKET_ADMIN_KEY-only halt/resume by scope appended to the ledger. | AC-GM-ADV-01, AC-GM-ADV-02 | DES-GM-ADV | Security controls | backend/tests/test_adversarial.py | CMD-RED-GREEN, CMD-WRITESET |
| S14 | 3 | adversary | Product Implementer | product | Implement anomaly flags, kill switch endpoints, and adversary.py scenario until S13 tests are green. | AC-GM-ADV-01, AC-GM-ADV-02 | DES-GM-ADV, CONTRACT-GM-API | Security controls, Market integrity | backend/gridmarket_server/adversary.py, backend/gridmarket_server/market.py, backend/gridmarket_server/api.py | CMD-RED-GREEN, CMD-TEST-ADVERSARY, CMD-TEST-ALL, CMD-WRITESET |
| S15 | 2 | stretch | Test Implementer | test | Author red tests for the backtest (Spearman, n, range, request budget, metrics-only output) with history fixtures, the engine parity suite over Python and Rust engines, and the benchmark script. The Rust parametrization of the parity suite skips when the extension is not importable, so the default suite stays green without it; CMD-TEST-PARITY fails when the extension is absent (red in S15, green in S17). | AC-GM-BT-01, AC-GM-PERF-01 | DES-GM-BT, DES-GM-RUST, CONTRACT-GM-ENGINE | Explainability, Performance | backend/tests/test_backtest.py, backend/tests/test_matching_parity.py, backend/tests/fixtures/ercot_history/, bench/bench_matching.py | CMD-RED-GREEN, CMD-WRITESET |
| S16 | 3 | stretch | Product Implementer | product | Implement backtest.py until test_backtest.py is green. | AC-GM-BT-01 | DES-GM-BT | Explainability, Data ingestion | backend/gridmarket_server/backtest.py | CMD-RED-GREEN, CMD-TEST-BACKTEST, CMD-WRITESET |
| S17 | 3 | rust | Product Implementer | product | Implement the PyO3 matching core, build it in the Dockerfile, run the benchmark, and enable GRIDMARKET_ENGINE=rust in compose only if faster; parity suite green. Dependency admission scan for maturin/PyO3. | AC-GM-PERF-01 | DES-GM-RUST, CONTRACT-GM-ENGINE | Performance, Market integrity | rust/matching_core/, deploy/Dockerfile, deploy/compose.yaml, bench/results.md | CMD-RED-GREEN, CMD-TEST-PARITY, CMD-BENCH, CMD-DEPSCAN, CMD-WRITESET |
| S18 | 3 | integration | Integration Engineer | integration | Assemble stretch: merge adversary (S14 exit) and backtest (S16 exit) each as soon as green; merge ML (S23 exit) only after backtest merged green and not reverted; merge Rust (S17 exit, only with benchmark gain) only after backtest merged; drop any lane not green by Sun 04:30 CDT; merge origin/main; produce the final integrated candidate. | AC-GM-LANE-02, AC-GM-SEC-01 | DES-GM-LANES | Integration | docs/plans/2026-09-25-gridmarket/evidence/assembly-stretch.md | PROC-ASSEMBLY, CMD-TEST-ALL, CMD-SMOKE, CMD-SECRETS, CMD-RULES |

| S19 | 2 | spec | Product Implementer | test | Author red tests for azdiagram (YAML input to SVG and .drawio from the same Graphviz coordinates, grid renderer for F5/F8, overlap and size lint failures), spec_build (generated front matter, Appendix A), and spec_lint (BLUF, six Frame fields, <=5 requirements, T1-T8/F1-F8 classes). | AC-GM-SPEC-01, AC-GM-SPEC-02 | DES-GM-SPEC | Explainability | tools/tests/test_azdiagram.py, tools/tests/test_spec_tools.py, tools/tests/fixtures/ | CMD-RED-GREEN, CMD-WRITESET |
| S20 | 2 | spec | Product Implementer | product | Implement tools/azdiagram, tools/spec_build.py, tools/spec_lint.py, the spec template, and the spec-author, spec-diagram, spec-lint skills until S19 tests are green. | AC-GM-SPEC-01, AC-GM-SPEC-02, AC-GM-SPEC-03 | DES-GM-SPEC | Explainability | tools/azdiagram/, tools/spec_build.py, tools/spec_lint.py, spec/template/, skills/spec-author/, skills/spec-diagram/, skills/spec-lint/ | CMD-RED-GREEN, CMD-TEST-SPEC, CMD-WRITESET |
| S21 | 2 | spec | Product Implementer | product | Write GridMarket's own specification in the template from design.md and the technical plan, with azdiagram figures, and build it; both lints pass. | AC-GM-SPEC-03 | DES-GM-SPEC | Explainability, Integration | spec/gridmarket/, spec/GridMarket-Specification.md | CMD-SPEC-LINT, CMD-WRITESET |
| S24 | 1 | worker | Test Implementer | test | DEC-GM-022: in worktree base-gridmarket-worker on branch gridmarket/lane-worker from origin/jordaaan (4853e51), author red node:test tests (report allowlist exactly /api/report/np6-905-cd/spp_node_zone_hub, /api/report/np4-190-cd/dam_stlmnt_pnt_prices, /api/report/np3-565-cd/lf_by_model_weather_zone, /api/report/np3-233-cd/hourly_res_outage_cap, /api/report/np6-86-cd/shdw_prices_bnd_trns_const; stub env with in-memory CACHE and sliding-window RATE_LIMITER and ERCOT_BUDGET stubs; stub fetch counting ERCOT calls): non-allowlisted /api/report 404; keyless /api/report, /api/products, /api/snapshot?fresh 401; 31st request in 60 s from one client address 429; burst of 40 requests from each of 10 addresses on an empty cache keeps ERCOT calls <= 25 and 429s abusers; snapshot 429 retry kept; views' routes unaffected; all with zero ERCOT calls where stated. | AC-GM-EDGE-01, AC-GM-EDGE-02, AC-GM-EDGE-03, AC-GM-EDGE-04 | DES-GM-EDGE, CONTRACT-GM-WORKER | Security controls | ercot-hackathon/test/security.test.mjs | CMD-RED-GREEN-WORKER, CMD-WRITESET |
| S25 | 1 | worker | Product Implementer | product | DEC-GM-022: implement the report allowlist (exactly /api/report/np6-905-cd/spp_node_zone_hub, /api/report/np4-190-cd/dam_stlmnt_pnt_prices, /api/report/np3-565-cd/lf_by_model_weather_zone, /api/report/np3-233-cd/hourly_res_outage_cap, /api/report/np6-86-cd/shdw_prices_bnd_trns_const), the market client key check (MARKET_KEY) on /api/report, /api/products and /api/snapshot?fresh, the per-client RATE_LIMITER binding on /api/*, the ERCOT_BUDGET guard in the shared ERCOT fetch path with one shared snapshot build per isolate, keep the snapshot 429 backoff, restrict /api/edc to the view's query parameters, and README setup lines, until S24 tests are green; push the lane and open a PR into jordaaan; deployment is Jordan's action. | AC-GM-EDGE-01, AC-GM-EDGE-02, AC-GM-EDGE-03, AC-GM-EDGE-04 | DES-GM-EDGE, CONTRACT-GM-WORKER | Security controls, Data ingestion | ercot-hackathon/src/index.js, ercot-hackathon/wrangler.jsonc, ercot-hackathon/README.md | CMD-RED-GREEN-WORKER, CMD-TEST-WORKER, CMD-WRITESET |
| S22 | 2 | ml | Test Implementer | test | Author red tests for ML feature building (peak flag, temperature, ERCOT inputs, WAC-RAC population weight per zone), train/test split by date, Spearman comparison with the deterministic score, importances, own ERCOT budget, fixtures only. | AC-GM-ML-01 | DES-GM-ML | Explainability | backend/tests/test_ml.py, backend/tests/fixtures/ml/ | CMD-RED-GREEN, CMD-WRITESET |
| S23 | 3 | ml | Product Implementer | product | Check Open-Meteo terms first, then implement ml_data.py and ml.py until S22 tests are green; write docs/ml-report.md from one owner-run live run through the ERCOT Worker (the owner loads GRIDMARKET_WORKER_URL and GRIDMARKET_WORKER_KEY; <= 5 requests/min; never during recording); otherwise mark it fixture-only. | AC-GM-ML-01 | DES-GM-ML | Explainability, Data ingestion | backend/gridmarket_server/ml.py, backend/gridmarket_server/ml_data.py, docs/ml-report.md | CMD-RED-GREEN, CMD-TEST-ML, CMD-WRITESET |
## Concurrency proof (write sets)

- Wave 1 slots (max 4 concurrent): foundation {S01}, worker {S24, S25}.
  Worker owns only `ercot-hackathon/` paths on a branch from
  `origin/jordaaan`; S01 writes no `ercot-hackathon/` path.
- Wave 2 slots (max 4 concurrent): market {S02, S05, S08}, data {S03, S06}
  then spec {S19, S20, S21} (slot edge S06 --> S19), ui {S04, S07}, and the
  red-test lanes lonestar {S10}, adversary {S13}, stretch {S15}, ml {S22}
  (DEC-GM-025). No path appears in two lanes (the red-test write sets are
  test files, fixtures, and bench/bench_matching.py that no other lane
  writes); S09 writes only its evidence file.
- Wave 3 slots (max 4 concurrent): lonestar {S11} then ml {S23} (slot edge
  S11 --> S23), adversary {S14} then rust {S17} (slot edge S14 --> S17),
  stretch {S16}; the spec lane may still hold a slot. No path appears in two
  lanes (S11 owns seed.py and providers/*; S14 owns market.py, api.py,
  adversary.py; S17 owns deploy/* and rust/*; S23 owns ml.py, ml_data.py,
  docs/ml-report.md); S12 and S18 write only their evidence files.
- Shared mutable resources: the ERCOT account budget (30 requests per 60 s)
  is owned by the ERCOT Worker (DEC-GM-021); market-side callers share the
  Worker's 30-per-60 s client limit: poller ≤ 12, backtest ≤ 5, ML ≤ 5
  (sum 22). PROC-ERCOT-LIVE-CHECK runs while the demo poller is stopped;
  backtest and ML live runs never run during demo recording. CMD-SMOKE always
  runs without `GRIDMARKET_WORKER_URL`, so no poller starts; backtest, ML,
  Worker, and NWS tests use fixtures; S24 tests stub `fetch` and never call
  ERCOT or the deployed Worker. The Worker's own upstream budget (25 per
  60 s, AC-GM-EDGE-03) bounds ERCOT calls for every caller.
- Docker daemon and host ports: port 8000 and compose project `gridmarket`
  are reserved for the demo stack started from the integration worktree.
  Every CMD-SMOKE run uses its own project name and port (IE
  `gm-smoke-integration`:18000, S08 `gm-smoke-market`:18001, S17
  `gm-smoke-stretch`:18002) and removes only its own project. compose.yaml
  sets no fixed `image:`, `container_name:`, or volume `name:`.
- SQLite: tests create their database under pytest `tmp_path`; the demo stack
  uses the project-scoped `gm-data` volume; no code or command uses a fixed
  absolute database path.
- NWS API: only the demo stack polls it (<= 6 requests/min); smoke stacks
  run with GRIDMARKET_NWS=off; tests use fixtures (CF-18).
- The cap of 4 (DEC-GM-025) counts active lanes across waves; a lane is
  active only while one of its slices runs, so a red-test lane waiting for its
  wave 3 implementation slice holds no slot. The Coordinator starts a ready
  slice in a new lane only when fewer than 4 lanes are active. When several
  lanes are ready, priority is: foundation, worker, market, data, ui, spec,
  lonestar, adversary, stretch, rust, ml. Slot edges S25 --> S04 and
  S06 --> S19 make the common wave 2 cases deterministic (CF-13).
- Integration branch: only IE slices write it, one step at a time.

## Role states

- active: implementer (Product Implementer; primary route, except spec lane
  S19-S21 on tech-writing and ui S07 on frontend, DEC-GM-024),
  test_implementer (primary route; ui S04 on the frontend entry, same
  harness, model, and reasoning), integration_engineer.execution, reviewer
  (Lifecycle cadence: one review of the integrated candidate at about Sat
  2026-09-26 22:00 CDT, DEC-GM-023), test_engineer.assurance (lifecycle
  cadence), coordinator (wave dispatch, max 4 concurrent lanes), scribe
  (receipts).
- Human lane: Jordan (ERCOT Worker, PR #3, 3D views, deployment); not a
  Bearing role. S24–S25 are agent work (DEC-GM-022); S25 carries the human
  dependency "Jordan merges the PR into jordaaan and deploys".
- unused_in_implementation: light_implementer (no slice meets all light
  criteria), systems_modeler, requirements_engineer, plan_integrator,
  test_engineer.planning, integration_engineer.planning (planning-only).
