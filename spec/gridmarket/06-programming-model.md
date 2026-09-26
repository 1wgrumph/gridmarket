---
requirements:
  - AC-GM-DOC-03
---

## 6 Programming Model

**BLUF:** Programming GridMarket means calling its REST API, through the stdlib SDK, a rules template, the prompt kit, or gridmarket-mcp, and handling its typed errors and limits.

**Frame**

- **Who:** Developers and users' agents.
- **What:** The client programming model and the onboarding skill that teaches it.
- **Why:** A new person or agent must reach a live order quickly and safely.
- **How:** `from gridmarket import Client`; a fresh Idempotency-Key per order; typed error codes; documented limits.
- **When:** Any time the market is reachable.
- **Where:** `sdk/python/`, `examples/`, `docs/`, and `skills/gridmarket-onboarding/`.

A client creates a `Client` with its API key and the base URL, reads the
market and predictions, and submits orders; every order carries a fresh
Idempotency-Key. A client honors `Retry-After` on 429, reads the typed reason
on 422, and backs off on 423 while the market is halted. Order size is at
most 50 credits and the absolute position per product at most 200. The exact
SDK method names are frozen in `CONTRACTS.md` and documented in
`docs/USER_GUIDE.md`. The onboarding skill
`skills/gridmarket-onboarding/SKILL.md` takes a user's agent through getting a
key, reading data, choosing the SDK, template, prompt kit, or MCP, monitoring
its own orders, and handling each limit and error code (AC-GM-DOC-03).
