import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import worker from "../src/index.js";

const MARKET_URL = "https://market.invalid";
const MARKET_ORIGIN = "https://market.example";
const PAGES = {
  "/": new URL("../public/index.html", import.meta.url),
  "/godseye/": new URL("../public/godseye/index.html", import.meta.url),
};
const ACTIVITY = [
  { id: "e1", type: "fill", label: "Harbor Desk", symbol: "LZ_NORTH", side: "buy", quantity: 3, price_cents: 8, reason: null, created_at: "2026-09-26T14:00:00Z", entry_type: "fill", subject_id: "t1" },
];
const ROUTER = {
  checks: [
    { check_id: "dart-lz-north", family: "dart", subject: "LZ_NORTH", horizon_s: 3600, probability: 0.91, band: "alert", baseline: true, jev_probability: null, created_at: "2026-09-26T14:00:00Z", resolves_at: "2026-09-26T15:00:00Z", outcome: null },
    { check_id: "dart-lz-west", family: "dart", subject: "LZ_WEST", horizon_s: 3600, probability: 0.22, band: "log", baseline: true, jev_probability: null, created_at: "2026-09-26T14:00:00Z", resolves_at: "2026-09-26T15:00:00Z", outcome: null },
  ],
  brier: {},
  jev_enabled: false,
};
const ERCOT_CONTENT = "ERCOT hub prices";

function page(route) {
  return readFileSync(PAGES[route], "utf8");
}

function feedUrl(input) {
  if (typeof input === "string") return input;
  if (input instanceof URL) return input.href;
  return input.url;
}

function feedTarget(input) {
  const url = new URL(feedUrl(input));
  return { origin: url.origin, pathname: url.pathname.replace(/\/$/, "") };
}

async function loadFeed() {
  return import("../public/market-feed.js");
}

function host(html) {
  return { innerHTML: html };
}

function configEnv(t) {
  const originalFetch = globalThis.fetch;
  const calls = [];
  const env = {
    CACHE: {
      async get() { return null; },
      async put() {},
    },
    RATE_LIMITER: { async limit() { return { success: true }; } },
    ERCOT_BUDGET: { async limit() { return { success: true }; } },
    MARKET_KEY: "test-market-key",
    MARKET_URL,
    ERCOT_USERNAME: "test-user",
    ERCOT_PASSWORD: "test-password",
    ERCOT_SUBSCRIPTION_KEY: "test-subscription-key",
  };
  globalThis.fetch = async (input) => {
    calls.push(String(input));
    throw new Error(`unexpected fetch: ${input}`);
  };
  t.after(() => { globalThis.fetch = originalFetch; });
  const request = (path) => worker.fetch(new Request(`https://worker.invalid${path}`), env);
  return { calls, request };
}

function okMarketFetch(input, init) {
  assert.equal((init?.method ?? input?.method ?? "GET").toUpperCase(), "GET");
  const target = feedTarget(input);
  assert.equal(target.origin, MARKET_ORIGIN, "market read must be cross-origin");
  if (target.pathname === "/v1/market/activity") return Response.json(ACTIVITY);
  if (target.pathname === "/v1/router") return Response.json(ROUTER);
  throw new Error(`unexpected market fetch ${target.pathname}`);
}

test("S26-01 SEIT-GM-EDGE-05 red-expected fetchMarket reads /v1/market/activity and /v1/router cross-origin", async () => {
  const { fetchMarket } = await loadFeed();
  const seen = [];
  const result = await fetchMarket(MARKET_ORIGIN, (input, init) => {
    seen.push(feedTarget(input));
    return okMarketFetch(input, init);
  });
  assert.deepEqual(seen.sort((a, b) => a.pathname.localeCompare(b.pathname)), [
    { origin: MARKET_ORIGIN, pathname: "/v1/market/activity" },
    { origin: MARKET_ORIGIN, pathname: "/v1/router" },
  ]);
  assert.notEqual(result.offline, true);
  assert.deepEqual(result.activity, ACTIVITY);
  assert.deepEqual(result.router, ROUTER);
});

