# NWS fixture provenance (rule 7; DEC-GM-147 RP-C)

Live `api.weather.gov` captures from sweep R1 (retrieval window 2026-09-26
20:47–20:48 UTC, from payload stamps: alerts `updated`
2026-09-26T20:47:32Z; the exact retrieval second was not recorded — gap
admitted). Fetched with the backend's User-Agent
(`gridmarket-hackathon (github.com/1wgrumph/gridmarket)`; see
`backend/gridmarket_server/nws.py`). Fixture sha256:
point `3bafecc9…ba0ddda465`, hourly `ede6d0e7…8bab28af2503a9e`,
alerts `b62c006b…f77cc595fa82a639a4`.
Re-validated 2026-09-27 ~02:55 UTC: `GET /points/29.76,-95.37` still resolves
`forecastHourly` to `.../gridpoints/HGX/63,95/forecast/hourly`, and the live
hourly payload carries the same 7 property keys with 156 periods, confirming
the transformations below describe the real endpoint shape.

## point.json — SOURCED (transformed)

- Source: `GET /points/29.76,-95.37` (LZ_HOUSTON).
- Source sha256: `cfe4f2d40c779b622ef47af20fc12531e4548068a84f500aebf95ff68352ed7c`.
- Transformation: `https://api.weather.gov` replaced with `__BASE_URL__` so the
  offline test server receives the forecastHourly follow-up. Nothing else changed.

## hourly.json — SOURCED (transformed)

- Source: `GET /gridpoints/HGX/63,95/forecast/hourly` (LZ_HOUSTON).
- Source sha256: `7ae028b24a83870328370760069fb7a2b463b7b635a0c645eb87e0a2a689a0f4`.
- Transformation: `properties.periods` truncated to the first 8 of 156 periods.
  Period objects are verbatim (note the `-05:00` startTime offsets and the
  `updateTime` published stamp `2026-09-26T18:22:06+00:00`; there is no plain
  `updated` property).
- Parent bytes: the full 156-period source body was not retained, only its
  sha256 above. Recapture: `GET /gridpoints/HGX/63,95/forecast/hourly` and
  truncate `properties.periods` to 8 (weather content will differ; the served
  test asserts shape/routing, not values).

## alerts.json — SOURCED (verbatim)

- Source: NWS alerts capture (1 Severe flash flood warning + 4 Unknown air
  quality alerts), `updated` 2026-09-26T20:47:32Z.
- Source sha256: `b62c006b7c7b31073d984ddcfeaaa6c552c6268abf4fcff77cc595fa82a639a4`.
- Transformation: none (fixture digest matches source digest).
- Query gap admitted: the exact capture query was not recorded. Contents span
  Houston-area, Dallas-area and Pecos zones, so it was likely a Texas
  aggregate (`GET /alerts/active?area=TX`) rather than the product's per-zone
  `GET /alerts/active?point={lat},{lon}` (product zone points in `nws.py`:
  LZ_HOUSTON 29.76,-95.37; LZ_NORTH 32.78,-96.80; LZ_SOUTH 29.42,-98.49;
  LZ_WEST 31.99,-102.08). Recapture with either query; re-record the query
  alongside the new digest. Note: alert properties carry
  `sent`/`effective`/`expires` but no `updated`; the collection has a
  top-level `updated`.
