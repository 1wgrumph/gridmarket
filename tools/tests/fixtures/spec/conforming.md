---
requirements:
  - AC-GM-MKT-01
  - AC-GM-MKT-02
---

## Market

**BLUF:** The market matches energy orders every interval and publishes clearing prices.

**Frame**

- **Who:** Traders, bots, and the dashboard.
- **What:** A continuous double auction per ERCOT zone.
- **Why:** Price discovery for grid scarcity.
- **How:** Price-time priority matching over a SQLite ledger.
- **When:** Every 60 s poll cycle.
- **Where:** The backend market service.

The market accepts orders from traders and bots and settles them against the
latest ERCOT snapshot.

Table (T2): Generator fleet

| Generator | Capacity | Zone |
|---|---|---|
| Solar | 100 MW | West |
| Wind | 200 MW | Panhandle |
| Gas | 300 MW | Houston |

The data flows between components as follows:

- ERCOT Worker -> Market
- Bot population -> Market
- Market -> Dashboard

Figure (F1): Market context

![Market context](figures/market-context.svg)
