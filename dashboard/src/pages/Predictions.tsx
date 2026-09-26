import { useState } from 'react';
import { contextLink, setViewQuery, useViewQuery } from '../components/navigation';
import Panel from '../components/Panel';
import { missingInputs } from '../components/predictionInputs';
import { usePredictions, useResource } from '../hooks';
import type { Prediction, RouterCheck, Signal } from '../api';
import { FeedBody, PageHeading, Stale } from './Market';

type Check = RouterCheck & { horizon_s: number; created_at: string; resolves_at: string; outcome: boolean | number | null };
/** Router response per CONTRACTS.md: latest checks, per-check Brier score, and the Jev flag. */
type Router = { checks: Check[]; brier: Record<string, number>; jev_enabled: boolean };

const bandTone = { alert: 'down', review: 'info', log: '' } as const;
const levelTone = { high: 'up', medium: 'info', low: '' } as const;
const pct = (p: number) => `${Math.round(p * 100)}%`;
const signed = (n: number) => `${n > 0 ? '+' : ''}${n.toFixed(2)}`;
const time = (iso: string) => Number.isFinite(Date.parse(iso)) ? new Date(iso).toLocaleString('en-US', { timeZone: 'America/Chicago', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) + ' CT' : iso;

/** Signed contribution bar: positive grows right in turf, negative grows left in the warm status hue. */
function FactorBar({ value, scale }: { value: number; scale: number }) {
  return <span className="factor-bar" aria-hidden>
    <i className={value >= 0 ? 'up' : 'down'} style={{ width: `${Math.min(50, Math.abs(value) / scale * 50)}%` }}/>
  </span>;
}

function Zone({ p, signals, expanded, onToggle }: { p: Prediction; signals: Signal[]; expanded: boolean; onToggle: () => void }) {
  const scale = Math.max(0.01, ...p.drivers.map(d => Math.abs(d.contribution)));
  return <article className="zone-card">
    <header>
      <h3>{p.zone}<time dateTime={p.delivery_hour}>{time(p.delivery_hour)}</time></h3>
      <span className="zone-score">
        <strong>{p.score}%</strong>
        <span className={`tag ${levelTone[p.level.toLowerCase() as keyof typeof levelTone] ?? ''}`}>{p.level}</span>
      </span>
    </header>
    <p className="num">
      Confidence {pct(p.confidence)} · expected value {signed(p.expected_value)}
      {p.drivers.some(d => missingInputs(d.factor, p.zone, signals).length) && ' · incomplete inputs (simulation)'}
      {p.market_price !== null && <> · market price {p.market_price.toFixed(2)}</>}
    </p>
    <button className="motion-toggle" aria-expanded={expanded} onClick={onToggle}>Why this estimate?</button>
    {expanded && <ul className="factor-rows">
      {p.drivers.map(d => <li key={d.factor}>
        <span>{d.factor}</span>
        <FactorBar value={d.contribution} scale={scale}/>
        <span className="num">{signed(d.contribution)}</span>
        <p className="factor-detail">{missingInputs(d.factor, p.zone, signals).length ? `Inputs not reported: ${missingInputs(d.factor, p.zone, signals).join(', ')}` : d.detail}</p>
      </li>)}
    </ul>}
    <p className="context-actions"><a href={contextLink('#/market', { zone: p.zone, hour: p.delivery_hour })}>View this market</a> · <a href={contextLink('#/replay', { zone: p.zone, hour: p.delivery_hour, day: '2026-08-26' })}>Replay a real day</a></p>
  </article>;
}

export default function Predictions() {
  const predictions = usePredictions();
  const signals = useResource<Signal[]>('/v1/signals');
  const params = useViewQuery();
  const zone = params.get('zone') ?? '';
  const window = params.get('hour') ?? '';
  const setZone = (zone: string) => setViewQuery({ zone });
  const setWindow = (hour: string) => setViewQuery({ hour });
  const [expanded, setExpanded] = useState('');
  const [all, setAll] = useState(false);
  const rows = predictions.data ?? [];
  const zones = [...new Set(rows.map(p => p.zone))];
  const windows = [...new Set(rows.map(p => p.delivery_hour))].sort();
  const selectedWindow = window || windows[0];
  const visible = rows.filter(p => (!zone || p.zone === zone) && (all || p.delivery_hour === selectedWindow));
  // hooks.ts types useRouterChecks as RouterCheck[], but /v1/router returns the object above.
  const router = useResource<Router>('/v1/router');
  const brier = router.data?.brier ?? {};
  const disclaimers = [...new Set((predictions.data ?? []).map(p => p.disclaimer))];
  const jev = router.data?.jev_enabled;
  const checks = router.data?.checks ?? [];

  return <>
    <PageHeading eyebrow="06 / SCARCITY OUTLOOK" title="Predictions"/>
    <div className="page-grid">
      <Panel title="Zone scores · factor contributions" index="01" className="span-all" busy={predictions.loading}
        meta={<><Stale feed={predictions}/><span>{rows.length} forecasts across {zones.length} zones</span></>}>
        <FeedBody feed={predictions} reserve="reserve-predictions-zones">
          {rows.length > 0 && <div className="forecast-filters"><label>Zone<select value={zone} onChange={e => { setZone(e.target.value); setExpanded(''); }}><option value="">All zones</option>{zones.map(z => <option key={z}>{z}</option>)}</select></label><label>Delivery window<select value={selectedWindow ?? ''} onChange={e => { setWindow(e.target.value); setAll(false); setExpanded(''); }}>{windows.map(w => <option key={w} value={w}>{Number.isFinite(Date.parse(w)) ? new Date(w).toLocaleString('en-US', { timeZone: 'America/Chicago' }) + ' CT' : w}</option>)}</select></label><button className="motion-toggle" onClick={() => setAll(!all)}>{all ? 'Selected window' : 'Show all forecasts'}</button></div>}
          {rows.length ? <div className="zone-cards">{visible.map(p => <Zone key={`${p.zone}-${p.delivery_hour}`} p={p} signals={signals.data ?? []} expanded={expanded === `${p.zone}-${p.delivery_hour}`} onToggle={() => setExpanded(expanded === `${p.zone}-${p.delivery_hour}` ? '' : `${p.zone}-${p.delivery_hour}`)}/>)}</div>
            : <div className="empty">No predictions served yet.</div>}
          <p className="panel-end">Heuristic scarcity percentage. Confidence is model confidence; incomplete inputs are not measured zeros.</p>
          {disclaimers.map(d => <p key={d} className="panel-end">{d}</p>)}
        </FeedBody>
      </Panel>
      <Panel title="Market and health checks" index="02" className="span-all" busy={router.loading}
        meta={<><Stale feed={router}/><span>{checks.length} CHECKS</span></>}>
        <FeedBody feed={router} reserve="reserve-predictions-checks">
          <div className="table-scroll"><table className="data-table">
            <thead><tr>
              <th scope="col">Subject</th><th scope="col">Family</th><th scope="col" className="end">Probability</th>
              {jev && <th scope="col" className="end">Jev</th>}
              <th scope="col">Band</th><th scope="col" className="end">Brier</th><th scope="col">Decided by</th><th scope="col">Resolves</th>
            </tr></thead>
            <tbody>{checks.map(c => <tr key={c.check_id}>
              <td><a href={c.family === 'health' ? contextLink('#/providers', { provider: c.subject, at: c.created_at }) : contextLink('#/', { zone: c.subject.split(':')[0], hour: c.subject.slice(c.subject.indexOf(':') + 1), at: c.created_at })}>{c.subject}</a></td>
              <td className="muted">{c.family}</td>
              <td className="end num">{pct(c.probability)}</td>
              {jev && <td className="end num">{c.jev_probability === null ? '—' : pct(c.jev_probability)}</td>}
              <td><span className={`tag ${bandTone[c.band] ?? ''}`}>{c.band}</span></td>
              <td className="end num">{brier[c.check_id]?.toFixed(2) ?? '—'}</td>
              <td className="muted">{c.baseline ? 'baseline rules' : 'model'}</td>
              <td><time dateTime={c.resolves_at}>{time(c.resolves_at)}</time></td>
            </tr>)}</tbody>
          </table></div>
        </FeedBody>
      </Panel>
    </div>
  </>;
}
