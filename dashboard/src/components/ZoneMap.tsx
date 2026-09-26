import type { Prediction } from '../api';

// Schematic geography: boundaries are illustrative, not survey data.
const outline = 'M83 17H154V69L176 73 190 69 208 77 227 73 242 83 249 113 246 132 260 151 246 169 219 182 202 195 186 218 180 235 154 221 141 195 126 186 116 164 96 154 79 174 61 157 49 136 24 119 19 105H83Z';
const zones = [
  { zone: 'NORTH', x: 129, y: 56, d: 'M83 17H154V69L187 75 180 104 113 112 83 85Z' },
  { zone: 'WEST', x: 75, y: 130, d: 'M19 105H83V85L113 112 130 148 116 164 96 154 79 174 61 157 49 136 24 119Z' },
  { zone: 'RAYBN', x: 216, y: 104, d: 'M187 75L208 77 227 73 242 83 249 113 233 125 180 104Z' },
  { zone: 'LCRA', x: 134, y: 124, d: 'M113 112L149 108 162 132 150 151 130 148Z' },
  { zone: 'AEN', x: 166, y: 140, d: 'M149 108L180 104 189 146 172 160 150 151 162 132Z' },
  { zone: 'HOUSTON', x: 217, y: 157, d: 'M180 104L233 125 246 132 260 151 246 169 219 182 191 169 189 146Z' },
  { zone: 'CPS', x: 147, y: 168, d: 'M130 148L150 151 172 160 170 184 141 195 126 186 116 164Z' },
  { zone: 'SOUTH', x: 175, y: 201, d: 'M172 160L191 169 219 182 202 195 186 218 180 235 154 221 141 195 170 184Z' },
];
export const zoneName = (zone: string) => zone.replace(/^LZ_|^HB_/, '');

export default function ZoneMap({ predictions, paused }: { predictions: Prediction[]; paused: boolean }) {
  const score = (zone: string) => predictions.find(p => zoneName(p.zone) === zone)?.score;
  const label = predictions.length ? predictions.map(p => `${zoneName(p.zone)} ${p.score}% scarcity`).join(', ') : 'Awaiting scarcity predictions';
  return <svg className={`zone-map ${paused ? 'motion-paused' : ''}`} viewBox="0 0 280 252" role="img" aria-label={`Schematic ERCOT load zones. ${label}. Geographic boundaries are illustrative.`}>
    <defs><clipPath id="texas-clip"><path d={outline}/></clipPath><pattern id="map-dots" width="10" height="10" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="0.6" fill="currentColor" opacity="0.3"/></pattern></defs>
    <rect width="280" height="252" fill="url(#map-dots)"/>
    <g clipPath="url(#texas-clip)">{zones.map(z => { const s = score(z.zone) ?? 0; return <path key={z.zone} d={z.d} className={`map-region ${s >= 80 ? 'high' : s >= 50 ? 'medium' : ''}`}/>; })}</g>
    <path d={outline} fill="none" stroke="var(--map-border)" strokeWidth="1.3"/>
    {zones.map(z => { const s = score(z.zone); return <g key={z.zone}>
      {s != null && s >= 70 && <circle className="scarcity-pulse" cx={z.x} cy={z.y - 7} r={s >= 80 ? 13 : 9}/>}
      <circle cx={z.x} cy={z.y - 7} r="2.5" fill="var(--text)"/>
      <text x={z.x} y={z.y + 6} textAnchor="middle">{z.zone}</text>
      {s != null && <text className="map-score" x={z.x} y={z.y + 20} textAnchor="middle">{s}%</text>}
    </g>; })}
    <text x="19" y="236" className="map-coordinate">TEXAS / ERCOT</text>
  </svg>;
}
