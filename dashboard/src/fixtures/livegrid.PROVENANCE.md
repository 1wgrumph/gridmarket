# Live grid history fixture provenance (XR-B, DEC-GM-152)

Rows of `GET /v1/signals/history` for the report/subject keys the backend actually stores
(test-rule 4 and 7). Built from real Worker responses through the backend's own parsers
(`ercot.parse_snapshot`, `ercot.parse_report`) and read back with `ercot.signals.history`,
the function the history route returns.

- Sources (real Worker responses, committed under `backend/tests/fixtures/ercot/captured/`):
  - `snapshot.json` (`/api/snapshot`, retrieved 2026-09-27T03:55:18Z),
    sha256 `672dd4a6ea74fd8c918b76f51e867ef5e27f5fd1282167576f6c04f681b5e0ca`
  - `NP4-190-CD__q4__p1.json` (NP4-190-CD `settlementPoint=HB_HUBAVG`, retrieved 2026-09-27T03:55:50Z),
    sha256 `0f4158440b9c6556e4dba707c5b3e538d5f33f31aed0375fdb9c484c31f6cde0`
- Keys: `SNAPSHOT-HUBS` × `HB_HOUSTON|HB_NORTH|HB_SOUTH|HB_WEST`, `SNAPSHOT-SCED:lambda`,
  `SNAPSHOT-DEMAND:ERCOT`, `NP4-190-CD:HB_HUBAVG` (a `PRICE_POINTS` subject the poll stores).
- Transformation:
  - Hubs and lambda: one stored snapshot per 5-minute step of the captured hub `series` and
    `sced.lambdaSeries` (12 values), `asOf` stepped back 5 minutes per value from the captured `asOf`.
  - Demand: one stored snapshot per hour of the captured `demand.series` (16 hourly values,
    the last equal to `demand.mw`), `asOf` stepped back one hour per value.
  - NP4-190-CD: the captured page parsed verbatim.
  - History window: captured `asOf` − 24 h to `asOf` + 1 min. `stale` set to `false` (freshness is
    relative to the generation clock, not the capture). Values are unchanged.
- File sha256: `786036e89c38e9038243924f30eb4ac76115d5c9f27f73e8ef13a4d4cd02f8d0`
