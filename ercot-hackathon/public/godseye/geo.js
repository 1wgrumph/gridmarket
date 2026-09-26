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
