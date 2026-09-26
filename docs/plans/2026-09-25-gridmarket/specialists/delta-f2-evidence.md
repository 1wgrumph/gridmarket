# Delta F2 evidence — ERCOT report slugs

Planning review finding F2 (candidate `4defcb4`) asked for the exact ERCOT
Public API report slugs behind three Worker report routes. The slugs come from
the ERCOT product catalog that Jordan's deployed Worker returns, not from memory.

## Calls

Three keyless GET requests, 2026-09-26T02:39Z (2026-09-25 21:39 CDT), no
`fresh` parameter, no other ERCOT traffic in this delta:

| Request | HTTP | Bytes |
|---|---|---|
| `GET https://ercot-hackathon.jordan-691.workers.dev/api/report/np3-565-cd` | 200 | 1786 |
| `GET https://ercot-hackathon.jordan-691.workers.dev/api/report/np3-233-cd` | 200 | 2715 |
| `GET https://ercot-hackathon.jordan-691.workers.dev/api/report/np6-86-cd` | 200 | 2301 |

Each response is ERCOT's product record for that EMIL ID; its
`artifacts[0]._links.endpoint.href` names the report endpoint.

| EMIL ID | Product name (ERCOT) | `artifacts[0]._links.endpoint.href` | Worker route |
|---|---|---|---|
| NP3-565-CD | Seven-Day Load Forecast by Model and Weather Zone | `https://api.ercot.com/api/public-reports/np3-565-cd/lf_by_model_weather_zone` | `/api/report/np3-565-cd/lf_by_model_weather_zone` |
| NP3-233-CD | Hourly Resource Outage Capacity | `https://api.ercot.com/api/public-reports/np3-233-cd/hourly_res_outage_cap` | `/api/report/np3-233-cd/hourly_res_outage_cap` |
| NP6-86-CD | SCED Shadow Prices and Binding Transmission Constraints | `https://api.ercot.com/api/public-reports/np6-86-cd/shdw_prices_bnd_trns_const` | `/api/report/np6-86-cd/shdw_prices_bnd_trns_const` |

Each product has exactly one artifact. Status `Active`, audience `Public`
for all three.

## Resulting report allowlist (DES-GM-ERCOT, CONTRACT-GM-WORKER)

1. `/api/report/np6-905-cd/spp_node_zone_hub` (unchanged from candidate; not re-fetched)
2. `/api/report/np4-190-cd/dam_stlmnt_pnt_prices` (unchanged from candidate; not re-fetched)
3. `/api/report/np3-565-cd/lf_by_model_weather_zone`
4. `/api/report/np3-233-cd/hourly_res_outage_cap`
5. `/api/report/np6-86-cd/shdw_prices_bnd_trns_const`

Field names are not established here; PROC-ERCOT-LIVE-CHECK confirms them with
one live call per route during phase 1 assembly (RISK-GM-09).
