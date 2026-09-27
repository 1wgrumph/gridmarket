// Prints one buildSnapshot() JSON document using spec-shaped stub inputs.
// No network. FIXED_NOW (ISO) pins the clock for reproducible fixtures.
import { buildSnapshot } from "../src/snapshot.js";

if (process.env.FIXED_NOW) {
  const RealDate = Date;
  const FIXED = RealDate.parse(process.env.FIXED_NOW);
  globalThis.Date = class extends RealDate {
    constructor(...a) { super(...(a.length ? a : [FIXED])); }
    static now() { return FIXED; }
  };
}

const f = (name) => ({ name, label: name, dataType: "VARCHAR" });
const report = (fields, data) => ({
  _meta: { totalRecords: data.length, pageSize: data.length, totalPages: 1, currentPage: 1 },
  report: {},
  fields,
  data,
});
const T = "2026-09-26";
const he = (n) => String(n).padStart(2, "0") + ":00";
const ZONES = ["coast", "east", "farWest", "north", "northCentral", "southCentral", "southern", "west"];
const PAYLOADS = {
  "/np6-235-cd/system_wide_demand": report(
    [f("deliveryDate"), f("timeEnding"), f("demand"), f("DSTFlag")],
    [[T, "09:45", 70100, false], [T, "10:00", 70234, false]]),
  "/np6-905-cd/spp_node_zone_hub": report(
    [f("deliveryDate"), f("deliveryHour"), f("deliveryInterval"), f("settlementPoint"),
     f("settlementPointType"), f("settlementPointPrice"), f("DSTFlag")],
    [[T, 10, 1, "HB_NORTH", "HU", 51.25, false], [T, 10, 1, "HB_HOUSTON", "HU", 48.5, false]]),
  "/np4-190-cd/dam_stlmnt_pnt_prices": report(
    [f("deliveryDate"), f("hourEnding"), f("settlementPoint"), f("settlementPointPrice"), f("DSTFlag")],
    Array.from({ length: 24 }, (_, i) => [T, he(i + 1), "HB_NORTH", 60.75, false])),
  "/np6-323-cd/rt_price_adder_sced": report(
    [f("SCEDTimestamp"), f("systemLambda"), f("RTRDPA"), f("RTOLHSL"), f("RTOLLSL")],
    [["2026-09-26T09:55:00", 36.5, 0, 82000, 30000]]),
  "/np4-732-cd/wpp_hrly_avrg_actl_fcast": report(
    [f("hourEnding"), f("genSystemWide"), f("STWPFSystemWide"), f("HSLSystemWide")],
    [[9, 12000, 12500, 13000], [10, null, 11800, null]]),
  "/np4-737-cd/spp_hrly_avrg_actl_fcast": report(
    [f("hourEnding"), f("genSystemWide"), f("STPPFSystemWide"), f("HSLSystemWide")],
    [[9, 9000, 9200, 9500], [10, null, 11000, null]]),
  "/np4-722-cd/weather_assumptions": report(
    [f("hourEnding"), ...ZONES.map(f)],
    Array.from({ length: 24 }, (_, i) => [he(i + 1), ...ZONES.map(() => 70 + i + 1)])),
};

const snap = await buildSnapshot(async (path) => {
  const body = PAYLOADS[path];
  if (!body) throw new Error(`not stubbed: ${path}`);
  return body;
});
console.log(JSON.stringify(snap));
