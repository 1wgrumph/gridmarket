# ERCOT × Jev Decision Map

> **Where Jev runs:** every decision in this map is served by the jev-gateway
> Cloudflare Worker (`https://jev-gateway.jordan-691.workers.dev`, `POST /v1/systemone`,
> `Authorization: Bearer $JEV_GATEWAY_TOKEN`). ercot-hackathon never calls TypeSafe directly
> and holds no Jev key.

Which ERCOT Public API reports can feed calibrated Jev checks, what each check decides, and how the answers are routed. Built from the 116 report products the `ercot-hackathon` Worker can reach.

## Read this first: what "trading ERCOT" requires

- **Day-ahead virtual bids, point-to-point obligations and offers** can only be submitted by a registered Qualified Scheduling Entity (QSE), through EWS or the MIS portal.
- **Congestion revenue rights (CRRs)** require registration as a CRR Account Holder, with credit posted to ERCOT.
- **Without registration**, the usual routes are exchange-listed ERCOT futures and options through a futures broker, partnering with a QSE, or controlling a physical asset such as a battery.
- The Public API is read-only and mostly delayed or disclosure data. It supports signals, research and paper trading, not order entry. This is a technical map, not investment advice.

## How data flows into decisions

```text
 ERCOT Public API (api.ercot.com/api/public-reports)
        │   token: B2C ROPC → KV (55 min)      key: Ocp-Apim-Subscription-Key
        ▼
 ┌──────────────────────────── ercot-hackathon Worker ─────────────────────────────┐
 │  Cron Triggers ──► ingest jobs ──► Queue ──► normalizer                         │
 │   5-min · hourly · daily            │            ├──► R2   raw JSON archive     │
 │                                     │            ├──► D1   tidy time series     │
 │                                     │            └──► KV   latest snapshot      │
 │                                     ▼                                           │
 │                              feature builder (D1)                               │
 │   DART spread · forecast error · reserve proxy · congestion rank · adders       │
 └─────────────────────────────────────┼───────────────────────────────────────────┘
                                       ▼
                         jev-gateway  (calibrated checks)
                 "P(HB_NORTH RT > $150 in next 2h) = 0.71"
                                       ▼
                    router (confidence bands + policy rules)
     log only (< 0.50) · human review (0.50–0.80) · Slack alert + paper ledger (≥ 0.80)
                                       ▼
        outcomes (actual SPP, load, generation) ──► Brier score + reliability ──► recalibrate
```

## Opportunities, grouped by decision

| Check family | Cadence | Question Jev answers | Key reports | Decides |
|---|---|---|---|---|
| Scarcity and price spikes | 5–15 min | P(hub RT price > $X within 2 h) | NP6-905-CD, NP6-970-CD, NP6-323-CD, NP6-325-CD, NP6-235-CD, NP3-763-CD, NP4-412-CD | Alert, hedge review, battery discharge timing |
| Day-ahead vs real-time (DART) | Daily | P(RT SPP > DA SPP at hub, HE n) | NP4-190-CD, NP6-905-CD, NP4-523-CD, NP6-322-CD, NP4-183-CD | Virtual position direction (QSE only) or load shifting; best first backtest |
| Wind and solar forecast error | Hourly · 5-min | P(renewables under-deliver by > N MW) | NP4-442-CD, NP4-443-CD, NP4-732-CD, NP4-737-CD, NP4-751-CD, NP4-752-CD | Net-load surprise risk, especially the evening solar ramp |
| Load forecast error | Hourly | P(actual load > forecast by > N%) | NP3-565-CD, NP3-562-CD, NP6-345-CD, NP4-722-CD, GEN-55-CD | Demand-side risk |
| Congestion and basis | 5-min · daily | P(node–hub basis > $Y given constraint C) | NP6-86-CD, NP4-191-CD, NP6-788-CD, NP5-754-CD, NP7-464-CD | CRR valuation, site-level risk |
| Ancillary services and storage | 15-min · daily | P(AS capacity pays more than energy arbitrage, HE n) | NP4-188-CD, NP6-331-CD, NP6-329-CD, NP4-212-CD, NP6-328-CD, NP4-765-ER | How a battery splits capacity between energy and AS |
| Outages and adequacy | Hourly · daily | P(reserve margin below threshold at tomorrow's peak) | NP3-233-CD, NP1-346-ER, NP3-162-CD, NP6-915-CD, NP5-108-CD | Next-day alert level |
| Supply stack and bid behavior | 2-day · 60-day | How steep is the stack near expected load? (training only) | NP3-907-EX, NP3-908-ER, NP3-909-ER, NP3-965-ER, NP3-966-ER | Feature engineering and honest backtests |
| Guardrails and data hygiene | As posted | Is this label safe to train or score on? | NP4-196-M, NP4-197-M, NP4-791-CD, NP4-790-CD | Router policy, not trades |

## Routing policy

| Jev probability | Route | What happens | Acts on its own? |
|---|---|---|---|
| ≥ 0.80 | Alert + paper trade | Slack alert with its drivers; entry in the D1 paper ledger | Paper only. Real orders always go through a person. |
| 0.50 – 0.80 | Human review | Queued with probability, features and source reports | No |
| < 0.50 | Log | Stored with its outcome for calibration scoring | No |
| Stale data | Abstain | Check doesn't run if an input is older than its cadence; gap is flagged | n/a |

## Phased build

0. **Foundation (deployed):** Worker, B2C token cached in KV, generic report proxy, NP3-907-EX demand-curve page.
1. **Ingest the real-time core:** cron + Queue for hub/zone SPPs, SCED lambda, demand, price adders, wind and solar actual vs forecast. Raw to R2, rows to D1, latest to KV.
2. **Feature store and labels:** D1 views for DART, forecast errors, reserve proxy, constraint recurrence; backfill history.
3. **Jev checks:** typed check schemas (inputs, horizon, threshold, outcome rule) calling jev-gateway; DART first because labels arrive daily.
4. **Router, ledger and scoring:** confidence bands, abstain rule, Slack alerts, paper ledger, Brier score and reliability per check.
5. **Decision dashboard:** live signals, review queue, calibration charts.
6. **Execution path decision:** QSE partner, futures broker, or storage partner; human approval on any real order.
7. **Reuse:** expose checks as MCP tools for Organized Router and other agents.

*Report list pulled live from the ERCOT Public API on 25 Sept 2026. Market-access notes are general and not financial or legal advice.*
