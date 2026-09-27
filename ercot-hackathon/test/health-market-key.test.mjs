// S76b red test: Worker /api/health is not ok when MARKET_KEY is unset (R6-13).
// Reporting only: keyless routes must keep serving 200 without the key.
import test from "node:test";
import assert from "node:assert/strict";
import worker from "../src/index.js";

function envWithoutMarketKey() {
  const store = new Map();
  return {
    ERCOT_USERNAME: "test-user",
    ERCOT_PASSWORD: "test-password",
    ERCOT_SUBSCRIPTION_KEY: "test-subscription-key",
    CACHE: {
      get: async (key) => store.get(key) ?? null,
      put: async (key, value) => void store.set(key, value),
    },
  };
}

test("R6-13 /api/health reports MARKET_KEY missing instead of ok:true", async () => {
  const response = await worker.fetch(new Request("https://worker.invalid/api/health"), envWithoutMarketKey());
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(body.ok, false);
  assert.ok(body.secretsMissing.includes("MARKET_KEY"));
});

test("R6-13 health stays keyless and ok with MARKET_KEY set", async () => {
  const env = { ...envWithoutMarketKey(), MARKET_KEY: "test-market-key" };
  const response = await worker.fetch(new Request("https://worker.invalid/api/health"), env);
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(body.ok, true);
  assert.deepEqual(body.secretsMissing, []);
});
