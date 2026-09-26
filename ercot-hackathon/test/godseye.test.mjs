import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { countyToZone, tradeLink, leadPrediction } from "../public/godseye/geo.js";

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
