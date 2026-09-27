import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { forecastHours, pastHours, historyPath, actualPath, scrubHours, hourKind, hourOffset, publishedText, shade, peakLabel, helpWindows, windowText, mwText, hourText, noData, HOUR, PAST_HOURS, SCRUB_HOURS, NOW_INDEX, HUB_REPORT, DEMAND_REPORT, HUB_FOR_ZONE, ACTUAL_HUBS } from "../public/godseye/help-grid.js";

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

// X4: past-24h actuals in the exact S81b history shape (see the provenance file).
// Values are synthetic: lane-esr 2bd168a 422s SNAPSHOT history over HTTP, so no
// real 24-hour capture exists; every row is stale:true exactly as the backend serves
// past intervals (_data_age counts the interval itself).
const actuals = JSON.parse(readFileSync(new URL("./fixtures/history-snapshot-hb-north.json", import.meta.url)));
const pastClock = Date.parse("2026-09-26T22:58:59Z"); // S81c capture time; past window [Sep 25 22:00Z, Sep 26 22:00Z)

test("X4 past hours take the latest published value per hour and ignore the backend stale flag", () => {
  const past = pastHours({ HB_NORTH: actuals }, pastClock, "$/MWh");
  const north = past.zones.HB_NORTH;
  assert.equal(past.hours.length, PAST_HOURS);
  assert.equal(past.hours[0], Date.parse("2026-09-25T22:00:00Z"));
  assert.equal(past.hours[23] + HOUR, Date.parse("2026-09-26T22:00:00Z"));
  const latest = actuals.filter((_, i) => i % 12 === 11);
  assert.deepEqual(north.values, latest.map(row => row.value));
  assert.deepEqual(north.publishedByHour, latest.map(row => row.published_at));
  assert.equal(north.values[0], 26.1);
  assert.equal(north.peak, 38.59);
  assert.equal(north.low, 26.1);
  assert.equal(north.peakHour, past.hours[north.values.indexOf(north.peak)]);
  assert.equal(north.published, "2026-09-26T21:55:00+00:00");
  assert.equal(publishedText(north.published), "Sep 26, 4:55 PM CDT");
  assert.equal(shade(north.peak, north), 1);
  assert.equal(shade(north.low, north), 0);
  assert.equal(shade(null, north), null);
  // A fresh flag changes nothing: past hours show published values.
  const fresh = pastHours({ HB_NORTH: actuals.map(row => ({ ...row, stale: false })) }, pastClock, "$/MWh").zones.HB_NORTH;
  assert.deepEqual(fresh.values, north.values);
});

test("X4 past hours exclude unpublished, unit-mismatched and non-finite rows; partial feed blocks the range", () => {
  const h22 = actuals.filter((_, i) => Math.floor(i / 12) === 22);
  const h23 = actuals.filter((_, i) => Math.floor(i / 12) === 23);
  const north = pastHours({ HB_NORTH: [
    ...h22,
    ...h23.slice(0, 8),
    { ...h23[8], published_at: null },
    { ...h23[9], published_at: "" },
    { ...h23[10], value: NaN },
    { ...h23[11], unit: "MW" },
  ] }, pastClock, "$/MWh").zones.HB_NORTH;
  assert.equal(north.values[22], h22[11].value);
  assert.equal(north.values[23], h23[7].value); // latest surviving published row wins
  assert.equal(north.values[0], null);
  assert.equal(north.peak, null);
  assert.equal(north.peakHour, null);
  assert.equal(shade(north.values[22], north), null);
  // Negative prices are real; negative loads are not.
  assert.equal(pastHours({ HB_NORTH: [{ ...actuals[11], value: -4.5 }] }, pastClock, "$/MWh").zones.HB_NORTH.values[0], -4.5);
  assert.equal(pastHours({ ERCOT: [{ ...actuals[11], unit: "MW", value: -1 }] }, pastClock, "MW").zones.ERCOT.values[0], null);
  // Rows outside the past window never leak in (real row from the current hour).
  const outside = pastHours({ HB_NORTH: [{ interval_start: "2026-09-26T22:37:59.273Z", interval_end: "2026-09-26T22:42:59.273+00:00", value: 28.16, unit: "$/MWh", published_at: "2026-09-26T22:37:59.273Z", stale: true }] }, pastClock, "$/MWh").zones.HB_NORTH;
  assert.ok(outside.values.every(value => value === null));
  assert.deepEqual(pastHours(null, pastClock, "$/MWh").zones, {});
  assert.equal(pastHours({ HB_NORTH: [] }, pastClock, "$/MWh").zones.HB_NORTH.peak, null);
});

test("X4 demand actuals read MW rows and ignore prices", () => {
  // Synthetic values on the sourced row shape; this asserts unit routing only.
  const rows = actuals.slice(0, 24).map((row, i) => ({ ...row, unit: "MW", value: 70000 + i }));
  const demand = pastHours({ ERCOT: [...rows, { ...actuals[35], unit: "$/MWh" }] }, pastClock, "MW").zones.ERCOT;
  assert.equal(demand.values[0], 70011);
  assert.equal(demand.values[1], 70023);
  assert.equal(demand.values[2], null);
  assert.equal(demand.peak, null);
});

