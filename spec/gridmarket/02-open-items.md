---
requirements: []
---

## 2 Open Items

**BLUF:** The open items are owner actions and time-boxed triggers, and none of them blocks the phase 1 market from running on fixtures or stale data.

**Frame**

- **Who:** The owner and the Orchestrator.
- **What:** Decisions and actions not yet closed at revision 0.1.
- **Why:** An open item hidden in prose is an item nobody closes.
- **How:** Each row names its owner, its deadline, and its impact if missed.
- **When:** Open at 2026-09-26; each closes by its due time or by the recorded fallback.
- **Where:** The Lifecycle journey and the owner's accounts.

Owner-only actions (production deploy, credentials, publication) stay with the
owner by rule; the architecture's fallbacks keep the demo running if one of
them is late.

Table (T7): Open items

| Item | Owner | Due | Impact |
|---|---|---|---|
| Deploy the ERCOT Worker with the allowlist, `MARKET_KEY`, and `MARKET_URL` | Owner | Before the phase 1 acceptance run | Without it live score inputs do not flow; views show `VIEWS_NOT_DEPLOYED` |
| Confirm live Worker field names per route | Integration Engineer | Phase 1 assembly | Parser fix in the data lane if fixtures differ (RISK-GM-09) |
| Slip trigger for diversity layers 2, 3, 5a, 6 | Orchestrator | Sat 2026-09-26 14:00 CDT | Layers move to phase 2; dormant rate stays in 1b |
| Create tunnel credentials and start the `tunnel` profile | Owner | Sunday recording | No public demo URL |
| Set the Jev key and turn the Jev flag on for the demo | Owner | Sunday recording | Jev column stays hidden; baseline rules still answer |
| AZHQ visual-review skill availability | Owner | Phase 1b | Typed gap; vitest render tests are the evidence (RISK-GM-18) |
| Make the repository public after the secret scan | Owner | Before submission 11:00 CDT Sunday | Judges cannot read the code or this specification |
