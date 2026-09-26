import { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import Panel from '../components/Panel';
import { get, send } from '../api';
import type { ReplayDecision, ReplayRun, ReplayScore } from '../api';
import { FeedBody, PageHeading } from './Market';

const ReplayChart = lazy(() => import('../components/ReplayChart'));

const STRATEGIES = [
  { id: 'fixed_schedule', label: 'Fixed schedule' },
  { id: 'price_based', label: 'Price-based' },
  { id: 'esr_informed', label: 'Battery-aware' },
];
const ZONES = ['LZ_HOUSTON', 'LZ_NORTH', 'LZ_SOUTH', 'LZ_WEST'];
const SPEEDS = [15, 60, 240];
const SOURCES = ['rt_spp', 'dam_spp', 'load', 'esr'];
const HOMES = 4;
const DAY_HINT = 'Historical ERCOT observations; simulated households, batteries, procurement and outcomes.';

const strategyLabel = (id: string) => STRATEGIES.find(s => s.id === id)?.label ?? id;
const clock = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Chicago', hour: 'numeric', minute: '2-digit' });
const fmtTime = (iso: string) => `${clock.format(new Date(iso))} CT`;
const fmtDay = (day: string) => new Intl.DateTimeFormat('en-GB', { timeZone: 'America/Chicago', day: 'numeric', month: 'long', year: 'numeric' }).format(new Date(`${day}T12:00:00Z`));
// True minus (U+2212) for negatives, per docs/design/DESIGN.md.
const money = (cents: number) => `${cents < 0 ? '−' : cents > 0 ? '+' : ''}$${(Math.abs(cents) / 100).toFixed(2)}`;
const messageOf = (reason: unknown) => (reason as { error?: { message?: string } })?.error?.message ?? String(reason);
const hashDay = () => new URLSearchParams(window.location.hash.split('?')[1] ?? '').get('day') ?? '';

/** Four simulated homes on one provider; the load interval covers any Chicago day without DST arithmetic. */
const fleetFor = (zone: string, day: string) => {
  const noon = new Date(`${day}T00:00:00Z`).getTime();
  const iso = (at: number) => new Date(at).toISOString().replace('.000Z', 'Z');
  return {
    zone,
    assets: Array.from({ length: HOMES }, (_, i) => ({
      asset_id: `home-${i}`, provider_id: 'sim',
      capacity_kwh: '13.5', initial_soc_kwh: '6.75', min_reserve_kwh: '5.4',
      max_charge_kw: '5', max_discharge_kw: '5', eta_round_trip: '0.9',
    })),
    household_load: { unit: 'kW', intervals: [{ interval_start: iso(noon - 12 * 3600 * 1000), interval_end: iso(noon + 36 * 3600 * 1000), kw: '0.8' }] },
  };
};

type LaneCell = { action: string; delivered: number; soc: number | null };
type RunView = {
  quarters: { start: string; end: string; at: number }[];
  prices: { at: number; price: number }[]; priceKind: string;
  procurement: boolean[]; procurementLabel: string;
  lanes: { strategy: string; cells: LaneCell[] }[];
  capacity: number; hasSelfSupply: boolean;
};
const ACTION_RANK = ['offer_flex', 'self_supply', 'charge', 'preserve_backup', 'hold'];
const actionWord = (action: string) => ({ charge: 'charging', offer_flex: 'offering flexibility', self_supply: 'self-supplying', hold: 'holding', preserve_backup: 'preserving backup' }[action] ?? action);

/** Pure derivation from one served run body; probes S69b keys first, falls back to S69 shapes. */
function buildView(run: ReplayRun): RunView {
  const quarters = run.timeline.map(step => ({ start: step.interval_start, end: step.interval_end, at: Date.parse(step.interval_start) }));
  const dam = new Map<string, number>();
  const rtp = new Map<string, number>();
  for (const step of run.timeline) for (const decision of step.decisions) for (const input of decision.inputs) {
    const value = Number(input.value);
    if (!Number.isFinite(value) || !input.interval_start) continue;
    if (input.source === 'dam_spp' && !dam.has(input.interval_start)) dam.set(input.interval_start, value);
    if (input.source === 'rt_spp' && !rtp.has(input.interval_start)) rtp.set(input.interval_start, value);
  }
  const series = rtp.size >= quarters.length * 0.9 ? rtp : dam;
  const prices = [...series].map(([at, price]) => ({ at: Date.parse(at), price })).sort((a, b) => a.at - b.at);
  const priceKind = series === rtp ? 'Real-time' : 'Day-ahead';
  const proc = new Set(run.procurement_quarters ?? []);
  if (!proc.size) for (const step of run.timeline) for (const settle of step.settlements) {
    if (Number(settle.accepted_kwh) > 0) proc.add(settle.delivery_start);
  }
  const procurement = quarters.map(q => proc.has(q.start));
  const ranges: string[] = [];
  for (let i = 0; i < quarters.length; i++) {
    if (!procurement[i] || procurement[i - 1]) continue;
    let j = i;
    while (j + 1 < quarters.length && procurement[j + 1]) j++;
    ranges.push(`${clock.format(new Date(quarters[i].start))}–${clock.format(new Date(quarters[j].end))}`);
  }
  const strategies = run.binding.strategies.length ? run.binding.strategies : [...new Set(run.scoreboard.map(s => s.strategy))];
  let hasSelfSupply = false;
  const lanes = strategies.map(strategy => {
    const fleet = new Map((run.fleet_timeline?.[strategy] ?? []).map(row => [row.interval_start, row]));
    return {
      strategy,
      cells: run.timeline.map(step => {
        const votes = new Map<string, number>();
        let soc: number | null = 0;
        for (const d of step.decisions.filter(d => d.strategy === strategy)) {
          votes.set(d.action, (votes.get(d.action) ?? 0) + 1);
          const snap = fleet.get(step.interval_start)?.soc_kwh ?? d.config.state_snapshot?.soc_kwh;
          const value = snap === undefined ? NaN : Number(snap);
          soc = soc === null || !Number.isFinite(value) ? null : soc + value;
          if (d.action === 'self_supply') hasSelfSupply = true;
        }
        const action = [...votes].sort((a, b) => b[1] - a[1] || ACTION_RANK.indexOf(a[0]) - ACTION_RANK.indexOf(b[0]))[0]?.[0] ?? 'hold';
        const delivered = step.settlements
          .filter(s => s.strategy === strategy && s.delivery_start === step.interval_start)
          .reduce((sum, s) => sum + Number(s.delivered_kwh), 0);
        return { action, delivered, soc } satisfies LaneCell;
      }),
    };
  });
  const capacity = run.binding.fleet.assets.reduce((sum, a) => sum + Number(a.capacity_kwh), 0);
  return { quarters, prices, priceKind, procurement, procurementLabel: ranges.length ? `${ranges.join(', ')} CT` : 'none in this run', lanes, capacity, hasSelfSupply };
}

const actionSentence = (d: ReplayDecision) => {
  const kw = Number(d.kw).toFixed(2);
  const window = `${fmtTime(d.delivery_start)}–${fmtTime(d.delivery_end)}`;
  if (d.action === 'charge') return `Charged at ${kw} kW during ${window}.`;
  if (d.action === 'offer_flex') return `Offered ${kw} kW for delivery ${window}.`;
  if (d.action === 'self_supply') return `Powered its own simulated home at ${kw} kW during ${window}.`;
  if (d.action === 'preserve_backup') return `Preserved backup; no new dispatch ${window}.`;
  return `Held position during ${window}.`;
};

/** Ledger phrases for the components whose posted cents changed between baseline and scenario. */
function ledgerDeltas(base: ReplayScore, scen: ReplayScore): string {
  const parts: string[] = [];
  const line: [string, number, number][] = [
    ['energy value', base.energy_value_cents, scen.energy_value_cents],
    ['charging cost', base.charging_cost_cents, scen.charging_cost_cents],
    ['flexibility bonus', base.flexibility_bonus_cents, scen.flexibility_bonus_cents],
    ['shortfall penalty', base.shortfall_penalty_cents, scen.shortfall_penalty_cents],
  ];
  for (const [label, b, s] of line) if (s !== b) parts.push(`${label} ${money(s - b)}`);
  const marks = (scen.terminal_energy_value_cents - scen.opening_energy_value_cents) - (base.terminal_energy_value_cents - base.opening_energy_value_cents);
  if (marks !== 0) parts.push(`inventory marks ${money(marks)}`);
  const failed = scen.failed_commitments - base.failed_commitments;
  if (failed !== 0) parts.push(`${failed > 0 ? '+' : ''}${failed} failed commitment${Math.abs(failed) === 1 ? '' : 's'}`);
  return parts.length ? parts.join('; ') : 'No ledger change.';
}

type DayInfo = { day: string; label: string; availability_mode: string; availability_note: string; gaps: string[]; peak_rt_price: { point: string; interval_start: string; interval_end: string; value: number; unit: string }; dataset_digest: string };

export default function Replay() {
  const [days, setDays] = useState<DayInfo[] | null>(null);
  const [daysError, setDaysError] = useState<string | null>(null);
  const [day, setDay] = useState(hashDay());
  const [zone, setZone] = useState('LZ_HOUSTON');
  const [base, setBase] = useState<ReplayRun | null>(null);
  const [baseError, setBaseError] = useState<string | null>(null);
  const [baseLoading, setBaseLoading] = useState(true);
  const [reruns, setReruns] = useState(0);
  const [firstId, setFirstId] = useState<string | null>(null);
  const [scen, setScen] = useState<ReplayRun | null>(null);
  const [scenError, setScenError] = useState<string | null>(null);
  const [scenLoading, setScenLoading] = useState(false);
  const [head, setHead] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(60);
  const [selStrategy, setSelStrategy] = useState('esr_informed');
  const [selAsset, setSelAsset] = useState('home-0');
  const [dtype, setDtype] = useState<'provider_offline' | 'feed_interrupt'>('provider_offline');
  const [source, setSource] = useState('rt_spp');
  const [startIdx, setStartIdx] = useState(-1);
  const [endIdx, setEndIdx] = useState(-1);
  const [formError, setFormError] = useState<string | null>(null);
  const reduced = useMemo(() => typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches, []);

  useEffect(() => {
    get<{ days: DayInfo[] }>('/v1/replay/days')
      .then(body => setDays(body.days))
      .catch(reason => setDaysError(messageOf(reason)));
    const sync = () => { const d = hashDay(); if (d) setDay(d); };
    window.addEventListener('hashchange', sync);
    return () => window.removeEventListener('hashchange', sync);
  }, []);
  useEffect(() => {
    if (days && days.length && !days.some(d => d.day === day)) setDay(days[0].day);
  }, [days, day]);
  useEffect(() => {
    if (!day || !days?.some(d => d.day === day)) return;
    let live = true;
    setBaseLoading(true);
    setBaseError(null);
    send<ReplayRun>('POST', '/v1/replay', { day, strategies: STRATEGIES.map(s => s.id), fleet: fleetFor(zone, day), seed: 0, disruptions: [] })
      .then(run => {
        if (!live) return;
        setFirstId(id => id ?? run.run_id);
        setBase(run);
        setScen(null);
        setHead(0);
        setPlaying(false);
        setStartIdx(-1);
        setEndIdx(-1);
      })
      .catch(reason => live && setBaseError(messageOf(reason)))
      .finally(() => live && setBaseLoading(false));
    return () => { live = false; };
  }, [day, zone, reruns, days]);
  useEffect(() => { setFirstId(null); setReruns(0); }, [day, zone]);

  const view = useMemo(() => base && buildView(base), [base]);
  const dayInfo = days?.find(d => d.day === day);
  const quarters = view?.quarters ?? [];
  useEffect(() => {
    if (view && startIdx < 0) {
      const first = view.procurement.findIndex(Boolean);
      const fallback = view.quarters.findIndex(q => new Date(q.start).getUTCHours() === 22);
      const start = first >= 0 ? first : Math.max(fallback, 0);
      setStartIdx(start);
      setEndIdx(Math.min(start + 4, view.quarters.length));
    }
  }, [view, startIdx]);
  useEffect(() => {
    if (!playing || reduced || head >= quarters.length - 1) {
      if (head >= quarters.length - 1) setPlaying(false);
      return;
    }
    const timer = window.setInterval(() => setHead(h => Math.min(h + 1, quarters.length - 1)), 15000 / speed);
    return () => window.clearInterval(timer);
  }, [playing, reduced, speed, head, quarters.length]);

  const why: ReplayDecision | null = base?.timeline[head]?.decisions.find(d => d.strategy === selStrategy && d.asset_id === selAsset)
    ?? base?.timeline[head]?.decisions.find(d => d.strategy === selStrategy) ?? null;
  const peak = dayInfo ? { at: Date.parse(dayInfo.peak_rt_price.interval_start), price: dayInfo.peak_rt_price.value } : null;
  const areas = useMemo(() => {
    if (!view) return [];
    const out: { from: number; to: number }[] = [];
    view.quarters.forEach((q, i) => {
      if (view.procurement[i] && !view.procurement[i - 1]) out.push({ from: q.at, to: q.at });
      if (view.procurement[i]) out[out.length - 1].to = Date.parse(q.end);
    });
    return out;
  }, [view]);
  const moveHead = (lane: HTMLElement, next: number) => {
    const clamped = Math.max(0, Math.min(quarters.length - 1, next));
    setHead(clamped);
    (lane.querySelector(`[data-q="${clamped}"]`) as HTMLElement | null)?.focus();
  };
  const runScenario = () => {
    if (!base || !view) return;
    setFormError(null);
    setScenError(null);
    if (startIdx < 0 || endIdx <= startIdx || endIdx > quarters.length) {
      setFormError('Pick a disruption window inside the day with its end after its start.');
      return;
    }
    const window = dtype === 'provider_offline'
      ? { type: dtype, provider_id: base.binding.fleet.assets[0].provider_id, start: quarters[startIdx].start, end: quarters[endIdx]?.start ?? quarters[quarters.length - 1].end }
      : { type: dtype, source, start: quarters[startIdx].start, end: quarters[endIdx]?.start ?? quarters[quarters.length - 1].end };
    setScenLoading(true);
    send<ReplayRun>('POST', '/v1/replay', { day, strategies: base.binding.strategies, fleet: fleetFor(zone, day), seed: 0, disruptions: [window] })
      .then(run => setScen(run))
      .catch(reason => setScenError(messageOf(reason)))
      .finally(() => setScenLoading(false));
  };
  const reset = () => {
    setScen(null);
    setScenError(null);
    setFormError(null);
    setHead(0);
    setPlaying(false);
    setSelStrategy('esr_informed');
    setSelAsset('home-0');
    setStartIdx(-1);
    setEndIdx(-1);
  };
  const sameId = reruns > 0 && firstId !== null && base?.run_id === firstId;

  return <>
    <PageHeading eyebrow="08 / HISTORICAL REPLAY" title="Replay" />
    {(daysError ?? baseError) && <p className="connection-line has-error" role="alert">{daysError ?? baseError}</p>}

    <div className="page-grid"><Panel title="Replay day" index="01" className="span-all" busy={baseLoading} meta={<span>{base ? `RUN ${base.run_id.slice(0, 12)}` : 'NO RUN'}</span>}>
      <div className="replay-head">
        <label>Day <select aria-label="Replay day" value={day} onChange={e => { setDay(e.target.value); window.location.hash = `#/replay?day=${e.target.value}` }}>
          {(days ?? []).map(d => <option key={d.day} value={d.day}>{d.day}</option>)}
        </select></label>
        <label>Zone <select aria-label="Zone" value={zone} onChange={e => setZone(e.target.value)}>
          {ZONES.map(z => <option key={z} value={z}>{z.replace(/^LZ_/, '')}</option>)}
        </select></label>
        <span className="muted">{day ? fmtDay(day) : '…'}</span>
        <span className="muted">Source {dayInfo?.label ?? (days ? 'unavailable' : '…')}</span>
        <span className={`tag ${base?.availability_mode === 'strict' ? 'up' : 'info'}`}>{base ? `${base.availability_mode} availability` : '…'}</span>
        {base && sameId && <span className="muted">Rerun returned the identical run id.</span>}
      </div>
      <p className="panel-copy">{base?.disclaimer ?? DAY_HINT}</p>
      <details className="panel-copy"><summary>Availability assumption</summary><p className="muted">{base?.availability_note ?? '…'}</p></details>
      <p className="panel-copy muted">Optional gaps: {dayInfo ? (dayInfo.gaps.length ? dayInfo.gaps.join(', ') : 'none') : '…'}</p>
    </Panel></div>

    <div className="replay-grid">
      <div className="replay-main">
        <Panel title="Prices and playback" index="02" className="reserve-prices" busy={baseLoading} meta={<span>{quarters.length ? fmtTime(quarters[Math.min(head, quarters.length - 1)].start) : '…'}</span>}>
          <FeedBody feed={{ data: view, error: baseError, loading: baseLoading }} unavailable="Replay unavailable · check the day and retry">
            {view && <>
              <div className="transport">
                {reduced
                  ? <button type="button" className="show-book" onClick={() => setHead(h => Math.min(h + 1, quarters.length - 1))} disabled={head >= quarters.length - 1}>Step</button>
                  : <button type="button" className="show-book" aria-pressed={playing} onClick={() => setPlaying(p => !p)}>{playing ? 'Pause' : 'Play'}</button>}
                <label>Speed <select aria-label="Speed" value={speed} onChange={e => setSpeed(Number(e.target.value))} disabled={reduced}>
                  {SPEEDS.map(s => <option key={s} value={s}>{s}×</option>)}
                </select></label>
                <label className="head-slider">Playback position <input type="range" aria-label="Playback position" min={0} max={quarters.length - 1} value={Math.min(head, quarters.length - 1)} onChange={e => setHead(Number(e.target.value))} /></label>
              </div>
              <div className="chart" role="img" aria-label={view.prices.length
                ? `${view.priceKind} ${base?.binding.fleet.zone.replace(/^LZ_/, '')} prices, ${view.prices.length} points; procurement ${view.procurementLabel}; playback ${quarters[head] ? fmtTime(quarters[head].start) : 'at start'}.`
                : 'No price series in this run.'}>
                {view.prices.length ? <Suspense fallback={<div className="empty loading">Drawing the price curve…</div>}>
                  <ReplayChart data={view.prices} kind={view.priceKind} areas={areas} headAt={quarters[head]?.at ?? null} peak={peak} />
                </Suspense> : <div className="empty">Price series unavailable in this run.</div>}
              </div>
              <p className="chart-foot"><span>Full-day chart · hindsight, not a strategy input</span><span>Procurement {view.procurementLabel}</span></p>
              {dayInfo && <p className="chart-foot"><span>Day peak real-time ${dayInfo.peak_rt_price.value.toFixed(2)}/MWh at {fmtTime(dayInfo.peak_rt_price.interval_start)} ({dayInfo.peak_rt_price.point})</span><span>{view.priceKind} series · {base?.binding.fleet.zone}</span></p>}
            </>}
          </FeedBody>
        </Panel>

        <Panel title="Strategy lanes" index="03" className="reserve-lanes" busy={baseLoading} meta={<span>{HOMES} SIMULATED HOMES</span>}>
          <FeedBody feed={{ data: view, error: baseError, loading: baseLoading }} unavailable="Lanes unavailable · check the day and retry">
            {view && <div className="replay-lanes">
              {view.lanes.map(lane => {
                const cell = lane.cells[Math.min(head, lane.cells.length - 1)];
                const pct = cell?.soc === null || cell?.soc === undefined || !view.capacity ? null : cell.soc / view.capacity * 100;
                return <div key={lane.strategy} className="lane-row" role="group" aria-label={`${strategyLabel(lane.strategy)} lane`}
                  onKeyDown={e => {
                    if (e.key === 'ArrowRight') moveHead(e.currentTarget, head + 1);
                    else if (e.key === 'ArrowLeft') moveHead(e.currentTarget, head - 1);
                    else if (e.key === 'Home') moveHead(e.currentTarget, 0);
                    else if (e.key === 'End') moveHead(e.currentTarget, quarters.length - 1);
                    else return;
                    e.preventDefault();
                  }}>
                  <button type="button" className="lane-name" onClick={() => setSelStrategy(lane.strategy)} aria-pressed={selStrategy === lane.strategy}>{strategyLabel(lane.strategy)}</button>
                  <div className="lane-track">
                    {lane.cells.map((c, i) => <button key={i} type="button" data-q={i} tabIndex={i === head ? 0 : -1}
                      className={`lane-cell${c.delivered > 0.000001 ? ' is-deliver' : c.action === 'charge' ? ' is-charge' : c.action === 'self_supply' ? ' is-self' : ''}${i === head ? ' is-head' : ''}`}
                      aria-label={`${strategyLabel(lane.strategy)}, ${fmtTime(quarters[i].start)}: ${c.delivered > 0.000001 ? 'delivering' : actionWord(c.action)}${c.soc !== null && view.capacity ? `, fleet SoC ${(c.soc / view.capacity * 100).toFixed(0)}%` : ''}`}
                      onClick={() => { setHead(i); setSelStrategy(lane.strategy); }} />)}
                  </div>
                  <span className="lane-soc num">SoC {pct === null ? '—' : `${pct.toFixed(0)}%`}</span>
                </div>;
              })}
              <p className="chart-foot"><span><i className="swatch is-charge" />Charging</span><span><i className="swatch is-deliver" />Delivering promised flexibility</span>{view.hasSelfSupply && <span><i className="swatch is-self" />Self-supply</span>}<span>Gap = holding</span></p>
              <p className="panel-copy muted">State of charge is simulated fleet energy over {HOMES} homes; capacity {view.capacity.toFixed(1)} kWh.</p>
            </div>}
          </FeedBody>
        </Panel>
      </div>

      <div className="replay-aside">
        <Panel title="Scoreboard · baseline" index="04" className="reserve-score" busy={baseLoading} meta={<span>SIMULATED</span>}>
          <FeedBody feed={{ data: base, error: baseError, loading: baseLoading }} unavailable="Scoreboard unavailable · check the day and retry">
            {base && <div className="table-scroll"><table className="data-table replay-board">
              <thead><tr><th scope="col">Strategy</th><th scope="col" className="end">Net value</th><th scope="col" className="end">Cash net</th><th scope="col" className="end">Marks</th><th scope="col" className="end">Delivered</th><th scope="col" className="end">Min backup</th><th scope="col" className="end">Broken</th></tr></thead>
              <tbody>{base.scoreboard.map(row => {
                const cap = view?.capacity ?? 0;
                return <tr key={row.strategy}>
                  <th scope="row">{strategyLabel(row.strategy)}</th>
                  <td className={`num end ${row.net_value_cents < 0 ? 'down-text' : 'up-text'}`}>{money(row.net_value_cents)}</td>
                  <td className="num end">{money(row.cash_net_cents)}</td>
                  <td className="num end">{money(row.terminal_energy_value_cents - row.opening_energy_value_cents)}</td>
                  <td className="num end">{Number(row.energy_delivered_kwh).toFixed(2)} kWh</td>
                  <td className="num end">{cap ? `${(Number(row.observed_min_soc_kwh) / cap * 100).toFixed(1)}%` : '—'}</td>
                  <td className="num end">{row.failed_commitments}</td>
                </tr>;
              })}</tbody>
            </table></div>}
          </FeedBody>
          {base && <p className="panel-copy muted">Marks are non-cash inventory value; backup floor {base.scoreboard[0] ? Number(base.scoreboard[0].min_reserve_kwh).toFixed(1) : '—'} kWh per home.</p>}
        </Panel>

        <Panel title="Why this decision" index="05" className="reserve-why" busy={baseLoading} meta={<span>{why ? fmtTime(why.decision_time) : '…'}</span>}>
          <FeedBody feed={{ data: why, error: baseError, loading: baseLoading }} unavailable="No decision at the playback head.">
            {why && <>
              <div className="why-pick">
                <div role="radiogroup" aria-label="Strategy" className="radio-row">
                  {STRATEGIES.map(s => <label key={s.id}><input type="radio" name="why-strategy" checked={selStrategy === s.id} onChange={() => setSelStrategy(s.id)} /> {s.label}</label>)}
                </div>
                <label>Home <select aria-label="Home" value={selAsset} onChange={e => setSelAsset(e.target.value)}>
                  {(base?.binding.fleet.assets ?? []).map(a => <option key={a.asset_id} value={a.asset_id}>{a.asset_id}</option>)}
                </select></label>
              </div>
              <p className="why-action">{strategyLabel(why.strategy)} · {why.asset_id} — {actionSentence(why)}</p>
              <p className="panel-copy">{why.reason}</p>
              {why.inputs.length ? <div className="table-scroll why-inputs"><table className="data-table">
                <thead><tr><th scope="col">Input</th><th scope="col">Value</th><th scope="col">Source</th><th scope="col">Published</th><th scope="col">Available</th></tr></thead>
                <tbody>{why.inputs.map((input, i) => <tr key={`${input.name}-${i}`}>
                  <td>{input.name}</td>
                  <td className="num">{String(input.value)} {input.unit}</td>
                  <td>{input.source}</td>
                  <td><time dateTime={input.published_at}>{fmtTime(input.published_at)}</time></td>
                  <td><time dateTime={input.available_at}>{fmtTime(input.available_at)}</time></td>
                </tr>)}</tbody>
              </table></div> : <p className="panel-copy muted">No inputs recorded for this decision.</p>}
            </>}
          </FeedBody>
        </Panel>

        <Panel title="Disruptions" index="06" busy={scenLoading} meta={<span>{scen ? `SCENARIO ${scen.run_id.slice(0, 12)}` : 'BASELINE ONLY'}</span>}>
          <div className="disrupt-form">
            <div role="radiogroup" aria-label="Disruption type" className="radio-row">
              <label><input type="radio" name="dtype" checked={dtype === 'provider_offline'} onChange={() => setDtype('provider_offline')} /> Provider offline</label>
              <label><input type="radio" name="dtype" checked={dtype === 'feed_interrupt'} onChange={() => setDtype('feed_interrupt')} /> Feed interrupt</label>
            </div>
            {dtype === 'provider_offline'
              ? <p className="muted">Provider {base?.binding.fleet.assets[0]?.provider_id ?? '…'} · dispatch blocked, liabilities kept — not a household blackout.</p>
              : <label>Source <select aria-label="Feed source" value={source} onChange={e => setSource(e.target.value)}>
                {SOURCES.map(s => <option key={s} value={s}>{s}</option>)}
              </select></label>}
            <div className="window-row">
              <label>From <select aria-label="Window start" value={startIdx} onChange={e => setStartIdx(Number(e.target.value))}>
                {quarters.map((q, i) => <option key={q.start} value={i}>{fmtTime(q.start)}</option>)}
              </select></label>
              <label>To <select aria-label="Window end" value={endIdx} onChange={e => setEndIdx(Number(e.target.value))}>
                {quarters.map((q, i) => <option key={q.end} value={i + 1}>{fmtTime(q.end)}</option>)}
              </select></label>
            </div>
            {formError && <p className="connection-line has-error" role="alert">{formError}</p>}
            {scenError && <p className="connection-line has-error" role="alert">{scenError}</p>}
            <div className="button-row">
              <button type="button" className="show-book" onClick={runScenario} disabled={!base || scenLoading}>Run scenario</button>
              <button type="button" className="show-book" onClick={reset}>Reset</button>
              <button type="button" className="show-book" onClick={() => setReruns(n => n + 1)} disabled={!base}>Rerun baseline</button>
            </div>
          </div>
        </Panel>

        {scen && base && <Panel title="Baseline versus scenario" index="07" meta={<span>{scen.binding.disruptions.length} DISRUPTION{scen.binding.disruptions.length === 1 ? '' : 'S'}</span>}>
          <div className="table-scroll"><table className="data-table replay-board">
            <thead><tr><th scope="col">Strategy</th><th scope="col" className="end">Baseline</th><th scope="col" className="end">Scenario</th><th scope="col" className="end">Δ net</th><th scope="col">Ledger explains</th></tr></thead>
            <tbody>{base.scoreboard.map(row => {
              const alt = scen.scoreboard.find(s => s.strategy === row.strategy);
              if (!alt) return null;
              return <tr key={row.strategy}>
                <th scope="row">{strategyLabel(row.strategy)}</th>
                <td className="num end">{money(row.net_value_cents)}</td>
                <td className="num end">{money(alt.net_value_cents)}</td>
                <td className={`num end ${alt.net_value_cents - row.net_value_cents < 0 ? 'down-text' : 'up-text'}`}>{money(alt.net_value_cents - row.net_value_cents)}</td>
                <td>{ledgerDeltas(row, alt)}</td>
              </tr>;
            })}</tbody>
          </table></div>
          <p className="panel-copy muted">Same starting fleet; only simulated decisions, dispatch and score change. Historical grid prices stay fixed.</p>
        </Panel>}
      </div>
    </div>
  </>;
}