// DEC-GM-152: exact bytes from the real route (see the provenance file).
const recorded = JSON.parse(readFileSync(new URL("./fixtures/history-snapshot-recorded.json", import.meta.url)));
const recordedClock = Date.parse("2026-09-26T22:00:00Z"); // window end

test("X4 recorded snapshot history parses through past hours", () => {
  assert.equal(recorded.length, 288);
  const past = pastHours({ HB_NORTH: recorded }, recordedClock, "$/MWh");
  const north = past.zones.HB_NORTH;
  assert.equal(past.hours.length, PAST_HOURS);
  assert.ok(north.values.every(Number.isFinite)); // full 24 h feed: no gaps
  assert.deepEqual(north.values, recorded.filter((_, i) => i % 12 === 11).map(row => row.value));
  assert.equal(north.values[0], 26.1);
  assert.equal(north.values[23], 53.7);
  assert.equal(north.peak, 53.7);
  assert.equal(north.low, 26.1);
  assert.equal(north.published, "2026-09-26T21:55:00+00:00");
});

test("X4 scrubber spans 48 hours with now at slot 24 and Actual/Forecast labels", () => {
  const scrub = scrubHours(pastClock);
  assert.equal(scrub.hours.length, SCRUB_HOURS);
  assert.equal(scrub.nowIndex, NOW_INDEX);
  assert.equal(scrub.hours[NOW_INDEX], Date.parse("2026-09-26T22:00:00Z"));
  assert.equal(scrub.hours[0], Date.parse("2026-09-25T22:00:00Z"));
  assert.equal(scrub.hours[47], Date.parse("2026-09-27T21:00:00Z"));
  assert.equal(scrub.hours[47] - scrub.hours[0], 47 * HOUR);
  // The past half meets the forecast half exactly at the current UTC hour.
  assert.equal(pastHours(null, pastClock, "$/MWh").hours[PAST_HOURS - 1] + HOUR, scrub.hours[NOW_INDEX]);
  assert.equal(forecastHours(null, pastClock).hours[0], scrub.hours[NOW_INDEX]);
  assert.deepEqual([0, 23, 24, 47].map(hourKind), ["Actual", "Actual", "Forecast", "Forecast"]);
  assert.deepEqual([0, 6, 23, 24, 25, 36, 47].map(hourOffset), ["24 h ago", "18 h ago", "1 h ago", "Now", "in 1 h", "in 12 h", "in 23 h"]);
});

test("X4 history requests keep each window within the endpoint 48-hour bound", () => {
  for (const path of [historyPath("LZ_HOUSTON", pastClock), actualPath(HUB_REPORT, "HB_NORTH", pastClock), actualPath(DEMAND_REPORT, "ERCOT", pastClock)]) {
    const url = new URL(path, "http://market.test");
    assert.equal(url.pathname, "/v1/signals/history");
    assert.ok(Date.parse(url.searchParams.get("end")) - Date.parse(url.searchParams.get("start")) <= 48 * HOUR);
  }
  const url = new URL(actualPath(HUB_REPORT, "HB_NORTH", pastClock), "http://market.test");
  assert.equal(url.searchParams.get("report_id"), "SNAPSHOT-HUBS");
  assert.equal(url.searchParams.get("zone"), "HB_NORTH");
  assert.equal(Date.parse(url.searchParams.get("end")), Date.parse("2026-09-26T22:00:00Z"));
  assert.equal(Date.parse(url.searchParams.get("end")) - Date.parse(url.searchParams.get("start")), 24 * HOUR);
  assert.deepEqual(ACTUAL_HUBS, ["HB_NORTH", "HB_HOUSTON", "HB_SOUTH", "HB_WEST"]);
  assert.equal(HUB_FOR_ZONE.LZ_NORTH, "HB_NORTH");
  assert.equal(HUB_FOR_ZONE.LZ_AEN, undefined);
});

test("X4 scrubber values read No data when missing and keep money and megawatt shapes", () => {
  assert.equal(hourText(null, "MW"), "No data");
  assert.equal(hourText(NaN, "$/MWh"), "No data");
  assert.equal(hourText(undefined, "MW"), "No data");
  assert.equal(hourText(19331.1992, "MW"), "19,331.2 MW");
  assert.equal(hourText(0, "MW"), "0 MW");
  assert.equal(hourText(28.16, "$/MWh"), "$28.16/MWh");
  assert.equal(hourText(-4.5, "$/MWh"), "−$4.50/MWh");
  assert.equal(hourText(0, "$/MWh"), "$0.00/MWh");
  assert.equal(noData, "No data");
  // Forecast hours now carry each value's publish time alongside the aggregate.
  assert.deepEqual(forecastHours({ LZ_HOUSTON: history }, clock).zones.LZ_HOUSTON.publishedByHour, history.map(row => row.published_at));
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
