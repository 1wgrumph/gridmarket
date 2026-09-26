---
requirements: []
---

## 7 Verification Approach

**BLUF:** GridMarket is verified by tests written before code in every lane, by deterministic gates at every assembly step, and by one uninterrupted acceptance run per phase.

**Frame**

- **Who:** Test Implementers, Product Implementers, the Integration Engineer, and phase assurance.
- **What:** How each requirement's verification method is applied.
- **Why:** A merged change that is not verified would put the demoable `main` at risk.
- **How:** Red tests, green implementation, write-set checks, post-merge V&V, and phase acceptance runs.
- **When:** Every slice, every assembly merge, and every phase landing.
- **Where:** `make` targets in the repository and the Lifecycle SEIT.

The Lifecycle's SEIT names, for each requirement, the method (test,
inspection, demonstration, analysis), the command, and the pass rule. Section
7.1 states the approach.
