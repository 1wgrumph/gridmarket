import type { ReactNode } from 'react';
import { Badge, Table, type TableColumn } from '@astryxdesign/core';
import Panel from '../components/Panel';
import { usePredictions, useResource } from '../hooks';
import type { Prediction, RouterCheck } from '../api';

type Check = RouterCheck & { horizon_s: number; created_at: string; resolves_at: string; outcome: boolean | number | null };
/** Router response per CONTRACTS.md: latest checks, per-check Brier score, and the Jev flag. */
type Router = { checks: Check[]; brier: Record<string, number>; jev_enabled: boolean };

const bandVariant = { alert: 'error', review: 'warning', log: 'neutral' } as const;
const levelVariant = { high: 'error', medium: 'warning', low: 'success' } as const;
const pct = (p: number) => `${Math.round(p * 100)}%`;
const signed = (n: number) => `${n > 0 ? '+' : ''}${n.toFixed(2)}`;
const time = (iso: string) => iso.replace('T', ' ').replace(/:\d\dZ$/, 'Z');

/** Lets a wide table scroll sideways on phones (Astryx scroll wrapper) without widening the page grid. */
const Wide = ({ children }: { children: ReactNode }) => <div style={{ contain: 'inline-size' }}>{children}</div>;

/** Signed contribution bar: positive grows right in accent, negative grows left in heat. */
function FactorBar({ value, scale }: { value: number; scale: number }) {
  const width = `${Math.min(50, (Math.abs(value) / scale) * 50)}%`;
  return <span aria-hidden style={{ position: 'relative', flex: '1 1 8rem', minWidth: '6rem', height: '0.5rem', borderRadius: 4, background: 'var(--color-background-muted)' }}>
    <span style={{ position: 'absolute', left: '50%', top: -2, bottom: -2, width: 1, background: 'var(--color-border-emphasized)' }} />
    <span style={{ position: 'absolute', top: 0, bottom: 0, borderRadius: 4, width,
      ...(value >= 0 ? { left: '50%', background: 'var(--color-accent)' } : { right: '50%', background: 'var(--color-error)' }) }} />
  </span>;
}

function Zone({ p }: { p: Prediction }) {
  const scale = Math.max(0.01, ...p.drivers.map(d => Math.abs(d.contribution)));
  return <article className="gm-zone">
    <header>
      <h3>{p.zone} <span className="gm-muted"><time dateTime={p.delivery_hour}>{time(p.delivery_hour)}</time></span></h3>
      <span className="gm-score">
        <span className="gm-num">{p.score}</span>
        <Badge variant={levelVariant[p.level.toLowerCase() as keyof typeof levelVariant] ?? 'neutral'} label={p.level} />
      </span>
    </header>
    <p className="gm-muted">
      Confidence {pct(p.confidence)} · expected value {signed(p.expected_value)}
      {p.market_price !== null && <> · market price {p.market_price.toFixed(2)}</>}
    </p>
    <ul className="gm-rows">
      {p.drivers.map(d => <li key={d.factor} title={d.detail}>
        <span style={{ flex: '0 0 7rem' }}>{d.factor}</span>
        <FactorBar value={d.contribution} scale={scale} />
        <span className="gm-num">{signed(d.contribution)}</span>
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

  const columns: TableColumn<Check>[] = [
    { key: 'subject', header: 'Subject', renderCell: c => <span>{c.subject}</span> },
    { key: 'family', header: 'Family' },
    { key: 'probability', header: 'Probability', align: 'end', renderCell: c => <span className="gm-num">{pct(c.probability)}</span> },
    ...(router.data?.jev_enabled ? [{ key: 'jev_probability', header: 'Jev', align: 'end',
      renderCell: (c: Check) => <span className="gm-num">{c.jev_probability === null ? '—' : pct(c.jev_probability)}</span> } as TableColumn<Check>] : []),
    { key: 'band', header: 'Band', renderCell: c => <Badge variant={bandVariant[c.band] ?? 'neutral'} label={c.band} /> },
    { key: 'brier', header: 'Brier', align: 'end', renderCell: c => <span className="gm-num">{brier[c.check_id]?.toFixed(2) ?? '—'}</span> },
    { key: 'baseline', header: 'Decided by', renderCell: c => <span className="gm-muted">{c.baseline ? 'baseline rules' : 'model'}</span> },
    { key: 'resolves_at', header: 'Resolves', renderCell: c => <time dateTime={c.resolves_at}>{time(c.resolves_at)}</time> },
  ];

  return <section className="gm-page">
    <div className="gm-page-head"><h1>Predictions</h1></div>
    <Panel title="Zone scores · factor contributions" state={predictions}>
      <div className="gm-zones">{(predictions.data ?? []).map(p => <Zone key={`${p.zone}-${p.delivery_hour}`} p={p} />)}</div>
      {disclaimers.map(d => <p key={d} className="gm-muted gm-note">{d}</p>)}
    </Panel>
    <Panel title="Market and health checks" state={router}>
      <Wide><Table<Check> style={{ minWidth: '46rem' }} data={router.data?.checks ?? []} idKey="check_id" density="compact" columns={columns} /></Wide>
    </Panel>
  </section>;
}
