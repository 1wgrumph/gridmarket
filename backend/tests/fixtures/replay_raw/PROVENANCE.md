# Captured ERCOT replay excerpts

These are real XML byte cuts from the captured public ZIP/XLSX files, repacked without regenerating cells. Full downloads remain outside the repository. `excerpts.json` records parent hashes, excerpt hashes, and retained row offsets in the original uncompressed worksheet members. All workbook metadata and shared-string tables are preserved.

Recreate from the captured parent files:

```sh
python3 scripts/replay_data/build.py --raw-dir RAW_DIR --output OUTPUT_DIR --excerpt-dir backend/tests/fixtures/replay_raw
```

The complete transport/publication/schema manifest is [sources.json](../../../../scripts/replay_data/sources.json). The generated dataset records the transformation script digest.

## da_prices

- URL: https://www.ercot.com/misdownload/servlets/mirDownload?doclookupId=1276779821
- Report: NP4-180-ER
- Retrieval UTC: 2026-09-26T20:55:24.717132+00:00
- Parent SHA-256: `c80ed1850974f739227f94013db18a9b16baed8053d8364fe5a179d284ad84f7`
- Original filename: `rpt.00013060.0000000000000000.20260920.080303414.DAMLZHBSPP_2026.zip`
- Member/sheet: `rpt.00013060.0000000000000000.DAMLZHBSPP_2026.xlsx` / `Aug`

## load

- URL: https://www.ercot.com/files/docs/2026/02/10/Native_Load_2026.zip
- Report: Hourly Load Data Archives
- Retrieval UTC: 2026-09-26T20:55:12.547230+00:00
- Parent SHA-256: `f93f640f9c8bc527728b625afbf1ab0f402cd73cd7608c605c67b6aa3b16d01c`
- Original filename: `Native_Load_2026.zip`
- Member/sheet: `Native_Load_2026.xlsx` / `Native Load Report`

## rt_prices

- URL: https://www.ercot.com/misdownload/servlets/mirDownload?doclookupId=1276781176
- Report: NP6-785-ER
- Retrieval UTC: 2026-09-26T20:55:26.288768+00:00
- Parent SHA-256: `30a1ecb886a3b28d78c6dd178f399e01b795816c76e929b3c792c2797b992886`
- Original filename: `rpt.00013061.0000000000000000.20260920.080732945.RTMLZHBSPP_2026.zip`
- Member/sheet: `rpt.00013061.0000000000000000.RTMLZHBSPP_2026.xlsx` / `Aug`

Negative-test mutations in test_replay_data.py truncate these parents, remove source rows, duplicate normalized captured rows, or replace content with a labelled synthetic error envelope. They are not observations of ERCOT failures.
