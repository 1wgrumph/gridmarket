# ercot-hackathon

Cloudflare Worker that reads the ERCOT Public Data API and serves two live 3D views of the Texas grid.

Live: https://ercot-hackathon.jordan-691.workers.dev

| Path | What it is |
|---|---|
| `/` | 2-Day Aggregate Energy Demand Curves (NP3-907-EX) chart |
| `/diagram/` | Grid District: weather → renewables → dispatch → prices → decision engine → router |
| `/planet/` | Grid Planet: the same data as a small cel-shaded planet |
| `/godseye/` | God's Eye ERCOT: CesiumJS globe over Texas with live hub prices, weather zones, renewables and flows. Visual language from [God's Eye View](https://github.com/bilawalsidhu/gods-eye-view) (MIT) |
| `/api/snapshot` | One cached call: demand, hub SPPs, DAM + DART, SCED lambda + headroom, wind, solar, weather, baseline checks |
| `/api/edc` | NP3-907-EX proxy |
| `/api/products` | All ERCOT EMIL products |
| `/api/report/<emil-id>/<report>` | Generic proxy for any report |
| `/api/health` | Which secrets are set, whether a token is cached |

## How it works

- Auth: ERCOT Azure B2C password grant → ID token cached in KV for 55 minutes (tokens last 60 and can't be refreshed), plus the `Ocp-Apim-Subscription-Key` header.
- Snapshot calls run in sequence with backoff on 429, then cache in KV for 5 minutes.
- Decision checks in `src/snapshot.js` are simple baseline rules that return probabilities in the same shape a Jev decision engine will. They route to log (< 0.50), review (0.50–0.80) or alert (≥ 0.80). Paper only, no order entry.

## Setup

```bash
cd ercot-hackathon
wrangler kv namespace create ercot-hackathon-cache   # put the id in wrangler.jsonc
wrangler secret put ERCOT_USERNAME          # API Explorer sign-in email
wrangler secret put ERCOT_PASSWORD
wrangler secret put ERCOT_SUBSCRIPTION_KEY  # Primary key from apiexplorer.ercot.com profile
wrangler secret put MARKET_KEY              # Shared key clients send as x-gridmarket-key
wrangler deploy
```
