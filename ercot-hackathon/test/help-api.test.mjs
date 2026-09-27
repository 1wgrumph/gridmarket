import test from "node:test";
import assert from "node:assert/strict";
import worker from "../src/index.js";

// /api/help is keyless: one shared cache entry, coalesced builds, ?fresh needs the market key,
// and every ERCOT call it makes spends the shared ERCOT_BUDGET.
const MARKET_KEY = "test-market-key";
const HELP_PATHS = [
  "/api/public-reports/np3-560-cd/7d_load_fcast_by_fzn",
  "/api/public-reports/np4-732-cd/wpp_hrly_avrg_actl_fcast",
  "/api/public-reports/np4-737-cd/spp_hrly_avrg_actl_fcast",
  "/api/public-reports/np4-190-cd/dam_stlmnt_pnt_prices",
];

function memoryBinding(max) {
  const values = new Map();
  const windows = new Map();
  return {
    puts: [],
    async get(key) { return values.get(key) ?? null; },
    async put(key, value, opts) { this.puts.push({ key, opts }); values.set(key, value); },
    async limit({ key }) {
      const now = Date.now();
      const recent = (windows.get(key) ?? []).filter((at) => now - at < 60_000);
      if (recent.length >= max) return { success: false };
      recent.push(now);
      windows.set(key, recent);
      return { success: true };
    },
  };
}

function fixture(t, { budget = 25 } = {}) {
  const originalFetch = globalThis.fetch;
  const calls = [];
  const env = {
    CACHE: memoryBinding(Infinity),
    RATE_LIMITER: memoryBinding(30),
    ERCOT_BUDGET: memoryBinding(budget),
    MARKET_KEY,
    ERCOT_USERNAME: "test-user",
    ERCOT_PASSWORD: "test-password",
    ERCOT_SUBSCRIPTION_KEY: "test-subscription-key",
  };
  env.CACHE.put("ercot:id_token", "test-token");
  globalThis.fetch = async (input) => {
    const url = new URL(input);
    assert.equal(url.origin, "https://api.ercot.com", `unexpected fetch: ${url.origin}`);
    calls.push(url);
    return Response.json({ fields: [], data: [] }); // ERCOT's report envelope with an empty page
  };
  t.after(() => { globalThis.fetch = originalFetch; });
  const request = (path, { key, ip = "192.0.2.1" } = {}) => {
    const headers = { "cf-connecting-ip": ip };
    if (key !== undefined) headers["x-gridmarket-key"] = key;
    return worker.fetch(new Request(`https://worker.invalid${path}`, { headers }), env);
  };
  return { env, calls, request };
}

test("HELP-01 keyless /api/help returns four zones over 24 hours from 7 ERCOT calls, then serves the cache", async (t) => {
  const { env, calls, request } = fixture(t);
  const response = await request("/api/help");
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("x-cache"), "MISS");
  const body = await response.json();
  assert.equal(body.horizonHours, 24);
  assert.deepEqual(body.unavailable, {});
  assert.deepEqual(body.zones.map((z) => [z.id, z.settlementPoint]),
    [["houston", "LZ_HOUSTON"], ["north", "LZ_NORTH"], ["south", "LZ_SOUTH"], ["west", "LZ_WEST"]]);
  for (const z of body.zones) {
    assert.equal(z.series.length, 24);
    assert.deepEqual(Object.keys(z.now).sort(), ["basis", "daPrice", "score", "zoneLoad"]);
    assert.deepEqual(z.windows, []);
  }
  assert.equal(calls.length, 7);
  assert.ok(calls.every((url) => HELP_PATHS.includes(url.pathname)), calls.map((u) => u.pathname).join());
  assert.equal(env.CACHE.puts.find((p) => p.key === "help:v1").opts.expirationTtl, 900);

  const again = await request("/api/help", { ip: "192.0.2.2" });
  assert.equal(again.status, 200);
  assert.equal(again.headers.get("x-cache"), "HIT");
  assert.equal(calls.length, 7, "cached help must not call ERCOT");
});

test("HELP-02 concurrent cold requests share one build", async (t) => {
  const { calls, request } = fixture(t);
  const responses = await Promise.all(Array.from({ length: 10 }, (_, i) => request("/api/help", { ip: `192.0.2.${i + 1}` })));
  assert.deepEqual(responses.map((r) => r.status), Array(10).fill(200));
  assert.equal(calls.length, 7);
});

test("HELP-03 ?fresh needs the market key before any ERCOT call", async (t) => {
  for (const key of [undefined, "invalid-key"]) {
    const { calls, request } = fixture(t);
    assert.equal((await request("/api/help?fresh", { key })).status, 401);
    assert.equal(calls.length, 0);
  }
  const { calls, request } = fixture(t);
  assert.equal((await request("/api/help?fresh", { key: MARKET_KEY })).status, 200);
  assert.equal(calls.length, 7);
});

test("HELP-04 an exhausted ERCOT budget returns 502 with every input unavailable, cached 30 s", async (t) => {
  const { env, calls, request } = fixture(t, { budget: 0 });
  const response = await request("/api/help");
  assert.equal(response.status, 502);
  const body = await response.json();
  assert.equal(Object.keys(body.unavailable).length, 7);
  assert.equal(calls.length, 0);
  assert.equal(env.CACHE.puts.find((p) => p.key === "help:v1").opts.expirationTtl, 30);
  const again = await request("/api/help", { ip: "192.0.2.2" });
  assert.equal(again.status, 502);
  assert.equal(again.headers.get("x-cache"), "HIT");
});
