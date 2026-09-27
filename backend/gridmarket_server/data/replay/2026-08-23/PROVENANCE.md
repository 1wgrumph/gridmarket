# ERCOT replay provenance: 2026-08-23

2026-08-23 has complete required data and the second largest HB_HOUSTON evening (17:00-21:00 Central) maximum minus daily minimum among August 2026 days inspected: 383.21 - 20.40 = 362.81/MWh, with peak RT price 562.40/MWh. This is a price-spread selection, not a declaration of an ERCOT scarcity event.

Historical ERCOT observations; simulated households, batteries, procurement and outcomes.
All required series are settlement/display-only: original publication/availability and revision history are unknown.
`published_at` identifies the captured archive version; it is never backdated to the operating interval.

## Captured sources

### da_prices (NP4-180-ER)
- URL: https://www.ercot.com/misdownload/servlets/mirDownload?doclookupId=1276779821
- Retrieved UTC: 2026-09-26T20:55:24.717132+00:00; HTTP 200
- Raw SHA-256: `c80ed1850974f739227f94013db18a9b16baed8053d8364fe5a179d284ad84f7`
- Original filename: `rpt.00013060.0000000000000000.20260920.080303414.DAMLZHBSPP_2026.zip`
- Member: `rpt.00013060.0000000000000000.DAMLZHBSPP_2026.xlsx`; sheet: `Aug` (`xl/worksheets/Sheet8.xml`)
- Archive publication: 2026-09-20T13:03:03Z; correction version: unknown; pinned captured archive version
- Pinned schema SHA-256: `e802ce97a8fb8233aac85619177616b3224e98fa10fa4b1d8601c0b6e44b4322`

### load (Hourly Load Data Archives)
- URL: https://www.ercot.com/files/docs/2026/02/10/Native_Load_2026.zip
- Retrieved UTC: 2026-09-26T20:55:12.547230+00:00; HTTP 200
- Raw SHA-256: `f93f640f9c8bc527728b625afbf1ab0f402cd73cd7608c605c67b6aa3b16d01c`
- Original filename: `Native_Load_2026.zip`
- Member: `Native_Load_2026.xlsx`; sheet: `Native Load Report` (`xl/worksheets/sheet1.xml`)
- Archive publication: None; correction version: unknown; pinned captured archive version
- Pinned schema SHA-256: `a3772ff7047b5e872220d21a6c676c1fb9b0620f6f9ed30c62aa1731f0123b43`

### rt_prices (NP6-785-ER)
- URL: https://www.ercot.com/misdownload/servlets/mirDownload?doclookupId=1276781176
- Retrieved UTC: 2026-09-26T20:55:26.288768+00:00; HTTP 200
- Raw SHA-256: `30a1ecb886a3b28d78c6dd178f399e01b795816c76e929b3c792c2797b992886`
- Original filename: `rpt.00013061.0000000000000000.20260920.080732945.RTMLZHBSPP_2026.zip`
- Member: `rpt.00013061.0000000000000000.RTMLZHBSPP_2026.xlsx`; sheet: `Aug` (`xl/worksheets/Sheet8.xml`)
- Archive publication: 2026-09-20T13:07:30Z; correction version: unknown; pinned captured archive version
- Pinned schema SHA-256: `6a859c732e4dfea6e8e8bc25519637ca99688b1185b104779af3179f6a9b0c1c`

## Transformation

`python3 scripts/replay_data/build.py --raw-dir RAW_DIR --output OUTPUT_DIR`

Script SHA-256: `a35f7aee9dfe4b673370e6f99c2739b8a19ae3b098e55fd1994fee08cd6094a5`.
Parse the actual ZIP/XLSX shared-string and worksheet bytes; select D and the eight named points, retaining HU/LZ and excluding LZEW.
Convert hour-ending/quarter labels to UTC. Keep hourly load at hourly resolution. No filling, interpolation or price clipping.
Canonical JSON is sorted by UTC start and point; numeric source values are converted to JSON numbers without price rounding.
Normalized output hashes are in meta.json; meta.json SHA-256: `b3763132e55b6c24d5ac9e31a215fe9d54986112c436bf9557c0f177517ab9ce`.

## Reproduction and fixture provenance

Run the same command with RAW_DIR=backend/tests/fixtures/replay_raw for a byte-identical complete rebuild.
Create those excerpts from the downloaded parents with `--excerpt-dir backend/tests/fixtures/replay_raw`.
excerpts.json records parent/output hashes and original uncompressed XML row byte ranges. Retained row bytes and all shared strings are unchanged; ZIP envelopes are repacked.
Tests use explicitly labelled mutations of these captured parents for malformed, empty and error-envelope inputs.

## Optional gaps

- ESR_DAY_NOT_CAPTURED: Captured dashboard covers only 2026-09-25 and 2026-09-26, not D; no verified historical aggregate power series captured. Source: https://www.ercot.com/api/1/services/read/dashboards/energy-storage-resources.json
- SCED_NOT_YET_PUBLISHED: D is 34 days before retrieval, inside the 60-day disclosure delay. No D-specific SCED schema or SoC captured; no stored energy inferred from MW. Source: https://www.ercot.com/misapp/servlets/IceDocListJsonWS?reportTypeId=13052
