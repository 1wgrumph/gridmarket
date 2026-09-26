// S76 red tests: Worker snapshot freshness (R1-05, R1-14) and ERCOT budget
// accounting with keyless-route limits (R5-04, R5-05). No network.
import test from "node:test";
import assert from "node:assert/strict";
import worker from "../src/index.js";

const MARKET_KEY = "test-market-key";

function memoryBinding(max) {
  const values = new Map();
  const windows = new Map();
  const puts = [];
  return {
    puts,
    async get(key) { return values.get(key) ?? null; },
    async put(key, value, opts) { values.set(key, value); puts.push({ key, opts }); },
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

const f = (name) => ({ name, label: name, dataType: "VARCHAR" });
const report = (fields, data) => ({
  _meta: { totalRecords: data.length, pageSize: data.length, totalPages: 1, currentPage: 1 },
  report: {},
  fields,
  data,
});
const T = "2026-09-26";
const he = (n) => String(n).padStart(2, "0") + ":00";
const ZONES = ["coast", "east", "farWest", "north", "northCentral", "southCentral", "southern", "west"];
const SNAPSHOT_INPUTS = {
  "/api/public-reports/np6-235-cd/system_wide_demand": report(
    [f("deliveryDate"), f("timeEnding"), f("demand")],
    [[T, "09:45", 70100], [T, "10:00", 70234]]),
  "/api/public-reports/np6-905-cd/spp_node_zone_hub": report(
    [f("deliveryHour"), f("deliveryInterval"), f("settlementPoint"), f("settlementPointPrice")],
    [[10, 1, "HB_NORTH", 51.25], [10, 1, "HB_HOUSTON", 48.5]]),
  "/api/public-reports/np4-190-cd/dam_stlmnt_pnt_prices": report(
    [f("hourEnding"), f("settlementPoint"), f("settlementPointPrice")],
    Array.from({ length: 24 }, (_, i) => [i + 1, "HB_NORTH", 60.75])),
  "/api/public-reports/np6-323-cd/rt_price_adder_sced": report(
    [f("SCEDTimestamp"), f("systemLambda"), f("RTRDPA"), f("RTOLHSL"), f("RTOLLSL")],
    [["2026-09-26T09:55:00", 36.5, 0, 82000, 30000]]),
  "/api/public-reports/np4-732-cd/wpp_hrly_avrg_actl_fcast": report(
    [f("hourEnding"), f("genSystemWide"), f("STWPFSystemWide"), f("HSLSystemWide")],
    [[9, 12000, 12500, 13000]]),
  "/api/public-reports/np4-737-cd/spp_hrly_avrg_actl_fcast": report(
    [f("hourEnding"), f("genSystemWide"), f("STPPFSystemWide"), f("HSLSystemWide")],
    [[9, 9000, 9200, 9500]]),
  "/api/public-reports/np4-722-cd/weather_assumptions": report(
    [f("hourEnding"), ...ZONES.map(f)],
    Array.from({ length: 24 }, (_, i) => [he(i + 1), ...ZONES.map(() => 70 + i + 1)])),
};

function fixture(t, { token = "stub-token", failPaths = new Set() } = {}) {
  const originalFetch = globalThis.fetch;
  let ercotCalls = 0;
  const env = {
    CACHE: memoryBinding(Infinity),
    RATE_LIMITER: memoryBinding(30),
    ERCOT_BUDGET: memoryBinding(25),
    MARKET_KEY,
    MARKET_URL: "https://market.invalid",
    ERCOT_USERNAME: "u",
    ERCOT_PASSWORD: "p",
    ERCOT_SUBSCRIPTION_KEY: "s",
  };
  if (token) env.CACHE.put("ercot:id_token", token);
  globalThis.fetch = async (input) => {
    const url = new URL(input);
    if (url.hostname.endsWith("b2clogin.com")) {
      return token
        ? Response.json({ id_token: token })
        : Response.json({ error: "invalid_grant" }, { status: 400 });
    }
    assert.equal(url.origin, "https://api.ercot.com", `unexpected fetch: ${url.origin}`);
    ercotCalls++;
    if (failPaths.has(url.pathname)) {
      return Response.json({ message: "stubbed failure" }, { status: 500 });
    }
    return Response.json(SNAPSHOT_INPUTS[url.pathname] ?? { fields: [], data: [] });
  };
  t.after(() => { globalThis.fetch = originalFetch; });
  const request = (path, { key, ip = "192.0.2.1" } = {}) => {
    const headers = { "cf-connecting-ip": ip };
    if (key !== undefined) headers["x-gridmarket-key"] = key;
    return worker.fetch(new Request(`https://worker.invalid${path}`, { headers }), env);
  };
  return { env, request, ercotCalls: () => ercotCalls };
}

// R1-14: snapshot weather uses the hour in progress (heNow), not the previous hour.
test("S76-R1-14 snapshot weather row matches heNow", async (t) => {
  const { request } = fixture(t);
  const response = await request("/api/snapshot?fresh", { key: MARKET_KEY });
  assert.equal(response.status, 200);
  const snap = await response.json();
  assert.equal(snap.weather.hourEnding, he(snap.heNow));
});

// R1-05: an all-errors snapshot is not a fresh 200, and error snapshots are short-lived.
test("S76-R1-05 all-errors snapshot returns 502 and stays 502 on cache hit", async (t) => {
  const { request } = fixture(t, { token: null });
  const first = await request("/api/snapshot");
  assert.equal(first.status, 502);
  assert.equal(first.headers.get("x-cache"), "MISS");
  assert.ok(Object.keys((await first.json()).errors).length > 0);
  const second = await request("/api/snapshot");
  assert.equal(second.status, 502);
  assert.equal(second.headers.get("x-cache"), "HIT");
});

test("S76-R1-05 error snapshot caches briefly, success caches 300s", async (t) => {
  const { env, request } = fixture(t, {
    failPaths: new Set(["/api/public-reports/np4-722-cd/weather_assumptions"]),
  });
  const partial = await request("/api/snapshot?fresh", { key: MARKET_KEY });
  assert.equal(partial.status, 200);
  assert.deepEqual(Object.keys(await partial.json().then((b) => b.errors)), ["weather"]);
  const ttl = (key) => env.CACHE.puts.filter((p) => p.key === key).at(-1).opts.expirationTtl;
  assert.ok(ttl("snapshot:v1") < 300, `partial snapshot TTL must be short, got ${ttl("snapshot:v1")}`);

  const ok = fixture(t);
  const good = await ok.request("/api/snapshot?fresh", { key: MARKET_KEY });
  assert.equal(good.status, 200);
  assert.deepEqual(Object.keys((await good.json()).errors), []);
  assert.equal(ok.env.CACHE.puts.filter((p) => p.key === "snapshot:v1").at(-1).opts.expirationTtl, 300);
});

// R5-05: the budget counts real ERCOT calls; snapshot + reports stay within 25.
test("S76-R5-05 snapshot plus reports make at most 25 ERCOT calls", async (t) => {
  const { request, ercotCalls } = fixture(t);
  const snap = await request("/api/snapshot");
  assert.equal(snap.status, 200);
  const codes = [];
  for (let i = 0; i < 24; i++) {
    codes.push((await request(`/api/report/np6-905-cd/spp_node_zone_hub?page=${i}`, {
      key: MARKET_KEY, ip: `198.51.100.${i}`,
    })).status);
  }
  assert.ok(ercotCalls() <= 25, `${ercotCalls()} ERCOT calls exceeded the 25-call budget`);
  assert.ok(codes.includes(429), "excess reports must return 429 once the budget is spent");
});

// R5-04: one keyless client cannot exhaust the shared budget through /api/edc.
test("S76-R5-04 keyless edc burst leaves the keyed market poll working", async (t) => {
  const { request } = fixture(t);
  const codes = [];
  for (let i = 1; i <= 26; i++) codes.push((await request(`/api/edc?size=${i}`)).status);
  assert.ok(
    codes.filter((c) => c === 200).length <= 5,
    `keyless burst spent too much: ${codes.filter((c) => c === 200).length} x 200`
  );
  const market = await request("/api/report/np6-905-cd/spp_node_zone_hub", {
    key: MARKET_KEY, ip: "198.51.100.9",
  });
  assert.equal(market.status, 200);
});

test("S76-R5-04 repeated identical edc query is served from cache", async (t) => {
  const { request } = fixture(t);
  const first = await request("/api/edc?size=7");
  const second = await request("/api/edc?size=7");
  assert.equal(first.status, 200);
  assert.equal(second.status, 200);
  assert.equal(second.headers.get("x-cache"), "HIT");
});
