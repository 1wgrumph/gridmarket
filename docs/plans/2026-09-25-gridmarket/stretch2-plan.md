# Stretch 2: "Replay a real Texas grid day" (DEC-GM-112)

Owner brief (15:45): replay a real Texas grid day, manage a battery fleet, and let the judge change the outcome. Household fleet stays explicitly SIMULATED; no claims of proven wholesale-price or blackout effects.

## Binding rules for every slice
- R1 Sourced data only at external boundaries. Every fixture or dataset that stands for an external source (ERCOT, NWS, EIA, ERCOT storage dashboard) is copied from a real response or file, or generated from the authoritative published spec, and has a provenance record (source URL, retrieval time UTC, sha256, and the transformation script). Invented external shapes are a contract failure.
- R2 No lookahead. A strategy's decision at replay time t may read only data whose publish/availability time is <= t. Enforced in code by an information-set object, and proven by a test that plants a future value and shows it is never read.
- R3 Units and time. Energy kWh (household) and MWh/MW (grid) with explicit conversion; money in integer cents; prices $/MWh from the source; all times stored UTC, displayed Central Time; ERCOT hourEnding and DST handled per the source spec.
- R4 Battery physics per asset: capacity_kwh, max_charge_kw, max_discharge_kw, round-trip efficiency (split as sqrt on charge and discharge), min_reserve_kwh (backup floor). SoC never leaves [0, capacity]; reserve breaches are counted, never hidden.
- R5 Determinism: same inputs + seed = identical outputs (replay, bots, disruptions). Reset and rerun reproduce results byte for byte in the API payload.
- R6 Honest labels: "simulated" on every household or fleet number; grid data labelled with source and timestamp.
- R7 Test rules (ops/guidance/test-rules.md) plus: no wall clock, public-surface assertions, 5 green runs, fixtures real-shaped (R1).

