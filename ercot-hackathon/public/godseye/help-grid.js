import { zoneName, ctTime } from "./geo.js";

export const HOUR = 3600000;
export const LOAD_ZONES = ["LZ_NORTH", "LZ_HOUSTON", "LZ_SOUTH", "LZ_WEST", "LZ_AEN", "LZ_CPS", "LZ_LCRA", "LZ_RAYBN"];
export const waiting = "Waiting for ERCOT";
export const mwText = value => Number.isFinite(value) ? `${value.toLocaleString("en-US", { maximumFractionDigits: 1 })} MW` : waiting;

export function historyPath(zone, now) {
  const start = Math.floor(now / HOUR) * HOUR;
  const query = new URLSearchParams({ report_id: "NP3-565-CD", zone, start: new Date(start).toISOString(), end: new Date(start + 24 * HOUR).toISOString() });
  return `/v1/signals/history?${query}`;
}

// history: { zone: rows from /v1/signals/history } for the 24 hours starting at the current UTC hour.
export function forecastHours(history, now) {
  const start = Math.floor(now / HOUR) * HOUR;
  const hours = Array.from({ length: 24 }, (_, i) => start + i * HOUR);
  const zones = {};
  for (const zone of LOAD_ZONES) {
    const values = Array(24).fill(null);
    let published = null;
    for (const row of Array.isArray(history?.[zone]) ? history[zone] : []) {
      const at = Date.parse(row.interval_start), i = hours.indexOf(at);
      if (i < 0 || row.unit !== "MW" || Date.parse(row.interval_end) - at !== HOUR) continue;
      // Stale or missing rows stay missing; nothing is filled in.
      values[i] = row.stale === false && Number.isFinite(row.value) && row.value >= 0 ? row.value : null;
      if (values[i] !== null && typeof row.published_at === "string" && row.published_at > (published ?? "")) published = row.published_at;
    }
    // A partial feed cannot establish the zone's own 24-hour peak.
    const peak = values.every(Number.isFinite) ? Math.max(...values) : null;
    zones[zone] = { values, peak, low: peak === null ? null : Math.min(...values), peakHour: peak === null ? null : hours[values.indexOf(peak)], published };
  }
  return { hours, zones };
}

// Map shade: 0 at the zone's 24-hour low, 1 at its own peak, so a flat day still shows its shape.
export const shade = (value, zone) => zone.peak === null || !Number.isFinite(value) ? null : zone.peak === zone.low ? 1 : (value - zone.low) / (zone.peak - zone.low);

// Short peak label for the map; the window is under 24 hours, so weekday and hour are unique.
const PEAK = new Intl.DateTimeFormat("en-US", { timeZone: "America/Chicago", weekday: "short", hour: "numeric", timeZoneName: "short" });
export const peakLabel = (ms) => PEAK.format(ms);

// ERCOT posts publish times in Central prevailing time without an offset.
const CT_WALL = new Intl.DateTimeFormat("en-US", { timeZone: "UTC", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
export function publishedText(stamp) {
  if (typeof stamp !== "string") return null;
  if (/(Z|[+-]\d\d:?\d\d)$/.test(stamp)) return ctTime(stamp);
  const m = /^(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d)/.exec(stamp);
  return m ? `${CT_WALL.format(Date.UTC(m[1], m[2] - 1, m[3], m[4], m[5]))} CT` : null;
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
