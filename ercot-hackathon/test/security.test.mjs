import test from "node:test";
import assert from "node:assert/strict";
import worker from "../src/index.js";

const MARKET_KEY = "test-market-key";
const ALLOWED = [
  "/api/report/np6-905-cd/spp_node_zone_hub",
  "/api/report/np4-190-cd/dam_stlmnt_pnt_prices",
  "/api/report/np3-565-cd/lf_by_model_weather_zone",
  "/api/report/np3-233-cd/hourly_res_outage_cap",
  "/api/report/np6-86-cd/shdw_prices_bnd_trns_const",
];

function memoryBinding(max) {
  const values = new Map();
  const windows = new Map();
  return {
    async get(key, type) {
      const value = values.get(key) ?? null;
      return type === "json" && value !== null ? JSON.parse(value) : value;
    },
    async put(key, value) { values.set(key, value); },
    async delete(key) { values.delete(key); },
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

function fixture(t, { retryOnce = false } = {}) {
  const originalFetch = globalThis.fetch;
  const calls = [];
  const callTimes = [];
  const env = {
    CACHE: memoryBinding(Infinity),
    RATE_LIMITER: memoryBinding(30),
    ERCOT_BUDGET: memoryBinding(25),
    MARKET_KEY,
    MARKET_URL: "https://market.invalid",
    ERCOT_USERNAME: "test-user",
    ERCOT_PASSWORD: "test-password",
    ERCOT_SUBSCRIPTION_KEY: "test-subscription-key",
  };
  env.CACHE.put("ercot:id_token", "test-token");
  globalThis.fetch = async (input) => {
    const url = new URL(input);
    assert.equal(url.origin, "https://api.ercot.com", `unexpected fetch: ${url.origin}`);
    calls.push(url);
    callTimes.push(performance.now());
    if (retryOnce && calls.filter((call) => call.pathname === "/api/public-reports/np6-235-cd/system_wide_demand").length === 1
      && url.pathname === "/api/public-reports/np6-235-cd/system_wide_demand") {
      return Response.json({ error: "rate limited" }, { status: 429, headers: { "retry-after": "0.02" } });
    }
    return Response.json({ fields: [], data: [] });
  };
  t.after(() => { globalThis.fetch = originalFetch; });
  const request = (path, { key, ip = "192.0.2.1" } = {}) => {
    const headers = { "cf-connecting-ip": ip };
    if (key !== undefined) headers["x-gridmarket-key"] = key;
    return worker.fetch(new Request(`https://worker.invalid${path}`, { headers }), env);
  };
  return { env, calls, callTimes, request };
}

test("S24-01 all five approved report paths remain available with a market key", async (t) => {
  for (const path of ALLOWED) {
    await t.test(path, async (t) => {
      const { calls, request } = fixture(t);
      const response = await request(path, { key: MARKET_KEY });
      assert.equal(response.status, 200);
      assert.equal(calls.length, 1);
    });
  }
});

test("S24-02 report paths outside the exact allowlist stop before ERCOT", async (t) => {
  for (const path of [
    "/api/report/np3-907-ex/2d_agg_edc",
    "/api/report/np6-905-cd",
    "/api/report/np6-905-cd/spp_node_zone_hub_extra",
  ]) {
    await t.test(path, async (t) => {
      const { calls, request } = fixture(t);
      const response = await request(path, { key: MARKET_KEY });
      assert.equal(calls.length, 0, "denied report must not call ERCOT");
      assert.equal(response.status, 404);
    });
  }
});

test("S24-03 protected routes reject missing and invalid market keys before ERCOT", async (t) => {
  for (const path of [ALLOWED[0], "/api/products", "/api/snapshot?fresh"]) {
    for (const key of [undefined, "invalid-key"]) {
      await t.test(`${path} / ${key === undefined ? "missing" : "invalid"}`, async (t) => {
        const { calls, request } = fixture(t);
        const response = await request(path, { key });
        assert.equal(calls.length, 0, "unauthenticated request must not call ERCOT");
        assert.equal(response.status, 401);
      });
    }
  }
});

test("S24-04 a valid market key authenticates all protected route types", async (t) => {
  for (const path of [ALLOWED[0], "/api/products", "/api/snapshot?fresh"]) {
    await t.test(path, async (t) => {
      const { request } = fixture(t);
      assert.equal((await request(path, { key: MARKET_KEY })).status, 200);
    });
  }
});

test("S24-05 the 31st API request from one client in 60 seconds is blocked before ERCOT", async (t) => {
  const { calls, request } = fixture(t);
  for (let i = 0; i < 30; i++) {
    assert.equal((await request("/api/health")).status, 200);
  }
  const response = await request(ALLOWED[0], { key: MARKET_KEY });
  assert.equal(calls.length, 0, "rate-limited request must not call ERCOT");
  assert.equal(response.status, 429);
});

test("S24-06 ten-client burst stays within 25 ERCOT calls and rejects excess", async (t) => {
  const { calls, request } = fixture(t);
  const responses = await Promise.all(Array.from({ length: 10 }, (_, client) =>
    Array.from({ length: 40 }, (_, n) => request(`${ALLOWED[0]}?burst=${client}-${n}`, {
      key: MARKET_KEY,
      ip: `192.0.2.${client + 1}`,
    }))
  ).flat());
  assert.ok(calls.length <= 25, `${calls.length} ERCOT calls exceeded the 25-call budget`);
  assert.ok(responses.filter((response) => response.status === 429).length >= 375, "excess requests must return 429");
});

test("S24-07 snapshot retries an ERCOT 429 with backoff", async (t) => {
  const { calls, callTimes, request } = fixture(t, { retryOnce: true });
  const response = await request("/api/snapshot?fresh", { key: MARKET_KEY });
  assert.equal(response.status, 200);
  const attempts = calls.flatMap((url, i) => url.pathname === "/api/public-reports/np6-235-cd/system_wide_demand" ? [i] : []);
  assert.equal(attempts.length, 2);
  assert.ok(callTimes[attempts[1]] - callTimes[attempts[0]] >= 10, "retry must wait after 429");
});

test("S24-08 cached snapshot, EDC, and health remain keyless", async (t) => {
  const { env, calls, request } = fixture(t);
  await env.CACHE.put("snapshot:v1", JSON.stringify({ asOf: "cached" }));
  assert.equal((await request("/api/snapshot")).status, 200);
  assert.equal(calls.length, 0, "cached snapshot must not call ERCOT");
  assert.equal((await request("/api/edc")).status, 200);
  assert.equal((await request("/api/health")).status, 200);
});
