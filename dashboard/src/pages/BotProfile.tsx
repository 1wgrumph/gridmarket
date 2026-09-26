import type { ReactNode } from 'react';
import { Badge } from '@astryxdesign/core';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import Panel from '../components/Panel';
import { useBotProfile } from '../hooks';
import type { Bot } from '../api';

/** Contract Bot fields plus the profile extras; extras may be absent, so they render as "—". */
type Profile = Bot & Partial<{
  blend: Record<string, number>; trades: number; loss_share: number; worst_loss: number;
  traits: { risk_appetite: number; patience: number };
  household: { batteries: number[]; zone: string; reserve_pct: number; schedule: number[] };
  employed: boolean; job: string | null; pay: number; deposits: number;
  balance_history: { at: string; balance: number }[];
}>;

const pct = (p?: number) => p === undefined ? '—' : `${Math.round(p * 100)}%`;
const usd = (n?: number) => n === undefined ? '—' : n.toLocaleString('en-US', { style: 'currency', currency: 'USD' });
const day = (iso: string) => iso.slice(5, 16).replace('T', ' ');

function Facts({ rows }: { rows: [string, ReactNode][] }) {
  return <ul className="gm-rows">
    {rows.map(([label, value]) => <li key={label}><span>{label}</span><span className="gm-num">{value}</span></li>)}
  </ul>;
}

export default function BotProfile({ id }: { id: string }) {
  const profile = useBotProfile(id);
  const b = profile.data as Profile | null;

  return <section className="gm-page">
    <div className="gm-page-head">
      <h1>Bot profile · {id}</h1>
      <a className="gm-views-link" href="#/bots">← All bots</a>
    </div>
    {!b ? <Panel title="Profile" state={profile}><p className="gm-muted">No profile.</p></Panel> : <>
      <div className="gm-stats">
        <Panel title="Traits">
          <Facts rows={[['Risk appetite', pct(b.traits?.risk_appetite)], ['Patience', pct(b.traits?.patience)]]} />
          <h3 className="gm-panel-title gm-note">Strategy blend</h3>
          <Facts rows={Object.entries(b.blend ?? {}).map(([type, w]) => [type, pct(w)])} />
        </Panel>
        <Panel title="Economy">
          <Facts rows={[
            ['Employment', b.employed === undefined ? '—' : b.employed ? b.job ?? 'employed' : 'unemployed'],
            ['Pay per period', usd(b.pay)],
            ['Deposits', usd(b.deposits)],
            ['Provider', b.provider_id],
          ]} />
        </Panel>
        <Panel title="Household">
          <Facts rows={[
            ['Zone', b.household?.zone ?? '—'],
            ['Batteries', b.household?.batteries.map(k => `${k} kWh`).join(', ') || '—'],
            ['Reserve', pct(b.household?.reserve_pct)],
          ]} />
          <div aria-label="Hourly load schedule" role="img" style={{ display: 'grid', gridTemplateColumns: 'repeat(24, 1fr)', gap: 2, marginTop: '0.5rem' }}>
            {(b.household?.schedule ?? []).map((load, hour) => <span key={hour} title={`${hour}:00 · load ${load}`}
              style={{ height: '0.75rem', borderRadius: 2, background: 'var(--color-accent)', opacity: 0.25 + 0.75 * Math.min(1, load) }} />)}
          </div>
        </Panel>
      </div>
      <div className="gm-stats">
        <Panel title="Performance">
          <Facts rows={[
            ['Cash', usd(b.cash)],
            ['Net worth', usd(b.net_worth)],
            ['P&L', usd(b.pnl)],
            ['Trades', b.trades ?? '—'],
            ['Losses', b.losses],
            ['Loss share', pct(b.loss_share)],
            ['Worst loss', usd(b.worst_loss)],
            ['State', <Badge key="state" variant={b.dormant ? 'warning' : 'success'} label={b.dormant ? 'dormant' : 'active'} />],
          ]} />
        </Panel>
        <Panel title="Balance history" className="gm-span-2">
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={b.balance_history ?? []} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
              <CartesianGrid stroke="var(--color-border)" />
              <XAxis dataKey="at" tickFormatter={day} stroke="var(--color-text-secondary)" />
              <YAxis domain={['auto', 'auto']} stroke="var(--color-text-secondary)" />
              <Tooltip formatter={v => usd(Number(v))} labelFormatter={l => day(String(l))} />
              <Line type="monotone" dataKey="balance" stroke="var(--color-accent)" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </Panel>
      </div>
    </>}
  </section>;
}
