# Requirements Engineer gate — GM-2026-09-25

- Verdict: **REPAIRABLE_FAILURE**
- candidate_ref: `docs/plans/2026-09-25-gridmarket/gridmarket-technical-plan.md`
- candidate sha256: `4348f5929e0e353624de90a5ce0ffae73f13be89df7c3e308c5f3d5548da76b2` (matches the file on disk)
- changed_paths: `docs/plans/2026-09-25-gridmarket/specialists/requirements-engineer-gate.md` (this file only)
- Register: none. Every `AC-*` / `RISK-*` row is Lifecycle-local.
- S8: `SRC-EMV-NASA-SEH` (Appendix C paraphrase only), `SRC-EMV-COE` (UIDs only), `SRC-EMV-29148` (metadata-only, no clauses).
- BRAN: unavailable (no `.bran/policy.yaml`).

## Mechanical evidence

`lint-sdoc.py --profile library` is a typed gap **not_applicable**: it targets COE `.sdoc` libraries (UID `^COE-`, 22 core fields) and no register exists.

`specialists/ac-mechanical-lint.txt` reuses that tool's EARS, banned-term, and agnostic-term constants: **32 AC rows, 0 flagged**. This gate does not re-decide those hits. It judges traceability, glossary fit, conflicts with DEC-GM-001..016, measurability the linter cannot see, and coverage.

Checklist: CHK-RE-01..50 applied. N/A with reason: CHK-RE-12 (these rows are the requirement layer), CHK-RE-06 where DEC-GM-009 or DEC-GM-010 names the design, CHK-RE-07/22/23 for `AC-GM-LANE-*` and `AC-GM-SEC-01` (lifecycle procedure, not a product duty), CHK-RE-40/42/46 (maintainability, reliability, and post-fault continuity are outside the confirmed scope). PROV-01 names its adapter operations; no interface field is left blank. Failures are only the rows below.

## Per-row findings

