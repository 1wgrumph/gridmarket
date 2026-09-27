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
