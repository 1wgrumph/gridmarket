# NWS fixture provenance (rule 7)

Live `api.weather.gov` captures from sweep R1 (2026-09-26 ~20:47 UTC), fetched
with the backend's User-Agent (`gridmarket-hackathon ...`).

## point.json

- Source: `GET /points/29.76,-95.37` (LZ_HOUSTON).
- Source sha256: `cfe4f2d40c779b622ef47af20fc12531e4548068a84f500aebf95ff68352ed7c`.
- Transformation: `https://api.weather.gov` replaced with `__BASE_URL__` so the
  offline test server receives the forecastHourly follow-up. Nothing else changed.

## hourly.json

- Source: `GET /gridpoints/HGX/63,95/forecast/hourly` (LZ_HOUSTON).
- Source sha256: `7ae028b24a83870328370760069fb7a2b463b7b635a0c645eb87e0a2a689a0f4`.
- Transformation: `properties.periods` truncated to the first 8 of 156 periods.
  Period objects are verbatim (note the `-05:00` startTime offsets and the
  `updateTime` published stamp; there is no plain `updated` property).

## alerts.json

- Source: `GET /alerts/active?point=` Texas aggregate capture (1 Severe flash
  flood warning + 4 Unknown air quality alerts).
- Source sha256: `b62c006b7c7b31073d984ddcfeaaa6c552c6268abf4fcff77cc595fa82a639a4`.
- Transformation: none. Note: alert properties carry `sent`/`effective`/`expires`
  but no `updated`; the collection has a top-level `updated`.
