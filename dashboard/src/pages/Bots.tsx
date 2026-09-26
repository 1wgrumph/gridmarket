import { useState, type FormEvent, type ReactNode } from 'react';
import { Badge, Button, Table } from '@astryxdesign/core';
import { CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from 'recharts';
import Panel from '../components/Panel';
import { useBotDiversity, useBots } from '../hooks';
import { send, type ApiError, type Bot } from '../api';

type PublicBot = Bot & { blend: Record<string, number>; trades: number };
type Diversity = { trait_space_coverage: number; behavior_entropy: number; risk_patience: { bot_id: string; risk_appetite: number; patience: number }[] };

const pct = (p: number) => `${Math.round(p * 100)}%`;
const usd = (n: number) => n.toLocaleString('en-US', { style: 'currency', currency: 'USD' });
const blend = (b: Record<string, number>) => Object.entries(b).map(([type, w]) => `${type} ${pct(w)}`).join(' · ');

/** Lets a wide table scroll sideways on phones (Astryx scroll wrapper) without widening the page grid. */
const Wide = ({ children }: { children: ReactNode }) => <div style={{ contain: 'inline-size' }}>{children}</div>;

function DiversityPanel() {
  const diversity = useBotDiversity();
  const data = diversity.data as Diversity | null;
  // ponytail: useResource drops the HTTP status, so any failure reads as "not yet enabled" (the 404 case); expose status there if outages need their own message.
  if (diversity.error) return <Panel title="Diversity"><p className="gm-muted">Diversity measures not yet enabled.</p></Panel>;
  return <Panel title="Diversity" state={diversity}>
    {data && <>
      <dl className="gm-rows" style={{ margin: 0 }}>
        <div style={{ display: 'flex', gap: '0.75rem', padding: '0.4rem 0' }}><dt>Trait-space coverage</dt><dd className="gm-num">{pct(data.trait_space_coverage)}</dd></div>
        <div style={{ display: 'flex', gap: '0.75rem', padding: '0.4rem 0' }}><dt>Behavior entropy</dt><dd className="gm-num">{data.behavior_entropy.toFixed(2)} bits</dd></div>
      </dl>
      <h3 className="gm-panel-title gm-note">Risk appetite vs patience</h3>
      <ResponsiveContainer width="100%" height={220}>
        <ScatterChart margin={{ top: 8, right: 8, bottom: 8, left: -16 }}>
          <CartesianGrid stroke="var(--color-border)" />
          <XAxis type="number" dataKey="risk_appetite" name="risk" domain={[0, 1]} stroke="var(--color-text-secondary)" />
          <YAxis type="number" dataKey="patience" name="wait" domain={[0, 1]} stroke="var(--color-text-secondary)" />
          <Tooltip cursor={{ strokeDasharray: '3 3' }} />
          <Scatter data={data.risk_patience} fill="var(--color-accent)" />
        </ScatterChart>
      </ResponsiveContainer>
    </>}
  </Panel>;
}

/** Owner spawn: the admin key lives only in this form's state and is sent once per click. */
function SpawnForm() {
  const [adminKey, setAdminKey] = useState('');
  const [count, setCount] = useState('1');
  const [seed, setSeed] = useState('');
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await send('POST', '/v1/admin/bots', { count: Number(count), ...(seed.trim() ? { seed: Number(seed) } : {}) }, adminKey);
      setResult({ ok: true, text: `Spawn of ${count} bot(s) accepted.` });
    } catch (err) {
      setResult({ ok: false, text: (err as ApiError)?.error?.message ?? String(err) });
    } finally { setBusy(false); }
  };

  const field = { display: 'grid', gap: '0.25rem', fontSize: '0.8rem' } as const;
  const input = { font: 'inherit', padding: '0.4rem 0.5rem', borderRadius: 6, border: '1px solid var(--color-border)', background: 'var(--color-background-surface)', color: 'var(--color-text-primary)' } as const;
  return <Panel title="Owner · spawn bots">
    <form onSubmit={submit} style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: '0.75rem' }}>
      <label style={field}>Admin key<input style={input} type="password" autoComplete="off" required value={adminKey} onChange={e => setAdminKey(e.target.value)} /></label>
      <label style={field}>Count (1–10)<input style={{ ...input, width: '5rem' }} type="number" min={1} max={10} required value={count} onChange={e => setCount(e.target.value)} /></label>
      <label style={field}>Seed (optional)<input style={{ ...input, width: '7rem' }} type="number" value={seed} onChange={e => setSeed(e.target.value)} /></label>
      <Button type="submit" label="Spawn bots" variant="primary" isLoading={busy} />
    </form>
    {result && <p className={result.ok ? 'gm-muted gm-note' : 'gm-reject gm-note'} role="status">{result.text}</p>}
  </Panel>;
}

export default function Bots() {
  const bots = useBots();
  const rows = (bots.data ?? []) as PublicBot[];
  const dormant = rows.filter(b => b.dormant).length;

  return <section className="gm-page">
    <div className="gm-page-head"><h1>Bots</h1></div>
    {/* The owner form sits above the polled panels so their first load never shifts it. */}
    <SpawnForm />
    <div className="gm-stats">
      <Panel title="Population" state={bots}>
        <p className="gm-stat"><span className="gm-num">{rows.length}</span> bots</p>
      </Panel>
      <Panel title="Dormant rate" state={bots} className="gm-span-2">
        <p className="gm-stat gm-num">{rows.length ? pct(dormant / rows.length) : '—'} ({dormant} / {rows.length})</p>
      </Panel>
    </div>
    <Panel title="All bots" state={bots}>
      <Wide><Table<PublicBot> style={{ minWidth: '60rem' }} data={rows} idKey="id" density="compact" hasHover columns={[
        { key: 'id', header: 'Bot', renderCell: b => <a className="gm-code" href={`#/bots/${encodeURIComponent(b.id)}`}>{b.id}</a> },
        { key: 'bot_type', header: 'Type', renderCell: b => <span>{b.bot_type}</span> },
        { key: 'blend', header: 'Blend', renderCell: b => <span className="gm-muted">{blend(b.blend ?? {})}</span> },
        { key: 'provider_id', header: 'Provider', renderCell: b => <span>{b.provider_id}</span> },
        { key: 'cash', header: 'Cash', align: 'end', renderCell: b => <span className="gm-num">{usd(b.cash)}</span> },
        { key: 'net_worth', header: 'Net worth', align: 'end', renderCell: b => <span className="gm-num">{usd(b.net_worth)}</span> },
        { key: 'pnl', header: 'P&L', align: 'end', renderCell: b => <span className="gm-num">{usd(b.pnl)}</span> },
        { key: 'trades', header: 'Trades', align: 'end' },
        { key: 'losses', header: 'Losses', align: 'end' },
        { key: 'dormant', header: 'State', renderCell: b => <Badge variant={b.dormant ? 'warning' : 'success'} label={b.dormant ? 'dormant' : 'active'} /> },
      ]} /></Wide>
    </Panel>
    {!bots.loading && <DiversityPanel />}
  </section>;
}
