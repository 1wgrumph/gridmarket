import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react';
import { completeFirstStep } from '../components/FirstSteps';
import Icon from '../components/Icon';
import Panel from '../components/Panel';
import { get, send } from '../api';
import type { ReplayDecision, ReplayRun, ReplayScore } from '../api';
import { estimateHome, fleetMw } from '../estimate';
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
const HOMES = 1000;
const DAY_HINT = 'Historical ERCOT observations; simulated households, batteries, procurement and outcomes.';
const HOME_SPEC = { capacityKwh: 13.5, initialSocKwh: 6.75, maxDischargeKw: 5, etaRoundTrip: 0.9, loadKw: 1.2 };
const FALLBACK_HORIZON = 4;

const DEFAULT_DAY = '2026-08-26';
const PLACES: Record<string, string> = {
  LZ_WEST: 'West Texas',
  LZ_NORTH: 'North Texas',
  LZ_SOUTH: 'South Texas',
  LZ_HOUSTON: 'Houston',
};
const strategyLabel = (id: string) => STRATEGIES.find(s => s.id === id)?.label ?? id;
const clock = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Chicago', hour: 'numeric', minute: '2-digit' });
const fmtTime = (iso: string) => `${clock.format(new Date(iso))} CT`;
const fmtDay = (day: string) => new Intl.DateTimeFormat('en-GB', { timeZone: 'America/Chicago', day: 'numeric', month: 'long', year: 'numeric' }).format(new Date(`${day}T12:00:00Z`));
const fmtShort = (day: string) => new Intl.DateTimeFormat('en-GB', { timeZone: 'America/Chicago', day: 'numeric', month: 'short' }).format(new Date(`${day}T12:00:00Z`));
const fmtWeekday = (day: string) => new Intl.DateTimeFormat('en-US', { timeZone: 'America/Chicago', weekday: 'long' }).format(new Date(`${day}T12:00:00Z`));
// True minus (U+2212) for negatives, per docs/design/DESIGN.md.
const money = (cents: number) => `${cents < 0 ? '−' : cents > 0 ? '+' : ''}$${(Math.abs(cents) / 100).toFixed(2)}`;
const messageOf = (reason: unknown) => (reason as { error?: { message?: string } })?.error?.message ?? String(reason);
const inputFmt = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 });
/** Round numeric inputs, truncate comma vectors to 3 values, cap long text. */
const fmtInput = (value: string | number): string => {
  if (Array.isArray(value)) {
    const items = (value as unknown[]).map(String);
    return items.slice(0, 3).join(', ') + (items.length > 3 ? ', …' : '');
  }
  if (typeof value === 'number') return Number.isFinite(value) ? inputFmt.format(value) : String(value);
  const text = value.trim();
  if (text !== '' && Number.isFinite(Number(text))) return inputFmt.format(Number(text));
  if (text.includes(',')) {
    const parts = text.split(',').map(part => part.trim()).filter(Boolean);
    return parts.slice(0, 3).join(', ') + (parts.length > 3 ? ', …' : '');
  }
  return text.length > 80 ? `${text.slice(0, 80)}…` : text;
};
const hashParams = () => new URLSearchParams(window.location.hash.split('?')[1] ?? '');
const onReplay = () => (window.location.hash || '#/replay').split('?')[0] === '#/replay';
const hashDay = () => hashParams().get('day') || DEFAULT_DAY;
const hashInt = (key: string, fallback: number, min: number, max: number) => {
  const value = Number(hashParams().get(key));
  return Number.isInteger(value) && value >= min && value <= max ? value : fallback;
};
/** Silent URL sync (no hashchange): slider state stays shareable and survives Back. */
const writeHash = (mutate: (p: URLSearchParams) => void) => {
  // Replay state belongs to Replay: never write it onto the page being navigated to.
  if (!onReplay()) return;
  const path = (window.location.hash || '#/replay').split('?')[0];
  const params = hashParams();
  mutate(params);
  window.history.replaceState(null, '', `${path}?${params.toString()}`);
};

/** Simulated fleet on one provider; household load is omitted so the engine supplies
    the contract Texas summer profile (averages 1.2 kW, the stated backup load). */
