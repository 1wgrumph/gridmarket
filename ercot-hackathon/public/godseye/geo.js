// Load zones are approximate, by county, for navigation only, not settlement.
// Hand-grouped from ERCOT's Load Zone Map (June 2023), covering the EIA plant corpus:
// https://www.ercot.com/files/assets/2023/06/05/ERCOT-Maps_Load-Zone.jpg
// ponytail: county boundaries cannot resolve mixed/NOIE service territories;
// use authoritative electrical-bus assignments if settlement precision is needed.
const COUNTIES = {
  LZ_NORTH: "Angelina|Archer|Baylor|Bell|Bosque|Brazos|Brown|Cherokee|Clay|Collin|Comanche|Cooke|Dallas|Delta|Denton|Eastland|Ellis|Erath|Falls|Fannin|Franklin|Freestone|Grayson|Grimes|Hamilton|Hill|Hood|Hopkins|Hunt|Jack|Johnson|Lamar|Limestone|McLennan|Milam|Mills|Nacogdoches|Navarro|Palo Pinto|Parker|Red River|Robertson|Rusk|Somervell|Stephens|Tarrant|Throckmorton|Wichita|Wilbarger|Williamson|Wise|Young",
  LZ_SOUTH: "Atascosa|Bee|Blanco|Brooks|Calhoun|Cameron|Comal|Dimmit|Frio|Goliad|Gonzales|Guadalupe|Hays|Hidalgo|Jackson|Jefferson|Jim Hogg|Jim Wells|Karnes|Kenedy|Kimble|Kinney|La Salle|Mason|Matagorda|Maverick|McCulloch|Menard|Nueces|Real|Refugio|San Patricio|Starr|Uvalde|Val Verde|Victoria|Webb|Wharton|Willacy|Wilson|Zapata",
  LZ_WEST: "Andrews|Armstrong|Borden|Brewster|Briscoe|Callahan|Carson|Castro|Childress|Coke|Concho|Crane|Crockett|Crosby|Culberson|Dawson|Deaf Smith|Dickens|Donley|Ector|Fisher|Floyd|Foard|Glasscock|Hale|Hardeman|Haskell|Howard|Irion|Jones|Kent|Kent & Stonewall|Knox|Lynn|Martin|Midland|Mitchell|Motley|Nolan|Oldham|Parmer|Pecos|Presidio|Randall|Reagan|Reeves|Roberts|Runnels|Schleicher|Scurry|Shackelford|Sterling|Swisher|Taylor|Tom Green|Upton|Ward|Winkler",
  LZ_HOUSTON: "Austin|Brazoria|Chambers|Fort Bend|Galveston|Harris|Montgomery|Waller",
  LZ_LCRA: "Bastrop|Burnet|Caldwell|Colorado|Fayette|Llano",
  LZ_AEN: "Travis",
  LZ_CPS: "Bexar",
  LZ_RAYBN: "Henderson|Kaufman|Van Zandt",
};
const countyZones = new Map(Object.entries(COUNTIES).flatMap(([zone, counties]) => counties.toLowerCase().split("|").map(county => [county, zone])));

export function countyToZone(county) {
  return countyZones.get(String(county ?? "").trim().toLowerCase().replace(/ county$/, "")) ?? null;
}

export function tradeLink(marketUrl, zone) {
  if (!Object.hasOwn(COUNTIES, zone)) return null;
  try {
    const url = new URL(marketUrl);
    if (!/^https?:$/.test(url.protocol) || url.username || url.password) return null;
    url.search = "";
    url.pathname = url.pathname.replace(/\/+$/, "") + "/";
    url.hash = `/?zone=${zone}`;
    return url.href;
  } catch {
    return null;
  }
}

export function leadPrediction(predictions, zone) {
  if (!Array.isArray(predictions)) return null;
  return predictions.filter(p => p?.zone === zone && Number.isFinite(p.score) && typeof p.level === "string" && Number.isFinite(Date.parse(p.delivery_hour)))
    .sort((a, b) => Date.parse(a.delivery_hour) - Date.parse(b.delivery_hour))[0] ?? null;
}

export function isBattery(plant) {
  return plant.prim === "storage" || (plant.units ?? []).some(unit => unit.cat === "storage" || unit.pm === "BA" || unit.stor);
}

