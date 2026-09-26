import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { forecastHours, historyPath, publishedText, shade, peakLabel, helpWindows, windowText, mwText, HOUR } from "../public/godseye/help-grid.js";

// Exact /v1/signals/history response from a local lane-esr backend (see the provenance file).
const history = JSON.parse(readFileSync(new URL("./fixtures/history-lz-houston.json", import.meta.url)));
const clock = Date.parse(history[0].interval_start) + 58 * 60000;
const now = Date.parse("2026-09-26T14:00:00Z");

test("S81c full 24-hour history shades against the zone's own peak and names its hour", () => {
  const forecast = forecastHours({ LZ_HOUSTON: history }, clock);
  const houston = forecast.zones.LZ_HOUSTON;
  assert.equal(forecast.hours[0], Date.parse(history[0].interval_start));
  assert.deepEqual(houston.values, history.map(row => row.value));
  assert.equal(houston.peak, Math.max(...history.map(row => row.value)));
  assert.equal(houston.peakHour, Date.parse(history[houston.values.indexOf(houston.peak)].interval_start));
  assert.equal(houston.published, "2026-09-26T17:30:00");
  assert.equal(publishedText(houston.published), "Sep 26, 5:30 PM CT");
  assert.equal(forecast.zones.LZ_NORTH.peak, null);
  assert.equal(forecast.zones.LZ_NORTH.published, null);
  assert.equal(shade(houston.peak, houston), 1);
  assert.equal(shade(houston.low, houston), 0);
  assert.equal(shade(null, houston), null);
  assert.equal(shade(houston.values[0], forecast.zones.LZ_NORTH), null);
  assert.equal(peakLabel(houston.peakHour), "Sun, 4 PM CDT");
});

test("S81c missing or stale hours never claim a 24-hour peak or fill values", () => {
  const sparse = forecastHours({ LZ_HOUSTON: history.slice(1) }, clock).zones.LZ_HOUSTON;
  assert.equal(sparse.values[0], null);
  assert.equal(sparse.peak, null);
  assert.equal(sparse.peakHour, null);
  assert.equal(mwText(sparse.values[0]), "Waiting for ERCOT");
  const stale = forecastHours({ LZ_HOUSTON: history.map((row, i) => i === 5 ? { ...row, stale: true } : row) }, clock).zones.LZ_HOUSTON;
  assert.equal(stale.values[5], null);
  assert.equal(stale.peak, null);
  // After the hour rolls over, the old first hour drops out rather than shifting.
  assert.equal(forecastHours({ LZ_HOUSTON: history }, clock + HOUR).zones.LZ_HOUSTON.peak, null);
  assert.equal(forecastHours(null, clock).zones.LZ_HOUSTON.peak, null);
  assert.equal(publishedText(null), null);
});

test("S81c history requests one 24-hour window from the current UTC hour", () => {
  const url = new URL(historyPath("LZ_HOUSTON", clock), "http://market.test");
  assert.equal(url.pathname, "/v1/signals/history");
  assert.equal(url.searchParams.get("report_id"), "NP3-565-CD");
  assert.equal(url.searchParams.get("zone"), "LZ_HOUSTON");
  assert.equal(Date.parse(url.searchParams.get("start")), Date.parse(history[0].interval_start));
  assert.equal(Date.parse(url.searchParams.get("end")) - Date.parse(url.searchParams.get("start")), 24 * HOUR);
});

test("S81 missing predictions produce no windows and labels use Central time", () => {
  assert.deepEqual(helpWindows(null, now), []);
  assert.deepEqual(helpWindows([], now), []);
  assert.equal(windowText({ zone: "LZ_HOUSTON", start: now, end: now + HOUR }), "Homes help: Houston Sep 26, 9:00 AM CDT–Sep 26, 10:00 AM CDT");
  assert.equal(mwText(null), "Waiting for ERCOT");
  assert.equal(mwText(NaN), "Waiting for ERCOT");
  assert.equal(mwText(0), "0 MW");
});

const prediction = JSON.parse(readFileSync(new URL("./fixtures/help-prediction.json", import.meta.url))).prediction;
test("S81 HIGH simulation hours merge by zone, exclude elapsed/unavailable, and keep gaps", () => {
  const start = Date.parse(prediction.delivery_hour), clock = start - 2 * HOUR;
  // Delivery-hour variations of the real scorer output; no external feed is simulated.
  const at = (offset, extra = {}) => ({ ...prediction, delivery_hour: new Date(start + offset * HOUR).toISOString(), ...extra });
  const windows = helpWindows([at(1), at(0), at(1), at(3), at(4, { level: "UNAVAILABLE" }), at(-3), at(24), at(0, { zone: "LZ_NORTH" })], clock);
  assert.deepEqual(windows, [
    { zone: "LZ_NORTH", start, end: start + HOUR },
    { zone: "LZ_HOUSTON", start, end: start + 2 * HOUR },
    { zone: "LZ_HOUSTON", start: start + 3 * HOUR, end: start + 4 * HOUR },
  ]);
  assert.deepEqual(helpWindows([at(0, { level: "MEDIUM" }), at(1, { level: "UNAVAILABLE" })], clock), []);
});
