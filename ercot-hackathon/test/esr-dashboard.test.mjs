import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import worker from "../src/index.js";

const source = JSON.parse(readFileSync(new URL("./fixtures/esr-dashboard.json", import.meta.url)));
const upstream = "https://www.ercot.com/api/1/services/read/dashboards/energy-storage-resources.json";
function fixture(t) {
  t.mock.timers.enable({ apis: ["Date"], now: new Date("2026-09-26T22:34:22Z") });
  const values = new Map(), puts = [], calls = [], keys = [];
  const state = { status: 200, body: source, allowed: true };
  const env = {
    CACHE: {
      async get(key) { const v = values.get(key); return v?.expires > Date.now() ? v.body : null; },
      async put(key, body, opts) { puts.push(opts); values.set(key, { body, expires: Date.now() + opts.expirationTtl * 1000 }); },
    },
    RATE_LIMITER: { async limit({ key }) { keys.push(key); return { success: state.allowed }; } },
  };
  t.mock.method(globalThis, "fetch", async (url, opts) => {
    calls.push({ url, opts });
    return Response.json(state.body, { status: state.status });
  });
  const request = (suffix = "") => worker.fetch(new Request(`https://worker.invalid/api/esr-dashboard${suffix}`, { headers: { "cf-connecting-ip": "192.0.2.81" } }), env);
  return { state, puts, calls, keys, request };
}

test("S81 dashboard normalizes the captured ERCOT response and preserves source times", async t => {
  const f = fixture(t), response = await f.request("?url=https://example.invalid");
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(body.timestamp, "2026-09-26T22:30:00.000Z");
  assert.equal(body.source_timestamp, source.lastUpdated);
  assert.equal(body.charging_mw, -226.874);
  assert.equal(body.discharging_mw, 453.375);
  assert.equal(body.net_mw, 226.501);
  assert.equal(body.hour_ago.timestamp, "2026-09-26T21:30:00.000Z");
  assert.equal(body.change_net_mw, body.net_mw - body.hour_ago.net_mw);
  assert.equal(f.calls[0].url, upstream);
  assert.equal(f.calls[0].opts.redirect, "manual");
  assert.equal(f.calls[0].opts.headers.Authorization, undefined);
});

test("S81 dashboard limits each client including cache hits and expires at 60 seconds", async t => {
  const f = fixture(t);
  assert.equal((await f.request()).status, 200);
  assert.equal((await f.request()).headers.get("x-cache"), "HIT");
  assert.equal(f.calls.length, 1);
  assert.equal(f.puts[0].expirationTtl, 60);
  f.state.allowed = false;
  assert.equal((await f.request()).status, 429);
  assert.deepEqual(f.keys, Array(3).fill("192.0.2.81"));
  assert.equal(f.calls.length, 1);
  f.state.allowed = true;
  t.mock.timers.tick(60000);
  assert.equal((await f.request()).headers.get("x-cache"), "MISS");
  assert.equal(f.calls.length, 2);
});

test("S81 dashboard never caches upstream failures or missing readings", async t => {
  const f = fixture(t);
  f.state.status = 503; // Required upstream-failure contract, not a claimed ERCOT incident.
  assert.equal((await f.request()).status, 502);
  assert.equal(f.puts.length, 0);
  f.state.status = 200;
  f.state.body = { ...source, currentDay: { ...source.currentDay, data: [] }, previousDay: { ...source.previousDay, data: [] } };
  assert.equal((await f.request()).status, 502);
  assert.equal(f.puts.length, 0);
  f.state.body = source;
  assert.equal((await f.request()).status, 200);
  assert.equal(f.calls.length, 3);
});

test("S81 missing or incorrectly signed latest readings cannot become zero or a cached older reading", async t => {
  const f = fixture(t);
  for (const change of [{ totalCharging: null }, { totalCharging: 1 }, { totalDischarging: -1 }, { netOutput: null }]) {
    const body = structuredClone(source);
    Object.assign(body.currentDay.data.at(-1), change);
    f.state.body = body;
    assert.equal((await f.request()).status, 502);
    assert.equal(f.puts.length, 0);
  }
});