## Components and contracts
C1 Replay dataset (S67). One historical ERCOT operating day D, chosen by the slice from public ERCOT archives (no credentials): at least 15-min real-time settlement point prices for the four load zones and hubs, day-ahead hourly prices, system load, and ESR aggregate charging/discharging/net if a public source covers D; ESR state of charge from the public 60-day SCED disclosure if D is at least 60 days old and the file is reachable. Output: backend/gridmarket_server/data/replay/<D>/ compact JSON/CSV (small, committed), scripts/replay_data/build.py that rebuilds it from the downloaded public files, and PROVENANCE.md. If a source is unreachable, the slice records a typed gap and ships the rest.
C2 Flex core (S68, backend/gridmarket_server/flex/): Battery (R4), InformationSet (R2), Decision = {action in charge|hold|offer_flex|preserve_backup, kw, reason (plain sentence), inputs: list of {name, value, unit, source, source_time}}, and three policies with one interface: FixedSchedule (charge at night hours, offer at the evening peak), PriceBased (charge below and offer above price thresholds derived only from information available at t), EsrInformed (PriceBased plus ESR charging trend and scarcity signal). Policies are pure functions of (battery state, information set, household load, config).
C3 Replay engine (S69, backend): replay(day, strategies, fleet_config, seed, disruptions) steps at 15-min intervals over D; each strategy gets an identical copy of the starting fleet; commitments = offered flexibility accepted by a simple market rule (documented); a commitment fails when the fleet cannot deliver it (SoC or reserve or provider offline). Scoreboard per strategy: net_value_cents (energy arbitrage + flexibility payments - charging cost), energy_delivered_kwh, min_reserve_kwh (and breaches), failed_commitments, terminal_energy_value_cents (end SoC valued at the day's final price, included in net value). Disruptions: provider_offline(provider, start, end), feed_interrupt(source, start, end) - affected offers become unavailable, agents see missing data (never zero), outcomes deterministic. API: POST /v1/replay (body: day, strategies, fleet, seed, disruptions) -> run id + full timeline + scoreboard; GET /v1/replay/{id}; GET /v1/replay/days. Rate limit and size bounds on the request.
C4 Live decisions (S70, backend + bot profile UI): bots with batteries run EsrInformed each tick on live signals; GET /v1/bots/{id}/decisions?limit returns recent decisions with reasons and source timestamps; POST /v1/flex/estimate (household load profile, battery, reserve_pct) -> available flexibility kWh, projected value cents over a stated day, backup hours at the stated load, and fleet scaling (n homes -> MW). The bot profile shows the decision list; clicking a decision shows its reason and inputs.
C5 Replay page (S71, dashboard): pick day and strategies, run, animate fleet SoC and trades against real prices/load/ESR, scoreboard table, disruption controls (provider offline, feed interrupt with time window), reset and rerun (deterministic). CLS <= 0.1, 1280/390/320, light/dark, keyboard.
C6 Earn vs backup (S72, dashboard): reserve slider for one simulated household -> flexibility, projected value, backup hours under a stated load (from /v1/flex/estimate); fleet size control -> MW contribution; all labelled simulated.
C7 Battery activity timeline (S73, backend + Worker + dashboard, lane esr after S66): GET /v1/signals/history?report_id&zone&start&end (bounded) ; a Worker route for ERCOT's public energy-storage dashboard JSON (charging, discharging, net; sourced fixture per R1; cached; allowlisted); the ESR tile becomes a timeline with 15-min and 1-hour deltas; selecting an interval lists the market trades (and bot decisions once C4 lands) in it.

## Slices, lanes, order
- S67 dataset: lane replay-data (from integration-2 fd1b9c4). Implementer. Starts now.
- S68-T red tests for C2, then S68 flex core: lane replay. Test Implementer then Implementer.
- S69-T red tests for C3 (against the C3 contract, may start in parallel with S68), then S69 engine: lane replay after S68 and S67.
- S70 live decisions + estimate: lane decisions from the S68 exit.
- S71 replay page: lane replay-ui after S69. S72 earn-vs-backup: lane replay-ui after S70's estimate endpoint (contract-first).
- S73 battery timeline: lane esr after S66.
- All land with the stretch assembly S18 (review + Test Engineering + one repair). Phase 2 merge: each lane merges origin/main after landed/2 before its exit.

## Amendments A1-A15 (DEC-GM-113, binding)
The independent planning review's 15 findings are adopted verbatim: ops/plans/stretch2-amendments.md. Each "Exact replacement" there supersedes the matching text above (A1=R1/R7 sourcing, A2=C1 data selection, A3=R2 availability, A4=R3 time and money, A5=R4 battery equations, A6=C2 decisions and policies, A7=C3 procurement and commitments, A8=C3 ledger, A9=disruptions, A10=C4 live decisions advisory only, A11=estimate and slider maths, A12=ESR sources and history, A13=R5 determinism and API bounds, A14=R6 demo claims, A15=R7 gates and order). Where this file and the amendments differ, the amendments win.
Scope choice (A10): live bot decisions are advisory and not executed; battery physics, dispatch and money are modelled in the replay (C3). Live execution would need a separate owner decision.

## C8 Story and tour (DEC-GM-119, owner: "yes lets do it")
Product sentence: "Texas home batteries, paid to help when the grid is tight." Subline: "A simulated flexibility exchange running on real ERCOT conditions."
Demo path (3 minutes): 1 Hook (God's Eye: Texas, and the replay day's real peak price) -> 2 Replay (the fleet decides hour by hour, three strategies on a scoreboard) -> 3 Your turn (earn-versus-backup slider, knock a provider offline) -> 4 Proof (live market with bots, sandbox key and first order).
- Overview hero leads with the sentence, a primary "Start the 3-minute tour" and a secondary "Try the sandbox".
- Route #/tour: four steps, one sentence and one action each, Back/Next, progress 1-4, skippable, keyboard and 390 px.
- Navigation: primary Overview, Tour, Replay, Market, Judge sandbox; a "More" group holds Predictions, Providers, Bots, Spec (all still reachable, deep links unchanged).
- Numbers in the tour come from APIs (the replay day's peak price from GET /v1/replay/days, which S69 must include as peak_rt_price with its point and interval); if an API is unavailable the sentence omits the number, never invents it.
- Slice S80 on lane ux after S63; the S18 assembly joins it with the replay page (S71) and slider (S72).
