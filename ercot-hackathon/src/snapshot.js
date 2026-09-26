// Builds one grid snapshot from several ERCOT Public API reports.
// `get(path, params)` returns parsed ERCOT JSON ({fields, data, _meta}).

const HUBS = ["HB_NORTH", "HB_HOUSTON", "HB_SOUTH", "HB_WEST"];
const WEATHER_ZONES = {
  coast: "Coast", east: "East", farWest: "Far West", north: "North",
  northCentral: "North Central", southCentral: "South Central", southern: "Southern", west: "West",
};

function ctNow() {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-CA", {
      timeZone: "America/Chicago", year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", hourCycle: "h23",
    }).formatToParts(new Date()).map((p) => [p.type, p.value])
  );
  return { date: `${parts.year}-${parts.month}-${parts.day}`, hour: Number(parts.hour), minute: Number(parts.minute) };
}

function rows(res) {
  if (!res || !Array.isArray(res.data)) return [];
  const names = (res.fields || []).map((f) => f.name);
  return res.data.map((r) => (Array.isArray(r) ? Object.fromEntries(names.map((n, i) => [n, r[i]])) : r));
}

const settle = (p) => p.then((v) => ({ ok: true, v })).catch((e) => ({ ok: false, e: String(e.message || e) }));
const round = (n, d = 1) => (n == null || !isFinite(n) ? null : Math.round(n * 10 ** d) / 10 ** d);
const hourOf = (he) => (typeof he === "string" ? Number(he.slice(0, 2)) : Number(he));

