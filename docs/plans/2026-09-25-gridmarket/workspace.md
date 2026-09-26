# Workspace Environment: GridMarket hackathon MVP

## Repository Identity
- Root: `/home/spectre/alphazede/Hackathons/Base`
- Plan directory: `docs/plans/2026-09-25-gridmarket/`
- Confirmed by: DEC-GM-001 (local Git repository, GitHub remote deferred to the
  owner) and DEC-GM-002 (root and plan directory) in `journey.json`.
- Observed at: HEAD `378fcb993f9b6993dddae95ea02bee037ac62d66`, branch
  `gridmarket/lifecycle-setup`, 2026-09-25.

## Mapped Inputs
- `gridmarket-intent.html`: owner intent and build specification (27,112 bytes).
  Product thesis, simulation model, Flex Credits, spot and simulated future
  markets, ERCOT signals, predictive engine, provider adapter contract, public
  API surface, security controls, conceptual architecture (§16), suggested data
  model (§17), P0/P1/P2 priority (§18), build sequence (§19), demo narrative
  (§20), non-goals (§21), success criteria (§22), ERCOT references (§24).
- `reference/hackathon-brief.md`: Base & AITX Talent Hackathon rules (3,447
  bytes). Event, submission, tracks, judging, agenda. Captured 2026-09-25 with
  two recorded capture gaps.
- `docs/plans/2026-09-25-gridmarket/journey.json`: Lifecycle state, checkout
  lease (generation 1), DEC-GM-001, DEC-GM-002.
- Detail: `repository-map.md` in this plan directory.

## Observed Systems
- None. The repository is greenfield: no source directories, no manifests, no
  task runner, no CI, no test configuration, no repository-level `AGENTS.md` or
  `CLAUDE.md`.

## Architecture Coverage
- Realized architecture: none.
- Modeled architecture: none.
- Intent-level architecture only: `gridmarket-intent.html` §10 (provider
  adapter contract), §11 (REST API surface), §12 (policy and risk flow), §16
  (conceptual component diagram), §17 (suggested data model). These are owner
  intent, not a realized or modeled architecture.
- **Gap:** no architecture covers the affected scope. Systems Modeler
  activation is needed per the Architectural Alignment skill (step 4). This
  node does not design the missing architecture.

## Constraints and Git Boundaries
- Branch / Worktree: `gridmarket/lifecycle-setup` (dirty: `docs/` untracked;
  committed inputs unmodified).
- Remote: none configured. GitHub remote deferred to the owner (DEC-GM-001).
- Rules: `/home/spectre/alphazede/AGENTS.md` and `CLAUDE.md` (workspace
  cross-repo rules; no Hackathons-specific entry found), owner global
  `~/.claude/CLAUDE.md` (agent author identity, PR-only `main`, owner-only
  actions include public export/release/publication and production deploy).
- Deadline: final submissions due **Sunday 2026-09-27 11:00 AM
  America/Chicago** (`reference/hackathon-brief.md`, Submission and Agenda;
  venue Austin, TX). Judging 11:00 AM–2:00 PM; awards 2:00–3:00 PM.
- Submission format: one **5-minute demo video** plus a **link to the
  codebase** per team. Top submissions per track present live at awards.
- Tracks: pick one; one project may enter up to 2 tracks if it fits. Options:
  Open Grid Data, Orchestration, Most Commercializable. Not yet chosen.
- Judging (100 points), judged from the demo video and the codebase:
  - Technical Execution & Completeness 30: Completeness 15 (core workflow
    completes without crashing), Technical Depth 15.
  - Fit to the Track 30: The Problem 15, The "Why" 15.
  - Value & Impact 20: Insight Quality 10, Usability 10.
  - Innovation and Execution 20: Creativity 10, Performance 10.
  - Philosophy: real working systems, not slide decks or simple API wrappers.
- Intent non-goals (§21): real electricity settlement, real customer billing,
  production Base integrations, real battery dispatch, real financial futures,
  real money, KYC/AML, regulatory market participation, QSE functionality,
  blockchain, cryptocurrency, production-grade clearing, sophisticated
  derivatives, options, leverage.
- Intent scope limits: no options, leverage, sophisticated margin, or
  real-money settlement (§7); Google OAuth only after the core market works
  (§14); P2 items only after the platform is stable (§18).
- Intent invariants: committed capacity never exceeds verified available
  capacity (§4.2); AI and algorithms never bypass policy checks and use the same
  trading API as humans (§12); required MVP security controls listed in §15.
- Intent disclosure requirements: future contracts are stated as simulated
  forward flexibility contracts, not regulated commodity futures (§7); Flex
  Credit is not a REC, cryptocurrency, or electron claim (§5); opportunity score
  is not presented as guaranteed profit (§9.2).
- Data source preference: official ERCOT public sources (§24).
- This node's authority: write only `workspace.md` and `repository-map.md` in
  the plan directory. No commit.

## Validation Commands [observed, not run]
- Test: none observed (no test configuration or task runner exists).
- Lint: none observed.
- Build: none observed.

## Unknowns
- Architecture: none realized or modeled. Systems Modeler activation needed.
- Track selection (1 or 2 of 3): owner decision, not recorded.
- Stack, runtime, storage, hosting, and deployment target: none observed.
- Codebase link for submission: no remote exists (DEC-GM-001 defers it).
  Codebase visibility to judges and any public hosting of the live dashboard
  or judge sandbox (§13, §20 Step 7) touch owner-only publication; path not
  recorded.
- ERCOT access: registration, key, rate limits, and data latency for the
  §8 signals are not verified.
- Brief capture gaps: Notion "Submission Checklist" toggle not expanded;
  Pitch kickoff deck text (25 slides) not captured.
- Team composition and demo video production owner: not recorded.
- Deadline time zone: brief gives local time without a zone; America/Chicago
  taken from the confirmed Lifecycle inputs and the Austin venue.
- Landing path: no remote, so PR-only `main` landing cannot run until the
  owner adds a remote.

## Map Freshness
- Tier 1: Recorded root and plan directory match confirmed inputs
  (DEC-GM-002).
- Tier 2: `git status --porcelain -- gridmarket-intent.html
  reference/hackathon-brief.md` showed no modifications at HEAD `378fcb9`.
  `docs/` is untracked.
- Note: Does not detect committed changes postdating this observation.
