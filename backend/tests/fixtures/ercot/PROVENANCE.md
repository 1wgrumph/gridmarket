# ERCOT fixture provenance (rule 7)

## snapshot.json

- Source: `ercot-hackathon/src/snapshot.js` `buildSnapshot()` run under node with
  spec-shaped stub inputs (`ercot-hackathon/test/snapshot-stub.mjs`).
- Regenerate: `FIXED_NOW=2026-09-26T14:00:00Z node ercot-hackathon/test/snapshot-stub.mjs`.
- Transformation: none; bytes are the producer's verbatim output for the stub inputs.
- Note: stub input *values* are synthetic; the snapshot *shape* is the real producer shape.

## np6-905-cd.json, np4-190-cd.json, np3-565-cd.json, np3-233-cd.json, np6-86-cd.json

- Source: ERCOT Public Reports API specification, `ercot/api-specs`
  `pubapi/pubapi-apim-api.json`, commit `e361e39` (2024-02-21),
  sha256 `108db99a2ba342888324307ae475b538cef449dfbb1496fa8cb8e6b935c36b4f`
  (retrieved 2026-09-26 ~20:44 UTC during sweep R1).
- Column names: each endpoint's documented filter parameters with From/To
  suffixes stripped (the spec names every filterable column this way).
  Full parameter list: sweep R1 `spec-extract.txt`.
- Label: spec-derived, synthetic values. Awaiting owner-captured real responses
  in `captured/` (see `scripts/capture_ercot.py`).
- `_meta` shape follows the spec's `ResultMetadata`
  (`totalRecords`, `pageSize`, `totalPages`, `currentPage`).

## esr-4-sec-charging-mw.json, ../esr_charging.json

- Predate rule 7; the ESR endpoint is absent from the published spec, so no
  filter vocabulary can be sourced for it. Still awaiting a captured real
  response (owner step).

## captured/ (ORC-5, DEC-GM-148)

- Source Worker URL: `https://ercot-hackathon.jordan-691.workers.dev` (retrieved without a key)
- Retrieval time UTC: 2026-09-27T03:56:02Z
- Capture tool: `scripts/capture_ercot.py --first-page-only` (pacing 2.5s, 429 retry backoff, User-Agent `gridmarket-capture/1.0`)
- What was kept: `snapshot.json` and the first page of each query for all five standard reports:
  - `NP3-233-CD__q0__p1.json`
  - `NP3-565-CD__q0__p1.json`
  - `NP4-190-CD__q0..4__p1.json` (5 queries)
  - `NP6-86-CD__q0__p1.json`
  - `NP6-905-CD__q0..4__p1.json` (5 queries)
  Each accompanied by its JSON provenance sidecar matching the body SHA-256. Total size is ~692 KB.

