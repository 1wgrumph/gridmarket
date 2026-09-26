---
requirements: []
---

## 5 Security

**BLUF:** GridMarket protects a simulated market on a public tunnel, so security rests on keys, limits, loopback-only admin, and owner-held secrets that never enter the repository.

**Frame**

- **Who:** The owner, judges, bots, and attackers on the public tunnel.
- **What:** Threats, controls, and security interfaces.
- **Why:** Security controls lens: auth, idempotency, limits, and secrets enforced at the boundary.
- **How:** Controls in `api.py`, the Worker, Compose, and the repository gates.
- **When:** Throughout the demo window and before publication.
- **Where:** The tunnel boundary, the host loopback, the Worker, and the Git history.

Section 5.1 lists threats and controls, 5.2 the security features, and 5.3
the interfaces where trust changes.
