---
requirements: []
---

## 4 Feature Architecture

**BLUF:** GridMarket is a single composition root that wires a transactional market core to data pollers, a scorer, a router, and a provider seam, with every client outside the process.

**Frame**

- **Who:** Implementers and reviewers.
- **What:** The decomposition of the system into features, their interfaces, data, performance, and fault behavior.
- **Why:** A reviewer checks a lane against the feature it owns.
- **How:** Section 4.1 decomposes features, 4.2 gives interfaces, 4.3 data, 4.4 performance, 4.5 faults, 4.6 to 4.8 views, model correspondence, and rationale.
- **When:** Stable from wave 1; feature internals change within their lanes.
- **Where:** `backend/gridmarket_server/`, `dashboard/`, `sdk/`, `ercot-hackathon/`, and `tools/`.

The architecture is hybrid (DEC-GM-021, DEC-GM-027): the owner's Cloudflare
Worker is the ERCOT data edge and serves the 3D views, and the Python market
is everything else. It is contract-first (DEC-GM-039): wave 1 froze every
shared name so that the lanes of wave 2 build their features in parallel
against stubs.
