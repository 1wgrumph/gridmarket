import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { forecastHours, helpWindows, windowText, mwText, HOUR } from "../public/godseye/help-grid.js";

// Existing NP3-565-CD corpus, with the backend's Coast -> Houston roll-up.
const report = JSON.parse(readFileSync(new URL("../../backend/tests/fixtures/ercot/np3-565-cd.json", import.meta.url)));
const coast = report.data.find(row => row[2] === "Coast");
const signal = { report_id: "NP3-565-CD", zone: "LZ_HOUSTON", interval_start: "2026-09-26T14:00:00Z", interval_minutes: 60,
  value: coast[3], unit: "MW", published_at: coast[4], fetched_at: coast[4], stale: false };
const now = Date.parse("2026-09-26T14:00:00Z");

test("S81 sparse load feed never claims a 24-hour peak or fills missing hours", () => {
  const forecast = forecastHours([signal], now);
  assert.equal(forecast.hours.length, 24);
  assert.equal(forecast.hours[23] - forecast.hours[0], 23 * HOUR);
  assert.equal(forecast.zones.LZ_HOUSTON.values[0], 1001);
  assert.equal(forecast.zones.LZ_HOUSTON.peak, null);
  assert.equal(forecast.zones.LZ_HOUSTON.values[1], null);
  assert.equal(mwText(forecast.zones.LZ_HOUSTON.values[1]), "Waiting for ERCOT");
  assert.equal(forecastHours(null, now).zones.LZ_NORTH.peak, null);
  assert.equal(forecastHours([{ ...signal, stale: true }], now).zones.LZ_HOUSTON.values[0], null);
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
