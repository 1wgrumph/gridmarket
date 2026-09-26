// ercot-hackathon — Cloudflare Worker proxy for the ERCOT Public Data API
// Secrets (set with `wrangler secret put`): ERCOT_USERNAME, ERCOT_PASSWORD, ERCOT_SUBSCRIPTION_KEY, ERCOT_ESR_SUBSCRIPTION_KEY, MARKET_KEY

import { buildSnapshot } from "./snapshot.js";
import { buildNodes, SP_PATTERN } from "./node.js";
import { SP_ALLOWLIST } from "./sp-allowlist.js";

const TOKEN_URL =
  "https://ercotb2c.b2clogin.com/ercotb2c.onmicrosoft.com/B2C_1_PUBAPI-ROPC-FLOW/oauth2/v2.0/token";
const CLIENT_ID = "fec253ea-0d06-4272-a5e6-b478baeecd70";
const API_BASE = "https://api.ercot.com/api/public-reports";
const TOKEN_KEY = "ercot:id_token";
const TOKEN_TTL = 55 * 60; // ERCOT ID tokens last 60 min and can't be refreshed
const DATA_TTL = 10 * 60; // cache report responses for 10 min

// ESR charging is a separate API product with its own subscription key and base.
const ESR_ROUTE = "/api/report/esr/charging_mw";
const ESR_API_BASE = "https://api.ercot.com/api/public-data";
const ESR_PATH = "/rptesr-m/4_sec_esr_charging_mw";
const ESR_TTL = 5 * 60; // cache ESR responses for 5 min

// Only these five reports plus the ESR route may be proxied; anything else under /api/report/ is 404.
const ALLOWED_REPORTS = new Set([
  "/api/report/np6-905-cd/spp_node_zone_hub",
  "/api/report/np4-190-cd/dam_stlmnt_pnt_prices",
  "/api/report/np3-565-cd/lf_by_model_weather_zone",
  "/api/report/np3-233-cd/hourly_res_outage_cap",
  "/api/report/np6-86-cd/shdw_prices_bnd_trns_const",
]);

// Query params the EDC view sends; nothing else is forwarded to ERCOT.
const EDC_PARAMS = ["deliveryDateFrom", "deliveryDateTo", "hourEndingFrom", "hourEndingTo", "size"];

// Coalesce concurrent snapshot builds per isolate.
let snapshotInflight = null;

const json = (body, status = 200, extra = {}) =>
  new Response(JSON.stringify(body, null, 2), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "access-control-allow-origin": "*",
      ...extra,
    },
  });

function missingSecrets(env) {
  return ["ERCOT_USERNAME", "ERCOT_PASSWORD", "ERCOT_SUBSCRIPTION_KEY"].filter(
    (k) => !env[k]
  );
}

async function getToken(env, force = false) {
  if (!force) {
    const cached = await env.CACHE.get(TOKEN_KEY);
    if (cached) return cached;
  }
  const body = new URLSearchParams({
    username: env.ERCOT_USERNAME,
    password: env.ERCOT_PASSWORD,
    grant_type: "password",
    scope: `openid ${CLIENT_ID} offline_access`,
    client_id: CLIENT_ID,
    response_type: "id_token",
  });
  const res = await fetch(TOKEN_URL, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.id_token) {
    throw new Error(
      `ERCOT token request failed (${res.status}): ${data.error_description || data.error || "no id_token returned"}`
    );
  }
  await env.CACHE.put(TOKEN_KEY, data.id_token, { expirationTtl: TOKEN_TTL });
  return data.id_token;
}

async function ercotGet(env, path, search, opts = {}) {
  const base = opts.base || API_BASE;
  const url = `${base}${path}${search || ""}`;
  const cacheKey = `data:${path}${search || ""}`;
  const hit = await env.CACHE.get(cacheKey);
  if (hit) return json(JSON.parse(hit), 200, { "x-cache": "HIT" });

  if (env.ERCOT_BUDGET) {
    const budget = await env.ERCOT_BUDGET.limit({ key: "ercot" });
    if (!budget.success) return json({ error: "Upstream ERCOT budget exceeded" }, 429);
  }

  const call = async (token) =>
    fetch(url, {
      headers: {
        Authorization: `Bearer ${token}`,
        "Ocp-Apim-Subscription-Key": opts.subKey || env.ERCOT_SUBSCRIPTION_KEY,
        Accept: "application/json",
      },
    });

  let res = await call(await getToken(env));
  if (res.status === 401) res = await call(await getToken(env, true)); // stale token
  const text = await res.text();
  let body;
  try {
    body = JSON.parse(text);
  } catch {
    body = { raw: text };
  }
  if (res.ok) {
    await env.CACHE.put(cacheKey, JSON.stringify(body), { expirationTtl: opts.ttl || DATA_TTL });
  }
  return json(body, res.status, { "x-cache": "MISS" });
}

