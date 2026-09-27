import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import worker from "../src/index.js";

const MARKET_KEY = "test-market-key";
const ESR_KEY = "test-esr-subscription-key";
const ESR_ROUTE = "/api/report/esr/charging_mw";
const ESR_UPSTREAM = "/api/public-data/rptesr-m/4_sec_esr_charging_mw";
const ESR_FIXTURE = JSON.parse(readFileSync(new URL("./fixtures/esr.json", import.meta.url), "utf8"));

function memoryBinding() {
  const values = new Map();
  const puts = [];
  return {
    puts,
    async get(key) { return values.get(key) ?? null; },
    async put(key, value, opts) { values.set(key, value); puts.push({ key, opts }); },
    async limit() { return { success: true }; },
  };
}

function fixture(t, { esrKey } = { esrKey: ESR_KEY }) {
  const originalFetch = globalThis.fetch;
  const calls = [];
  const env = {
    CACHE: memoryBinding(),
    RATE_LIMITER: memoryBinding(),
    ERCOT_BUDGET: memoryBinding(),
    MARKET_KEY,
    MARKET_URL: "https://market.invalid",
    ERCOT_USERNAME: "test-user",
    ERCOT_PASSWORD: "test-password",
    ERCOT_SUBSCRIPTION_KEY: "test-subscription-key",
  };
  if (esrKey !== undefined) env.ERCOT_ESR_SUBSCRIPTION_KEY = esrKey;
  env.CACHE.put("ercot:id_token", "test-token");
  globalThis.fetch = async (input, init) => {
    const url = new URL(typeof input === "string" ? input : input.url);
    assert.equal(url.origin, "https://api.ercot.com", `unexpected fetch: ${url.origin}`);
    calls.push({ url, headers: init?.headers ?? {} });
    return Response.json(ESR_FIXTURE);
  };
  t.after(() => { globalThis.fetch = originalFetch; });
  const request = (path, { key, ip = "192.0.2.1" } = {}) => {
    const headers = { "cf-connecting-ip": ip };
    if (key !== undefined) headers["x-gridmarket-key"] = key;
    return worker.fetch(new Request(`https://worker.invalid${path}`, { headers }), env);
  };
  return { env, calls, request };
}

test("S55-01 ESR route requires the market key before calling ERCOT", async (t) => {
  for (const key of [undefined, "invalid-key"]) {
    await t.test(`key ${key === undefined ? "missing" : "invalid"}`, async (t) => {
      const { calls, request } = fixture(t);
      const response = await request(ESR_ROUTE, { key });
      assert.equal(calls.length, 0, "unauthenticated request must not call ERCOT");
      assert.equal(response.status, 401);
    });
  }
});

test("S55-02 ESR route proxies the ESR product with bearer and ESR key, cached 300 s", async (t) => {
  const { env, calls, request } = fixture(t);
  const first = await request(ESR_ROUTE, { key: MARKET_KEY });
  assert.equal(first.status, 200);
  assert.equal(first.headers.get("x-cache"), "MISS");
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url.pathname, ESR_UPSTREAM);
  assert.equal(calls[0].headers.Authorization, "Bearer test-token");
  assert.equal(calls[0].headers["Ocp-Apim-Subscription-Key"], ESR_KEY);
  assert.deepEqual(await first.json(), ESR_FIXTURE);
  const cached = env.CACHE.puts.find((put) => put.key.startsWith("data:"));
  assert.equal(cached?.opts?.expirationTtl, 300);

  const second = await request(ESR_ROUTE, { key: MARKET_KEY });
  assert.equal(second.status, 200);
  assert.equal(second.headers.get("x-cache"), "HIT");
  assert.equal(calls.length, 1, "cache hit must not call ERCOT again");
});

test("S55-03 missing ESR key 503s only the ESR route while health stays ok", async (t) => {
  const { calls, request } = fixture(t, { esrKey: undefined });
  const esr = await request(ESR_ROUTE, { key: MARKET_KEY });
  assert.equal(esr.status, 503);
  assert.deepEqual(await esr.json(), {
    error: "Worker secrets not set",
    secretsMissing: ["ERCOT_ESR_SUBSCRIPTION_KEY"],
  });
  assert.equal(calls.length, 0, "missing-key ESR request must not call ERCOT");

  const health = await request("/api/health");
  assert.equal(health.status, 200);
  const body = await health.json();
  assert.equal(body.ok, true);
  assert.equal(body.esrKey, false);

  const other = await request("/api/report/np6-905-cd/spp_node_zone_hub", { key: MARKET_KEY });
  assert.equal(other.status, 200);
});