test("S26-02 SEIT-GM-EDGE-05 red-expected fetchMarket returns offline on 5xx and the view keeps ERCOT content", async () => {
  const { fetchMarket, renderFeed } = await loadFeed();
  const result = await fetchMarket(MARKET_ORIGIN, () => new Response("down", { status: 503 }));
  assert.deepEqual(result, { offline: true });
  const el = host(ERCOT_CONTENT);
  renderFeed(el, result);
  assert.equal(el.innerHTML, ERCOT_CONTENT);
});

test("S26-03 SEIT-GM-EDGE-05 red-expected fetchMarket returns offline on a 20s timeout and the view keeps ERCOT content", { timeout: 24_000 }, async () => {
  const { fetchMarket, renderFeed } = await loadFeed();
  const started = performance.now();
  const result = await fetchMarket(MARKET_ORIGIN, (input, init) => new Promise((resolve, reject) => {
    const signal = init?.signal ?? input?.signal;
    const timer = setTimeout(() => reject(Object.assign(new Error("timeout"), { name: "TimeoutError" })), 20_000);
    signal?.addEventListener("abort", () => {
      clearTimeout(timer);
      reject(Object.assign(new Error("aborted"), { name: "AbortError" }));
    }, { once: true });
  }));
  const elapsed = performance.now() - started;
  assert.deepEqual(result, { offline: true });
  assert.ok(elapsed >= 19_000 && elapsed < 23_000, `timeout was ${Math.round(elapsed)}ms, want 20s`);
  const el = host(ERCOT_CONTENT);
  renderFeed(el, result);
  assert.equal(el.innerHTML, ERCOT_CONTENT);
});

test("S26-04 SEIT-GM-EDGE-05 red-expected renderFeed shows the activity strip and alert-band checks", async () => {
  const { renderFeed } = await loadFeed();
  const el = host("");
  renderFeed(el, { activity: ACTIVITY, router: ROUTER });
  assert.match(el.innerHTML, /activity/i);
  assert.match(el.innerHTML, /Harbor Desk/);
  assert.match(el.innerHTML, /buy 3 LZ_NORTH/);
  assert.match(el.innerHTML, /@ 8¢/);
  assert.match(el.innerHTML, /dart-lz-north/);
});

test("S26-05 SEIT-GM-EDGE-05 red-expected GET /api/config returns MARKET_URL", async (t) => {
  const { calls, request } = configEnv(t);
  const response = await request("/api/config");
  assert.equal(calls.length, 0, "config must not call ERCOT");
  assert.equal(response.status, 200);
  assert.equal((await response.json()).MARKET_URL, MARKET_URL);
});

test("S26-06 SEIT-GM-EDGE-05 red-expected / and /godseye/ import market-feed.js", () => {
  for (const route of Object.keys(PAGES)) {
    assert.match(
      page(route),
      /from\s+["'][^"']*market-feed\.js["']|import\s*\(?\s*["'][^"']*market-feed\.js["']/,
      `${route} imports market-feed.js`,
    );
  }
});

test("S26-07 SEIT-GM-EDGE-05 red-expected / and /godseye/ link to the dashboard", () => {
  for (const route of Object.keys(PAGES)) {
    const html = page(route);
    const linked = /<a\b[^>]*\bdashboard\b[^>]*>/i.test(html)
      || /<a\b[^>]*>[^<]*\bdashboard\b[^<]*<\/a>/i.test(html);
    assert.equal(linked, true, `${route} links to the dashboard`);
  }
});

test("S26-08 SEIT-GM-RULE-02-VIEWS red-expected / and /godseye/ label router results baseline rules", async () => {
  for (const route of Object.keys(PAGES)) {
    assert.match(page(route), /baseline rules/, `${route} labels router results baseline rules`);
  }
  const { renderFeed } = await loadFeed();
  const el = host("");
  renderFeed(el, { activity: ACTIVITY, router: ROUTER });
  assert.match(el.innerHTML, /baseline rules/);
});

test("S26-09 SEIT-GM-EDGE-05 regression-guard / and /godseye/ keep their ERCOT reads", () => {
  assert.match(page("/"), /\/api\/edc/);
  assert.match(page("/godseye/"), /\/api\/snapshot/);
});
