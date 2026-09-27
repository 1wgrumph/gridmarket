/* GridMarket layers for God's Eye:
   1. Replay of the real 26 Aug 2026 ERCOT day (baked from the ERCOT Public API).
   2. "Help the grid": demand now and upcoming help windows per zone (/api/help, ERCOT data only).
   3. 1,000 simulated home batteries (Base Sim, LoneStar Storage). Simulated and labelled as such.
   4. Start-here link: #start opens the replay at the evening ramp and stops on the $780 spike.
   Runs after the main God's Eye script and uses its globals (viewer, G, state, SNAP, PLANTS, selectPlant...). */
(() => {
const GM = { aug: null, help: null, replay: { on: false, i: 0, playing: false, speed: 4, acc: 0, stopAtSpike: false }, bat: [], batOn: true, helpOn: true };
window.GM = GM;

/* Zones: the four ERCOT forecast/load zones that Flex Credits trade in, anchored on their main metro */
const ZONE_POS = { houston: [-95.37, 29.76, 'Houston'], north: [-96.8, 32.78, 'North'], south: [-98.2, 29.9, 'South'], west: [-101.9, 31.95, 'West'] };
const ZONE_HUB = { houston: 'HB_HOUSTON', north: 'HB_NORTH', south: 'HB_SOUTH', west: 'HB_WEST' };
const ZONE_LZ = { houston: 'LZ_HOUSTON', north: 'LZ_NORTH', south: 'LZ_SOUTH', west: 'LZ_WEST' };
const WZ_OF = { houston: ['Coast'], north: ['North', 'North Central', 'East'], south: ['Southern', 'South Central'], west: ['West', 'Far West'] };
const PROVIDERS = { base: { name: 'Base Sim', color: '#7dd3fc' }, lonestar: { name: 'LoneStar Storage', color: '#f0abfc' } };
const scoreColor = s => s == null ? '#6b7280' : s >= 70 ? '#ff4d5e' : s >= 50 ? '#ffb020' : '#3ddc84';
const hhmm = t => { const [h, m] = t.split(':').map(Number); const ap = h >= 12 ? 'PM' : 'AM'; const hh = h % 12 || 12; return `${hh}:${String(m).padStart(2, '0')} ${ap}`; };
const hr = h => { h = ((h % 24) + 24) % 24; return `${h % 12 || 12} ${h >= 12 ? 'PM' : 'AM'}`; };

/* ---------- styles ---------- */
const css = document.createElement('style');
css.textContent = `
.gm-start{top:72px;left:24px;font:600 11px var(--font-mono);letter-spacing:.14em;text-transform:uppercase;padding:8px 12px;border-radius:10px;border:1px solid #ffb020;color:#0a0a0f;background:#ffb020;cursor:pointer;box-shadow:0 0 18px rgba(255,176,32,.35)}
body.gm-has-start .rail{top:118px}
.gm-mode{position:absolute;z-index:5;top:72px;left:292px;display:inline-flex;gap:0;border:1px solid var(--glass-border);border-radius:10px;overflow:hidden;background:var(--glass-bg);backdrop-filter:blur(20px)}
.gm-mode button{font:600 11px var(--font-mono);letter-spacing:.12em;padding:9px 12px;border:0;background:transparent;color:var(--text-secondary);cursor:pointer}
.gm-mode button.on{background:var(--accent-dim);color:var(--accent)}
.gm-tl{left:50%;transform:translateX(-50%);bottom:84px;width:min(640px,calc(100vw - 690px));padding:10px 14px;display:none}
body.gm-replay .gm-tl{display:block}
body.gm-replay .rail,body.gm-replay .intel{max-height:calc(100% - 270px)}
.gm-tl .top{display:flex;align-items:center;gap:10px}
.gm-tl .clock{font:700 20px var(--font-mono);font-variant-numeric:tabular-nums}
.gm-tl .date{font:500 10px var(--font-mono);letter-spacing:.14em;color:var(--text-secondary);text-transform:uppercase}
.gm-tl .px{margin-left:auto;text-align:right;font:500 11px var(--font-mono);color:var(--text-secondary)}
.gm-tl .px b{display:block;font:700 18px var(--font-mono);color:var(--text-primary)}
.gm-btn{font:600 11px var(--font-mono);letter-spacing:.08em;padding:7px 10px;border-radius:8px;border:1px solid var(--accent);background:var(--accent-dim);color:var(--accent);cursor:pointer}
.gm-btn.ghost{border-color:var(--glass-border);background:transparent;color:var(--text-secondary)}
.gm-chart{position:relative;margin-top:8px;height:74px;cursor:pointer}
.gm-chart svg{display:block;width:100%;height:100%}
.gm-spike{position:absolute;left:50%;top:30%;transform:translate(-50%,-50%) scale(.9);opacity:0;pointer-events:none;z-index:7;padding:16px 20px;border:1px solid #ff4d5e;border-radius:14px;background:rgba(20,6,10,.86);text-align:center;box-shadow:0 0 40px rgba(255,77,94,.35)}
.gm-spike .k{font:500 10px var(--font-mono);letter-spacing:.2em;color:#ff8a95;text-transform:uppercase}
.gm-spike .v{font:700 42px var(--font-mono);color:#fff;margin:4px 0}
.gm-spike .s{font-size:12px;color:var(--text-secondary);max-width:340px}
.gm-sim{font:600 9px var(--font-mono);letter-spacing:.14em;padding:2px 5px;border-radius:4px;background:#f0abfc22;color:#f0abfc;border:1px solid #f0abfc66;margin-left:6px;vertical-align:1px}
.gm-zone{border:1px solid var(--glass-border);border-radius:10px;padding:8px 10px;margin-top:8px;cursor:pointer}
.gm-zone:hover{border-color:var(--glass-border-hover)}
.gm-zone .h{display:flex;justify-content:space-between;gap:8px;font-size:12px}
.gm-zone .h b{font:600 12px var(--font-sans)}
.gm-zone .w{font:500 11px var(--font-mono);margin-top:3px}
.gm-strip{display:flex;gap:1px;height:16px;margin-top:6px;align-items:flex-end}
.gm-strip i{flex:1;display:block;border-radius:1px}
.gm-why{border-left:2px solid #ffb020;padding:6px 10px;margin-top:10px;font-size:12px;line-height:1.5;color:var(--text-primary);background:rgba(255,176,32,.06);border-radius:0 8px 8px 0}
.gm-legend-row{display:grid;grid-template-columns:30px 1fr auto;gap:8px;align-items:center;padding:5px 6px;border-radius:9px;border:1px solid transparent;background:transparent;color:var(--text-primary);cursor:pointer;text-align:left;font:500 12px var(--font-sans);width:100%}
.gm-legend-row:hover{border-color:var(--glass-border-hover)}
.gm-legend-row.off{opacity:.35}
.gm-legend-row .n{font:500 10px var(--font-mono);color:var(--text-secondary);text-align:right}
.gm-dots{display:flex;gap:4px;justify-content:center}
.gm-dots i{width:8px;height:8px;border-radius:50%;display:block}
@media (max-width:900px){.gm-mode{top:56px;left:auto;right:12px}.gm-tl{width:calc(100vw - 24px);bottom:auto;top:70px}.gm-start{top:56px;left:12px}}
`;
document.head.appendChild(css);

/* ---------- HUD pieces ---------- */
const startBtn = document.createElement('button');
startBtn.className = 'hud gm-start'; startBtn.textContent = '▶ Start here · the real day';
startBtn.onclick = () => startTour();
document.body.appendChild(startBtn); document.body.classList.add('gm-has-start');

const modeWrap = document.createElement('span'); modeWrap.className = 'gm-mode';
modeWrap.innerHTML = '<button data-m="live" class="on">LIVE</button><button data-m="replay">26 AUG</button>';
document.body.appendChild(modeWrap);
modeWrap.querySelectorAll('button').forEach(b => b.onclick = () => setReplay(b.dataset.m === 'replay'));

const tl = document.createElement('div'); tl.className = 'hud glass gm-tl';
tl.innerHTML = `<div class="top">
  <button class="gm-btn" id="gmPlay" aria-label="Play">▶ Play</button>
  <div><div class="date">Replay · Wed 26 Aug 2026 · real ERCOT data</div><div class="clock" id="gmClock">00:00</div></div>
  <div class="px"><span id="gmPxLbl">Houston hub</span><b id="gmPx">—</b></div>
  <div class="px"><span>Demand</span><b id="gmDem">—</b></div>
  <button class="gm-btn ghost" id="gmSpeed">4×</button>
  <button class="gm-btn ghost" id="gmExit">Back to live</button></div>
  <div class="gm-chart" id="gmChart"></div>`;
document.body.appendChild(tl);
const spikeCard = document.createElement('div'); spikeCard.className = 'gm-spike'; document.body.appendChild(spikeCard);

/* legend entries for the new layers */
const legend = document.getElementById('legend');
const extra = document.createElement('div'); extra.className = 'legend';
extra.innerHTML = `<div class="eyebrow" style="margin:6px 0 2px">// gridmarket layers</div>
  <button class="gm-legend-row" id="gmHelpToggle"><span class="gm-dots"><i style="background:#ff4d5e;box-shadow:0 0 8px #ff4d5e"></i></span><span>Help the grid<br><span style="font-size:10px;color:var(--text-secondary)">demand now + help windows</span></span><span class="n" id="gmHelpN">—</span></button>
  <button class="gm-legend-row" id="gmBatToggle"><span class="gm-dots"><i style="background:${PROVIDERS.base.color}"></i><i style="background:${PROVIDERS.lonestar.color}"></i></span><span>Home batteries<span class="gm-sim">SIM</span><br><span style="font-size:10px;color:var(--text-secondary)">Base Sim · LoneStar Storage</span></span><span class="n" id="gmBatN">1,000</span></button>`;
legend.parentNode.insertBefore(extra, legend.nextSibling);
document.getElementById('gmHelpToggle').onclick = e => { GM.helpOn = !GM.helpOn; e.currentTarget.classList.toggle('off', !GM.helpOn); helpDS.show = GM.helpOn; };
document.getElementById('gmBatToggle').onclick = e => { GM.batOn = !GM.batOn; e.currentTarget.classList.toggle('off', !GM.batOn); batPoints.show = GM.batOn; };

/* ---------- help-the-grid layer (Cesium) ---------- */
const helpDS = new Cesium.CustomDataSource('help'); viewer.dataSources.add(helpDS);
let helpPulse = 0;
function zoneView(id) {
  // What the layer shows for a zone: live (/api/help) or the replay day
  if (GM.replay.on && GM.aug) return GM.augHelp?.[id] || null;
  const z = GM.help?.zones?.find(z => z.id === id); if (!z) return null;
  return { score: z.now.score, load: z.now.zoneLoad, next: z.next, series: z.series, basis: z.now.basis };
}
Object.entries(ZONE_POS).forEach(([id, [lon, lat, name]]) => {
  const radius = () => { const v = zoneView(id); const s = v?.score ?? 0; return 45000 + s * 900 + (helpPulse % 1) * 25000 * (s >= 70 ? 1 : .3); };
  helpDS.entities.add({ position: Cesium.Cartesian3.fromDegrees(lon, lat),
    ellipse: { semiMajorAxis: new Cesium.CallbackProperty(radius, false), semiMinorAxis: new Cesium.CallbackProperty(radius, false), height: 500,
      material: new Cesium.ColorMaterialProperty(new Cesium.CallbackProperty(() => Cesium.Color.fromCssColorString(scoreColor(zoneView(id)?.score)).withAlpha(.14 * (1 - (helpPulse % 1) * .6)), false)),
      outline: true, outlineColor: new Cesium.CallbackProperty(() => Cesium.Color.fromCssColorString(scoreColor(zoneView(id)?.score)).withAlpha(.85), false) } });
  helpDS.entities.add({ position: Cesium.Cartesian3.fromDegrees(lon, lat, 2000),
    label: { text: new Cesium.CallbackProperty(() => helpLabel(id, name), false), font: '500 11px "JetBrains Mono", ui-monospace, Menlo, monospace',
      fillColor: Cesium.Color.WHITE, showBackground: true, backgroundColor: Cesium.Color.fromCssColorString('#0a0a0f').withAlpha(.8), backgroundPadding: new Cesium.Cartesian2(6, 4),
      pixelOffset: new Cesium.Cartesian2(0, 30), verticalOrigin: Cesium.VerticalOrigin.TOP, disableDepthTestDistance: Number.POSITIVE_INFINITY,
      distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 3.2e6) } });
});
function helpLabel(id, name) {
  const v = zoneView(id); if (!v) return `${name.toUpperCase()} · help data unavailable`;
  const load = v.load != null ? `${fmt(v.load / 1000, 1)} GW` : '—';
  const nx = v.next ? `HELP ${hr(+v.next.start.slice(0, 2))}–${hr(+v.next.end.slice(0, 2))}` : 'no help window ahead';
  return `${name.toUpperCase()} · ${load} · ${nx}`;
}

/* ---------- 1,000 simulated home batteries ---------- */
function rng(seed) { return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
const R = rng(20260826);
const gauss = () => Math.sqrt(-2 * Math.log(R() || 1e-9)) * Math.cos(2 * Math.PI * R());
const CLUSTERS = [ // [zone, lon, lat, spread°, count]
  ['houston', -95.37, 29.76, .32, 300], ['north', -96.8, 32.78, .38, 300], ['north', -97.33, 32.75, .2, 80],
  ['south', -97.74, 30.27, .22, 110], ['south', -98.49, 29.42, .22, 100], ['south', -97.4, 27.8, .15, 30],
  ['west', -102.08, 31.99, .2, 45], ['west', -99.73, 32.45, .15, 35]];
const batPoints = viewer.scene.primitives.add(new Cesium.PointPrimitiveCollection());
let n = 0;
for (const [zone, lon, lat, sp, count] of CLUSTERS) for (let k = 0; k < count; k++) {
  const b = { idx: ++n, zone, provider: R() < .58 ? 'base' : 'lonestar', kwh: 13.5, kw: 5, reserve: .2,
    lon: lon + gauss() * sp * 1.15, lat: lat + gauss() * sp, soc: .55 + R() * .2, mode: 'idle', phase: R() };
  b.pt = batPoints.add({ position: Cesium.Cartesian3.fromDegrees(b.lon, b.lat, 300), pixelSize: 4.5, color: Cesium.Color.fromCssColorString(PROVIDERS[b.provider].color),
    outlineColor: Cesium.Color.fromCssColorString('#0a0a0f'), outlineWidth: 1, id: { battery: b }, disableDepthTestDistance: Number.POSITIVE_INFINITY,
    scaleByDistance: new Cesium.NearFarScalar(2e4, 2.2, 3e6, .7) });
  GM.bat.push(b);
}
/* Simulated dispatch rule, the same for live and replay:
   discharge (5 kW) while the zone is inside a help window or its real-time price is above $150;
   charge from 10 AM to 4 PM when prices are low; otherwise hold. Never below the 20% backup reserve. */
function batteryMode(zone, hour, price, inWindow) {
  if ((inWindow || (price != null && price > 150))) return 'discharge';
  if (hour >= 10 && hour < 16 && (price == null || price < 60)) return 'charge';
  return 'idle';
}
function stepBatteries(hours, hour, priceByZone, windowByZone) {
  // hours: simulated time elapsed since last step
  let dis = 0, chg = 0, energy = 0, value = 0;
  for (const b of GM.bat) {
    const m = batteryMode(b.zone, hour, priceByZone[b.zone], windowByZone[b.zone]);
    let p = 0;
    if (m === 'discharge' && b.soc > b.reserve) p = -Math.min(b.kw, (b.soc - b.reserve) * b.kwh / Math.max(hours, 1e-6));
    if (m === 'charge' && b.soc < .98) p = Math.min(b.kw, (.98 - b.soc) * b.kwh / Math.max(hours, 1e-6));
    b.soc = clamp(b.soc + p * hours / b.kwh, b.reserve * .999, 1);
    b.mode = p < -0.01 ? 'discharge' : p > 0.01 ? 'charge' : 'idle'; b.kwNow = p;
    if (p < 0) { dis += -p; value += -p * hours * (priceByZone[b.zone] ?? 0) / 1000; }
    if (p > 0) chg += p;
    energy += b.soc * b.kwh;
    const c = Cesium.Color.fromCssColorString(PROVIDERS[b.provider].color);
    b.pt.color = b.mode === 'discharge' ? Cesium.Color.WHITE : c.withAlpha(.35 + b.soc * .65);
    b.pt.pixelSize = b.mode === 'discharge' ? 6.5 : 4.5;
    b.pt.outlineColor = b.mode === 'discharge' ? Cesium.Color.fromCssColorString('#ff4d5e') : Cesium.Color.fromCssColorString('#0a0a0f');
  }
  GM.fleet = { dischargeMW: dis / 1000, chargeMW: chg / 1000, energyMWh: energy / 1000, capMWh: GM.bat.length * 13.5 / 1000 };
  return value; // $ earned this step at real-time prices (simulated)
}
function fleetLabel() {
  const f = GM.fleet; if (!f) return '1,000';
  return f.dischargeMW > 0.01 ? `${fmt(f.dischargeMW, 1)} MW out` : f.chargeMW > 0.01 ? `charging ${fmt(f.chargeMW, 1)} MW` : `${fmt(f.energyMWh / f.capMWh * 100)}% full`;
}

/* ---------- live help data ---------- */
async function loadHelp() {
  try { const r = await fetch(API + '/api/help'); if (!r.ok) throw new Error(r.status); GM.help = await r.json(); }
  catch (e) { GM.help = { error: e.message, zones: [] }; }
  updateHelpCount(); if (!selected && !GM.replay.on) renderSystem();
}
function updateHelpCount() {
  const zs = GM.replay.on ? Object.values(GM.augHelp || {}) : (GM.help?.zones || []).map(z => ({ next: z.next }));
  const nWin = zs.filter(z => z?.next).length;
  document.getElementById('gmHelpN').textContent = GM.replay.on ? '26 Aug' : GM.help?.error ? 'unavailable' : `${nWin}/4 zones`;
}

/* live battery simulation: one step per minute of wall time, using live prices and help windows */
function liveBatteryStep(mins = 1) {
  if (GM.replay.on) return;
  const ct = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Chicago', hour: 'numeric', hourCycle: 'h23' }).format(new Date()) | 0;
  const price = {}, win = {};
  for (const id of Object.keys(ZONE_POS)) {
    price[id] = state.hub[ZONE_HUB[id]] ?? null;
    const z = GM.help?.zones?.find(z => z.id === id); const s = z?.series?.[0]?.score; win[id] = s != null && s >= 70;
  }
  stepBatteries(mins / 60, ct, price, win);
  document.getElementById('gmBatN').textContent = fleetLabel();
}

/* ---------- replay ---------- */
async function loadAug() {
  if (GM.aug) return GM.aug;
  GM.aug = window.__AUG26 || await (await fetch(API + '/data/aug26.json')).json();
  // help windows for that day, scored the same way as /api/help (actual load, wind and solar for the day)
  const H = GM.aug.hours;
  const net = H.map(h => h.load && h.wind != null && h.solar != null ? h.load.total - h.wind - h.solar : null);
  const scale = v => { const x = v.filter(a => a != null), mn = Math.min(...x), mx = Math.max(...x); return v.map(a => a == null ? null : (a - mn) / ((mx - mn) || 1)); };
  const ns = scale(net); GM.augHelp = {};
  for (const id of Object.keys(ZONE_POS)) {
    const ps = scale(H.map(h => h.da?.[ZONE_LZ[id]] ?? null));
    const score = ns.map((a, i) => a == null || ps[i] == null ? null : Math.round(100 * (.5 * a + .5 * ps[i])));
    const hrs = score.map((s, i) => s >= 70 ? i : -1).filter(i => i >= 0);
    GM.augHelp[id] = { scores: score, window: hrs.length ? { start: `${String(hrs[0]).padStart(2, '0')}:00`, end: `${String(hrs[hrs.length - 1] + 1).padStart(2, '0')}:00` } : null };
  }
  GM.augNet = net;
  drawChart();
  return GM.aug;
}
function augAt(i) {
  const A = GM.aug, iv = A.intervals[i], h = A.hours[Math.floor(i / 4)], t = iv.t;
  const sc = A.sced.filter(s => s.ts <= (t.slice(0, 3) + String(Math.min(59, +t.slice(3) + 14)).padStart(2, '0'))).pop() || A.sced[0];
  return { iv, h, sc, hour: Math.floor(i / 4) };
}
function applyReplay(stepHours = 0) {
  const { iv, h, sc, hour } = augAt(GM.replay.i);
  for (const hub of Object.keys(HUBS)) state.hub[hub] = iv.p[hub] ?? null;
  if (h.temp) for (const [z, t] of Object.entries(h.temp)) state.temps[z] = t;
  // zone views for the help layer at this moment
  for (const id of Object.keys(ZONE_POS)) {
    const ah = GM.augHelp[id]; const s = ah.scores[hour];
    ah.score = s; ah.load = h.load ? WZ_OF[id].reduce((a, w) => a + (h.load[w] || 0), 0) : null; ah.next = ah.window && hour <= +ah.window.end.slice(0, 2) ? ah.window : null;
  }
  // batteries
  const price = {}, win = {};
  for (const id of Object.keys(ZONE_POS)) { price[id] = iv.p[ZONE_HUB[id]] ?? null; const s = GM.augHelp[id].scores[hour]; win[id] = s != null && s >= 70; }
  if (stepHours > 0) { GM.replayValue = (GM.replayValue || 0) + stepBatteries(stepHours, hour, price, win);
    if (!GM.drainedAt && GM.fleet && GM.fleet.energyMWh <= GM.fleet.capMWh * .205 && hour >= 12) GM.drainedAt = iv.t; }
  else stepBatteries(1e-6, hour, price, win);
  document.getElementById('gmBatN').textContent = fleetLabel();
  // timeline readouts
  document.getElementById('gmClock').textContent = `${hhmm(iv.t)}`;
  const px = iv.p.HB_HOUSTON; const pxEl = document.getElementById('gmPx');
  pxEl.textContent = money(px); pxEl.style.color = px > 300 ? '#ff4d5e' : px > 100 ? '#ffb020' : 'var(--text-primary)';
  document.getElementById('gmDem').textContent = iv.d ? `${fmt(iv.d / 1000, 1)} GW` : '—';
  document.getElementById('sced').textContent = sc.ts; document.getElementById('lam').textContent = money(sc.lam);
  if (GM.quiet) return;
  moveHead(); if (!selected) renderReplayPanel(); renderDock();
}
function setReplay(on) {
  if (on && !GM.aug) { loadAug().then(() => setReplay(true)); return; }
  GM.replay.on = on; document.body.classList.toggle('gm-replay', on);
  modeWrap.querySelectorAll('button').forEach(b => b.classList.toggle('on', (b.dataset.m === 'replay') === on));
  if (on) {
    GM.bat.forEach(b => b.soc = .6 + b.phase * .15); GM.replayValue = 0; GM.drainedAt = null;
    // warm the fleet up to the current replay time so state of charge is consistent
    GM.quiet = true; const target = GM.replay.i;
    for (let k = 0; k < target; k++) { GM.replay.i = k; applyReplay(0.25); }
    GM.replay.i = target; GM.quiet = false;
    applyReplay(0);
  } else {
    GM.replay.playing = false; setPlayBtn();
    (SNAP?.hubs || []).forEach(h => state.hub[h.hub] = h.price); (SNAP?.weather?.zones || []).forEach(z => state.temps[z.zone] = z.tempF);
    document.getElementById('sced').textContent = SNAP?.sced ? SNAP.sced.timestamp.slice(11, 16) : '—';
    document.getElementById('lam').textContent = money(SNAP?.sced?.systemLambda);
    renderDock(); liveBatteryStep(1e-6); if (!selected) renderSystem();
  }
  updateHelpCount();
}
function setPlayBtn() { const b = document.getElementById('gmPlay'); b.textContent = GM.replay.playing ? '❚❚ Pause' : '▶ Play'; }
document.getElementById('gmPlay').onclick = () => { if (GM.replay.i >= 95) { GM.replay.i = 0; setReplay(true); } GM.replay.playing = !GM.replay.playing; setPlayBtn(); };
document.getElementById('gmSpeed').onclick = e => { const s = [2, 4, 8, 16]; GM.replay.speed = s[(s.indexOf(GM.replay.speed) + 1) % s.length]; e.currentTarget.textContent = GM.replay.speed + '×'; };
document.getElementById('gmExit').onclick = () => setReplay(false);

/* timeline chart: 96 fifteen-minute intervals, four hubs, help window shading, spike marker */
const CW = 600, CH = 74;
function drawChart() {
  const A = GM.aug, el = document.getElementById('gmChart');
  const mx = 820, y = v => CH - 6 - (Math.max(0, v) / mx) * (CH - 14), x = i => (i / 95) * CW;
  const line = (hub, col, w, op) => `<polyline points="${A.intervals.map((e, i) => `${x(i).toFixed(1)},${y(e.p[hub] ?? 0).toFixed(1)}`).join(' ')}" fill="none" stroke="${col}" stroke-width="${w}" opacity="${op}" vector-effect="non-scaling-stroke"/>`;
  const w = GM.augHelp.houston.window; const wx0 = w ? x(+w.start.slice(0, 2) * 4) : 0, wx1 = w ? x(+w.end.slice(0, 2) * 4) : 0;
  const sp = A.spike, sx = x(sp.interval);
  el.innerHTML = `<svg viewBox="0 0 ${CW} ${CH}" preserveAspectRatio="none" aria-label="Hub prices on 26 Aug">
    ${w ? `<rect x="${wx0}" y="0" width="${wx1 - wx0}" height="${CH}" fill="#ff4d5e" opacity=".10"/><text x="${wx0 + 4}" y="10" fill="#ff8a95" font-size="8" font-family="JetBrains Mono, monospace">HOUSTON HELP WINDOW ${hr(+w.start.slice(0, 2))}–${hr(+w.end.slice(0, 2))}</text>` : ''}
    ${[100, 400, 800].map(v => `<line x1="0" x2="${CW}" y1="${y(v)}" y2="${y(v)}" stroke="rgba(255,255,255,.07)"/><text x="${CW - 2}" y="${y(v) - 2}" fill="rgba(232,234,237,.35)" font-size="7" text-anchor="end" font-family="JetBrains Mono, monospace">$${v}</text>`).join('')}
    ${line('HB_NORTH', '#e8eaed', 1, .35)}${line('HB_SOUTH', '#e8eaed', 1, .35)}${line('HB_WEST', '#ffb020', 1, .55)}${line('HB_HOUSTON', '#00d4ff', 1.8, 1)}
    <circle cx="${sx}" cy="${y(sp.price)}" r="3.5" fill="#ff4d5e"/><text x="${sx - 5}" y="${y(sp.price) + 3}" fill="#ff8a95" font-size="9" text-anchor="end" font-family="JetBrains Mono, monospace">$${fmt(sp.price, 0)}</text>
    ${[0, 6, 12, 18].map(h => `<text x="${x(h * 4) + 2}" y="${CH - 1}" fill="rgba(232,234,237,.4)" font-size="7" font-family="JetBrains Mono, monospace">${hr(h)}</text>`).join('')}
    <line id="gmHead" x1="0" x2="0" y1="0" y2="${CH}" stroke="#fff" stroke-width="1.2" vector-effect="non-scaling-stroke"/></svg>`;
  const seek = ev => { const r = el.getBoundingClientRect(); GM.replay.i = clamp(Math.round((ev.clientX - r.left) / r.width * 95), 0, 95); GM.replay.acc = 0; applyReplay(0); };
  let drag = false;
  el.onpointerdown = ev => { drag = true; el.setPointerCapture(ev.pointerId); seek(ev); };
  el.onpointermove = ev => { if (drag) seek(ev); };
  el.onpointerup = () => drag = false;
}
function moveHead() { const h = document.getElementById('gmHead'); if (h) { const X = (GM.replay.i / 95) * CW; h.setAttribute('x1', X); h.setAttribute('x2', X); } }

/* replay intel panel: the "why" behind each moment */
function renderReplayPanel() {
  const A = GM.aug; const { iv, h, sc, hour } = augAt(GM.replay.i); const sp = A.spike;
  const net = GM.augNet[hour]; const head = sc.hsl && iv.d ? (sc.hsl - iv.d) / iv.d * 100 : null;
  const hubs = Object.keys(HUBS).map(k => [k, iv.p[k]]);
  const da = h.da?.HB_HOUSTON, rt = iv.p.HB_HOUSTON;
  let why;
  if (GM.replay.i >= sp.interval - 1 && GM.replay.i <= sp.interval + 1) why = `Solar had fallen from ${fmt(sp.solar19 / 1000, 1)} GW at 6–7 PM to ${fmt(sp.solar20 / 1000, 1)} GW at 7–8 PM and nothing after 9 PM. Wind was only ${fmt(sp.wind23 / 1000, 1)} GW. Demand was ${fmt(iv.d / 1000, 1)} GW, well below the ${fmt(sp.peakDemand / 1000, 1)} GW afternoon peak, but net of renewables it was near the day's high, and the dispatch price reached ${money(sp.lamMax)}. Day-ahead had priced this hour at ${money(sp.da)}.${GM.drainedAt ? ` The simulated fleet had already run down to its 20% backup reserve by ${hhmm(GM.drainedAt)}, so it had nothing left for the peak. That's what the replay's reserve slider and strategies test.` : ''}`;
  else if (h.solar > 15000) why = `Solar is carrying the grid: ${fmt(h.solar / 1000, 1)} GW this hour. Net load (demand minus wind and solar) is ${fmt(net / 1000, 1)} GW, so prices stay low even as demand climbs.`;
  else if (hour >= 18 && hour <= 21) why = `The sun is going down. Solar is ${fmt((h.solar || 0) / 1000, 1)} GW, and net load has climbed to ${fmt(net / 1000, 1)} GW. This is the help window: simulated batteries are discharging into it.`;
  else why = `Net load (demand minus wind and solar) is ${fmt(net / 1000, 1)} GW. Real-time Houston is ${money(rt)} against ${money(da)} day-ahead.`;
  const f = GM.fleet || {};
  intel.innerHTML = `<div class="eyebrow">// replay · 26 aug 2026 · ${hhmm(iv.t)} CT</div>
    <h2>The real day</h2>
    <div class="gm-why">${why}</div>
    <div class="sect eyebrow">// hubs this interval $/MWh</div>
    ${hubs.map(([k, v]) => `<div class="row"><span class="k">${k}</span><span class="v" style="color:${v > 300 ? '#ff4d5e' : v > 100 ? '#ffb020' : 'var(--text-primary)'}">${money(v)}</span></div>`).join('')}
    <div class="row"><span class="k">Day-ahead HB_HOUSTON · this hour</span><span class="v">${money(da)}</span></div>
    <div class="sect eyebrow">// system</div>
    <div class="row"><span class="k">Demand</span><span class="v">${fmt(iv.d)} MW</span></div>
    <div class="row"><span class="k">Wind · Solar (hourly)</span><span class="v">${fmt(h.wind)} · ${fmt(h.solar)} MW</span></div>
    <div class="row"><span class="k">Net load</span><span class="v">${fmt(net)} MW</span></div>
    <div class="row"><span class="k">Dispatch price (SCED λ) · ${sc.ts}</span><span class="v">${money(sc.lam)}</span></div>
    <div class="row"><span class="k">Online capacity · headroom</span><span class="v">${fmt(sc.hsl)} MW · ${fmt(head, 1)}%</span></div>
    <div class="sect eyebrow">// 1,000 home batteries <span class="gm-sim">SIMULATED</span></div>
    <div class="row"><span class="k">Discharging now</span><span class="v">${fmt(f.dischargeMW, 2)} MW</span></div>
    <div class="row"><span class="k">Stored energy</span><span class="v">${fmt(f.energyMWh, 1)} of ${fmt(f.capMWh, 1)} MWh</span></div>
    <div class="row"><span class="k">Earned so far at real-time prices</span><span class="v">$${fmt(GM.replayValue || 0, 0)}</span></div>
    <div class="note">Rule: discharge 5 kW in a zone's help window or when its real-time price tops $150, charge 10 AM–4 PM when prices are low, never below a 20% backup reserve. Batteries and money are simulated; prices, demand, wind and solar are ERCOT's.</div>
    <div class="sect eyebrow">// help windows that day (same scoring as live)</div>
    ${Object.entries(GM.augHelp).map(([id, a]) => `<div class="row"><span class="k">${ZONE_POS[id][2]}</span><span class="v">${a.window ? `${hr(+a.window.start.slice(0, 2))}–${hr(+a.window.end.slice(0, 2))}` : 'none'}</span></div>`).join('')}
    <div class="note">Houston's window was flagged ${GM.augHelp.houston.window ? `${hr(+GM.augHelp.houston.window.start.slice(0, 2))}–${hr(+GM.augHelp.houston.window.end.slice(0, 2))}` : '—'} from day-ahead prices and net load. The ${money(sp.price)} peak landed at ${hhmm(sp.t)}, 15 minutes past the window's edge, when real-time ran to about ${fmt(sp.price / sp.da, 0)}× the day-ahead price. The day's highest hub was ${sp.dayHigh.hub} at ${money(sp.dayHigh.price)} (${hhmm(sp.dayHigh.t)}). Source: ${esc(A.source)}.</div>`;
}

/* system panel: add "help the grid" and the battery fleet to the live intel feed */
const baseRenderSystem = renderSystem;
renderSystem = function () {
  if (GM.replay.on) { renderReplayPanel(); return; }
  baseRenderSystem();
  const help = GM.help; const box = document.createElement('div');
  if (!help) box.innerHTML = '<div class="sect eyebrow">// help the grid</div><div class="note">Loading help windows…</div>';
  else if (help.error) box.innerHTML = `<div class="sect eyebrow">// help the grid</div><div class="note">Help windows unavailable right now (${esc(help.error)}).</div>`;
  else box.innerHTML = `<div class="sect eyebrow">// help the grid · next 24 h</div>
    ${help.zones.map(z => `<div class="gm-zone" data-z="${z.id}"><div class="h"><b>${z.name}</b><span class="v" style="font-family:var(--font-mono)">${z.now.zoneLoad != null ? fmt(z.now.zoneLoad / 1000, 1) + ' GW now' : 'load unavailable'}</span></div>
      <div class="w" style="color:${z.next ? scoreColor(z.next.peakScore) : 'var(--text-secondary)'}">${z.next ? `Help window ${hr(+z.next.start.slice(0, 2))}–${hr(+z.next.end.slice(0, 2))}${z.next.date !== help.ct.date ? ' tomorrow' : ''} · score ${z.next.peakScore} · DA ${money(z.next.avgDaPrice)}` : 'No help window in the next 24 h'}</div>
      <div class="gm-strip" title="Score by hour, next 24 h">${z.series.map(s => `<i style="height:${s.score == null ? 2 : 3 + s.score * .13}px;background:${scoreColor(s.score)}" title="${s.label} · score ${s.score ?? 'n/a'}${s.daPrice != null ? ' · DA $' + s.daPrice : ''}"></i>`).join('')}</div></div>`).join('')}
    <div class="note">${esc(help.method)} Hours without a posted day-ahead price use net load alone.</div>
    <div class="sect eyebrow">// 1,000 home batteries <span class="gm-sim">SIMULATED</span></div>
    <div class="row"><span class="k">Discharging</span><span class="v">${fmt(GM.fleet?.dischargeMW, 2)} MW</span></div>
    <div class="row"><span class="k">Charging</span><span class="v">${fmt(GM.fleet?.chargeMW, 2)} MW</span></div>
    <div class="row"><span class="k">Stored</span><span class="v">${fmt(GM.fleet?.energyMWh, 1)} of ${fmt(GM.fleet?.capMWh, 1)} MWh</span></div>
    <div class="row"><span class="k">Providers</span><span class="v">Base Sim ${GM.bat.filter(b => b.provider === 'base').length} · LoneStar ${GM.bat.filter(b => b.provider === 'lonestar').length}</span></div>`;
  intel.insertBefore(box, intel.querySelector('.sect.eyebrow'));
  box.querySelectorAll('.gm-zone').forEach(el => el.onclick = () => { const [lon, lat] = ZONE_POS[el.dataset.z]; flyTo(lon, lat, 420000, -40); });
};

/* battery drill-down on click */
const bh = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
bh.setInputAction(ev => {
  const hit = viewer.scene.pick(ev.position); const b = hit?.id?.battery; if (!b) return;
  selected = null;
  const zname = ZONE_POS[b.zone][2], p = PROVIDERS[b.provider];
  const price = state.hub[ZONE_HUB[b.zone]];
  intel.innerHTML = `<div class="topline"><div class="eyebrow">// home battery #${String(b.idx).padStart(4, '0')}</div><button class="back" id="back">← ${GM.replay.on ? 'Replay' : 'System'}</button></div>
    <h2 style="margin-top:10px">Simulated home battery <span class="gm-sim">SIM</span></h2>
    <div class="badges"><span class="badge" style="border-color:${p.color};color:${p.color}">${p.name}</span><span class="badge accent">${zname} zone</span><span class="badge">${b.mode}</span></div>
    <div class="tiles"><div class="tile"><div class="k">State of charge</div><div class="v">${fmt(b.soc * 100)}%</div><div class="s">${fmt(b.soc * b.kwh, 1)} kWh</div></div>
    <div class="tile"><div class="k">Power now</div><div class="v">${fmt(Math.abs(b.kwNow || 0), 1)}</div><div class="s">kW ${b.mode === 'discharge' ? 'out' : b.mode === 'charge' ? 'in' : ''}</div></div>
    <div class="tile"><div class="k">Size</div><div class="v">${b.kwh}</div><div class="s">kWh · ${b.kw} kW</div></div></div>
    <div class="row"><span class="k">Backup reserve kept</span><span class="v">${fmt(b.reserve * 100)}%</span></div>
    <div class="row"><span class="k">Zone price ${GM.replay.on ? '(26 Aug)' : '(live)'}</span><span class="v">${money(price)} /MWh</span></div>
    <div class="row"><span class="k">Location (simulated)</span><span class="v">${b.lat.toFixed(3)}°, ${b.lon.toFixed(3)}°</span></div>
    <div class="note">One of 1,000 simulated home batteries. The household, the battery and the money are simulated; the prices and help windows it reacts to are real ERCOT data.</div>`;
  document.getElementById('back').onclick = () => renderSystem();
}, Cesium.ScreenSpaceEventType.LEFT_CLICK);

/* ---------- start-here tour: the real day ---------- */
async function startTour() {
  await loadAug(); selected = null;
  GM.replay.i = 21 * 4; setReplay(true); GM.replay.speed = 4; document.getElementById('gmSpeed').textContent = '4×';
  GM.replay.stopAtSpike = true; GM.replay.playing = true; setPlayBtn();
  flyTo(-96.4, 30.4, 950000, -42, 2.6);
  history.replaceState(null, '', '#start');
}
function showSpike() {
  const sp = GM.aug.spike;
  spikeCard.innerHTML = `<div class="k">Houston hub · ${hhmm(sp.t)}–${hhmm(sp.tEnd)} · 26 Aug 2026</div><div class="v">${money(sp.price)}<span style="font-size:14px;color:var(--text-secondary)">/MWh</span></div><div class="s">${fmt(sp.price / sp.da, 0)}× the day-ahead price for that hour. Solar had gone dark and the grid ran short. Step 2: open the replay and change the outcome.</div>`;
  flyTo(-95.6, 29.9, 700000, -45, 2.2);
  if (window.gsap) gsap.fromTo(spikeCard, { opacity: 0, scale: .9 }, { opacity: 1, scale: 1, duration: .5, ease: 'back.out(1.6)' }); else spikeCard.style.opacity = 1;
  setTimeout(() => { if (window.gsap) gsap.to(spikeCard, { opacity: 0, duration: .6 }); else spikeCard.style.opacity = 0; }, 7000);
}

/* ---------- clock ---------- */
let last = performance.now();
viewer.clock.onTick.addEventListener(() => {
  const now = performance.now(), dt = Math.min(.1, (now - last) / 1000); last = now;
  helpPulse += dt * .5;
  if (GM.replay.on && GM.aug) { const p = GM.aug.intervals[GM.replay.i].p; for (const hub of Object.keys(HUBS)) state.hub[hub] = p[hub] ?? null; }
  if (GM.replay.on && GM.replay.playing) {
    GM.replay.acc += dt * GM.replay.speed;              // 1× = one 15-minute interval per second
    while (GM.replay.acc >= 1 && GM.replay.i < 95) {
      GM.replay.acc -= 1; GM.replay.i++; applyReplay(0.25);
      if (GM.replay.stopAtSpike && GM.replay.i === GM.aug.spike.interval) { GM.replay.playing = false; GM.replay.stopAtSpike = false; setPlayBtn(); showSpike(); break; }
    }
    if (GM.replay.i >= 95) { GM.replay.playing = false; setPlayBtn(); }
  }
});
setInterval(() => liveBatteryStep(1), 60000);

/* ---------- boot ---------- */
loadHelp(); setInterval(loadHelp, 10 * 60 * 1000);
liveBatteryStep(1e-6);
if (/#start|#replay/.test(location.hash)) setTimeout(startTour, 2500);
})();
