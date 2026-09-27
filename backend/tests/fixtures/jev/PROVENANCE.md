# Jev adapter fixture provenance (rule 7; DEC-GM-147 RP-C)

## `{"probability": 0.73}` in `backend/tests/test_jev.py` — SYNTHETIC

- The stub HTTP reply body `{"probability": 0.73}` (test_jev.py `respond`)
  is a handwritten contract example, not a capture of the external Jev
  endpoint. No real-response capture or authoritative published schema exists
  in this repository; no live call was made.
- What it proves: the adapter contract in `backend/gridmarket_server/jev.py`
  — POST the check JSON with `Authorization: Bearer <key>`, accept a numeric
  `probability` in [0, 1] (rejecting bools/out-of-range), 6-calls/min budget,
  error/timeout → `None`, never stalling `/v1/market`.
- What would replace it: a real endpoint response capture (request shape,
  response bytes, source URL, retrieval UTC, sha256) or the vendor's
  published response schema pinned by URL and digest.
