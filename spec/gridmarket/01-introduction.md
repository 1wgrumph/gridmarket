---
requirements: []
---

## 1 Introduction

**BLUF:** GridMarket is a provider-neutral, API-first simulated exchange for battery flexibility that prices Flex Credits from live ERCOT and NWS data and explains every score it publishes.

**Frame**

- **Who:** Judges, traders, bot authors, and the owner who operates the demo.
- **What:** The GridMarket hackathon MVP: market, data edge, score, router, bots, dashboard, and onboarding surfaces.
- **Why:** To show a commercially plausible flexibility market that runs on open grid data without real money.
- **How:** One Python process owns the market and one SQLite file owns the state; every client uses one public HTTP API.
- **When:** Built during the Base hackathon from 2026-09-25 17:00 CDT to the 2026-09-27 11:00 CDT submission.
- **Where:** Section 1 of GM-SPEC-001; the repository `github.com/1wgrumph/gridmarket`.

This specification describes the architecture of GridMarket as designed in
Lifecycle GM-2026-09-25. It is written from the approved `design.md` and
`gridmarket-technical-plan.md` of that Lifecycle and is a product deliverable
for the judges, not a planning artifact. Section 1 identifies the system and
its baseline; section 2 lists open items; section 3 gives the use model;
section 4 the feature architecture; section 5 security; section 6 the
programming model; and section 7 the verification approach. Appendix A is the
generated traceability from each Lifecycle-local requirement to the sections
that bind it.

Every requirement named here carries its Lifecycle-local identifier
(`AC-GM-*`), and every design decision its design identifier (`DES-GM-*`) or
contract identifier (`CONTRACT-GM-*`). Where this document and the approved
plan differ, the plan wins and this document is corrected.
