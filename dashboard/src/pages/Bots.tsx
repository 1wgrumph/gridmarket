import { useState, type FormEvent } from 'react';
import { Button } from '@astryxdesign/core';
import { CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from 'recharts';
import Panel from '../components/Panel';
import { useBotDiversity, useBots } from '../hooks';
import { send, type ApiError } from '../api';
import { FeedBody, PageHeading, Stale } from './Market';

/** GET /v1/bots lists id, bot_index, bot_type, provider_id, dormant; economy columns render "—" until served. */
type PublicBot = { id: string; bot_type: string; provider_id: string; dormant: boolean }
  & Partial<{ blend: Record<string, number>; cash: number; net_worth: number; pnl: number; trades: number; losses: number }>;
type Diversity = { coverage: number; entropy: number; points: { risk_appetite: number; patience: number }[] };

const pct = (p: number) => `${Math.round(p * 100)}%`;
const usd = (n?: number) => n === undefined ? '—' : n.toLocaleString('en-US', { style: 'currency', currency: 'USD' });
const blend = (b: Record<string, number>) => Object.entries(b).map(([type, w]) => `${type} ${pct(w)}`).join(' · ');
const tick = { fill: 'var(--muted)', fontSize: 11 };
const tooltip = { background: 'var(--surface)', border: '1px solid var(--line)', color: 'var(--text)', fontSize: 12, borderRadius: 'var(--r-2)' };

function DiversityPanel() {
  const diversity = useBotDiversity();
  const data = diversity.data as Diversity | null;
  // ponytail: useResource drops the HTTP status, so any failure reads as "not yet enabled" (the 404 case); expose status there if outages need their own message.
  return <Panel title="Diversity" index="03" className="span-all" busy={diversity.loading} meta={<Stale feed={diversity}/>}>
    <FeedBody feed={diversity} unavailable="Diversity measures not yet enabled.">
      {data && <>
        <dl className="facts">
          <div><dt>Trait-space coverage</dt><dd>{pct(data.coverage)}</dd></div>
          <div><dt>Behavior entropy</dt><dd>{data.entropy.toFixed(2)} bits</dd></div>
        </dl>
        <h3 className="sub-head">Risk appetite vs patience</h3>
        <div className="chart">
          <ResponsiveContainer width="100%" height="100%" minWidth={0}>
            <ScatterChart margin={{ top: 8, right: 18, bottom: 2, left: -8 }}>
              <CartesianGrid stroke="var(--line)" strokeDasharray="2 4"/>
              <XAxis type="number" dataKey="risk_appetite" name="risk" domain={[0, 1]} axisLine={false} tickLine={false} tick={tick}/>
              <YAxis type="number" dataKey="patience" name="wait" domain={[0, 1]} axisLine={false} tickLine={false} tick={tick}/>
              <Tooltip cursor={{ strokeDasharray: '3 3' }} contentStyle={tooltip} itemStyle={{ color: 'var(--text)' }} isAnimationActive={false}/>
              <Scatter data={data.points} fill="var(--accent)" isAnimationActive={false}/>
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      </>}
    </FeedBody>
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
    if (!adminKey.trim()) { setResult({ ok: false, text: 'Enter the admin key to spawn bots' }); return; }
    setBusy(true);
    try {
      await send('POST', '/v1/admin/bots', { count: Number(count), ...(seed.trim() ? { seed: seed.trim() } : {}) }, adminKey);
      setResult({ ok: true, text: `Spawn of ${count} bot(s) accepted.` });
    } catch (err) {
      setResult({ ok: false, text: (err as ApiError)?.error?.message ?? String(err) });
    } finally { setBusy(false); }
  };

  return <Panel title="Owner · spawn bots" index="01" className="span-all" meta={<span>ADMIN KEY · NOT STORED</span>}>
    <form className="form-row" onSubmit={submit}>
      <label className="field">Admin key<input type="password" autoComplete="off" value={adminKey} onChange={e => setAdminKey(e.target.value)}/></label>
      <label className="field">Count (1–10)<input style={{ width: '6rem' }} type="number" min={1} max={10} required value={count} onChange={e => setCount(e.target.value)}/></label>
      <label className="field">Seed (optional)<input style={{ width: '8rem' }} value={seed} onChange={e => setSeed(e.target.value)}/></label>
      <Button type="submit" label="Spawn bots" variant="primary" isLoading={busy}/>
    </form>
    {result && <p className={`form-result ${result.ok ? 'muted' : 'warning-text'}`} role="status" aria-live="polite">{result.text}</p>}
  </Panel>;
}

export default function Bots() {
  const bots = useBots();
  const rows = (bots.data ?? []) as PublicBot[];
  const dormant = rows.filter(b => b.dormant).length;
  const value = (text: string) => bots.data ? <strong>{text}</strong>
    : <strong className="unavailable">{bots.loading ? 'loading' : 'not yet available'}</strong>;

  return <>
    <PageHeading eyebrow="05 / BOT POPULATION" title="Bots"/>
    <div className="page-grid">
      {/* The owner form sits above the polled panels so their first load never shifts it. */}
      <SpawnForm/>
    </div>
    <section className="stat-strip" aria-label="Population key numbers">
      <div><span>Population</span>{value(String(rows.length))}<span>bots listed</span></div>
      <div><span>Dormant rate</span>{value(rows.length ? pct(dormant / rows.length) : '—')}<span>{bots.data ? `${dormant} of ${rows.length} bots` : 'share of population'}</span></div>
    </section>
    <div className="page-grid">
      <Panel title="All bots" index="02" className="span-all" busy={bots.loading} meta={<><Stale feed={bots}/><span>SIMULATED ACCOUNTS</span></>}>
        <FeedBody feed={bots} unavailable="Bots not yet available">
          {rows.length ? <div className="table-scroll"><table className="data-table">
            <thead><tr>
              <th scope="col">Bot</th><th scope="col">Type</th><th scope="col">Blend</th><th scope="col">Provider</th>
              <th scope="col" className="end">Cash</th><th scope="col" className="end">Net worth</th><th scope="col" className="end">P&L</th>
              <th scope="col" className="end">Trades</th><th scope="col" className="end">Losses</th><th scope="col">State</th>
            </tr></thead>
            <tbody>{rows.map(b => <tr key={b.id}>
              <td><a className="code" href={`#/bots/${encodeURIComponent(b.id)}`}>{b.id}</a></td>
              <td>{b.bot_type}</td>
              <td className="muted">{blend(b.blend ?? {})}</td>
              <td>{b.provider_id}</td>
              <td className="end num">{usd(b.cash)}</td>
              <td className="end num">{usd(b.net_worth)}</td>
              <td className={`end num ${(b.pnl ?? 0) < 0 ? 'down-text' : 'up-text'}`}>{usd(b.pnl)}</td>
              <td className="end num">{b.trades ?? '—'}</td>
              <td className="end num">{b.losses ?? '—'}</td>
              <td><span className={`tag ${b.dormant ? 'down' : 'up'}`}>{b.dormant ? 'dormant' : 'active'}</span></td>
            </tr>)}</tbody>
          </table></div> : <div className="empty">No bots yet</div>}
        </FeedBody>
      </Panel>
      {!bots.loading && <DiversityPanel/>}
    </div>
  </>;
}
