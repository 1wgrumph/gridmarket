/// <reference types="vite/client" />
import { Badge } from '@astryxdesign/core';
import Panel from '../components/Panel';
import { useBots, useMarketActivity, useMarketStatus, usePredictions, useProviders, useSignals } from '../hooks';

type Signal = { report_id: string; zone: string; value: number; unit: string; published_at: string; stale: boolean };
type Activity = { id: string; type: string; label: string; symbol: string | null; side: string | null; quantity: number | null; price_cents: number | null; reason: string | null; created_at: string };

const levelVariant = { HIGH: 'error', MEDIUM: 'warning', LOW: 'success' } as const;
const time = (iso: string) => iso.replace('T', ' ').replace(/:\d\dZ$/, 'Z');

function groupBy<T>(rows: T[], key: (row: T) => string) {
  const groups = new Map<string, T[]>();
  for (const row of rows) {
    const group = groups.get(key(row));
    if (group) group.push(row); else groups.set(key(row), [row]);
  }
  return groups;
}

export default function Overview() {
  const status = useMarketStatus();
  const signals = useSignals();
  const predictions = usePredictions();
  const providers = useProviders();
  const bots = useBots();
  const activity = useMarketActivity();
  const viewsUrl = import.meta.env.VITE_VIEWS_URL as string | undefined;

  const signalsByZone = groupBy((signals.data ?? []) as Signal[], s => s.zone);
  const scoreByZone = new Map((predictions.data ?? []).map(p => [p.zone, p]));
  const zones = [...new Set([...scoreByZone.keys(), ...signalsByZone.keys()])];
  const zoneState = { loading: signals.loading || predictions.loading, error: signals.error ?? predictions.error };

  return <section className="gm-page">
    <div className="gm-page-head">
      <h1>Overview</h1>
      {viewsUrl && <a className="gm-views-link" href={viewsUrl}>3D views ↗</a>}
    </div>

    <div className="gm-stats">
      <Panel title="Market status" state={status}>
        <p className="gm-stat"><Badge variant={status.data?.status === 'halted' ? 'error' : 'success'} label={status.data?.status} /></p>
      </Panel>
      <Panel title="Participants" state={providers} className="gm-span-2">
        <p className="gm-muted">{providers.data?.length} providers · {bots.data ? `${bots.data.length} bots` : bots.error ? 'bots not yet available' : 'bots loading…'}</p>
        <ul className="gm-rows">
          {(providers.data ?? []).map(p => <li key={p.id}>
            {p.online !== undefined && <span className={`gm-dot ${p.online ? 'is-on' : ''}`} aria-label={p.online ? 'online' : 'offline'} />}
            <span>{p.display_name}</span>
            {bots.data && <span className="gm-num">{bots.data.filter(b => b.provider_id === p.id).length} bots</span>}
          </li>)}
        </ul>
      </Panel>
    </div>

    <Panel title="Zones · ERCOT signals and scores" state={zoneState}>
      <div className="gm-zones">
        {zones.map(zone => {
          const score = scoreByZone.get(zone);
          return <article key={zone} className="gm-zone">
            <header>
              <h3>{zone}</h3>
              {score && <span className="gm-score">
                <span className="gm-num">{score.score}</span>
                <Badge variant={levelVariant[score.level as keyof typeof levelVariant] ?? 'neutral'} label={score.level} />
              </span>}
            </header>
            <ul className="gm-rows">
              {(signalsByZone.get(zone) ?? []).map(s => <li key={s.report_id}>
                <span className="gm-code">{s.report_id}</span>
                <span className="gm-num">{s.value} {s.unit}</span>
                <span className="gm-muted"><time dateTime={s.published_at}>{time(s.published_at)}</time></span>
                {s.stale && <Badge variant="warning" label="stale" />}
              </li>)}
            </ul>
          </article>;
        })}
      </div>
      <p className="gm-muted gm-note">Scores are a simulation estimate, not guaranteed profit.</p>
    </Panel>

    <Panel title="Activity" state={activity}>
      {[...groupBy((activity.data ?? []) as Activity[], a => a.symbol ?? '—')].map(([symbol, events]) => <div key={symbol} className="gm-feed">
        <div className="gm-code gm-feed-symbol">{symbol}</div>
        <ul className="gm-rows">
          {events.map(e => <li key={e.id}>
            <span className="gm-muted"><time dateTime={e.created_at}>{time(e.created_at).slice(11)}</time></span>
            <span className={e.label === 'judge' ? 'gm-judge' : undefined}>{e.label}</span>
            {e.quantity != null && e.price_cents != null && <span className="gm-num">{e.side} {e.quantity} @ ${(e.price_cents / 100).toFixed(2)}</span>}
            {e.type === 'reject'
              ? <span className="gm-reject"><Badge variant="error" label="rejected" /> {e.reason}</span>
              : <><Badge variant="cyan" label={e.type} />{e.reason && <span className="gm-muted">{e.reason}</span>}</>}
          </li>)}
        </ul>
      </div>)}
    </Panel>
  </section>;
}
