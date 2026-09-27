import { useRef } from 'react';
import type { Prediction } from '../api';
import { round1 } from '../format';

// Schematic geography: boundaries are illustrative, not survey data.
const outline = 'M83 17H154V69L176 73 190 69 208 77 227 73 242 83 249 113 246 132 260 151 246 169 219 182 202 195 186 218 180 235 154 221 141 195 126 186 116 164 96 154 79 174 61 157 49 136 24 119 19 105H83Z';
const regions = [
  { zone: 'NORTH', x: 129, y: 56, d: 'M83 17H154V69L187 75 180 104 113 112 83 85Z' },
  { zone: 'WEST', x: 75, y: 130, d: 'M19 105H83V85L113 112 130 148 116 164 96 154 79 174 61 157 49 136 24 119Z' },
  { zone: 'RAYBN', x: 223, y: 87, d: 'M187 75L208 77 227 73 242 83 249 113 233 125 180 104Z' },
  { zone: 'LCRA', x: 132, y: 117, d: 'M113 112L149 108 162 132 150 151 130 148Z' },
  { zone: 'AEN', x: 177, y: 115, d: 'M149 108L180 104 189 146 172 160 150 151 162 132Z' },
  { zone: 'HOUSTON', x: 225, y: 160, d: 'M180 104L233 125 246 132 260 151 246 169 219 182 191 169 189 146Z' },
  { zone: 'CPS', x: 143, y: 166, d: 'M130 148L150 151 172 160 170 184 141 195 126 186 116 164Z' },
  { zone: 'SOUTH', x: 175, y: 215, d: 'M172 160L191 169 219 182 202 195 186 218 180 235 154 221 141 195 170 184Z' },
];
const zones = regions.filter(z => ['NORTH', 'WEST', 'SOUTH', 'HOUSTON'].includes(z.zone));
export const mapZones = zones.map(z => `LZ_${z.zone}`);
export const zoneName = (zone: string) => zone.replace(/^LZ_|^HB_/, '');

export default function ZoneMap({ predictions, deliveryHour, selectedZone, paused, onSelect }: { selectedZone?: string | null; deliveryHour?: string; predictions: Prediction[]; paused: boolean; onSelect: (zone: string, trigger: SVGElement | HTMLElement) => void }) {
  const controls = useRef<Record<string, SVGGElement | null>>({});
  const score = (zone: string) => predictions.find(p => zoneName(p.zone) === zone)?.score;
  const label = zones.map(z => `${z.zone} ${score(z.zone) == null ? 'not reported' : `${round1(score(z.zone) as number)}% scarcity`}`).join(', ');
  return <><svg className={`zone-map ${paused ? 'motion-paused' : ''}`} viewBox="0 0 280 252" role="group" aria-label="ERCOT zone controls">
    <g role="img" aria-label={`Schematic ERCOT load zones. ${label}. Geographic boundaries are illustrative.`}>
    <defs><clipPath id="texas-clip"><path d={outline}/></clipPath><pattern id="map-dots" width="10" height="10" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="0.6" fill="currentColor" opacity="0.3"/></pattern></defs>
    <rect width="280" height="252" fill="url(#map-dots)"/>
    <g clipPath="url(#texas-clip)">{regions.map(z => { const s = score(z.zone) ?? 0; return <path key={z.zone} d={z.d} className={`map-region ${s >= 80 ? 'high' : s >= 50 ? 'medium' : ''}`} onClick={() => { const control = controls.current[z.zone]; if (control) onSelect(`LZ_${z.zone}`, control); }}/>; })}</g>
    <path d={outline} fill="none" stroke="var(--map-border)" strokeWidth="1.3"/>
    </g>
    {zones.map(z => { const s = score(z.zone); return <g key={z.zone} ref={node => { controls.current[z.zone] = node; }} role="button" tabIndex={0} aria-label={`${z.zone} zone details`} className="zone-control"
      onClick={e => onSelect(`LZ_${z.zone}`, e.currentTarget)}
      onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(`LZ_${z.zone}`, e.currentTarget); } }}>
      <rect className="zone-target" x={z.x - 22} y={z.y - 22} width="44" height="44" fill="transparent"/>
      {s != null && s >= 70 && <circle className="scarcity-pulse" cx={z.x} cy={z.y - 7} r={s >= 80 ? 13 : 9}/>}
      <circle cx={z.x} cy={z.y - 7} r="2.5" fill="var(--text)"/>
      <text x={z.x} y={z.y + 6} textAnchor="middle">{z.zone}</text>
      <text className="map-score" x={z.x} y={z.y + 20} textAnchor="middle">{s == null ? '—' : `${round1(s)}%`}</text>
    </g>; })}
    <text x="19" y="236" className="map-coordinate">TEXAS / ERCOT</text>
  </svg><p className="map-legend">Scarcity scale: low &lt;50% · medium 50–79% · high ≥80%. Unreported values have no score. Simulation estimates.</p><p className="map-legend">Delivery window: {deliveryHour ? new Date(deliveryHour).toLocaleString('en-US', { timeZone: 'America/Chicago' }) + ' CT' : 'not reported'}</p>
    <div className="zone-list" role="radiogroup" aria-label="Market zone">{zones.map(z => <label key={z.zone}><input type="radio" name="market-zone" value={`LZ_${z.zone}`} checked={selectedZone === `LZ_${z.zone}`} onChange={e => onSelect(e.target.value, e.currentTarget)}/>{z.zone}</label>)}</div></>;
}