| ID | finding | exact proposed replacement text |
|---|---|---|
| AC-GM-DATA-01 | CHK-RE-25, CHK-RE-17. Definitions **Zone** is only `LZ_HOUSTON`, `LZ_NORTH`, `LZ_SOUTH`, `LZ_WEST`. The same sentence requires that zone on every stored value, including the weather-zone load forecast and NP6-86 constraint shadow prices, which are not load-zone records. | While valid ERCOT credentials are configured, the system shall poll the ERCOT Public API for real-time settlement point prices (NP6-905-CD), day-ahead settlement point prices (NP4-190-CD), the seven-day load forecast by weather zone (NP3-565-CD), hourly resource outage capacity (NP3-233-CD), and SCED shadow prices and binding constraints (NP6-86-CD), and shall store each settlement-point price with its settlement-point name, each load-forecast value with its ERCOT weather-zone name, each outage-capacity value with its load zone, and each shadow price with its constraint identity, and shall store each of those values with its interval, ERCOT publish time, and fetch time. |
| AC-GM-DATA-03 | CHK-RE-05. "A timeout" has no duration, so a test cannot tell a hang from a pass. The 5-minute cap and the stale-data duty stay; they already trace to the DEC-GM-007 recorded risk. | If an ERCOT request returns HTTP 401, HTTP 429, or a 5xx status, or the connection fails before a complete HTTP response, then the system shall retry that request with exponential backoff whose delay is at most 5 minutes, shall keep serving the last stored values marked stale with their age in seconds, and shall keep every API endpoint able to return an HTTP response. |
| AC-GM-SCORE-02 | CHK-RE-13, CHK-RE-25. "Binding-constraint shadow price for a zone" has no defined link from a constraint to a load zone. A test cannot set up the antecedent, and a global reading would move every zone together, against intent §8. | When the hourly resource outage capacity stored for a load zone increases while every other input to that zone's opportunity score is unchanged, the opportunity score for that zone shall not decrease. When a shadow price cited by that zone's congestion-pressure explanation increases while every other input to that zone's opportunity score is unchanged, the opportunity score for that zone shall not decrease. |
| AC-GM-MKT-01 | CHK-RE-13, CHK-RE-24. "Spot and future products for each delivery hour from 1 to 24" reads as both product types on every hour. Definitions give spot hours 1–2 and future hours 3–24. | The system shall list one spot product for every zone for each delivery hour starting 1 or 2 hours after the current hour and one future product for every zone for each delivery hour starting 3 to 24 hours after the current hour, and shall trade both product types through one matching engine. |
| AC-GM-MKT-04 | CHK-RE-30. "Collateral holds" adds a margin hold. Intent §7, cited as source, forbids sophisticated margin for the weekend MVP. The 50-credit order cap and 200-credit position cap stay: DEC-GM-012 requires a maximum order size and intent §7 requires position limits, and neither source gives other numbers. | If an order exceeds 50 credits, would raise the account's absolute net position in the product above 200 credits, or requires more cash than the account's cash minus cash held for that account's open orders, then the system shall reject it with a typed reason and change no balances. |
| AC-GM-MKT-05 | CHK-RE-24, CHK-RE-30. DEC-GM-008 sets the reference at the four-interval average in $/MWh ÷ 1000 and sets cash P&L to (reference − trade price) × quantity. The clamp to −$0.25..$5.00 per credit is not in that decision and changes settlement. Signed quantity stays: it is the reading of that formula that pays a short the opposite of a long. | When all four 15-minute real-time settlement point prices of a future product's delivery hour are stored, the system shall settle every open position in that product at the reference price (their average in $/MWh ÷ 1000) with cash P&L equal to (reference − trade price) × signed quantity, and shall report realized and unrealized P&L per account. |
| AC-GM-ADV-01 | CHK-RE-24, CHK-RE-49. "Reject a replayed order" contradicts AC-GM-API-02, which returns the original result for an identical Idempotency-Key and creates no second order. "Contain" is not an observable. "At least 100 orders in 10 seconds" is 10 orders per second on average, which does not exceed the standard-key limit in AC-GM-API-03 (20 requests per second), so the burst does not force the control. | When the adversarial scenario runs, the system shall reject an over-capacity spot sell and change no balances, shall create no second order when an identical request reuses an Idempotency-Key, and shall return HTTP 429 and change no state once one account exceeds its AC-GM-API-03 rate limit, and shall show each of those three outcomes as an anomaly on the dashboard. |
| AC-GM-ADV-02 | CHK-RE-25. "Admin key" and "audit trail" are not in Definitions, so the actor and the record are not checkable. | When a request authenticated as the admin API key named in the untracked environment file invokes the kill switch for the market or for one account, the system shall reject every later order in that scope with a typed reason and change no balances until a request authenticated as that same admin API key lifts the halt, and shall append the halt and the lift to the append-only trade ledger. |
| AC-GM-ACC-02 | CHK-RE-13, CHK-RE-30. "Every phase 1 criterion" can mean every phase-1 AC or the success criteria. DEC-GM-016 says phase 2 adds criterion 6 to the phase-1 set SC-1..SC-5 and SC-7..SC-11, shown in one tunnel session. | The phase 2 acceptance run shall show SC-1 through SC-11 in one uninterrupted session through the tunnel URL. |

All other `AC-*` rows and all `RISK-*` rows pass. RISK-GM-01's control text follows the AC-GM-DATA-03 repair; the risk row itself is not a separate failure.

## Coverage check

### SC-1..SC-11

| SC | Covered by | Gap |
|---|---|---|
| SC-1 | AC-GM-DATA-01, AC-GM-UI-01, AC-GM-ACC-01 | none after the DATA-01 repair |
| SC-2 | AC-GM-ACCT-01, AC-GM-MKT-02, AC-GM-MKT-04 | spot fill does not move cash or Flex Credits; see gap below |
| SC-3 | AC-GM-MKT-01, AC-GM-MKT-02, AC-GM-MKT-05 | same spot-fill gap; future settlement is MKT-05 |
| SC-4 | AC-GM-SCORE-01, AC-GM-SCORE-02 | none after the SCORE-02 repair |
| SC-5 | AC-GM-SCORE-01 | none |
| SC-6 | AC-GM-PROV-02, AC-GM-ACC-02 | none after the ACC-02 repair |
| SC-7 | AC-GM-API-01, AC-GM-API-04 | none |
| SC-8 | AC-GM-API-04 | none |
| SC-9 | AC-GM-BOT-01 | none |
| SC-10 | AC-GM-MKT-03, AC-GM-MKT-04 | none after the MKT-04 repair |
| SC-11 | AC-GM-UI-01, AC-GM-UI-02, AC-GM-SCORE-03 | none |

