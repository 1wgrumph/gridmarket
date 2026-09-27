import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import worker from "../src/index.js";

const plants = JSON.parse(readFileSync(new URL("../public/data/tx_plants.json", import.meta.url)));
const points = [...new Set(plants.plants.flatMap((plant) => plant.nodes))].sort();
// Committed report rows, using the public API's fields[].name envelope.
const report = (name) => {
  const data = JSON.parse(readFileSync(new URL(`../../backend/tests/fixtures/ercot/${name}.json`, import.meta.url)));
  return { ...data, fields: data.fields.map((name) => ({ name })) };
};
const RT = report("np6-905-cd");
const DA = report("np4-190-cd");
const NOW = new Date("2026-09-26T14:05:00Z");

// Mirrors the ERCOT_BUDGET binding in wrangler.jsonc: 25 units per key per window.
function fixture(t, { budget = 25 } = {}) {
  t.mock.timers.enable({ apis: ["Date", "setTimeout"], now: NOW });
  const values = new Map([["ercot:id_token", "test-token"]]);
  const puts = [], calls = [], budgetKeys = [], clientKeys = [];
  const env = {
    ERCOT_USERNAME: "test-user", ERCOT_PASSWORD: "test-password",
    ERCOT_SUBSCRIPTION_KEY: "test-subscription-key", MARKET_KEY: "test-market-key",
    CACHE: {
      async get(key) {
        const entry = values.get(key);
        if (typeof entry === "string") return entry;
        return entry && entry.expires > Date.now() ? entry.value : null;
      },
      async put(key, value, opts) {
        puts.push({ key, opts });
        values.set(key, { value, expires: Date.now() + opts.expirationTtl * 1000 });
      },
    },
    RATE_LIMITER: { async limit({ key }) { clientKeys.push(key); return { success: true }; } },
    ERCOT_BUDGET: { async limit({ key }) { budgetKeys.push(key); return { success: budgetKeys.filter((k) => k === key).length <= budget }; } },
  };
  t.mock.method(globalThis, "fetch", async (input) => {
    const url = new URL(input);
    calls.push(url);
    assert.equal(url.origin, "https://api.ercot.com");
    assert.equal(url.searchParams.get("deliveryDateFrom"), "2026-09-26");
    assert.equal(url.searchParams.get("deliveryDateTo"), "2026-09-26");
    const rt = url.pathname === "/api/public-reports/np6-905-cd/spp_node_zone_hub";
    if (!rt) assert.equal(url.pathname, "/api/public-reports/np4-190-cd/dam_stlmnt_pnt_prices");
    return Response.json(rt ? RT : DA);
  });
  // No market key: this is the browser's public route.
  const request = (sp, ip = "192.0.2.1") => worker.fetch(new Request(`https://worker.invalid/api/node${sp === undefined ? "" : `?sp=${encodeURIComponent(sp)}`}`, {
    headers: { "cf-connecting-ip": ip },
  }), env);
  return { env, values, puts, calls, budgetKeys, clientKeys, request };
}

test("S60 missing settlement points return 400 without ERCOT", async (t) => {
  const { request, calls, budgetKeys } = fixture(t);
  assert.equal((await request()).status, 400);
  assert.equal(calls.length, 0);
  assert.equal(budgetKeys.length, 0);
});

test("S60 unknown or malformed settlement points return 400 without ERCOT", async (t) => {
  const { request, calls, budgetKeys } = fixture(t);
  for (const sp of ["UNKNOWN_TEST_POINT", `${points[0]},UNKNOWN_TEST_POINT`, `${points[0]},!`]) {
    assert.equal((await request(sp)).status, 400);
  }
  assert.equal(calls.length, 0);
  assert.equal(budgetKeys.length, 0);
});

test("S60 accepts four distinct points and rejects five", async (t) => {
  const { request, calls } = fixture(t);
  assert.equal((await request(points.slice(0, 5).join(","))).status, 400);
  assert.equal(calls.length, 0);
  const response = await request(points.slice(0, 4).join(","));
  assert.equal(response.status, 200);
  assert.deepEqual((await response.json()).nodes.map((node) => node.sp), points.slice(0, 4));
  assert.equal(calls.length, 8);
});