const fleetFor = (zone: string, count: number, reserveKwh: string) => {
  return {
    zone,
    assets: Array.from({ length: count }, (_, i) => ({
      asset_id: `home-${i}`, provider_id: 'sim',
      capacity_kwh: '13.5', initial_soc_kwh: '6.75', min_reserve_kwh: reserveKwh,
      max_charge_kw: '5', max_discharge_kw: '5', eta_round_trip: '0.9',
    })),
  };
};

type LaneCell = { action: string; delivered: number; soc: number | null };
type RunView = {
  quarters: { start: string; end: string; at: number }[];
  prices: { at: number; price: number }[]; priceKind: string;
  procurement: boolean[]; procurementLabel: string;
  lanes: { strategy: string; cells: LaneCell[] }[];
  capacity: number;
};
const actionWord = (action: string) => ({ charge: 'charging', self_supply: 'self-supplying', hold: 'holding', preserve_backup: 'preserving backup' }[action] ?? action);

/** Pure derivation from one served S69b run body: RT curve, procurement hours, fleet lanes. */
function buildView(run: ReplayRun): RunView {
  const quarters = run.timeline.map(step => ({ start: step.interval_start, end: step.interval_end, at: Date.parse(step.interval_start) }));
  const strategies = run.binding.strategies.length ? run.binding.strategies : [...new Set(run.scoreboard.map(s => s.strategy))];
  const prices = (run.fleet_timeline[strategies[0]] ?? [])
    .map(row => ({ at: Date.parse(row.interval_start), price: Number(row.spp) }))
    .filter(point => Number.isFinite(point.price))
    .sort((a, b) => a.at - b.at);
  const priceKind = 'Real-time';
  const hours = (run.procurement_hours ?? []).map(Date.parse);
  const procurement = quarters.map(q => hours.some(h => h <= q.at && q.at < h + 3600 * 1000));
  const ranges: string[] = [];
  for (let i = 0; i < quarters.length; i++) {
    if (!procurement[i] || procurement[i - 1]) continue;
    let j = i;
    while (j + 1 < quarters.length && procurement[j + 1]) j++;
    ranges.push(`${clock.format(new Date(quarters[i].start))}–${clock.format(new Date(quarters[j].end))}`);
  }
  const lanes = strategies.map(strategy => {
    const fleet = new Map((run.fleet_timeline[strategy] ?? []).map(row => [row.interval_start, row]));
    return {
      strategy,
      cells: quarters.map(q => {
        const row = fleet.get(q.start);
        const delivered = Number(row?.delivered_kwh ?? 0);
        const self = Number(row?.self_supply_kwh ?? 0);
        const charge = Number(row?.charge_kw ?? 0);
        const action = self > 0.000001 ? 'self_supply' : charge > 0 ? 'charge' : 'hold';
        const soc = row === undefined ? NaN : Number(row.soc_kwh);
        return { action, delivered, soc: Number.isFinite(soc) ? soc : null } satisfies LaneCell;
      }),
    };
  });
  const capacity = run.binding.fleet.assets.reduce((sum, a) => sum + Number(a.capacity_kwh), 0);
  return { quarters, prices, priceKind, procurement, procurementLabel: ranges.length ? `${ranges.join(', ')} CT` : 'none in this run', lanes, capacity };
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

const WARNING_TEXT: Record<string, (reserve: number) => string> = {
  reserve_not_yet_met: reserve => `Reserve not yet met: the ${reserve.toFixed(1)} kWh reserve sits above the starting charge (${HOME_SPEC.initialSocKwh} kWh), so flexibility is zero until the battery charges past it.`,
  power_insufficient: () => 'Power insufficient: the stated load exceeds the 5 kW discharge limit.',
  not_applicable: () => 'Backup hours do not apply at zero load.',
};

type DayInfo = { day: string; label: string; availability_mode: string; availability_note: string; gaps: string[]; peak_rt_price: { point: string; interval_start: string; interval_end: string; value: number; unit: string }; dataset_digest: string };

export default function Replay() {
  const [days, setDays] = useState<DayInfo[] | null>(null);
  const [daysError, setDaysError] = useState<string | null>(null);
  const [day, setDay] = useState(hashDay());
  const [zone, setZone] = useState(() => {
    const fromUrl = hashParams().get('zone');
    return fromUrl && ZONES.includes(fromUrl) ? fromUrl : 'LZ_HOUSTON';
  });
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
  const [remote, setRemote] = useState<ReplayDecision | null>(null);
  const [remoteError, setRemoteError] = useState<string | null>(null);
  const [remoteLoading, setRemoteLoading] = useState(false);
  const [dtype, setDtype] = useState<'provider_offline' | 'feed_interrupt'>(() => hashParams().get('dtype') === 'feed_interrupt' ? 'feed_interrupt' : 'provider_offline');
  const [source, setSource] = useState(() => SOURCES.includes(hashParams().get('source') ?? '') ? hashParams().get('source') as string : 'rt_spp');
  const [startIdx, setStartIdx] = useState(-1);
  const [endIdx, setEndIdx] = useState(-1);
  const [formError, setFormError] = useState<string | null>(null);
  const [reserve, setReserve] = useState(() => hashInt('reserve', 40, 0, 100));
  const [homes, setHomes] = useState(() => hashInt('homes', 1000, 1, 10000));
  const [valueRun, setValueRun] = useState<ReplayRun | null>(null);
  const [valueError, setValueError] = useState<string | null>(null);
  const [valueLoading, setValueLoading] = useState(false);
  const [valueNonce, setValueNonce] = useState(0);
  const yourRef = useRef<HTMLDivElement>(null);
  const scoreRef = useRef<HTMLDivElement>(null);
  const mountControls = useRef({ reserve, homes, zone, day });
  const headRestored = useRef(false);
  const windowInit = useRef(false);
  const reduced = useMemo(() => typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches, []);

  useEffect(() => {
    get<{ days: DayInfo[] }>('/v1/replay/days')
      .then(body => setDays(body.days))
      .catch(reason => setDaysError(messageOf(reason)));
    const sync = () => { if (onReplay()) setDay(hashDay()); };
    window.addEventListener('hashchange', sync);
    return () => window.removeEventListener('hashchange', sync);
  }, []);
  useEffect(() => {
    if (hashParams().get('panel') === 'your-turn') yourRef.current?.scrollIntoView?.();
  }, []);
  useEffect(() => {
    if (days && days.length && !days.some(d => d.day === day)) {
      const fallback = days.some(d => d.day === DEFAULT_DAY) ? DEFAULT_DAY : days[0].day;
      setDay(fallback);
    }
  }, [days, day]);
  useEffect(() => {
    if (!day || !days?.some(d => d.day === day)) return;
    let live = true;
    setBaseLoading(true);
    setBaseError(null);
    send<ReplayRun>('POST', '/v1/replay', { day, strategies: STRATEGIES.map(s => s.id), fleet: fleetFor(zone, HOMES, '5.4'), seed: 0, disruptions: [] })
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
  const horizon = base?.procurement_hours.length || FALLBACK_HORIZON;
  const estimate = useMemo(() => estimateHome({ ...HOME_SPEC, horizonHours: horizon, reservePct: reserve }), [horizon, reserve]);
  const fleet = useMemo(() => fleetMw({ perHomeKwh: estimate.flexibilityKwh, homes, horizonHours: horizon, maxDischargeKw: HOME_SPEC.maxDischargeKw }), [estimate.flexibilityKwh, homes, horizon]);
  useEffect(() => {
    writeHash(p => {
      p.set('day', day);
      // Back the zone only once it is explicit (URL or user choice); the fallback stays out of links.
      if (zone !== 'LZ_HOUSTON' || hashParams().get('zone') !== null) p.set('zone', zone);
      p.set('reserve', String(reserve));
      p.set('homes', String(homes));
      p.set('dtype', dtype);
      if (dtype === 'feed_interrupt') p.set('source', source); else p.delete('source');
      // Head and window restore from the URL after the run loads; leave the params alone until then.
      if (windowInit.current) {
        if (startIdx >= 0 && endIdx > startIdx && quarters[endIdx - 1]) {
          p.set('dstart', quarters[startIdx].start);
          p.set('dend', quarters[endIdx - 1].end);
        } else {
          p.delete('dstart');
          p.delete('dend');
        }
      }
      if (headRestored.current) {
        if (head > 0) p.set('head', String(head)); else p.delete('head');
      }
    });
  }, [day, zone, reserve, homes, dtype, source, startIdx, endIdx, head, quarters]);
  useEffect(() => {
    if (!view || headRestored.current) return;
    headRestored.current = true;
    const at = hashInt('head', 0, 0, Math.max(0, view.quarters.length - 1));
    if (at > 0) setHead(at);
  }, [view]);
  useEffect(() => {
    if (view && startIdx < 0) {
      const at = (iso: string | null) => iso && view.quarters.findIndex(q => q.start === iso);
      const fromUrl = hashParams().get('dstart');
      const toUrl = hashParams().get('dend');
      const start = Number.isInteger(at(fromUrl)) && (at(fromUrl) as number) >= 0 ? at(fromUrl) as number : view.procurement.findIndex(Boolean);
      const endAt = Number.isInteger(at(toUrl)) && (at(toUrl) as number) > start ? (at(toUrl) as number) + 1 : Math.min(start + 4, view.quarters.length);
      const fallback = view.quarters.findIndex(q => new Date(q.start).getUTCHours() === 22);
      const picked = start >= 0 ? start : Math.max(fallback, 0);
      setStartIdx(picked);
      setEndIdx(start >= 0 ? endAt : Math.min(picked + 4, view.quarters.length));
      windowInit.current = true;
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
  useEffect(() => {
    if (!base || selAsset === base.sample_asset_id) {
      setRemote(null);
      setRemoteError(null);
      setRemoteLoading(false);
      return;
    }
    const window_ = quarters[head];
    if (!window_) return;
    let live = true;
    setRemoteLoading(true);
    setRemoteError(null);
    get<{ run_id: string; decisions: ReplayDecision[] }>(
      `/v1/replay/${base.run_id}/decisions?strategy=${selStrategy}&asset=${selAsset}&start=${encodeURIComponent(window_.start)}&end=${encodeURIComponent(window_.end)}`)
      .then(body => live && setRemote(body.decisions[0] ?? null))
      .catch(reason => live && setRemoteError(messageOf(reason)))
      .finally(() => live && setRemoteLoading(false));
    return () => { live = false; };
  }, [base, selAsset, selStrategy, head, quarters]);
  useEffect(() => {
    if (!day || !days?.some(d => d.day === day)) return;
    if (estimate.warnings.includes('reserve_not_yet_met')) {
      setValueRun(null);
      setValueError(null);
      setValueLoading(false);
      return;
    }
    let live = true;
    setValueLoading(true);
    setValueError(null);
    const reserveKwh = String(Number(estimate.reserveKwh.toFixed(6)));
    const timer = window.setTimeout(() => {
      send<ReplayRun>('POST', '/v1/replay', { day, strategies: ['esr_informed'], fleet: fleetFor(zone, 1, reserveKwh), seed: 0, disruptions: [] })
        .then(run => {
          if (!live) return;
          setValueRun(run);
          const first = mountControls.current;
          if (reserve !== first.reserve || homes !== first.homes || zone !== first.zone || day !== first.day) completeFirstStep(2);
        })
        .catch(reason => live && setValueError(messageOf(reason)))
        .finally(() => live && setValueLoading(false));
    }, 500);
    return () => { live = false; window.clearTimeout(timer); };
  }, [day, zone, days, estimate.reserveKwh, estimate.warnings, valueNonce]);

  const sampleWhy = selAsset === base?.sample_asset_id
    ? base?.timeline[head]?.decisions.find(d => d.strategy === selStrategy && d.asset_id === selAsset)
      ?? base?.timeline[head]?.decisions.find(d => d.strategy === selStrategy) ?? null
    : null;
  const why = sampleWhy ?? (selAsset === base?.sample_asset_id ? null : remote);
  const whyLoading = baseLoading || (selAsset !== base?.sample_asset_id && remoteLoading);
  const whyError = baseError ?? (selAsset !== base?.sample_asset_id ? remoteError : null);
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
  /** User-driven playback moves mark checklist step 1; programmatic sets (load, reset, URL restore) do not. */
  const userHead = (next: number) => { completeFirstStep(1); setHead(next); };
  const moveHead = (lane: HTMLElement, next: number) => {
    const clamped = Math.max(0, Math.min(quarters.length - 1, next));
    completeFirstStep(1);
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
    send<ReplayRun>('POST', '/v1/replay', { day, strategies: base.binding.strategies, fleet: fleetFor(zone, HOMES, '5.4'), seed: 0, disruptions: [window] })
      .then(run => { setScen(run); completeFirstStep(2); })
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
    setSelAsset(base?.sample_asset_id ?? 'home-0');
    setStartIdx(-1);
    setEndIdx(-1);
  };
  const compareHref = (() => {
    const params = hashParams();
    params.delete('panel');
    return `#/replay?${params.toString()}`;
  })();
  const scrollScore = (event: React.MouseEvent) => {
    event.preventDefault();
    writeHash(p => p.delete('panel'));
    scoreRef.current?.scrollIntoView?.();
  };
  const sameId = reruns > 0 && firstId !== null && base?.run_id === firstId;
  const valueScore = valueRun?.scoreboard.find(s => s.strategy === 'esr_informed') ?? valueRun?.scoreboard[0];
  const homeCount = base ? base.binding.fleet.assets.length : HOMES;

  const selectDay = (nextDay: string) => {
    setDay(nextDay);
    const params = hashParams();
    params.set('day', nextDay);
    const path = (window.location.hash || '#/replay').split('?')[0];
    window.location.hash = `${path}?${params.toString()}`;
  };

  const godseye = import.meta.env.VITE_GODSEYE_URL as string | undefined;
  return <>
    <PageHeading eyebrow="03 / HISTORICAL REPLAY" title="Replay">
      {godseye && <a className="action-secondary action-external" href={new URL('/replay/#start', godseye).href} target="_blank" rel="noreferrer">See 26 Aug in 3D (God's Eye) <Icon name="up-right"/></a>}
    </PageHeading>
    {(daysError ?? baseError) && <p className="connection-line has-error" role="alert">{daysError ?? baseError}</p>}

    <div className="page-grid"><Panel title="Replay day" index="01" className="span-all" busy={baseLoading} meta={<span>{base ? `RUN ${base.run_id.slice(0, 12)}` : 'NO RUN'}</span>}>
      <div className="replay-head">
        <label>Day <select aria-label="Replay day" value={day} onChange={e => selectDay(e.target.value)}>
          {(days ?? []).map(d => <option key={d.day} value={d.day}>{fmtDay(d.day)}</option>)}
        </select></label>
        <label>Zone <select aria-label="Zone" value={zone} onChange={e => setZone(e.target.value)}>
          {ZONES.map(z => <option key={z} value={z}>{z.replace(/^LZ_/, '')}</option>)}
        </select></label>
        <span className="muted">{day ? fmtDay(day) : '…'}</span>
        <span className="muted">Source {dayInfo?.label ?? (days ? 'unavailable' : '…')}</span>
        {dayInfo && <span className="muted">Dataset {dayInfo.dataset_digest.slice(0, 7)} · original issue times unknown, see assumption</span>}
        <span className={`tag ${base?.availability_mode === 'strict' ? 'up' : 'info'}`}>{base ? `${base.availability_mode} availability` : '…'}</span>
        {base && sameId && <span className="muted">Rerun returned the identical run id.</span>}
      </div>
      <p className="panel-copy">{base?.disclaimer ?? DAY_HINT}</p>
      <details className="panel-copy"><summary>Availability assumption</summary><p className="muted">{base?.availability_note ?? '…'}</p></details>
      <p className="panel-copy muted">Optional gaps: {dayInfo ? (dayInfo.gaps.length ? dayInfo.gaps.join(', ') : 'none') : '…'}</p>

      <div className="table-scroll" aria-label="Catalogued replay days">
        <table className="data-table day-picker-table" aria-label="Catalogued replay days">
          <thead>
            <tr>
              <th scope="col">Date</th>
              <th scope="col">Weekday</th>
              <th scope="col" className="end">Peak RT price</th>
              <th scope="col">Peak location</th>
              <th scope="col">Data gaps</th>
              <th scope="col" className="end">Select</th>
            </tr>
          </thead>
          <tbody>
            {(days ?? []).map(d => {
              const isSelected = d.day === day;
              const peakWhere = d.peak_rt_price
                ? (PLACES[d.peak_rt_price.point] ? `${PLACES[d.peak_rt_price.point]} (${d.peak_rt_price.point})` : d.peak_rt_price.point)
                : '—';
              const gapsText = d.gaps && d.gaps.length ? d.gaps.join(', ') : 'None';
              return (
                <tr
                  key={d.day}
                  className={isSelected ? 'selected' : ''}
                  onClick={() => selectDay(d.day)}
                  style={{ cursor: 'pointer' }}
                >
                  <th scope="row">
                    <button
                      type="button"
                      className="code"
                      style={{ background: 'none', border: 0, padding: 0, font: 'inherit', color: 'var(--accent)', cursor: 'pointer', textAlign: 'left' }}
                      onClick={e => { e.stopPropagation(); selectDay(d.day); }}
                      aria-pressed={isSelected}
                    >
                      {d.day}
                    </button>
                  </th>
                  <td>{fmtWeekday(d.day)}</td>
                  <td className="num end">{d.peak_rt_price ? `$${d.peak_rt_price.value.toFixed(2)}/MWh` : '—'}</td>
                  <td>{peakWhere}</td>
                  <td>{gapsText}</td>
                  <td className="end">
                    <button
                      type="button"
                      className="show-book"
                      aria-pressed={isSelected}
                      onClick={e => { e.stopPropagation(); selectDay(d.day); }}
                    >
                      {isSelected ? 'Selected' : 'Replay'}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Panel></div>

    <div className="replay-grid">
      <div className="replay-main">
        <Panel title="Prices and playback" index="02" className="reserve-prices" busy={baseLoading} meta={<span>{quarters.length ? fmtTime(quarters[Math.min(head, quarters.length - 1)].start) : '…'}</span>}>
          <FeedBody feed={{ data: view, error: baseError, loading: baseLoading }} unavailable="Replay unavailable · check the day and retry">
            {view && <>
              <div className="transport">
                {reduced
                  ? <button type="button" className="show-book" onClick={() => userHead(Math.min(head + 1, quarters.length - 1))} disabled={head >= quarters.length - 1}>Step</button>
                  : <button type="button" className="show-book" aria-pressed={playing} onClick={() => { if (!playing) completeFirstStep(1); setPlaying(!playing); }}>{playing ? 'Pause' : 'Play'}</button>}
                <label>Speed <select aria-label="Speed" value={speed} onChange={e => setSpeed(Number(e.target.value))} disabled={reduced}>
                  {SPEEDS.map(s => <option key={s} value={s}>{s}×</option>)}
                </select></label>
                <label className="head-slider">Playback position <input type="range" aria-label="Playback position" min={0} max={quarters.length - 1} value={Math.min(head, quarters.length - 1)} onChange={e => userHead(Number(e.target.value))} /></label>
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

        <Panel title="Strategy lanes" index="03" className="reserve-lanes" busy={baseLoading} meta={<span>{homeCount.toLocaleString()} SIMULATED HOMES</span>}>
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
                      onClick={() => { userHead(i); setSelStrategy(lane.strategy); }} />)}
                  </div>
                  <span className="lane-soc num">SoC {pct === null ? '—' : `${pct.toFixed(0)}%`}</span>
                </div>;
              })}
              <p className="chart-foot"><span><i className="swatch is-charge" />Charging</span><span><i className="swatch is-deliver" />Delivering promised flexibility</span><span><i className="swatch is-self" />Self-supply</span><span>Gap = holding</span></p>
              <p className="panel-copy muted">State of charge is simulated fleet energy over {homeCount.toLocaleString()} homes; capacity {view.capacity.toFixed(1)} kWh.</p>
            </div>}
          </FeedBody>
        </Panel>
      </div>

      <div className="replay-aside">
        <div ref={scoreRef} className="score-anchor"><Panel title="Scoreboard · baseline" index="04" className="reserve-score" busy={baseLoading} meta={<span>SIMULATED</span>}>
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
        </Panel></div>

        <Panel title="Why this decision" index="05" className="reserve-why" busy={whyLoading} meta={<span>{why ? fmtTime(why.decision_time) : '…'}</span>}>
          <FeedBody feed={{ data: why, error: whyError, loading: whyLoading }} unavailable="No decision at the playback head.">
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
              {(why.inputs ?? []).length ? <div className="table-scroll why-inputs"><table className="data-table">
                <thead><tr><th scope="col">Input</th><th scope="col">Value</th><th scope="col">Source</th><th scope="col">Published</th><th scope="col">Available</th></tr></thead>
                <tbody>{(why.inputs ?? []).map((input, i) => <tr key={`${input.name}-${i}`}>
                  <td>{input.name}</td>
                  <td className="num">{fmtInput(input.value)} {input.unit}</td>
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

    <div className="page-grid" id="your-turn" ref={yourRef}><Panel title="Your turn" index="08" className="span-all reserve-your" busy={valueLoading} meta={<span>SIMULATED</span>}>
      <p className="panel-copy">One home · 13.5 kWh battery · simulated — move the slider, then scale to a fleet.</p>
      <div className="your-slider">
        <div className="slider-scale" aria-hidden="true"><span>Earn more</span><span>Keep more backup</span></div>
        <label className="slider-label" htmlFor="reserve">Keep <strong>{reserve}%</strong> for backup</label>
        <input id="reserve" type="range" min={0} max={100} value={reserve} onChange={e => setReserve(Number(e.target.value))} aria-label={`Reserve for backup, ${reserve} percent`} />
      </div>
      <div className="your-cards">
        <div className="your-card"><span className="muted">Flexibility to sell</span><strong className="num">{estimate.flexibilityKwh.toFixed(1)} kWh</strong><span className="muted">{horizon}-hour window · simulated</span></div>
        <div className="your-card"><span className="muted">Value on {day ? fmtShort(day) : '…'}</span>
          {estimate.warnings.includes('reserve_not_yet_met')
            ? <strong>unavailable</strong>
            : valueError
              ? <strong className="warning-text">unavailable</strong>
              : <strong className="num">{valueScore ? money(valueScore.net_value_cents) : '…'}</strong>}
          <span className="muted">Battery-aware · {valueScore && !estimate.warnings.length ? `cash ${money(valueScore.cash_net_cents)} · marks ${money(valueScore.terminal_energy_value_cents - valueScore.opening_energy_value_cents)} · ` : ''}simulated replay value</span>
        </div>
        <div className="your-card"><span className="muted">Backup at {HOME_SPEC.loadKw} kW</span>
          <strong className="num">{estimate.backupHours === null ? 'n/a' : `${estimate.backupHours.toFixed(1)} h`}</strong>
          <span className="muted">from half charge ({HOME_SPEC.initialSocKwh} kWh) · simulated</span>
        </div>
      </div>
      {estimate.warnings.map(code => <p key={code} className="connection-line has-error" role="alert">{WARNING_TEXT[code](estimate.reserveKwh)}</p>)}
      {valueError && !estimate.warnings.length && <p className="connection-line has-error" role="alert">{valueError}</p>}
      <div className="your-fleet">
        <label className="slider-label" htmlFor="homes">Homes in the fleet <strong>{homes.toLocaleString()}</strong></label>
        <input id="homes" type="range" min={1} max={10000} value={homes} onChange={e => setHomes(Number(e.target.value))} aria-label="Homes in the fleet" />
        <p className="fleet-line">About <strong>{fleet.mw.toFixed(1)} MW</strong> for {fleet.durationHours} hours: a technical estimate, not a grid effect.</p>
      </div>
      <ul aria-label="Next steps" className="next-steps">
        <li><button type="button" className="show-book" onClick={() => setValueNonce(n => n + 1)} disabled={valueLoading}>Rerun the day</button></li>
        <li><a href={compareHref} onClick={scrollScore}>Compare with the baseline</a></li>
        <li><a href="#/sandbox">Place a sandbox order</a></li>
      </ul>
    </Panel></div>
  </>;
}
