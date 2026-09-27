# ercot-hackathon

Cloudflare Worker that reads the ERCOT Public Data API and serves two live 3D views of the Texas grid.

Live: https://ercot-hackathon.jordan-691.workers.dev

| Path | What it is |
|---|---|
| `/` | 2-Day Aggregate Energy Demand Curves (NP3-907-EX) chart |
| `/diagram/` | Grid District: weather → renewables → dispatch → prices → decision engine → router |
| `/planet/` | Grid Planet: the same data as a small cel-shaded planet |
| `/godseye/` | God's Eye ERCOT: CesiumJS globe over Texas with 1,023 EIA-860 power plants (resource silhouettes, legend filters, search) and a drill-down per plant with units, grid connection and live settlement-point prices. Also hub prices and weather zones. Visual language from [God's Eye View](https://github.com/bilawalsidhu/gods-eye-view) (MIT) |
| `/api/snapshot` | One cached call: demand, hub SPPs, DAM + DART, SCED lambda + headroom, wind, solar, weather, baseline checks |
| `/godseye/#start` | Start here: replays the real 26 Aug 2026 day and stops on the Houston $780.46/MWh spike (10:15–10:30 PM) |
| `/api/help` | Help the grid: per-zone load now and upcoming help windows for Houston, North, South and West, scored from ERCOT load forecast, wind and solar forecasts and day-ahead prices; inputs that are missing are reported as unavailable (cached 15 min) |
| `/data/aug26.json` | The 26 Aug 2026 replay day from the ERCOT Public API: 15-minute hub and load-zone prices, demand, SCED lambda and online capacity, hourly day-ahead prices, wind, solar, load by weather zone and temperatures |
| `/api/node?sp=<settlement point>` | Latest real-time SPP, recent intervals and day-ahead price at up to 4 ERCOT settlement points (cached 5 min) |
| `/data/tx_plants.json` | Texas power plants built from EIA-860 2025 early release: plant, generator, wind, solar and storage files |
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
wrangler deploy
```

## Docs

- `docs/ercot-jev-map.html`: ERCOT × Jev decision map. Which ERCOT reports feed which calibrated checks, the routing policy, and the phased build.

## God's Eye layers

- **Power plants**: 1,023 operable Texas plants from EIA-860 (643 ERCOT plants of 10 MW and up shown by default).
- **Help the grid**: rings on each zone sized and coloured by the current help score, with the next help window.
- **Home batteries (simulated)**: 1,000 simulated home batteries (13.5 kWh, 5 kW) from two simulated providers, Base Sim and LoneStar Storage. They discharge in a zone's help window or above $150/MWh, charge 10 AM–4 PM when prices are low, and keep a 20% backup reserve. Batteries and money are simulated; prices and windows are real ERCOT data.
- **26 Aug replay**: toggle LIVE / 26 AUG, scrub the timeline, and read the "why" for each moment.
