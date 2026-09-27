# Replay dashboard fixture provenance (S72; supersedes the S71 note)

Captured from the running S69b backend on this lane (DEC-GM-127).
Rule R1 / test-rule 7: replay runs are our own backend's bytes, captured
verbatim, then trimmed only as listed below (values untouched).

- Source: local backend `uvicorn gridmarket_server.main:app` on 127.0.0.1:18321
  with the committed `2026-08-26` dataset
  (`backend/gridmarket_server/data/replay/2026-08-26`,
  dataset digest `a3c14a6...`, availability_mode `assumed`).
- Retrieval: 2026-09-26T23:42Z.
- Requests: `GET /v1/replay/days`; `POST /v1/replay` with 1,000 assets
  (`home-0`..`home-999`, provider `sim`, 13.5 kWh / 6.75 SoC / 5.4 reserve /
  5 kW / eta 0.9), zone `LZ_HOUSTON`, constant 0.8 kW load, seed 0,
  strategies `fixed_schedule`, `price_based`, `esr_informed`; baseline with
  no disruptions, scenario with one `provider_offline` window for `sim`
  2026-08-27T00:00:00Z–2026-08-27T01:00:00Z (7–8 PM CT, inside the
  DAM-selected procurement window 19:00–23:00 CT); `homeValue` is a
  1-asset Battery-aware run at 40% reserve for the slider's day value.
- Trims: decision `inputs` emptied outside quarters 0, 1, 76, 79 (key kept);
  `scoreboard[].assets` per-asset rows dropped (fleet totals kept);
  `homeValue` keeps scoreboard/binding only (no timeline trace).
- Observed scoreboards: baseline net fixed +193426c, price +197502c,
  esr +81252c, 0 failed each; scenario net fixed +147598c,
  price +152520c, esr +83943c, 1000 failed each (outage overlaps accepted
  delivery); homeValue net +81c, cash +88c.
- File sha256 (trimmed): `b37333572104715939a2149bcecb93a72998d21f9e9e6e4fde7abd2283ecce30`.
