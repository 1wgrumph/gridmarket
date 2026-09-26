import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { countyToZone, tradeLink, leadPrediction, isBattery, latestESR, formatESR } from "../public/godseye/geo.js";

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
