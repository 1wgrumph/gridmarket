import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { countyToZone, tradeLink, leadPrediction, isBattery, latestESR, formatESR, zoneName, sectorName, ctTime, intervalText, checkName, checkQuestion, routeName, activityText } from "../public/godseye/geo.js";

const plants = JSON.parse(readFileSync(new URL("../public/data/tx_plants.json", import.meta.url))).plants;

test("S61 #12 county approximation covers the ERCOT plant corpus and leaves unknown counties unmapped", () => {
  for (const [county, zone] of Object.entries({ Dallas: "NORTH", Nueces: "SOUTH", Midland: "WEST", Harris: "HOUSTON", Fayette: "LCRA", Travis: "AEN", Bexar: "CPS", Kaufman: "RAYBN" })) {
    assert.equal(countyToZone(county), `LZ_${zone}`);
  }
  assert.equal(countyToZone("  harris County "), "LZ_HOUSTON");
  assert.equal(countyToZone("Unknown"), null);
  assert.equal(countyToZone(null), null);
  for (const plant of plants.filter(p => p.ba === "ERCO")) assert.ok(countyToZone(plant.county), plant.county);
});

test("S61 #12 trade links use the dashboard zone route and require an HTTP market URL", () => {
  assert.equal(tradeLink("https://market.example", "LZ_NORTH"), "https://market.example/#/?zone=LZ_NORTH");
  assert.equal(tradeLink("https://market.example/", "LZ_AEN"), "https://market.example/#/?zone=LZ_AEN");
  for (const url of ["", undefined, "javascript:alert(1)"]) assert.equal(tradeLink(url, "LZ_NORTH"), null);
  assert.equal(tradeLink("https://market.example", null), null);
});

test("S61 #12 selects the zone's lead delivery hour independent of response order", () => {
  const first = { zone: "LZ_NORTH", score: 72, level: "high", confidence: 0.8, drivers: [], delivery_hour: "2026-09-26T15:00:00Z" };
  const later = { ...first, score: 90, delivery_hour: "2026-09-26T16:00:00Z" };
  assert.deepEqual(leadPrediction([later, { ...first, zone: "LZ_SOUTH" }, first], "LZ_NORTH"), first);
  assert.equal(leadPrediction([first], "LZ_WEST"), null);
  assert.equal(leadPrediction(null, "LZ_NORTH"), null);
  assert.equal(leadPrediction([{ ...first, score: null }], "LZ_NORTH"), null);
});

const esrFixture = JSON.parse(readFileSync(new URL("./fixtures/esr.json", import.meta.url)));
const signals = esrFixture.data.map(([time, value, published]) => ({ report_id: "ESR", zone: "ERCOT", interval_start: time, interval_minutes: 0, value, unit: "MW", published_at: published, fetched_at: published, stale: false }));

test("S61 #13 ESR formatting distinguishes charging, discharging, zero and unavailable", () => {
  assert.equal(formatESR(signals[0]), "812.5 MW charging");
  assert.equal(formatESR(signals[2]), "120.75 MW discharging");
  assert.equal(formatESR({ ...signals[0], value: 0 }), "0 MW · idle");
  for (const signal of [null, { ...signals[0], value: null }, { ...signals[0], stale: true }, { ...signals[0], unit: "MWh" }]) {
    assert.equal(formatESR(signal), "Battery data unavailable");
  }
});

test("S61 #13 latest ESR uses the system-wide signal and fetched time", () => {
  assert.deepEqual(latestESR([signals[2], { ...signals[2], report_id: "OTHER" }, signals[0], { ...signals[2], zone: "LZ_NORTH" }]), signals[2]);
  assert.equal(latestESR([]), null);
  assert.equal(latestESR(null), null);
});

test("S61 #13 batteries include hybrid plants with storage units", () => {
  assert.equal(isBattery(plants.find(p => p.code === 67737)), true);
  assert.equal(isBattery(plants.find(p => p.code === 8063)), true);
  assert.equal(isBattery(plants.find(p => p.prim === "nuclear")), false);
});

test("S62r plain names cover every load zone and plant sector in the corpus", () => {
  for (const plant of plants.filter(p => p.ba === "ERCO")) assert.ok(zoneName(countyToZone(plant.county)), plant.county);
  for (const sector of new Set(plants.map(p => p.sector))) assert.doesNotMatch(sectorName(sector), /IPP|CHP|Non-/, sector);
  assert.equal(zoneName("LZ_NORTH"), "North");
  assert.equal(zoneName("HB_NORTH"), null);
});

test("S62r ERCOT times read in Central time", () => {
  assert.equal(ctTime("2026-09-25T19:00:00Z"), "Sep 25, 2:00 PM CDT");
  assert.equal(ctTime("2026-12-01T19:00:00Z"), "Dec 1, 1:00 PM CST");
  assert.equal(ctTime("not a time"), null);
  assert.equal(intervalText(14, 1), "1:00 PM–1:15 PM CT");
  assert.equal(intervalText(1, 1), "12:00 AM–12:15 AM CT");
  assert.equal(intervalText(24, 4), "11:45 PM–12:00 AM CT");
  assert.equal(intervalText(25, 1), null);
});

test("S62r checks and market activity read as plain sentences", () => {
  for (const id of ["scarcity-2h", "dart-north", "renew-shortfall"]) {
    assert.doesNotMatch(checkQuestion(id, "P(x)"), /P\(|HB_|RT|DA\b|HE\d/);
    assert.notEqual(checkName(id), id);
  }
  assert.equal(checkQuestion("new-check", "Raw question"), "Raw question");
  assert.deepEqual(["alert", "review", "log"].map(routeName), ["Alert", "Worth watching", "No action"]);
  // Symbols follow the market generator: SPOT-<zone>-<YYYYMMDDHH>.
  assert.equal(activityText({ type: "fill", label: "Harbor Desk", side: "buy", quantity: 3, price_cents: 8, symbol: "SPOT-LZ_NORTH-2026092615" }), "Harbor Desk bought 3 · North zone · $0.08");
  assert.equal(activityText({ type: "order", label: "Prairie Wind Co", side: "sell", quantity: 5, price_cents: 412, symbol: "FLEX-LZ_AEN-2026092620" }), "Prairie Wind Co offered 5 · Austin Energy zone · $4.12");
});