export function latestESR(signals) {
  if (!Array.isArray(signals)) return null;
  return signals.filter(s => s?.report_id === "ESR" && s.zone === "ERCOT" && Number.isFinite(Date.parse(s.fetched_at)))
    .sort((a, b) => Date.parse(b.fetched_at) - Date.parse(a.fetched_at))[0] ?? null;
}

export function formatESR(signal) {
  if (!signal || signal.report_id !== "ESR" || signal.zone !== "ERCOT" || signal.unit !== "MW" || signal.stale !== false || !Number.isFinite(signal.value) || !Number.isFinite(Date.parse(signal.fetched_at))) return "Battery data unavailable";
  const mw = Math.abs(signal.value).toLocaleString("en-US", { maximumFractionDigits: 2 });
  return `${mw} MW ${signal.value < 0 ? "discharging" : signal.value > 0 ? "charging" : "· idle"}`;
}

// Plain-language names for codes shown in the page. Codes stay in links and data.
const ZONE_NAMES = { LZ_NORTH: "North", LZ_HOUSTON: "Houston", LZ_SOUTH: "South", LZ_WEST: "West", LZ_LCRA: "Lower Colorado River Authority", LZ_AEN: "Austin Energy", LZ_CPS: "CPS Energy", LZ_RAYBN: "Rayburn Country" };
export const zoneName = (zone) => ZONE_NAMES[zone] ?? null;

const SECTORS = { "IPP Non-CHP": "Independent power producer", "IPP CHP": "Independent power producer · combined heat and power", "Electric Utility": "Utility", "Industrial Non-CHP": "Industrial", "Industrial CHP": "Industrial · combined heat and power", "Commercial Non-CHP": "Commercial", "Commercial CHP": "Commercial · combined heat and power" };
export const sectorName = (sector) => SECTORS[sector] ?? sector;

const CT = new Intl.DateTimeFormat("en-US", { timeZone: "America/Chicago", month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short" });
export const ctTime = (iso) => (Number.isFinite(Date.parse(iso)) ? CT.format(new Date(iso)) : null);

// ERCOT real-time prices: hour ending h, 15-minute interval i (1-4), Central time.
export function intervalText(hour, interval) {
  if (!(hour >= 1 && hour <= 24 && interval >= 1 && interval <= 4)) return null;
  const clock = (m) => { const h = Math.floor(m / 60) % 24; return `${h % 12 || 12}:${String(m % 60).padStart(2, "0")} ${h < 12 ? "AM" : "PM"}`; };
  const start = (hour - 1) * 60 + (interval - 1) * 15;
  return `${clock(start)}–${clock(start + 15)} CT`;
}

// Baseline snapshot checks and market router checks share these ids.
const CHECKS = {
  "scarcity-2h": ["North hub price spike", "Chance the North hub real-time price tops $150/MWh in the next 2 hours"],
  "dart-north": ["North hub above day-ahead", "Chance the North hub real-time price ends above day-ahead this hour"],
  "renew-shortfall": ["Wind and solar shortfall", "Chance wind and solar fall more than 1 GW short next hour"],
};
export const checkName = (id) => CHECKS[id]?.[0] ?? id;
export const checkQuestion = (id, question) => CHECKS[id]?.[1] ?? question;
export const routeName = (route) => ({ alert: "Alert", review: "Worth watching", log: "No action" })[route] ?? route;

export function activityText(item) {
  const zone = zoneName(/LZ_[A-Z]+/.exec(item.symbol ?? "")?.[0]);
  const verb = item.type === "fill" ? (item.side === "sell" ? "sold" : "bought") : item.type === "order" ? (item.side === "sell" ? "offered" : "bid for") : String(item.type ?? "").replace(/_/g, " ");
  const who = [item.label || "Trader", verb, Number.isFinite(item.quantity) ? item.quantity : null].filter((p) => p !== null && p !== "").join(" ");
  const price = Number.isFinite(item.price_cents) ? `$${(item.price_cents / 100).toFixed(2)}` : null;
  return [who, zone ? `${zone} zone` : item.symbol, price].filter(Boolean).join(" · ");
}
