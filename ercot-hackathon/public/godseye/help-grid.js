import { zoneName, ctTime } from "./geo.js";

export const HOUR = 3600000;
export const LOAD_ZONES = ["LZ_NORTH", "LZ_HOUSTON", "LZ_SOUTH", "LZ_WEST", "LZ_AEN", "LZ_CPS", "LZ_LCRA", "LZ_RAYBN"];
export const waiting = "Waiting for ERCOT";
export const mwText = value => Number.isFinite(value) ? `${value.toLocaleString("en-US", { maximumFractionDigits: 1 })} MW` : waiting;

export function forecastHours(signals, now) {
  const start = Math.floor(now / HOUR) * HOUR;
  const hours = Array.from({ length: 24 }, (_, i) => start + i * HOUR);
  const zones = Object.fromEntries(LOAD_ZONES.map(zone => [zone, { values: Array(24).fill(null), peak: null }]));
  const latest = new Map();
  for (const s of Array.isArray(signals) ? signals : []) {
    if (s.report_id !== "NP3-565-CD" || !zones[s.zone] || s.unit !== "MW" || s.interval_minutes !== 60) continue;
    const i = hours.indexOf(Date.parse(s.interval_start));
    if (i < 0) continue;
    const key = `${s.zone}:${i}`, fetched = Date.parse(s.fetched_at);
    if (!Number.isFinite(fetched) || (latest.has(key) && latest.get(key) > fetched)) continue;
    latest.set(key, fetched);
    zones[s.zone].values[i] = s.stale === false && Number.isFinite(s.value) && s.value >= 0 ? s.value : null;
  }
  for (const zone of Object.values(zones)) {
    // A partial feed cannot establish the zone's own 24-hour peak.
    if (zone.values.every(Number.isFinite)) zone.peak = Math.max(...zone.values);
  }
  return { hours, zones };
}

export function helpWindows(predictions, now) {
  const rows = (Array.isArray(predictions) ? predictions : []).filter(p =>
    LOAD_ZONES.includes(p.zone) && Number.isFinite(p.score) &&
    ["HIGH", "VERY HIGH", "VERY_HIGH", "CRITICAL", "EXTREME", "EMERGENCY"].includes(String(p.level).toUpperCase()) &&
    Date.parse(p.delivery_hour) >= now && Date.parse(p.delivery_hour) < now + 24 * HOUR);
  const windows = [];
  for (const zone of LOAD_ZONES) {
    const times = [...new Set(rows.filter(p => p.zone === zone).map(p => Date.parse(p.delivery_hour)))].sort((a, b) => a - b);
    let last;
    for (const start of times) {
      if (last && last.end === start) last.end += HOUR;
      else { last = { zone, start, end: start + HOUR }; windows.push(last); }
    }
  }
  return windows;
}

export function windowText(window) {
  // Dates and zone abbreviations remain visible across midnight and DST changes.
  return `Homes help: ${zoneName(window.zone)} ${ctTime(new Date(window.start).toISOString())}–${ctTime(new Date(window.end).toISOString())}`;
}
