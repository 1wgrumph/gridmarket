# Synthetic replay fixtures

These files are constructed test values for C3 engine tests. They are not ERCOT
captures, not parser-qualification evidence, and not external observations.
S67 owns real-shape parser cases against captured bytes.

`claims_external_observation` is false. `quality` and `label` are `synthetic`.

## Layout

`GRIDMARKET_REPLAY_DIR/<YYYY-MM-DD>/`

- `manifest.json` — day, timezone `America/Chicago`, quarter count, label, gaps
- `observations.json` — array of observation objects

## Observation fields

`series` (`rt_spp`, `dam_spp`, `load`, `esr_charging`), `source`, `value`
(decimal string), `unit`, `interval_start`, `interval_end`, `published_at`,
`available_at`, `retrieval_time`, `quality`, `zone`, `settlement_point`,
`provenance.label`, `provenance.claims_external_observation`.

Times are UTC with a `Z` suffix. Intervals are half-open. A local calendar day
is every 15-minute UTC step from that America/Chicago midnight to the next
(92, 96, or 100 quarters). Both fall-back hours are distinct UTC intervals.
Prices are copied across LZ_HOUSTON, LZ_NORTH, LZ_SOUTH, LZ_WEST, HB_HOUSTON,
HB_NORTH, HB_SOUTH, and HB_WEST. Load is hourly, zone `ERCOT`, unit MW.
`esr_charging` is optional; a missing series is a gap named `esr`.

Settlement uses each interval's RT SPP even when the agent could not see it yet.
DAM `available_at` is 13:30 America/Chicago on D−1.