export async function buildSnapshot(get) {
  const now = ctNow();
  const today = now.date;
  const heNow = Math.min(24, now.hour + 1); // hour ending in progress

  // Sequential calls: ERCOT rate-limits bursts (429). ercotJSON retries with backoff.
  const demandR = await settle(get("/np6-235-cd/system_wide_demand", { deliveryDateFrom: today, deliveryDateTo: today, size: 200 }));
  const sppR = await settle(get("/np6-905-cd/spp_node_zone_hub", { deliveryDateFrom: today, deliveryDateTo: today, settlementPointType: "HU", size: 1000 }));
  const damR = await settle(get("/np4-190-cd/dam_stlmnt_pnt_prices", { deliveryDateFrom: today, deliveryDateTo: today, settlementPoint: "HB_NORTH", size: 30 }));
  const adderR = await settle(get("/np6-323-cd/rt_price_adder_sced", { size: 12 }));
  const windR = await settle(get("/np4-732-cd/wpp_hrly_avrg_actl_fcast", { deliveryDateFrom: today, deliveryDateTo: today, size: 24 }));
  const solarR = await settle(get("/np4-737-cd/spp_hrly_avrg_actl_fcast", { deliveryDateFrom: today, deliveryDateTo: today, size: 24 }));
  const wxR = await settle(get("/np4-722-cd/weather_assumptions", { deliveryDateFrom: today, deliveryDateTo: today, size: 300 }));

  const out = { asOf: new Date().toISOString(), ct: now, heNow, errors: {} };
  const fail = (k, r) => { if (!r.ok) out.errors[k] = r.e; return r.ok; };

  // Demand: latest 15-min interval today
  if (fail("demand", demandR)) {
    const d = rows(demandR.v).filter((r) => r.demand != null).sort((a, b) => a.timeEnding.localeCompare(b.timeEnding));
    const last = d[d.length - 1];
    const peak = d.reduce((m, r) => Math.max(m, r.demand), 0);
    out.demand = last ? { mw: round(last.demand, 0), timeEnding: last.timeEnding, todayPeak: round(peak, 0),
      series: d.slice(-16).map((r) => round(r.demand, 0)) } : null;
  }

  // Real-time hub prices: latest interval per hub
  if (fail("spp", sppR)) {
    const all = rows(sppR.v).filter((r) => HUBS.includes(r.settlementPoint));
    const key = (r) => r.deliveryHour * 10 + r.deliveryInterval;
    out.hubs = HUBS.map((hub) => {
      const h = all.filter((r) => r.settlementPoint === hub).sort((a, b) => key(a) - key(b));
      const last = h[h.length - 1];
      return last ? { hub, price: round(last.settlementPointPrice, 2), hour: last.deliveryHour, interval: last.deliveryInterval,
        series: h.slice(-12).map((r) => round(r.settlementPointPrice, 2)) } : { hub, price: null };
    });
  }

  // Day-ahead HB_NORTH for the hour in progress, and DART
  if (fail("dam", damR)) {
    const d = rows(damR.v);
    const hit = d.find((r) => hourOf(r.hourEnding) === heNow);
    const rtNorth = out.hubs?.find((h) => h.hub === "HB_NORTH")?.price;
    out.dam = { hub: "HB_NORTH", hourEnding: heNow, price: round(hit?.settlementPointPrice, 2),
      dart: hit && rtNorth != null ? round(rtNorth - hit.settlementPointPrice, 2) : null,
      dayPeak: round(Math.max(...d.map((r) => r.settlementPointPrice)), 2) };
  }

  // SCED system lambda, reliability adder, online reserve headroom
  if (fail("adders", adderR)) {
    const a = rows(adderR.v).sort((x, y) => y.SCEDTimestamp.localeCompare(x.SCEDTimestamp));
    const last = a[0];
    if (last) {
      out.sced = { timestamp: last.SCEDTimestamp, systemLambda: round(last.systemLambda, 2),
        reliabilityAdder: round(last.RTRDPA, 2), onlineHSL: round(last.RTOLHSL, 0), onlineLSL: round(last.RTOLLSL, 0),
        lambdaSeries: a.slice(0, 12).reverse().map((r) => round(r.systemLambda, 2)) };
      if (out.demand?.mw) {
        out.sced.headroomMW = round(last.RTOLHSL - out.demand.mw, 0);
        out.sced.headroomPct = round(((last.RTOLHSL - out.demand.mw) / out.demand.mw) * 100, 1);
      }
    }
  }

  // Wind & solar: latest completed hour with actuals, plus forecast for that hour
  const renew = (r, fcKey, label) => {
    const list = rows(r.v).sort((a, b) => a.hourEnding - b.hourEnding);
    const done = list.filter((x) => x.genSystemWide != null);
    const last = done[done.length - 1];
    const fcNow = list.find((x) => x.hourEnding === heNow);
    return {
      source: label,
      actualMW: round(last?.genSystemWide, 0), actualHE: last?.hourEnding ?? null,
      forecastAtActualMW: round(last?.[fcKey], 0),
      errorMW: last && last[fcKey] != null ? round(last.genSystemWide - last[fcKey], 0) : null,
      forecastNowMW: round(fcNow?.[fcKey], 0),
      capacityMW: round(last?.HSLSystemWide ?? last?.COPHSLSystemWide, 0),
      series: list.map((x) => round(x.genSystemWide ?? x[fcKey], 0)),
    };
  };
  if (fail("wind", windR)) out.wind = renew(windR, "STWPFSystemWide", "wind");
  if (fail("solar", solarR)) out.solar = renew(solarR, "STPPFSystemWide", "solar");

  // Weather assumptions (°F) for the hour in progress
  if (fail("weather", wxR)) {
    const w = rows(wxR.v);
    const same = w.filter((r) => hourOf(r.hourEnding) === now.hour);
    const hit = same[same.length - 1] || w[w.length - 1];
    if (hit) {
      const zones = Object.entries(WEATHER_ZONES).map(([k, name]) => ({ zone: name, tempF: round(hit[k], 1) }));
      const temps = zones.map((z) => z.tempF).filter((t) => t != null);
      out.weather = { hourEnding: hit.hourEnding, zones, avgF: round(temps.reduce((s, t) => s + t, 0) / temps.length, 1),
        maxF: Math.max(...temps), minF: Math.min(...temps) };
    }
  }

  // Baseline decision checks (simple rules, NOT Jev). Same shape Jev will return: probability in [0,1].
  const clamp = (x) => Math.max(0.02, Math.min(0.98, x));
  const logistic = (z) => 1 / (1 + Math.exp(-z));
  const checks = [];
  if (out.sced?.headroomPct != null) {
    const p = clamp(logistic((12 - out.sced.headroomPct) / 3 + (out.sced.reliabilityAdder > 0 ? 1.5 : 0)));
    checks.push({ id: "scarcity-2h", question: "P(HB_NORTH RT > $150 within 2h)", p: round(p, 2),
      inputs: { headroomPct: out.sced.headroomPct, reliabilityAdder: out.sced.reliabilityAdder } });
  }
  if (out.dam?.dart != null) {
    const p = clamp(logistic(out.dam.dart / 8));
    checks.push({ id: "dart-north", question: `P(RT > DA at HB_NORTH, HE${heNow})`, p: round(p, 2),
      inputs: { dart: out.dam.dart, daPrice: out.dam.price } });
  }
  const netErr = (out.wind?.errorMW ?? 0) + (out.solar?.errorMW ?? 0);
  if (out.wind?.errorMW != null || out.solar?.errorMW != null) {
    const p = clamp(logistic(-netErr / 800));
    checks.push({ id: "renew-shortfall", question: "P(renewables under-deliver next hour > 1 GW)", p: round(p, 2),
      inputs: { windErrorMW: out.wind?.errorMW, solarErrorMW: out.solar?.errorMW } });
  }
  const route = (p) => (p >= 0.8 ? "alert" : p >= 0.5 ? "review" : "log");
  out.checks = checks.map((c) => ({ ...c, route: route(c.p), engine: "baseline" }));
  return out;
}
