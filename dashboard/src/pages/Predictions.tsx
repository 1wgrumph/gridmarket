import Panel from '../components/Panel';
import { usePredictions, useResource } from '../hooks';
import type { Prediction, RouterCheck } from '../api';
import { FeedBody, PageHeading, Stale } from './Market';

type Check = RouterCheck & { horizon_s: number; created_at: string; resolves_at: string; outcome: boolean | number | null };
/** Router response per CONTRACTS.md: latest checks, per-check Brier score, and the Jev flag. */
type Router = { checks: Check[]; brier: Record<string, number>; jev_enabled: boolean };

const bandTone = { alert: 'down', review: 'info', log: '' } as const;
const levelTone = { high: 'up', medium: 'info', low: '' } as const;
const pct = (p: number) => `${Math.round(p * 100)}%`;
const signed = (n: number) => `${n > 0 ? '+' : ''}${n.toFixed(2)}`;
const time = (iso: string) => iso.replace('T', ' ').replace(/:\d\dZ$/, 'Z');

/** Signed contribution bar: positive grows right in turf, negative grows left in the warm status hue. */
function FactorBar({ value, scale }: { value: number; scale: number }) {
  return <span className="factor-bar" aria-hidden>
    <i className={value >= 0 ? 'up' : 'down'} style={{ width: `${Math.min(50, Math.abs(value) / scale * 50)}%` }}/>
  </span>;
}

function Zone({ p }: { p: Prediction }) {
  const scale = Math.max(0.01, ...p.drivers.map(d => Math.abs(d.contribution)));
  return <article className="zone-card">
    <header>
      <h3>{p.zone}<time dateTime={p.delivery_hour}>{time(p.delivery_hour)}</time></h3>
      <span className="zone-score">
        <strong>{p.score}</strong>
        <span className={`tag ${levelTone[p.level.toLowerCase() as keyof typeof levelTone] ?? ''}`}>{p.level}</span>
      </span>
    </header>
    <p className="num">
      Confidence {pct(p.confidence)} · expected value {signed(p.expected_value)}
      {p.market_price !== null && <> · market price {p.market_price.toFixed(2)}</>}
    </p>
    <ul className="factor-rows">
      {p.drivers.map(d => <li key={d.factor} title={d.detail}>
        <span>{d.factor}</span>
        <FactorBar value={d.contribution} scale={scale}/>
        <span className="num">{signed(d.contribution)}</span>
      </li>)}
    </ul>
  </article>;
}

export default function Predictions() {
  const predictions = usePredictions();
  // hooks.ts types useRouterChecks as RouterCheck[], but /v1/router returns the object above.
  const router = useResource<Router>('/v1/router');
  const brier = router.data?.brier ?? {};
  const disclaimers = [...new Set((predictions.data ?? []).map(p => p.disclaimer))];
  const jev = router.data?.jev_enabled;
  const checks = router.data?.checks ?? [];

  return <>
    <PageHeading eyebrow="03 / SCARCITY OUTLOOK" title="Predictions"/>
    <div className="page-grid">
      <Panel title="Zone scores · factor contributions" index="01" className="span-all" busy={predictions.loading}
        meta={<><Stale feed={predictions}/><span>{predictions.data?.length ?? 0} ZONES</span></>}>
        <FeedBody feed={predictions} reserve="reserve-predictions-zones">
          {predictions.data?.length ? <div className="zone-cards">{predictions.data.map(p => <Zone key={`${p.zone}-${p.delivery_hour}`} p={p}/>)}</div>
            : <div className="empty">No predictions served yet.</div>}
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
              <td>{c.subject}</td>
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