// Raw JSON fetch used by the snapshot builder
async function ercotJSON(env, path, params = {}, budget = null) {
  const qs = new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)]));
  const url = `${API_BASE}${path}?${qs}`;
  const call = async (forceToken = false) => {
    if (budget && !(await budget.limit({ key: "ercot" })).success) {
      throw new Error("Upstream ERCOT budget exceeded");
    }
    const token = await getToken(env, forceToken);
    return fetch(url, { headers: { Authorization: `Bearer ${token}`, "Ocp-Apim-Subscription-Key": env.ERCOT_SUBSCRIPTION_KEY, Accept: "application/json" } });
  };
  let res = await call();
  if (res.status === 401) res = await call(true);
  for (let attempt = 1; res.status === 429 && attempt <= 4; attempt++) {
    const wait = Number(res.headers.get("retry-after")) * 1000 || 900 * attempt;
    await new Promise((r) => setTimeout(r, Math.min(wait, 4000)));
    res = await call();
  }
  if (!res.ok) throw new Error(`${path} returned ${res.status}`);
  return res.json();
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const p = url.pathname;

    if (request.method === "OPTIONS") {
      return new Response(null, {
        headers: {
          "access-control-allow-origin": "*",
          "access-control-allow-methods": "GET, OPTIONS",
        },
      });
    }

    try {
      // Per-client rate limit on every API route.
      if (p.startsWith("/api/") && env.RATE_LIMITER) {
        const ip = request.headers.get("cf-connecting-ip") || "unknown";
        const limited = await env.RATE_LIMITER.limit({ key: ip });
        if (!limited.success) return json({ error: "Rate limit exceeded" }, 429);
      }

      // Market-key auth for protected routes; health/edc/cached snapshot stay keyless.
      const needsKey =
        p.startsWith("/api/report/") ||
        p === "/api/products" ||
        (p === "/api/snapshot" && url.searchParams.has("fresh"));
      if (needsKey && request.headers.get("x-gridmarket-key") !== env.MARKET_KEY) {
        return json({ error: "Unauthorized" }, 401);
      }

      if (p === "/api/health") {
        const missing = missingSecrets(env);
        return json({
          ok: missing.length === 0,
          worker: "ercot-hackathon",
          secretsMissing: missing,
          tokenCached: Boolean(await env.CACHE.get(TOKEN_KEY)),
          esrKey: Boolean(env.ERCOT_ESR_SUBSCRIPTION_KEY),
        });
      }

      // Public config for the views' market feed; the owner sets MARKET_URL at deploy.
      if (p === "/api/config") {
        return json({ MARKET_URL: env.MARKET_URL || null });
      }

      // The ESR route alone needs the ESR key; every other route ignores it.
      if (p === ESR_ROUTE && !env.ERCOT_ESR_SUBSCRIPTION_KEY) {
        return json({ error: "Worker secrets not set", secretsMissing: ["ERCOT_ESR_SUBSCRIPTION_KEY"] }, 503);
      }

      if (p.startsWith("/api/")) {
        const missing = missingSecrets(env);
        if (missing.length) {
          return json({ error: "Worker secrets not set", secretsMissing: missing }, 503);
        }
      }

      // Live price at one or more settlement points, for the plant drill-down
      if (p === "/api/node") {
        const sps = [...new Set((url.searchParams.get("sp") || "").split(",").map((x) => x.trim().toUpperCase()))].sort();
        if (sps.length > 4 || sps.some((sp) => !SP_PATTERN.test(sp) || !SP_ALLOWLIST.has(sp))) {
          return json({ error: "Pass ?sp=SETTLEMENT_POINT (comma-separated, up to 4 known points)" }, 400);
        }
        const key = "node:v1:" + sps.join(",");
        const hit = await env.CACHE.get(key);
        if (hit) return json(JSON.parse(hit), 200, { "x-cache": "HIT" });
        const out = await buildNodes((path, params) => ercotJSON(env, path, params, env.ERCOT_BUDGET), sps);
        await env.CACHE.put(key, JSON.stringify(out), { expirationTtl: 300 });
        return json(out, 200, { "x-cache": "MISS" });
      }

      // One cached call for the 3D grid diagram
      if (p === "/api/snapshot") {
        const cached = url.searchParams.has("fresh") ? null : await env.CACHE.get("snapshot:v1");
        if (cached) return json(JSON.parse(cached), 200, { "x-cache": "HIT" });
        if (env.ERCOT_BUDGET && !snapshotInflight) {
          const budget = await env.ERCOT_BUDGET.limit({ key: "ercot" });
          if (!budget.success) return json({ error: "Upstream ERCOT budget exceeded" }, 429);
        }
        if (!snapshotInflight) {
          snapshotInflight = (async () => {
            try {
              const snap = await buildSnapshot((path, params) => ercotJSON(env, path, params));
              await env.CACHE.put("snapshot:v1", JSON.stringify(snap), { expirationTtl: 300 });
              return snap;
            } finally {
              snapshotInflight = null;
            }
          })();
        }
        const snap = await snapshotInflight;
        return json(snap, 200, { "x-cache": "MISS" });
      }

      // 2-Day Aggregate Energy Demand Curves (NP3-907-EX)
      if (p === "/api/edc") {
        const fwd = new URLSearchParams();
        for (const k of EDC_PARAMS) {
          const v = url.searchParams.get(k);
          if (v !== null) fwd.set(k, v);
        }
        const qs = fwd.toString();
        return await ercotGet(env, "/np3-907-ex/2d_agg_edc", qs ? `?${qs}` : "");
      }

      // List all EMIL products
      if (p === "/api/products") {
        return await ercotGet(env, "", url.search);
      }

      // ESR charging (separate API product): same auth and limiters, 5 min cache.
      if (p === ESR_ROUTE) {
        return await ercotGet(env, ESR_PATH, url.search, {
          base: ESR_API_BASE,
          subKey: env.ERCOT_ESR_SUBSCRIPTION_KEY,
          ttl: ESR_TTL,
        });
      }

      // Allowlisted reports only: /api/report/<emil-id>/<report>
      if (p.startsWith("/api/report/")) {
        if (!ALLOWED_REPORTS.has(p)) return json({ error: "Not found" }, 404);
        return await ercotGet(env, p.slice("/api/report".length), url.search);
      }

      if (p.startsWith("/api/")) return json({ error: "Not found" }, 404);
      return env.ASSETS.fetch(request);
    } catch (err) {
      return json({ error: err.message }, 502);
    }
  },
};
