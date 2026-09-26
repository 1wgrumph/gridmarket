---
requirements: []
---

## 3 Use Model

**BLUF:** GridMarket is used through one public HTTP API, whether the client is the dashboard, a judge's script, a bot, or a user's own LLM agent.

**Frame**

- **Who:** Judges, traders, bots, user agents, and the owner.
- **What:** How each kind of user interacts with the system.
- **Why:** One surface means one set of limits, errors, and docs for every client (API contract lens).
- **How:** REST with JSON, Bearer keys, Idempotency-Key on orders, and 2-second polling.
- **When:** During the demo recording and judging; the tunnel is open until Sunday 15:00 CDT.
- **Where:** The dashboard, the SDK, gridmarket-mcp on the user's machine, and the bots container.

A visitor opens the dashboard without logging in, reads live ERCOT signals and
zone scores, and gets a sandbox key from the Judge sandbox page. A developer
installs nothing beyond Python 3, copies the SDK example, and places an order
with that key. A user's own LLM agent reads the prompt kit or runs
gridmarket-mcp locally with the user's key. The seeded bots trade through the
same API with their own derived keys. The owner operates admin functions
(spawn bots, provider outage, kill switch) only from the host loopback.
