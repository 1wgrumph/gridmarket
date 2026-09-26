# Requirements Engineer gate — GM-2026-09-25 — correction round 1

- Verdict: **REPAIRABLE_FAILURE**
- candidate_ref: `docs/plans/2026-09-25-gridmarket/gridmarket-technical-plan.md`
- candidate sha256: `0d792040197d6c40cdea1745529a330238298ae65b9ce99dd402abd697abe0b1` (matches the file on disk)
- changed_paths: `docs/plans/2026-09-25-gridmarket/specialists/requirements-engineer-gate-r1.md` (this file only)
- Register: none. Every `AC-*` / `RISK-*` row is Lifecycle-local.
- S8: `SRC-EMV-NASA-SEH` (Appendix C paraphrase only), `SRC-EMV-COE` (UIDs only), `SRC-EMV-29148` (metadata-only, no clauses).
- BRAN: unavailable (no `.bran/policy.yaml`).
- Scope: corrected rows, new `AC-GM-MKT-06`, the new definition, and rows whose meaning those change. Rows that passed round 0 were not reopened.

## Mechanical evidence

`lint-sdoc.py --profile library` remains **not_applicable** (no COE register). `specialists/ac-mechanical-lint-r1.txt`: **33 AC rows, 0 flagged**. This gate does not re-decide those hits.

Checklist CHK-RE-01..50, same N/A set as round 0. Round 0 failures that the verbatim text removes are closed below. The only new failure is `AC-GM-MKT-06`.

## Per-row findings

| ID | result | finding | exact proposed replacement text |
|---|---|---|---|
| AC-GM-DATA-01 | PASS | Round 0 CHK-RE-25 / CHK-RE-17 closed. Weather-zone and constraint records are no longer stored as a load-zone **Zone**. | |
| AC-GM-DATA-03 | PASS | Round 0 CHK-RE-05 closed. The retry trigger is an HTTP status or a failed connection, and the backoff delay is bounded by 5 minutes. RISK-GM-01 still matches the stale-with-age duty; that risk row is not reopened. | |
| AC-GM-SCORE-02 | PASS | Round 0 CHK-RE-13 / CHK-RE-25 closed. The shadow-price antecedent is the price cited by that zone's congestion-pressure explanation (AC-GM-SCORE-01), not a global constraint. | |
| AC-GM-MKT-01 | PASS | Round 0 CHK-RE-13 / CHK-RE-24 closed. Spot hours 1–2 and future hours 3–24 match the **Spot product** and **Future product** definitions. | |
| AC-GM-MKT-02 | PASS | Consistency only. "Append-only trade ledger" now matches the new definition. "Each fill exactly once" is unchanged and is not contradicted. | |
| AC-GM-MKT-04 | PASS | Round 0 CHK-RE-30 closed. Cash held for open orders is the account-balance check from intent §7. It is not a margin hold. | |
| AC-GM-MKT-05 | PASS | Round 0 CHK-RE-24 / CHK-RE-30 closed. The clamp is gone. Cash P&L is the DEC-GM-008 formula, with signed quantity so a short is paid the opposite of a long. The definition's settlement records are an allowed ledger kind; this row does not update or delete them. | |
| AC-GM-MKT-06 | FAIL | CHK-RE-13, CHK-RE-24. AC-GM-MKT-02 fills one incoming order against multiple resting orders, each at that order's price. "When a spot order fills" plus singular "the seller" and singular "fill price" also reads as one transfer for the whole order. A test with two sellers cannot tell which reading passes. Buyer-only Flex Credit increase stays: a spot sell is a capacity reservation (**Spot product**, AC-GM-MKT-03), not a debit of the seller's Flex Credit inventory. | When a spot fill occurs, the system shall transfer simulated cash from the buyer to the seller of that fill in the amount fill price × filled quantity and shall increase the buyer's Flex Credit inventory by that filled quantity. |
| AC-GM-ADV-01 | PASS | Round 0 CHK-RE-24 / CHK-RE-49 closed. Identical Idempotency-Key reuse creates no second order (AC-GM-API-02). The rate-limit trigger is the account exceeding its AC-GM-API-03 limit. The three outcomes are the dashboard anomalies. | |
| AC-GM-ADV-02 | PASS | Round 0 CHK-RE-25 closed. The actor is the admin API key named in the untracked environment file. Halt and lift match the new definition and are append-only. | |
| AC-GM-ACC-02 | PASS | Round 0 CHK-RE-13 / CHK-RE-30 closed. SC-1 through SC-11 is the DEC-GM-016 phase-1 set plus criterion 6. | |
| Definition **Append-only trade ledger** | PASS | Fills, market or account halts, and halt lifts are the record kinds AC-GM-MKT-02 and AC-GM-ADV-02 append. "Never updates or deletes" makes append-only checkable. Settlements are an allowed record kind, not a duty to write a settlement row on AC-GM-MKT-05. No passed row changes meaning. | |

## Blocker

`AC-GM-MKT-06` only. No owner decision is required to apply the replacement text. No missing mechanical evidence.
