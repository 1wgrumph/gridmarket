# Replay dashboard fixture provenance (S71)

Captured from the running S69 backend on this lane (no S69b yet).
Rule R1 / test-rule 7: replay runs are our own backend's bytes, captured
verbatim, then trimmed only by dropping repeated `dam_hour_*` decision
inputs outside quarters 0, 68 and 72 (values untouched).

- Source: local backend `uvicorn gridmarket_server.main:app` on 127.0.0.1:18311
  with the committed `2026-08-26` dataset
  (`backend/gridmarket_server/data/replay/2026-08-26`,
  dataset digest `a3c14a6...`, availability_mode `assumed`).
- Retrieval: 2026-09-26T17:47Z.
- Requests: `GET /v1/replay/days`; `POST /v1/replay` with 1 asset
  (`home-0`, provider `sim`, 13.5 kWh / 6.75 SoC / 5.4 reserve / 5 kW / eta 0.9),
  zone `LZ_HOUSTON`, constant 0.8 kW load, seed 0, strategies
  `fixed_schedule`, `price_based`, `esr_informed`; baseline with no
  disruptions, scenario with one `provider_offline` window for `sim`
  2026-08-26T23:00:00Z–2026-08-27T00:00:00Z (6–7 PM CT, inside the
  17:00–21:00 CT procurement window).
- Observed scoreboards: baseline net +105c / 0 failed per strategy;
  scenario net +83c / 1 failed per strategy.
- File sha256 (trimmed): `669437d4b0705a40c66096cf72a23783b4f9121b94375ff0a92c96094e23ee91`.

Regenerate after S69b lands (fleet timeline, procurement hours,
self_supply) and update this note.
