import { useEffect, useMemo, useRef, useState } from 'react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { get, type SignalHistoryRow } from '../api';
import { centralStamp, csvName, ExportActions, toCsv, utcStamp } from '../csv';
import { centralTime, parseTime } from '../format';
import { contextLink, setViewQuery, useViewQuery } from './navigation';
import Panel from './Panel';

type Props = {
  index?: string;
  marketProducts?: { zone: string }[];
  /** False until the page's first polls have answered; history reads wait for it. */
  ready?: boolean;
};

/** History keys the backend stores: Worker snapshot hubs, SCED lambda and actual demand,
    plus the day-ahead price of a polled settlement point (ercot.PRICE_POINTS). */
const SERIES = [
  { key: 'HB_HOUSTON', report: 'SNAPSHOT-HUBS', subject: 'HB_HOUSTON', label: 'HB_HOUSTON', unit: '$/MWh', color: 'var(--series-1)' },
  { key: 'HB_NORTH', report: 'SNAPSHOT-HUBS', subject: 'HB_NORTH', label: 'HB_NORTH', unit: '$/MWh', color: 'var(--series-2)' },
  { key: 'HB_SOUTH', report: 'SNAPSHOT-HUBS', subject: 'HB_SOUTH', label: 'HB_SOUTH', unit: '$/MWh', color: 'var(--series-3)' },
  { key: 'HB_WEST', report: 'SNAPSHOT-HUBS', subject: 'HB_WEST', label: 'HB_WEST', unit: '$/MWh', color: 'var(--series-4)' },
  { key: 'lambda', report: 'SNAPSHOT-SCED', subject: 'lambda', label: 'system lambda', unit: '$/MWh', color: 'var(--text)' },
  { key: 'da', report: 'NP4-190-CD', subject: 'HB_HUBAVG', label: 'HB_HUBAVG day-ahead', unit: '$/MWh', color: 'var(--muted)' },
  { key: 'demand', report: 'SNAPSHOT-DEMAND', subject: 'ERCOT', label: 'ERCOT actual demand', unit: 'MW', color: 'var(--accent)' },
] as const;
type Key = typeof SERIES[number]['key'];
const HUBS = SERIES.slice(0, 4);
const CSV_COLUMNS = ['interval_start_utc', 'interval_start_central', 'series', 'report_id', 'subject', 'value', 'unit', 'published_at_utc', 'source'];
const SOURCE = 'ERCOT via GridMarket (GET /v1/signals/history)';

// The anonymous per-IP bucket is shared with the page's first polls, and any
// non-public request clamps it to 20 tokens: wait for those polls, then space reads.
const START_WAIT_MS = 1000;
const SPACING_MS = 400;
const sleep = (ms: number) => new Promise(r => setTimeout(r, ms));

type SeriesPoint = { at: number } & Partial<Record<Key, number>>;

const centralClock = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/Chicago',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});

const centralExact = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/Chicago',
  month: 'short',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});

const centralDateOnly = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/Chicago',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
});

const tickStyle = { fill: 'var(--muted)', fontSize: 11 };
const tooltipStyle = {
  background: 'var(--surface)',
  border: '1px solid var(--line)',
  color: 'var(--text)',
  fontSize: 12,
  borderRadius: 'var(--r-2)',
};

/** Way forward for an empty ERCOT feed (the battery panel's line). */
export const WorkerHint = () => <> · Live ERCOT data needs the Worker: set GRIDMARKET_WORKER_URL. <a href="#/spec">Setup docs</a></>;

export function hubToZone(hub: string, marketProducts?: { zone: string }[]): string {
  if (marketProducts?.some(p => p.zone === hub)) return hub;
  if (hub.startsWith('HB_')) {
    const lz = hub.replace('HB_', 'LZ_');
    if (!marketProducts || marketProducts.some(p => p.zone === lz)) return lz;
  }
  return hub;
}

async function fetchSeries(url: string, active: () => boolean): Promise<SignalHistoryRow[]> {
  // One retry: a 429 carries Retry-After.
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      return await get<SignalHistoryRow[]>(url);
    } catch (err) {
      if (attempt === 1 || !active()) return [];
      const waitS = Number((err as { retryAfter?: string })?.retryAfter ?? 1);
      await sleep(1000 * Math.min(5, Number.isFinite(waitS) && waitS > 0 ? waitS : 1));
    }
  }
  return [];
}

