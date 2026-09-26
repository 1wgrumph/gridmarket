// market-feed.js — GridMarket activity strip and router alerts for the ERCOT views.
// Reads the market by cross-origin GET; on any failure the view keeps its ERCOT content.

const TIMEOUT_MS = 20_000;

const esc = (v) =>
  String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const list = (v, key) => (Array.isArray(v) ? v : Array.isArray(v?.[key]) ? v[key] : []);

export async function fetchMarket(baseUrl, fetchImpl = fetch) {
  const base = String(baseUrl).replace(/\/+$/, "");
  const signal = AbortSignal.timeout(TIMEOUT_MS);
  const get = async (path) => {
    const res = await fetchImpl(`${base}${path}`, { method: "GET", signal });
    if (!res.ok) throw new Error(`${path} ${res.status}`);
    return res.json();
  };
  try {
    const [activity, router] = await Promise.all([get("/v1/market/activity"), get("/v1/router")]);
    return { activity, router };
  } catch {
    return { offline: true };
  }
}

export function renderFeed(el, data) {
  if (!data || data.offline) return;
  const items = list(data.activity, "items").slice(0, 8);
  const alerts = list(data.router, "results").filter((r) => r.band === "alert");
  el.innerHTML = `
    <div class="mf-title">Market activity</div>
    <ul class="mf-strip">${items.map((i) => `<li><b>${esc(i.name)}</b> ${esc(i.text)}</li>`).join("") || "<li>No trades yet</li>"}</ul>
    <div class="mf-title">Router alerts · baseline rules</div>
    <ul class="mf-alerts">${alerts.map((r) => `<li>${esc(r.check_id)} <b>${esc(Math.round(r.probability * 100))}%</b></li>`).join("") || "<li>No alert-band checks</li>"}</ul>`;
}

// Wires one view: reads MARKET_URL from the Worker, points the dashboard link at it, renders the feed.
export async function mountFeed(el, link) {
  const cfg = await fetch("/api/config").then((r) => r.json()).catch(() => ({}));
  let url;
  try {
    url = new URL(cfg.MARKET_URL);
  } catch {
    return;
  }
  if (!/^https?:$/.test(url.protocol)) return;
  link.href = url.href;
  link.hidden = false;
  const data = await fetchMarket(url.href);
  renderFeed(el, data);
  el.hidden = Boolean(data.offline);
}
