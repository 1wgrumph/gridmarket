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

## esr-4-sec-charging-mw.json, ../esr_charging.json — SYNTHETIC (legacy, owner capture pending; G2)

- Fixture sha256: `fce1aeb6…4a1ae90b60` (`ercot/esr-4-sec-charging-mw.json`),
  `078ba1b1…b809fd2121c38c72` (`esr_charging.json`). Worker-side mirror
  `ercot-hackathon/test/fixtures/esr.json`
  (`06934dd8…b99863bdbb6f5e6533d`, see its `esr.provenance.json` sidecar).
- Predate rule 7; the ESR endpoint is absent from the published spec, so no
  filter vocabulary can be sourced for it. Shapes are invented/legacy and
  qualify only the adapter contract (route wiring, credential headers, 300 s
  cache, latest-row parsing), never the external format.
- What would replace them: an owner market-key capture of the upstream
  response (bytes, retrieval UTC, sha256) via `scripts/capture_ercot.py`.
