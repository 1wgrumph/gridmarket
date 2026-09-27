import { zoneName, ctTime } from "./geo.js";

export const HOUR = 3600000;
export const LOAD_ZONES = ["LZ_NORTH", "LZ_HOUSTON", "LZ_SOUTH", "LZ_WEST", "LZ_AEN", "LZ_CPS", "LZ_LCRA", "LZ_RAYBN"];
export const waiting = "Waiting for ERCOT";
export const mwText = value => Number.isFinite(value) ? `${value.toLocaleString("en-US", { maximumFractionDigits: 1 })} MW` : waiting;
export const noData = "No data";
// Scrubber values read per hour: missing is "No data", never 0. Prices keep their
// sign (negative real-time prices are real); loads are screened at parse time.
export const hourText = (value, unit) => {
  if (!Number.isFinite(value)) return noData;
  if (unit === "$/MWh") return `${value < 0 ? "−$" : "$"}${Math.abs(value).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}/MWh`;
  return `${value.toLocaleString("en-US", { maximumFractionDigits: 1 })} MW`;
};

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
    const values = Array(24).fill(null), publishedByHour = Array(24).fill(null);
    let published = null;
    for (const row of Array.isArray(history?.[zone]) ? history[zone] : []) {
      const at = Date.parse(row.interval_start), i = hours.indexOf(at);
      if (i < 0 || row.unit !== "MW" || Date.parse(row.interval_end) - at !== HOUR) continue;
      // Stale or missing rows stay missing; nothing is filled in.
      values[i] = row.stale === false && Number.isFinite(row.value) && row.value >= 0 ? row.value : null;
      if (values[i] !== null && typeof row.published_at === "string") {
        publishedByHour[i] = row.published_at;
        if (row.published_at > (published ?? "")) published = row.published_at;
      }
    }
    // A partial feed cannot establish the zone's own 24-hour peak.
    const peak = values.every(Number.isFinite) ? Math.max(...values) : null;
    zones[zone] = { values, publishedByHour, peak, low: peak === null ? null : Math.min(...values), peakHour: peak === null ? null : hours[values.indexOf(peak)], published };
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

// X4: the scrubber runs 24 hours back and 24 forward. Slots before NOW_INDEX show
// Actual values from the snapshot reports; NOW_INDEX (the current UTC hour) and
// later show the Forecast, so the future half keeps S81c's exact meaning.
export const PAST_HOURS = 24, SCRUB_HOURS = 48, NOW_INDEX = 24;
export const HUB_REPORT = "SNAPSHOT-HUBS", DEMAND_REPORT = "SNAPSHOT-DEMAND", DEMAND_ZONE = "ERCOT";
// Hub prices stand in for their same-named load zones; the four municipal zones
// have no hub and read "No data" in the past.
export const HUB_FOR_ZONE = { LZ_NORTH: "HB_NORTH", LZ_HOUSTON: "HB_HOUSTON", LZ_SOUTH: "HB_SOUTH", LZ_WEST: "HB_WEST" };
export const ACTUAL_HUBS = ["HB_NORTH", "HB_HOUSTON", "HB_SOUTH", "HB_WEST"];

export function actualPath(report, zone, now) {
  const end = Math.floor(now / HOUR) * HOUR;
  const query = new URLSearchParams({ report_id: report, zone, start: new Date(end - PAST_HOURS * HOUR).toISOString(), end: new Date(end).toISOString() });
  return `/v1/signals/history?${query}`;
}

export function scrubHours(now) {
  const current = Math.floor(now / HOUR) * HOUR;
  return { hours: Array.from({ length: SCRUB_HOURS }, (_, i) => current + (i - NOW_INDEX) * HOUR), nowIndex: NOW_INDEX };
}
export const hourKind = i => i < NOW_INDEX ? "Actual" : "Forecast";
export const hourOffset = i => i === NOW_INDEX ? "Now" : i < NOW_INDEX ? `${NOW_INDEX - i} h ago` : `in ${i - NOW_INDEX} h`;

// history: { zone: rows from /v1/signals/history } for the 24 hours before the
// current UTC hour. Past hours show the latest published value per hour: the
// backend ages every past interval stale (its age counts the interval itself),
// so the stale flag is meaningless here and published values are taken as-is.
// Missing, unpublished, unit-mismatched and non-finite rows stay missing.
export function pastHours(history, now, unit) {
  const end = Math.floor(now / HOUR) * HOUR, start = end - PAST_HOURS * HOUR;
  const hours = Array.from({ length: PAST_HOURS }, (_, i) => start + i * HOUR);
  const zones = {};
  const feeds = history && typeof history === "object" ? history : {};
  for (const zone of Object.keys(feeds)) {
    const values = Array(PAST_HOURS).fill(null), publishedByHour = Array(PAST_HOURS).fill(null), latest = Array(PAST_HOURS).fill(-1);
    let published = null;
    for (const row of Array.isArray(feeds[zone]) ? feeds[zone] : []) {
      const at = Date.parse(row.interval_start), i = Math.floor((at - start) / HOUR);
      if (!Number.isFinite(at) || i < 0 || i >= PAST_HOURS || row.unit !== unit || !Number.isFinite(row.value)) continue;
      if (unit === "MW" && row.value < 0) continue; // loads can't be negative; prices can
      if (typeof row.published_at !== "string" || !row.published_at || at <= latest[i]) continue;
      latest[i] = at; values[i] = row.value; publishedByHour[i] = row.published_at;
      if (row.published_at > (published ?? "")) published = row.published_at;
    }
    // A partial feed cannot establish the zone's own past-24-hour range.
    const peak = values.every(Number.isFinite) ? Math.max(...values) : null;
    zones[zone] = { values, publishedByHour, peak, low: peak === null ? null : Math.min(...values), peakHour: peak === null ? null : hours[values.indexOf(peak)], published };
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