export default function LiveGridPanel({ index = 'LIVE', marketProducts, ready = true }: Props) {
  const params = useViewQuery();
  const range: 24 | 48 = params.get('range') === '48' ? 48 : 24;
  const setRange = (hours: 24 | 48) => setViewQuery({ range: hours === 48 ? '48' : undefined });
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<Partial<Record<Key, SignalHistoryRow[]>>>({});
  const [span, setSpan] = useState({ start: '', end: '' });
  const warm = useRef(false);

  useEffect(() => {
    if (!warm.current && !ready) return;
    let active = true;
    const isActive = () => active;

    async function fetchAll() {
      if (!warm.current) await sleep(START_WAIT_MS);
      // Minute-floored window.
      const nowMs = Math.floor(Date.now() / 60_000) * 60_000;
      const end = new Date(nowMs).toISOString();
      const start = new Date(nowMs - range * 3600_000).toISOString();
      const next: Partial<Record<Key, SignalHistoryRow[]>> = {};
      // ponytail: seven spaced reads; one batched history route would replace them.
      for (const s of SERIES) {
        if (!active) return;
        next[s.key] = await fetchSeries(`/v1/signals/history?${new URLSearchParams({ report_id: s.report, zone: s.subject, start, end })}`, isActive);
        await sleep(SPACING_MS);
      }
      if (!active) return;
      warm.current = true;
      setData(next);
      setSpan({ start, end });
      setLoading(false);
    }

    let timerId = 0;
    const cycle = async () => {
      await fetchAll();
      // Refreshed every 5 minutes.
      if (active) timerId = window.setTimeout(cycle, 300_000);
    };
    cycle();
    return () => {
      active = false;
      window.clearTimeout(timerId);
    };
  }, [range, ready]);

  const rows = (key: Key) => data[key] ?? [];

  const latestPublished = useMemo(() => {
    let latest = '';
    for (const key of ['HB_HOUSTON', 'HB_NORTH', 'HB_SOUTH', 'HB_WEST', 'lambda', 'demand'] as const) {
      for (const r of data[key] ?? []) if (r.published_at && r.published_at > latest) latest = r.published_at;
    }
    return latest;
  }, [data]);

  // Real-time hubs and lambda share snapshot stamps. The day-ahead hour's price is
  // carried onto every real-time point inside that hour, so it draws as a line.
  const priceChartData = useMemo<SeriesPoint[]>(() => {
    const map = new Map<number, SeriesPoint>();
    for (const key of ['HB_HOUSTON', 'HB_NORTH', 'HB_SOUTH', 'HB_WEST', 'lambda'] as const) {
      for (const r of data[key] ?? []) {
        const at = parseTime(r.interval_start);
        if (!Number.isFinite(at) || !Number.isFinite(r.value)) continue;
        const pt = map.get(at) ?? { at };
        pt[key] = r.value;
        map.set(at, pt);
      }
    }
    const da = (data.da ?? []).map(r => ({ from: parseTime(r.interval_start), to: parseTime(r.interval_end), value: r.value }));
    for (const pt of map.values()) {
      const hour = da.find(d => d.from <= pt.at && pt.at < d.to);
      if (hour) pt.da = hour.value;
    }
    return [...map.values()].sort((a, b) => a.at - b.at);
  }, [data]);

  const hasDayAhead = priceChartData.some(p => p.da !== undefined);
  const hasLambda = rows('lambda').length > 0;

  const demandChartData = useMemo(() => rows('demand')
    .filter(r => Number.isFinite(parseTime(r.interval_start)) && Number.isFinite(r.value))
    .map(r => ({ at: parseTime(r.interval_start), demand: r.value }))
    .sort((a, b) => a.at - b.at), [data]);

  // Today's peak demand in Central Time.
  const todayPeak = useMemo(() => {
    if (!demandChartData.length) return null;
    const todayCt = centralDateOnly.format(Date.now());
    const todayPoints = demandChartData.filter(d => centralDateOnly.format(d.at) === todayCt);
    const values = (todayPoints.length ? todayPoints : demandChartData).map(p => p.demand).filter(v => v > 0);
    return values.length ? Math.max(...values) : null;
  }, [demandChartData]);

  const csvRows = useMemo(() => SERIES
    .flatMap(s => rows(s.key).map(r => [utcStamp(r.interval_start), centralStamp(r.interval_start), s.label, s.report, s.subject, r.value, r.unit || s.unit, utcStamp(r.published_at), SOURCE]))
    .sort((a, b) => String(a[0]).localeCompare(String(b[0])) || String(a[2]).localeCompare(String(b[2]))), [data]);
  const query = `curl -s '${window.location.origin}/v1/signals/history?${new URLSearchParams({ report_id: 'SNAPSHOT-HUBS', zone: 'HB_HOUSTON', start: span.start, end: span.end })}'`;

  const openMarketForHub = (hub: string) => {
    window.location.hash = contextLink('#/market', { zone: hubToZone(hub, marketProducts) });
  };

  const empty = (what: string) => <div className="empty">{loading ? 'Connecting to ERCOT live grid…' : <span>No ERCOT {what} observations yet<WorkerHint/></span>}</div>;

  return (
    <Panel
      title="Live grid"
      index={index}
      className="live-grid-panel"
      busy={loading}
      meta={
        <div className="live-grid-header-meta">
          <span className="source-tag">Real ERCOT data</span>
          <span className="source-label">Source: ERCOT MIS</span>
          <span className="published-label">Published: <time className="num">{latestPublished ? centralTime(latestPublished) : 'Awaiting signal'}</time></span>
        </div>
      }
    >
      <div className="live-grid-controls">
        <div className="range-picker" role="group" aria-label="Time range">
          {([24, 48] as const).map(hours => (
            <button
              key={hours}
              type="button"
              className={`range-btn ${range === hours ? 'active' : ''}`}
              aria-pressed={range === hours}
              onClick={() => setRange(hours)}
            >
              {hours} h
            </button>
          ))}
        </div>
        <ExportActions query={query} exports={[{
          label: 'Download CSV',
          disabled: !csvRows.length,
          name: () => csvName(`live-grid-${range}h`),
          csv: () => toCsv(CSV_COLUMNS, csvRows),
        }]}/>
      </div>

      <div className="live-grid-legend" role="group" aria-label="Grid series">
        <span className="legend-title">Real-time hubs:</span>
        {HUBS.map(hub => (
          <a
            key={hub.key}
            href={contextLink('#/market', { zone: hubToZone(hub.key, marketProducts) })}
            className="legend-item"
            onClick={(e) => {
              e.preventDefault();
              openMarketForHub(hub.key);
            }}
            title={`View ${hub.key} in Market`}
          >
            <i className="legend-line" style={{ borderColor: hub.color }} />
            <span>{hub.label}</span>
          </a>
        ))}
        {hasLambda && (
          <span className="legend-item">
            <i className="legend-line" style={{ borderColor: SERIES[4].color }} />
            <span>system lambda</span>
          </span>
        )}
        {hasDayAhead && (
          <span className="legend-item">
            <i className="legend-line forecast" style={{ borderColor: SERIES[5].color }} />
            <span>HB_HUBAVG day-ahead (DA)</span>
          </span>
        )}
      </div>

      <div className="live-grid-charts">
        <div className="live-grid-main-chart" role="img" aria-label="Real-time ERCOT hub prices, system lambda and HB_HUBAVG day-ahead price">
          <div className="chart-header">
            <h4>Hub prices & system lambda <span className="unit-label">($/MWh)</span></h4>
          </div>
          <div className="chart-wrapper">
            {priceChartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={240} minWidth={0}>
                <LineChart data={priceChartData} margin={{ top: 12, right: 16, left: -4, bottom: 2 }} accessibilityLayer>
                  <CartesianGrid stroke="var(--line)" vertical={false} strokeDasharray="2 4" />
                  <XAxis
                    dataKey="at"
                    type="number"
                    scale="time"
                    domain={['dataMin', 'dataMax']}
                    tickFormatter={at => centralClock.format(at)}
                    axisLine={false}
                    tickLine={false}
                    tick={tickStyle}
                    minTickGap={30}
                  />
                  <YAxis
                    domain={['auto', 'auto']}
                    tickFormatter={v => `$${v}`}
                    axisLine={false}
                    tickLine={false}
                    tick={tickStyle}
                  />
                  <Tooltip
                    labelFormatter={at => `${centralExact.format(Number(at))} CT`}
                    formatter={(val, name) => [val == null ? '—' : `$${Number(val).toFixed(2)} $/MWh`, name]}
                    contentStyle={tooltipStyle}
                    isAnimationActive={false}
                  />
                  {HUBS.map(hub => (
                    <Line
                      key={hub.key}
                      type="monotone"
                      dataKey={hub.key}
                      name={hub.label}
                      stroke={hub.color}
                      strokeWidth={2}
                      dot={false}
                      connectNulls={false}
                      isAnimationActive={false}
                      style={{ cursor: 'pointer' }}
                      onClick={() => openMarketForHub(hub.key)}
                    />
                  ))}
                  {hasLambda && (
                    <Line
                      type="monotone"
                      dataKey="lambda"
                      name="system lambda"
                      stroke={SERIES[4].color}
                      strokeWidth={1.5}
                      dot={false}
                      connectNulls={false}
                      isAnimationActive={false}
                    />
                  )}
                  {hasDayAhead && (
                    <Line
                      type="stepAfter"
                      dataKey="da"
                      name="HB_HUBAVG day-ahead"
                      stroke={SERIES[5].color}
                      strokeWidth={2}
                      strokeDasharray="4 4"
                      dot={false}
                      connectNulls={false}
                      isAnimationActive={false}
                    />
                  )}
                </LineChart>
              </ResponsiveContainer>
            ) : empty('price')}
          </div>
        </div>

        <div className="live-grid-demand-chart" role="img" aria-label="ERCOT actual demand and today's peak">
          <div className="chart-header">
            <h4>ERCOT actual demand <span className="unit-label">(MW)</span></h4>
            {todayPeak !== null && (
              <span className="peak-badge">Today's peak: <strong className="num">{todayPeak.toLocaleString('en-US', { maximumFractionDigits: 0 })} MW</strong></span>
            )}
          </div>
          <div className="series-note">System load, Worker snapshot</div>
          <div className="chart-wrapper">
            {demandChartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={240} minWidth={0}>
                <LineChart data={demandChartData} margin={{ top: 12, right: 16, left: -4, bottom: 2 }} accessibilityLayer>
                  <CartesianGrid stroke="var(--line)" vertical={false} strokeDasharray="2 4" />
                  <XAxis
                    dataKey="at"
                    type="number"
                    scale="time"
                    domain={['dataMin', 'dataMax']}
                    tickFormatter={at => centralClock.format(at)}
                    axisLine={false}
                    tickLine={false}
                    tick={tickStyle}
                    minTickGap={30}
                  />
                  <YAxis
                    domain={['auto', 'auto']}
                    tickFormatter={v => `${(v / 1000).toFixed(0)}k`}
                    axisLine={false}
                    tickLine={false}
                    tick={tickStyle}
                  />
                  <Tooltip
                    labelFormatter={at => `${centralExact.format(Number(at))} CT`}
                    formatter={val => [val == null ? '—' : `${Number(val).toLocaleString('en-US', { maximumFractionDigits: 1 })} MW`, 'Actual demand']}
                    contentStyle={tooltipStyle}
                    isAnimationActive={false}
                  />
                  {todayPeak !== null && (
                    <ReferenceLine
                      y={todayPeak}
                      stroke="var(--down)"
                      strokeDasharray="3 3"
                    />
                  )}
                  <Line
                    type="monotone"
                    dataKey="demand"
                    name="Actual demand"
                    stroke={SERIES[6].color}
                    strokeWidth={2}
                    dot={false}
                    connectNulls={false}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : empty('demand')}
          </div>
        </div>
      </div>
      <div className="panel-end">
        <span>5-minute ERCOT refresh</span>
        <span>{range} hours plotted</span>
      </div>
    </Panel>
  );
}
