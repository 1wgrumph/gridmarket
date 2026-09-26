// ercot-hackathon — Cloudflare Worker proxy for the ERCOT Public Data API
// Secrets (set with `wrangler secret put`): ERCOT_USERNAME, ERCOT_PASSWORD, ERCOT_SUBSCRIPTION_KEY

import { buildSnapshot } from "./snapshot.js";

const TOKEN_URL =
  "https://ercotb2c.b2clogin.com/ercotb2c.onmicrosoft.com/B2C_1_PUBAPI-ROPC-FLOW/oauth2/v2.0/token";
const CLIENT_ID = "fec253ea-0d06-4272-a5e6-b478baeecd70";
const API_BASE = "https://api.ercot.com/api/public-reports";
const TOKEN_KEY = "ercot:id_token";
const TOKEN_TTL = 55 * 60; // ERCOT ID tokens last 60 min and can't be refreshed
const DATA_TTL = 10 * 60; // cache report responses for 10 min

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

async function ercotGet(env, path, search) {
  const url = `${API_BASE}${path}${search || ""}`;
  const cacheKey = `data:${path}${search || ""}`;
  const hit = await env.CACHE.get(cacheKey);
  if (hit) return json(JSON.parse(hit), 200, { "x-cache": "HIT" });

  const call = async (token) =>
    fetch(url, {
      headers: {
        Authorization: `Bearer ${token}`,
        "Ocp-Apim-Subscription-Key": env.ERCOT_SUBSCRIPTION_KEY,
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
    await env.CACHE.put(cacheKey, JSON.stringify(body), { expirationTtl: DATA_TTL });
  }
  return json(body, res.status, { "x-cache": "MISS" });
}

// Raw JSON fetch used by the snapshot builder
async function ercotJSON(env, path, params = {}) {
  const qs = new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)]));
  const url = `${API_BASE}${path}?${qs}`;
  const call = async (token) =>
    fetch(url, { headers: { Authorization: `Bearer ${token}`, "Ocp-Apim-Subscription-Key": env.ERCOT_SUBSCRIPTION_KEY, Accept: "application/json" } });
  let res = await call(await getToken(env));
  if (res.status === 401) res = await call(await getToken(env, true));
  for (let attempt = 1; res.status === 429 && attempt <= 4; attempt++) {
    const wait = Number(res.headers.get("retry-after")) * 1000 || 900 * attempt;
    await new Promise((r) => setTimeout(r, Math.min(wait, 4000)));
    res = await call(await getToken(env));
  }
  if (!res.ok) throw new Error(`${path} returned ${res.status}`);
  return res.json();
}

// only allow safe path segments like np3-907-ex / 2d_agg_edc
const SEG = /^[a-z0-9_-]+$/i;

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
      if (p === "/api/health") {
        const missing = missingSecrets(env);
        return json({
          ok: missing.length === 0,
          worker: "ercot-hackathon",
          secretsMissing: missing,
          tokenCached: Boolean(await env.CACHE.get(TOKEN_KEY)),
        });
      }

      if (p.startsWith("/api/")) {
        const missing = missingSecrets(env);
        if (missing.length) {
          return json({ error: "Worker secrets not set", secretsMissing: missing }, 503);
        }
      }

      // One cached call for the 3D grid diagram
      if (p === "/api/snapshot") {
        const cached = url.searchParams.has("fresh") ? null : await env.CACHE.get("snapshot:v1");
        if (cached) return json(JSON.parse(cached), 200, { "x-cache": "HIT" });
        const snap = await buildSnapshot((path, params) => ercotJSON(env, path, params));
        await env.CACHE.put("snapshot:v1", JSON.stringify(snap), { expirationTtl: 300 });
        return json(snap, 200, { "x-cache": "MISS" });
      }

      // 2-Day Aggregate Energy Demand Curves (NP3-907-EX)
      if (p === "/api/edc") {
        return await ercotGet(env, "/np3-907-ex/2d_agg_edc", url.search);
      }

      // List all EMIL products
      if (p === "/api/products") {
        return await ercotGet(env, "", url.search);
      }

      // Generic: /api/report/<emil-id>/<report> e.g. /api/report/np3-907-ex/2d_agg_esc
      const m = p.match(/^\/api\/report\/([^/]+)(?:\/([^/]+))?$/);
      if (m && SEG.test(m[1]) && (!m[2] || SEG.test(m[2]))) {
        return await ercotGet(env, `/${m[1]}${m[2] ? "/" + m[2] : ""}`, url.search);
      }

      if (p.startsWith("/api/")) return json({ error: "Not found" }, 404);
      return env.ASSETS.fetch(request);
    } catch (err) {
      return json({ error: err.message }, 502);
    }
  },
};
