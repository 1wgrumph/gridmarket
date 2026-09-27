import type { ReactNode } from 'react';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { centralTime, contextLink, query } from '../components/navigation';
import Panel from '../components/Panel';
import { useBotProfile } from '../hooks';
import { usd } from '../format';
import type { Bot } from '../api';
import { FeedBody, PageHeading, Stale } from './Market';

/** Contract Bot fields plus the profile extras; extras may be absent, so they render as "—". */
type Profile = Bot & Partial<{
  blend: Record<string, number>; trades: number; loss_share: number; worst_loss: number;
  traits: { 'risk appetite'?: number; risk_appetite?: number; patience?: number };
  household: { batteries: number[]; zone: string; reserve_pct: number; schedule: number[] };
  employed: boolean; pay: number; balance: number[]; deposits: number;
  balance_history: { at: string; balance: number }[];
}>;

const pct = (p?: number) => p === undefined ? '—' : `${Math.round(p * 100)}%`;
const day = centralTime;
const tick = { fill: 'var(--muted)', fontSize: 11 };
const tooltip = { background: 'var(--surface)', border: '1px solid var(--line)', color: 'var(--text)', fontSize: 12, borderRadius: 'var(--r-2)' };

function Facts({ rows }: { rows: [string, ReactNode][] }) {
  return <dl className="facts">
    {rows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
  </dl>;
}

export default function BotProfile({ id }: { id: string }) {
  const profile = useBotProfile(id);
  const b = profile.data as Profile | null;
  const meta = <><Stale feed={profile}/><span>SIMULATED</span></>;

  return <>
    <PageHeading eyebrow="08 / BOT POPULATION" title={`Bot profile · ${id}`}>
      <a className="back-link" href="#/bots">All bots</a>
    </PageHeading>
    {query().get('at') && <p className="panel-copy">Selected event: {centralTime(query().get('at')!)}. Performance below is the latest simulation snapshot.</p>}
    {!b ? <div className="page-grid"><Panel title="Profile" index="01" className="span-all profile-reserve" busy={profile.loading}>
      <FeedBody feed={profile} unavailable="Bot profile not yet available" reserve="reserve-profile"><div className="empty">No profile.</div></FeedBody>
    </Panel></div> : <>
      <div className="page-grid thirds">
        <Panel title="Traits" index="01" meta={meta}>
          <Facts rows={[['Risk appetite', pct(b.traits?.['risk appetite'] ?? b.traits?.risk_appetite)], ['Patience', pct(b.traits?.patience)]]}/>
          <h3 className="sub-head">Strategy blend</h3>
          <Facts rows={Object.entries(b.blend ?? {}).map(([type, w]) => [type, pct(w)])}/>
        </Panel>
        <Panel title="Economy" index="02" meta={meta}>
          <Facts rows={[
            ['Employment', b.employed === undefined ? 'Unavailable' : b.employed ? 'Employed' : 'Not employed'],
            ['Pay per period', usd(b.pay)],
            ['Deposits', usd(b.deposits ?? (b.balance?.length === 2 ? b.balance[1] - b.balance[0] : undefined))],
            ['Provider', <a key="provider" href={contextLink('#/providers', { provider: b.provider_id })}>{b.provider_id}</a>],
          ]}/>
        </Panel>
        <Panel title="Household" index="03" meta={meta}>
          <Facts rows={[
            ['Zone', b.household?.zone ?? '—'],
            ['Batteries', b.household?.batteries.map(k => `${k} kWh`).join(', ') || '—'],
            ['Reserve', pct(b.household?.reserve_pct)],
          ]}/>
          <h3 className="sub-head">Hourly load schedule</h3>
          <div className="schedule" aria-label={`Hourly load schedule: ${(b.household?.schedule ?? []).map((load, hour) => `${hour}:00 load ${load}`).join('; ')}`} role="img">
            {(b.household?.schedule ?? []).map((load, hour) => <span key={hour} title={`${hour}:00 · load ${load}`} style={{ opacity: 0.25 + 0.75 * load / Math.max(1, ...(b.household?.schedule ?? [])) }}/>)}
          </div>
          <div className="schedule-hours">{[0, 6, 12, 18, 23].map(hour => <span key={hour}>{hour}</span>)}</div>
          <p className="panel-copy">Hours 0–23 · Load weight legend: low (pale) to high (solid green). Hours in CT.</p>
        </Panel>
      </div>
      <div className="page-grid thirds">
        <Panel title="Performance" index="04" meta={meta}>
          <Facts rows={[
            ['Cash', usd(b.cash)],
            ['Net worth', usd(b.net_worth)],
            ['P&L', <span key="pnl" className={b.pnl < 0 ? 'down-text' : 'up-text'}>{usd(b.pnl)}</span>],
            ['Trades', b.trades ?? '—'],
            ['Losses', b.losses],
            ['Loss share', pct(b.loss_share)],
            ['Worst loss', usd(b.worst_loss)],
            ['State', <span key="state" className={`tag ${b.dormant ? 'down' : 'up'}`}>{b.dormant ? 'dormant' : 'active · not dormant'}</span>],
          ]}/>
        </Panel>
        <Panel title="Balance history" index="05" className="span-2" meta={meta}>
          <div className="chart" role="img" aria-label={`Simulated balance, ${b.balance_history?.length ?? 0} points.`}>
            {b.balance_history?.length ? <ResponsiveContainer width="100%" height="100%" minWidth={0}>
              <LineChart data={b.balance_history} margin={{ top: 24, right: 36, left: 0, bottom: 2 }}>
                <CartesianGrid stroke="var(--line)" vertical={false} strokeDasharray="2 4"/>
                <XAxis dataKey="at" tickFormatter={day} axisLine={false} tickLine={false} tick={tick}/>
                <YAxis domain={['auto', 'auto']} tickFormatter={v => `$${v}`} axisLine={false} tickLine={false} tick={tick}/>
                <Tooltip formatter={v => [usd(Number(v)), 'Balance']} labelFormatter={l => day(String(l))} contentStyle={tooltip} itemStyle={{ color: 'var(--text)' }} isAnimationActive={false}/>
                <Line type="monotone" dataKey="balance" stroke="var(--accent)" strokeWidth={3} dot={false} isAnimationActive={false}/>
              </LineChart>
            </ResponsiveContainer> : <div className="empty">No balance history served.</div>}
          </div>
        </Panel>
      </div>
    </>}
    <p className="context-actions"><a href={contextLink('#/market', { zone: b?.household?.zone })}>View this household’s market</a> · <a href="#/bots">Compare bots</a></p>
  </>;
}
