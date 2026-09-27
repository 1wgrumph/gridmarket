// "Help the grid": upcoming hours per ERCOT forecast zone when stored battery power helps most.
// Built only from ERCOT data: zone load forecast (NP3-560-CD), day-ahead zone prices (NP4-190-CD),
// and system wind and solar forecasts (NP4-732-CD, NP4-737-CD). Missing inputs are reported as
// unavailable; nothing is filled in.

const ZONES = [
  { id: "houston", name: "Houston", lz: "LZ_HOUSTON", col: "houston" },
  { id: "north", name: "North", lz: "LZ_NORTH", col: "north" },
  { id: "south", name: "South", lz: "LZ_SOUTH", col: "south" },
  { id: "west", name: "West", lz: "LZ_WEST", col: "west" },
];
const HORIZON = 24;        // hours ahead
const WINDOW_SCORE = 70;   // score (0-100) at or above which an hour counts as a help window

function ctParts(d = new Date()) {
  const p = Object.fromEntries(new Intl.DateTimeFormat("en-CA", { timeZone: "America/Chicago", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" })
    .formatToParts(d).map((x) => [x.type, x.value]));
  return { date: `${p.year}-${p.month}-${p.day}`, hour: Number(p.hour), minute: Number(p.minute) };
}
function addDays(date, n) {
  const d = new Date(date + "T12:00:00Z"); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10);
}
function rows(res) {
  if (!res || !Array.isArray(res.data)) return [];
  const names = (res.fields || []).map((f) => f.name);
  return res.data.map((r) => (Array.isArray(r) ? Object.fromEntries(names.map((n, i) => [n, r[i]])) : r));
}
const he = (v) => Number(String(v).split(":")[0]);
const key = (date, h) => `${date}|${h}`;
const r0 = (n) => (n == null || !isFinite(n) ? null : Math.round(n));
const r2 = (n) => (n == null || !isFinite(n) ? null : Math.round(n * 100) / 100);
const settle = (p) => p.then((v) => ({ ok: true, v })).catch((e) => ({ ok: false, e: String(e.message || e) }));

export async function buildHelp(get) {
  const now = ctParts();
  const today = now.date, tomorrow = addDays(today, 1);
  const out = { asOf: new Date().toISOString(), ct: now, horizonHours: HORIZON, windowScore: WINDOW_SCORE, zones: [], unavailable: {}, method:
    "Score 0-100 per zone-hour: half from ERCOT net load (load forecast minus wind and solar forecasts), half from the zone's day-ahead price, each scaled across the next 24 hours. A help window is a run of hours scoring 70 or more." };

  // Sequential: ERCOT rate-limits bursts.
  const lf = await settle(get("/np3-560-cd/7d_load_fcast_by_fzn", { deliveryDateFrom: today, deliveryDateTo: tomorrow, size: 48 }));
  const wind = await settle(get("/np4-732-cd/wpp_hrly_avrg_actl_fcast", { deliveryDateFrom: today, deliveryDateTo: tomorrow, size: 48 }));
  const solar = await settle(get("/np4-737-cd/spp_hrly_avrg_actl_fcast", { deliveryDateFrom: today, deliveryDateTo: tomorrow, size: 48 }));
  const da = {};
  for (const z of ZONES) {
    da[z.id] = await settle(get("/np4-190-cd/dam_stlmnt_pnt_prices", { deliveryDateFrom: today, deliveryDateTo: tomorrow, settlementPoint: z.lz, size: 60 }));
  }

  // Load forecast: keep only the latest posting.
  const load = {};
  if (lf.ok) {
    const lr = rows(lf.v); const latest = lr.reduce((m, r) => (r.postedDatetime > m ? r.postedDatetime : m), "");
    for (const r of lr.filter((r) => r.postedDatetime === latest)) load[key(r.deliveryDate, he(r.hourEnding))] = r;
    out.loadPosted = latest;
  } else out.unavailable.loadForecast = lf.e;
  const renew = (res, col, label) => {
    const m = {}; if (!res.ok) { out.unavailable[label] = res.e; return m; }
    const rr = rows(res.v); const latest = rr.reduce((a, r) => (r.postedDatetime > a ? r.postedDatetime : a), "");
    for (const r of rr.filter((r) => r.postedDatetime === latest)) m[key(r.deliveryDate, Number(r.hourEnding))] = r.genSystemWide ?? r[col];
    return m;
  };
  const windF = renew(wind, "STWPFSystemWide", "windForecast");
  const solarF = renew(solar, "STPPFSystemWide", "solarForecast");

  // The next 24 hour-endings starting with the hour in progress.
  const hours = [];
  for (let i = 0; i < HORIZON; i++) {
    const abs = now.hour + 1 + i; const date = abs > 24 ? tomorrow : today; const h = ((abs - 1) % 24) + 1;
    const L = load[key(date, h)]; const w = windF[key(date, h)], s = solarF[key(date, h)];
    const net = L && w != null && s != null ? L.systemTotal - w - s : null;
    hours.push({ date, he: h, label: `${String(h - 1).padStart(2, "0")}:00`, load: r0(L?.systemTotal), wind: r0(w), solar: r0(s), netLoad: r0(net), L });
  }
  const scale = (vals) => { const v = vals.filter((x) => x != null); const mn = Math.min(...v), mx = Math.max(...v); return (x) => (x == null || !v.length ? null : mx === mn ? 0.5 : (x - mn) / (mx - mn)); };
  const netScale = scale(hours.map((h) => h.netLoad));

  for (const z of ZONES) {
    const zp = {};
    if (da[z.id].ok) for (const r of rows(da[z.id].v)) zp[key(r.deliveryDate, he(r.hourEnding))] = r.settlementPointPrice;
    else out.unavailable[`da_${z.id}`] = da[z.id].e;
    const priceScale = scale(hours.map((h) => zp[key(h.date, h.he)] ?? null));
    const series = hours.map((h) => {
      const price = zp[key(h.date, h.he)] ?? null, zl = h.L ? h.L[z.col] : null;
      const a = netScale(h.netLoad), b = priceScale(price);
      const score = a == null && b == null ? null : a == null ? b : b == null ? a : 0.5 * a + 0.5 * b;
      return { date: h.date, he: h.he, label: h.label, zoneLoad: r0(zl), netLoad: h.netLoad, daPrice: r2(price), score: score == null ? null : Math.round(score * 100),
        basis: a != null && b != null ? "net load + day-ahead price" : a != null ? "net load only (day-ahead price not posted)" : b != null ? "day-ahead price only (forecast missing)" : "unavailable" };
    });
    // Contiguous windows at or above the threshold
    const windows = []; let cur = null;
    for (const s of series) {
      if (s.score != null && s.score >= WINDOW_SCORE) {
        if (!cur) cur = { start: s.label, startDate: s.date, hours: [] };
        cur.hours.push(s);
      } else if (cur) { windows.push(cur); cur = null; }
    }
    if (cur) windows.push(cur);
    const shaped = windows.map((w) => {
      const last = w.hours[w.hours.length - 1];
      const prices = w.hours.map((x) => x.daPrice).filter((x) => x != null);
      return { start: w.start, end: `${String(last.he % 24).padStart(2, "0")}:00`, date: w.startDate, hours: w.hours.length,
        peakScore: Math.max(...w.hours.map((x) => x.score)), avgDaPrice: prices.length ? r2(prices.reduce((a, b) => a + b, 0) / prices.length) : null,
        peakZoneLoad: Math.max(...w.hours.map((x) => x.zoneLoad ?? 0)) || null, basis: w.hours[0].basis };
    }).sort((a, b) => b.peakScore - a.peakScore || a.date.localeCompare(b.date) || a.start.localeCompare(b.start));
    const nowRow = series[0];
    out.zones.push({ id: z.id, name: z.name, settlementPoint: z.lz,
      now: { zoneLoad: nowRow.zoneLoad, daPrice: nowRow.daPrice, score: nowRow.score, basis: nowRow.basis },
      next: shaped[0] || null, windows: shaped, series: series.map(({ date, he, label, zoneLoad, daPrice, score }) => ({ date, he, label, zoneLoad, daPrice, score })) });
  }
  out.system = { netLoadNext: hours.map((h) => ({ date: h.date, he: h.he, load: h.load, wind: h.wind, solar: h.solar, netLoad: h.netLoad })) };
  return out;
}
