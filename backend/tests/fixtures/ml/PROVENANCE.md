# ML fixture provenance (rule 7; DEC-GM-147 RP-C)

Consumers: `backend/tests/test_ml.py`, `backend/gridmarket_server/ml_data.py`.
Status line in `docs/ml-report.md` stays FIXTURE-ONLY; nothing here is a live
model-skill claim.

## wac.csv.gz / rac.csv.gz — SYNTHETIC (real column shape)

- Fixture sha256: `1ece4cf6…92879d00` (wac), `4224f999…f04df71f070b9` (rac).
- Shape matches the real Census LODES columns (`w_geocode,C000,CA01` /
  `h_geocode,C000,CA01`); values are hand-picked to exercise
  `zone_population_weight` (expected LZ_HOUSTON 64, LZ_NORTH 20, LZ_SOUTH -15).
- Spot-check 2026-09-27 against LODES8 2022 Texas vintage:
  `https://lehd.ces.census.gov/data/lodes/LODES8/tx/wac/tx_wac_S000_JT00_2022.csv.gz`
  (sha256 `870509e9…36db24c0d19`) and
  `.../tx/rac/tx_rac_S000_JT00_2022.csv.gz`
  (sha256 `8386fd38…4b5338e33`).
  Only block `481130001001001` exists in the real files; the other fixture
  blocks (including county `48999`, which is not a real Texas county code)
  are invented. The `48999…999` row proves unknown counties are ignored.
- What would replace it: real per-county excerpts cut from the LODES files
  above (same columns, `createdate`-stamped vintage recorded).

## report.json — SYNTHETIC (transport/budget contract example only)

- Fixture sha256: `2643db87…513502f2d`. Content `{"fields":["example"],
  "data":[[1]],"_meta":{"size":1}}` is invented and is served for all five
  allowlisted Worker routes by `test_seit_gm_ml_01_ercot_budget`, which proves
  only allowlisting and the 5-requests/min budget in `ml_data.fetch_report`.
- It does not qualify any ERCOT report parser. Real route shapes live in
  `../ercot/` and `../ercot_history/PROVENANCE.json` (spec-derived).
- What would replace it: owner-run Worker captures per route (see the
  "Live run" section of `docs/ml-report.md`); one shared body can never be a
  real capture for five different schemas.

## rows.json / hour.json / county_zone.csv — SYNTHETIC (pipeline check)

- Fixture sha256: rows `790a9e42…2eb7660d`, hour `87848d91…50aace3c8b8dbc8`,
  county_zone `3e98434d…53843b1b9`.
- Hand-built training rows where the target equals temperature exactly, so the
  near-perfect fixture Spearman is a pipeline check, not a skill claim.
- What would replace it: rows built by `ml_data.build_features` from live
  Worker fetches plus real LODES weights (owner step, `docs/ml-report.md`).