test("S60 keyless cache normalizes case, duplicates and order for five minutes", async (t) => {
  const { request, calls, puts, budgetKeys, clientKeys } = fixture(t);
  const first = await request(`${points[1]},${points[0]}`);
  assert.equal(first.status, 200);
  assert.equal(first.headers.get("x-cache"), "MISS");
  const body = await first.json();
  assert.equal(body.asOf, NOW.toISOString());
  assert.equal(body.heNow, 10);
  assert.deepEqual(body.errors, {});
  assert.deepEqual(body.nodes.map((node) => node.sp), points.slice(0, 2));
  assert.equal(body.nodes[0].rt.price, 47.25);
  assert.deepEqual(body.nodes[0].rt.series, [48.5, 47.25]);
  assert.deepEqual(body.nodes[0].da, { price: 60.75, he: 10, dayMax: 60.75 });
  assert.equal(calls.length, 4);
  // Per upstream call: three units of the client's pool, one of the shared node pool; never the market's key.
  assert.deepEqual(budgetKeys, Array(4).fill(["node:192.0.2.1", "node:192.0.2.1", "node:192.0.2.1", "node"]).flat());
  assert.equal(puts.at(-1).opts.expirationTtl, 300);
  t.mock.timers.tick(299_999);
  const second = await request(` ${points[0].toLowerCase()},${points[1]},${points[0]} `);
  assert.equal(second.headers.get("x-cache"), "HIT");
  assert.deepEqual(await second.json(), body);
  assert.equal(calls.length, 4);
  assert.equal(budgetKeys.length, 16);
  assert.deepEqual(clientKeys, ["192.0.2.1", "192.0.2.1"]);
  t.mock.timers.tick(1);
  assert.equal((await request(points.slice(0, 2).join(","))).headers.get("x-cache"), "MISS");
  assert.equal(calls.length, 8);
});

test("S60 exhausted upstream budget preserves per-point errors without ERCOT or token fetch", async (t) => {
  const { request, calls, values, budgetKeys } = fixture(t, { budget: 0 });
  values.clear();
  const response = await request(points[0]);
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), {
    asOf: NOW.toISOString(), date: "2026-09-26", heNow: 10,
    nodes: [{ sp: points[0], rt: null, da: null }],
    errors: {
      [`${points[0]}:rt`]: "Upstream ERCOT budget exceeded",
      [`${points[0]}:da`]: "Upstream ERCOT budget exceeded",
    },
  });
  assert.deepEqual(budgetKeys, ["node:192.0.2.1", "node:192.0.2.1"]);
  assert.equal(calls.length, 0);
});

test("S62r failed node lookups are not cached", async (t) => {
  const { request, calls, puts } = fixture(t, { budget: 0 });
  const first = await request(points[0]);
  assert.equal(first.headers.get("x-cache"), "MISS");
  assert.notDeepEqual((await first.json()).errors, {});
  assert.equal(puts.length, 0);
  const second = await request(points[0]);
  assert.equal(second.headers.get("x-cache"), "MISS");
  assert.equal(calls.length, 0);
});

test("S62r one keyless client cannot exhaust the node budget or the market's ERCOT key", async (t) => {
  const { request, calls, budgetKeys } = fixture(t);
  const first = await request(points.slice(0, 4).join(","));
  assert.deepEqual((await first.json()).errors, {});
  assert.equal(calls.length, 8);
  // Same client, new points: its pool is spent, so ERCOT is not called and nothing is cached.
  const again = await (await request(points.slice(4, 8).join(","))).json();
  assert.ok(again.nodes.every((node) => node.rt === null && node.da === null));
  assert.equal(again.errors[`${points[4]}:rt`], "Upstream ERCOT budget exceeded");
  assert.equal(calls.length, 8);
  // Another client is still served.
  const other = await (await request(points.slice(4, 6).join(","), "198.51.100.7")).json();
  assert.deepEqual(other.errors, {});
  assert.equal(calls.length, 12);
  assert.ok(!budgetKeys.includes("ercot"));
});
