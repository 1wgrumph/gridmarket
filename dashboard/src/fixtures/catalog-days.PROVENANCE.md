# Catalog replay days fixture provenance (X2b)

Authoritative fixture captured from the local backend running with merged ERCOT operating days (lane-replay-days / DEC-GM-142).
Rule R1 / test-rule 7: response of GET /v1/replay/days captured verbatim.

- Source: local backend `gridmarket_server.main:app` running GET /v1/replay/days
- Retrieval: 2026-09-26T21:29:48Z
- Request: `GET /v1/replay/days`
- Days included: 2026-07-20, 2026-08-17, 2026-08-23, 2026-08-24, 2026-08-26, 2026-08-31
- Transformation: None (verbatim json response formatted with 2-space indentation)
- File sha256: `7812d150ddba5e477e5edc9e9ad2c0a3d3c13ca19fcb042ec3bd04be68a45227`
