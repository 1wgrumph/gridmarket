// Live prices for individual ERCOT settlement points (resource nodes).
// `get(path, params)` returns parsed ERCOT JSON ({fields, data}); it retries on 429.

export const SP_PATTERN = /^[A-Z0-9_.]{2,40}$/i;

function ctNow() {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-CA", {
      timeZone: "America/Chicago", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", hourCycle: "h23",
    }).formatToParts(new Date()).map((p) => [p.type, p.value])
  );
  return { date: `${parts.year}-${parts.month}-${parts.day}`, hour: Number(parts.hour) };
}

function rows(res) {
  if (!res || !Array.isArray(res.data)) return [];
  const names = (res.fields || []).map((f) => f.name);
  return res.data.map((r) => (Array.isArray(r) ? Object.fromEntries(names.map((n, i) => [n, r[i]])) : r));
}

const round2 = (n) => (n == null || !isFinite(n) ? null : Math.round(n * 100) / 100);
const hourOf = (he) => (typeof he === "string" ? Number(he.slice(0, 2)) : Number(he));

export async function buildNodes(get, points) {
  const { date, hour } = ctNow();
  const heNow = Math.min(24, hour + 1);
  const out = { asOf: new Date().toISOString(), date, heNow, nodes: [], errors: {} };

  // Sequential on purpose: ERCOT rate-limits bursts.
  for (const sp of points) {
    const node = { sp, rt: null, da: null };
    try {
      const rt = rows(await get("/np6-905-cd/spp_node_zone_hub", { deliveryDateFrom: date, deliveryDateTo: date, settlementPoint: sp, size: 200 }))
        .sort((a, b) => a.deliveryHour * 10 + a.deliveryInterval - (b.deliveryHour * 10 + b.deliveryInterval));
      const last = rt[rt.length - 1];
      if (last) {
        node.rt = { price: round2(last.settlementPointPrice), hour: last.deliveryHour, interval: last.deliveryInterval,
          type: last.settlementPointType, series: rt.slice(-24).map((r) => round2(r.settlementPointPrice)) };
      }
    } catch (e) { out.errors[`${sp}:rt`] = String(e.message || e); }
    try {
      const da = rows(await get("/np4-190-cd/dam_stlmnt_pnt_prices", { deliveryDateFrom: date, deliveryDateTo: date, settlementPoint: sp, size: 30 }));
      const hit = da.find((r) => hourOf(r.hourEnding) === heNow);
      if (hit) node.da = { price: round2(hit.settlementPointPrice), he: heNow, dayMax: round2(Math.max(...da.map((r) => r.settlementPointPrice))) };
    } catch (e) { out.errors[`${sp}:da`] = String(e.message || e); }
    out.nodes.push(node);
  }
  return out;
}
