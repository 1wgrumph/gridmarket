# Texas plant corpus provenance (rule 7; DEC-GM-147 RP-C)

## tx_plants.json — SOURCED (EIA Form EIA-860)

- Fixture sha256: `62c025f2a1e07f2cdac8c00ca8c811c4556a15754814457867469d80153ddd5d`
  (1,023 plants). Consumers: `ercot-hackathon/test/node.test.mjs`,
  `ercot-hackathon/test/godseye.test.mjs`, `ercot-hackathon/scripts/build-sp-allowlist.mjs`.
- Declared source: U.S. EIA Form EIA-860, 2025 early release
  (`https://www.eia.gov/electricity/data/eia860/xls/eia8602025ER.zip`).
  That URL is superseded: since the final 2025 release (published
  2026-09-10) it redirects to the EIA electricity landing page (verified
  2026-09-27). Retrievable successor:
  `https://www.eia.gov/electricity/data/eia860/xls/eia8602025.zip`,
  retrieved 2026-09-27 ~02:52 UTC, 23,622,347 bytes,
  sha256 `2b27929d26cc1da9ad6a530da1cac6718cd8496098ee560c4d47cfffd96d08ba`.
- Transformation (from the corpus `meta`): operable generators only; plants
  under 1 MW omitted; per-plant ERCOT settlement point taken from the
  EIA-860 "RTO/ISO LMP Node Designation" where it matches an ERCOT
  settlement point, else matched by ERCOT naming convention (marked
  name-matched). Input workbooks in the zip: `2___Plant_Y2025.xlsx`,
  `3_1_Generator_Y2025.xlsx`, `3_2_Wind_Y2025.xlsx`, `3_3_Solar_Y2025.xlsx`,
  `3_4_Energy_Storage_Y2025.xlsx`.
- Reconciliation sample (fixture vs final-2025 Plant schedule, 2026-09-27):
  code 3470 W A Parish — Thompsons/Fort Bend 29.4828,-95.6311 TRE — match;
  code 3456 Newman — El Paso/El Paso 31.98359,-106.43178 WECC — match
  (fixture rounds to 5 decimals); code 3601 Sim Gideon —
  Bastrop/Bastrop 30.1456,-97.2708 TRE — match. 3/3 agree.
- Gap admitted: the early-release input bytes are no longer retrievable, so
  the sample is reconciled against the final release, not the exact input
  vintage. ERCOT node-name mapping was not independently source-reconciled.

## aug26.json — SOURCED (ERCOT Public API)

- Fixture sha256: `3d69318405d64c296a6aacb40fe4419dfbf6dcdb87f53d0ab98893fbf218847e`.
  Consumer: `ercot-hackathon/public/replay/` (God's Eye replay page).
- Stated source: `ERCOT Public API: NP6-905-CD, NP4-190-CD, NP6-235-CD, NP6-323-CD, NP4-732-CD, NP4-737-CD, NP4-722-CD, NP6-345-CD`.
- Contents:
  - `source`: stated as `"ERCOT Public API: NP6-905-CD, NP4-190-CD, NP6-235-CD, NP6-323-CD, NP4-732-CD, NP4-737-CD, NP4-722-CD, NP6-345-CD"`.
  - `intervals`: 96 real-time 15-minute intervals for 2026-08-26, each with timestamp `t`, prices `p` (for hubs `HB_HOUSTON`, `HB_NORTH`, `HB_SOUTH`, `HB_WEST` and load zone `LZ_HOUSTON`), and demand `d`.
  - `hours`: 24 hourly records with hour ending `he`, day-ahead price `da`, `wind`, `solar`, `load`, and `temp`.
  - `sced`: 295 SCED records with timestamp `ts`, system lambda `lam`, online HSL `hsl`, and `adder`.
  - `spike`: summary object for the peak event (`interval`: 89, `t`: "22:15", `tEnd`: "22:30", `hub`: "HB_HOUSTON", `price`: 780.46, `lz`: 780.45, `demand`: 73518, `daHE`: 23, `da`: 98.54, `lamMax`: 914.5, `hsl`: 86441, `solar19`: 16901, `solar20`: 3867, `solar21`: 25, `wind23`: 7716, `peakDemand`: 90482, `peakDemandT`: "16:30", `dayHigh`: {`hub`: "HB_WEST", `price`: 795.33, `t`: "22:00"}).
- Provenance and retrieval: the retrieval time was not recorded; the file was added in commit 80d673f by Jordan Hill. It is served as-is.