### DEC-GM-001..016

| Decision | Product obligation | Where |
|---|---|---|
| DEC-GM-001, DEC-GM-002 | Repository and plan paths. Not a product duty. | Exclusions (owner git actions) |
| DEC-GM-003 | Track entry. Not a product duty. | Outcome |
| DEC-GM-004 | Team size. Deferred. | open decision CELL-GM-HEADCOUNT-VIDEO |
| DEC-GM-005 | Phased demo that does not crash; freeze Sun 07:00 CDT. | AC-GM-ACC-01, AC-GM-ACC-02, exit criteria, RISK-GM-06 |
| DEC-GM-006 | LoneStar on the same books; parallel lanes; demoable integration. | AC-GM-PROV-02, AC-GM-LANE-01, AC-GM-LANE-02 |
| DEC-GM-007 | Live ERCOT polling only; untracked credentials; 30/min and 1-hour token. | AC-GM-DATA-01, AC-GM-DATA-02, AC-GM-DATA-04 |
| DEC-GM-008 | Future settlement formula. | AC-GM-MKT-05 (repair removes the clamp) |
| DEC-GM-009 | Compose isolation, outbound tunnel, rate-limited sandbox keys. | AC-GM-OPS-01, AC-GM-API-03, RISK-GM-07 |
| DEC-GM-010 | One matching engine; Rust core only with a benchmark. | AC-GM-MKT-01, AC-GM-PERF-01, AC-GM-OPS-01 |
| DEC-GM-011, DEC-GM-015 | Secret scan and MIT license before the owner publishes. | AC-GM-SEC-01 |
| DEC-GM-012 | Phase-1 core, never-cut controls, three stretch items, P2 out. | Phase-1 ACs, AC-GM-ADV-01, AC-GM-ADV-02, AC-GM-BT-01, AC-GM-PERF-01, Exclusions |
| DEC-GM-013 | No TypeScript trading example. | Exclusions; AC-GM-API-04 is the Python example |
| DEC-GM-014 | Fixtures allowed off the live path. | AC-GM-DATA-01 verification, AC-GM-DATA-04 |
| DEC-GM-016 | Phase-1 SC set, then SC-6. | AC-GM-ACC-01, AC-GM-ACC-02 |

Never-cut controls each have a row: capacity reservation AC-GM-MKT-03, API keys AC-GM-API-01, idempotency AC-GM-API-02, maximum order size AC-GM-MKT-04, rate limits AC-GM-API-03.

Not gaps: wind and solar (DEC-GM-012 signal list), generic-bess (DEC-GM-006 names LoneStar), maximum daily loss and provider health (intent §15, not in the DEC-GM-012 never-cut list), WebSockets and the other P2 items (DEC-GM-012).

Open decisions CELL-GM-SUBMISSION-CHECKLIST and CELL-GM-KICKOFF-DECK are already blocked and are not product ACs. They do not add a row failure. CELL-GM-HEADCOUNT-VIDEO stays deferred under DEC-GM-016.

### Coverage gap (add one row)

CHK-RE-18. No row states that a spot fill moves money or Flex Credits. SC-2, SC-3, intent §6 simulated settlement, and DEC-GM-012 ledger and P&L require it. Capacity reservation stays on AC-GM-MKT-03 (at accept time). Future cash P&L stays on AC-GM-MKT-05.

Proposed new row, phase 1, verification test, source intent §6, DEC-GM-012, SC-2, SC-3:

`AC-GM-MKT-06`: When a spot order fills, the system shall transfer simulated cash from the buyer to the seller in the amount fill price × filled quantity and shall increase the buyer's Flex Credit inventory by that filled quantity.

## Blocker

The nine rows in the findings table, plus the missing AC-GM-MKT-06. No owner decision is required to apply the replacement text. No missing mechanical evidence.
