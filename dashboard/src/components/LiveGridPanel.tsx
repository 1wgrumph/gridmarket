import { useEffect, useMemo, useState } from 'react';
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
import { centralTime, parseTime } from '../format';
import { contextLink } from './navigation';
import Panel from './Panel';

type Props = {
  index?: string;
  marketProducts?: { zone: string }[];
};

type SeriesPoint = {
  at: number;
  timeStr: string;
  HB_HOUSTON?: number | null;
  HB_NORTH?: number | null;
  HB_SOUTH?: number | null;
  HB_WEST?: number | null;
  lambda?: number | null;
  daHouston?: number | null;
  daNorth?: number | null;
  daSouth?: number | null;
  daWest?: number | null;
  daForecast?: number | null;
};

type DemandPoint = {
  at: number;
  timeStr: string;
  demand?: number | null;
};

type ExportItem = {
  timestamp_utc: string;
  timestamp_ct: string;
  series: string;
  value: number;
  unit: string;
  published_at: string;
};

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

// Shared in-flight history reads: StrictMode double-mounts (and remounts)
// reuse one request per URL instead of doubling the Overview burst (429s).
// Entries are removed on settle, so refreshes always refetch.
const inflight = new Map<string, Promise<SignalHistoryRow[]>>();

export function hubToZone(hub: string, marketProducts?: { zone: string }[]): string {
  if (marketProducts?.some(p => p.zone === hub)) return hub;
  if (hub.startsWith('HB_')) {
    const lz = hub.replace('HB_', 'LZ_');
    if (!marketProducts || marketProducts.some(p => p.zone === lz)) return lz;
  }
  return hub;
}

export default function LiveGridPanel({ index = 'LIVE', marketProducts }: Props) {
  const [range, setRange] = useState<24 | 48>(24);
  const [loading, setLoading] = useState(true);

  // Raw series data
  const [rtHouston, setRtHouston] = useState<SignalHistoryRow[]>([]);
  const [rtNorth, setRtNorth] = useState<SignalHistoryRow[]>([]);
  const [rtSouth, setRtSouth] = useState<SignalHistoryRow[]>([]);
  const [rtWest, setRtWest] = useState<SignalHistoryRow[]>([]);
  const [rtLambda, setRtLambda] = useState<SignalHistoryRow[]>([]);
  const [daHouston, setDaHouston] = useState<SignalHistoryRow[]>([]);
  const [daNorth, setDaNorth] = useState<SignalHistoryRow[]>([]);
  const [daSouth, setDaSouth] = useState<SignalHistoryRow[]>([]);
  const [daWest, setDaWest] = useState<SignalHistoryRow[]>([]);
  const [demandRows, setDemandRows] = useState<SignalHistoryRow[]>([]);

  useEffect(() => {
    let active = true;

    async function fetchAll() {
      // Minute-floored window: concurrent mounts share URLs, so the
      // in-flight dedupe collapses them to one request each.
      const nowMs = Math.floor(Date.now() / 60_000) * 60_000;
      const end = new Date(nowMs).toISOString();
      const start = new Date(nowMs - range * 3600_000).toISOString();

      // One retry: the Overview burst can exhaust the shared IP bucket (429).
      const fetchSeries = async (reportId: string, zone: string): Promise<SignalHistoryRow[]> => {
        const url = `/v1/signals/history?${new URLSearchParams({ report_id: reportId, zone, start, end })}`;
        for (let attempt = 0; attempt < 2; attempt++) {
          try {
            let req = inflight.get(url);
            if (!req) {
              req = get<SignalHistoryRow[]>(url);
              inflight.set(url, req);
            }
            const rows = await req;
            inflight.delete(url);
            return rows;
          } catch (err) {
            inflight.delete(url);
            if (attempt === 1 || !active) return [];
            const waitS = Number((err as { retryAfter?: string })?.retryAfter ?? 1);
            await new Promise(r => setTimeout(r, 1000 * Math.min(5, Number.isFinite(waitS) && waitS > 0 ? waitS : 1)));
          }
        }
        return [];
      };

      const [
        houston,
        north,
        south,
        west,
        lam,
        daH,
        daN,
        daS,
        daW,
        demH,
        demN,
        demS,
        demW,
      ] = await Promise.all([
        fetchSeries('NP6-905-CD', 'HB_HOUSTON'),
        fetchSeries('NP6-905-CD', 'HB_NORTH'),
        fetchSeries('NP6-905-CD', 'HB_SOUTH'),
        fetchSeries('NP6-905-CD', 'HB_WEST'),
        fetchSeries('NP6-905-CD', 'lambda'),
        fetchSeries('NP4-190-CD', 'HB_HOUSTON'),
        fetchSeries('NP4-190-CD', 'HB_NORTH'),
        fetchSeries('NP4-190-CD', 'HB_SOUTH'),
        fetchSeries('NP4-190-CD', 'HB_WEST'),
        // NP3-565-CD stores no ERCOT total; the four LZ rollups sum to it.
        fetchSeries('NP3-565-CD', 'LZ_HOUSTON'),
        fetchSeries('NP3-565-CD', 'LZ_NORTH'),
        fetchSeries('NP3-565-CD', 'LZ_SOUTH'),
        fetchSeries('NP3-565-CD', 'LZ_WEST'),
      ]);

      if (!active) return;

      const demandByStart = new Map<string, SignalHistoryRow[]>();
      for (const r of [...demH, ...demN, ...demS, ...demW]) {
        if (!r.interval_start || !Number.isFinite(r.value)) continue;
        const list = demandByStart.get(r.interval_start) ?? [];
        list.push(r);
        demandByStart.set(r.interval_start, list);
      }
      const demTotal: SignalHistoryRow[] = [...demandByStart.entries()].map(([start, rows]) => ({
        interval_start: start,
        interval_end: rows[0].interval_end,
        value: rows.reduce((sum, r) => sum + r.value, 0),
        unit: 'MW',
        published_at: rows.reduce((m, r) => (r.published_at > m ? r.published_at : m), ''),
        stale: rows.some(r => r.stale),
      }));

      setRtHouston(houston);
      setRtNorth(north);
      setRtSouth(south);
      setRtWest(west);
      setRtLambda(lam);
      setDaHouston(daH);
      setDaNorth(daN);
      setDaSouth(daS);
      setDaWest(daW);
      setDemandRows(demTotal);
      setLoading(false);
    }

    fetchAll();
    // Refreshed every 5 minutes (300,000 ms)
    let timerId: number;
    const scheduleNext = () => {
      timerId = window.setTimeout(async () => {
        if (!active) return;
        await fetchAll();
        scheduleNext();
      }, 300_000);
    };
    scheduleNext();
    return () => {
      active = false;
      window.clearTimeout(timerId);
    };
  }, [range]);

  // Find latest published time across all observations
  const allRows = useMemo(() => [
    ...rtHouston,
    ...rtNorth,
    ...rtSouth,
    ...rtWest,
    ...rtLambda,
    ...daHouston,
    ...daNorth,
    ...daSouth,
    ...daWest,
    ...demandRows,
  ], [rtHouston, rtNorth, rtSouth, rtWest, rtLambda, daHouston, daNorth, daSouth, daWest, demandRows]);

  const latestPublished = useMemo(() => {
    let latest = '';
    for (const r of allRows) {
      if (r.published_at && r.published_at > latest) {
        latest = r.published_at;
      }
    }
    return latest;
  }, [allRows]);

  const publishedDisplay = useMemo(() => {
    if (!latestPublished) return 'Awaiting signal';
    return centralTime(latestPublished);
  }, [latestPublished]);

  // Combine real-time price series into points by timestamp
  const priceChartData = useMemo<SeriesPoint[]>(() => {
    const map = new Map<string, SeriesPoint>();

    const insert = (rows: SignalHistoryRow[], key: keyof SeriesPoint) => {
      for (const r of rows) {
        if (!r.interval_start) continue;
        const at = parseTime(r.interval_start);
        if (!Number.isFinite(at)) continue;
        let pt = map.get(r.interval_start);
        if (!pt) {
          pt = { at, timeStr: r.interval_start };
          map.set(r.interval_start, pt);
        }
        (pt[key] as any) = r.value;
      }
    };

    insert(rtHouston, 'HB_HOUSTON');
    insert(rtNorth, 'HB_NORTH');
    insert(rtSouth, 'HB_SOUTH');
    insert(rtWest, 'HB_WEST');
    insert(rtLambda, 'lambda');

    // Day-ahead series
    insert(daHouston, 'daHouston');
    insert(daNorth, 'daNorth');
    insert(daSouth, 'daSouth');
    insert(daWest, 'daWest');

    // Also populate a general daForecast line if any DA is available
    for (const pt of map.values()) {
      const daVal = pt.daHouston ?? pt.daNorth ?? pt.daSouth ?? pt.daWest ?? null;
      if (daVal !== null) {
        pt.daForecast = daVal;
      }
    }

    return Array.from(map.values()).sort((a, b) => a.at - b.at);
  }, [rtHouston, rtNorth, rtSouth, rtWest, rtLambda, daHouston, daNorth, daSouth, daWest]);

  const hasDayAhead = useMemo(() => (
    daHouston.length > 0 || daNorth.length > 0 || daSouth.length > 0 || daWest.length > 0
  ), [daHouston, daNorth, daSouth, daWest]);

  const hasLambda = useMemo(() => rtLambda.length > 0, [rtLambda]);

  // Combine demand series into points
  const demandChartData = useMemo<DemandPoint[]>(() => {
    return demandRows
      .filter(r => r.interval_start && Number.isFinite(r.value))
      .map(r => ({
        at: parseTime(r.interval_start),
        timeStr: r.interval_start,
        demand: r.value,
      }))
      .sort((a, b) => a.at - b.at);
  }, [demandRows]);

  // Compute today's peak demand in Central Time
  const todayPeak = useMemo(() => {
    if (!demandChartData.length) return null;
    const todayCt = centralDateOnly.format(Date.now());
    const todayPoints = demandChartData.filter(d => {
      try {
        return centralDateOnly.format(d.at) === todayCt && Number.isFinite(d.demand);
      } catch {
        return false;
      }
    });
    const pool = todayPoints.length ? todayPoints : demandChartData;
    const values = pool.map(p => p.demand ?? 0).filter(v => v > 0);
    return values.length ? Math.max(...values) : null;
  }, [demandChartData]);

  // CSV export handler
  const handleDownloadCsv = () => {
    const items: ExportItem[] = [];

    const addRows = (rows: SignalHistoryRow[], seriesName: string, unit: string) => {
      for (const r of rows) {
        if (!r.interval_start || r.value === null || r.value === undefined) continue;
        items.push({
          timestamp_utc: r.interval_start,
          timestamp_ct: centralTime(r.interval_start),
          series: seriesName,
          value: r.value,
          unit: r.unit || unit,
          published_at: r.published_at || '',
        });
      }
    };

    addRows(rtHouston, 'HB_HOUSTON', '$/MWh');
    addRows(rtNorth, 'HB_NORTH', '$/MWh');
    addRows(rtSouth, 'HB_SOUTH', '$/MWh');
    addRows(rtWest, 'HB_WEST', '$/MWh');
    addRows(rtLambda, 'system lambda', '$/MWh');
    if (daHouston.length) addRows(daHouston, 'HB_HOUSTON (DA)', '$/MWh');
    if (daNorth.length) addRows(daNorth, 'HB_NORTH (DA)', '$/MWh');
    if (daSouth.length) addRows(daSouth, 'HB_SOUTH (DA)', '$/MWh');
    if (daWest.length) addRows(daWest, 'HB_WEST (DA)', '$/MWh');
    addRows(demandRows, 'ERCOT Total Demand', 'MW');

    // Sort by timestamp_utc, then series
    items.sort((a, b) => {
      const cmp = a.timestamp_utc.localeCompare(b.timestamp_utc);
      return cmp !== 0 ? cmp : a.series.localeCompare(b.series);
    });

    const cell = (v: string | number) => {
      const s = String(v);
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const header = 'timestamp_utc,timestamp_ct,series,value,unit,published_at';
    const lines = [header];
    for (const item of items) {
      lines.push([item.timestamp_utc, item.timestamp_ct, item.series, item.value, item.unit, item.published_at].map(cell).join(','));
    }

    const csvContent = lines.join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `ercot-live-grid-${range}h.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const openMarketForHub = (hub: string) => {
    const zone = hubToZone(hub, marketProducts);
    window.location.hash = contextLink('#/market', { zone });
  };

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
          <span className="published-label">Published: <time className="num">{publishedDisplay}</time></span>
        </div>
      }
    >
      <div className="live-grid-controls">
        <div className="range-picker" role="group" aria-label="Time range">
          <button
            type="button"
            className={`range-btn ${range === 24 ? 'active' : ''}`}
            aria-pressed={range === 24}
            onClick={() => setRange(24)}
          >
            24 h
          </button>
          <button
            type="button"
            className={`range-btn ${range === 48 ? 'active' : ''}`}
            aria-pressed={range === 48}
            onClick={() => setRange(48)}
          >
            48 h
          </button>
        </div>
        <button
          type="button"
          className="download-csv-btn action-secondary"
          onClick={handleDownloadCsv}
        >
          Download CSV
        </button>
      </div>

      <div className="live-grid-legend" role="navigation" aria-label="Grid series filter">
        <span className="legend-title">Real-time Hubs:</span>
        {(['HB_HOUSTON', 'HB_NORTH', 'HB_SOUTH', 'HB_WEST'] as const).map(hub => {
          const zone = hubToZone(hub, marketProducts);
          const colorClass = hub === 'HB_HOUSTON' ? 'houston' : hub === 'HB_NORTH' ? 'north' : hub === 'HB_SOUTH' ? 'south' : 'west';
          return (
            <a
              key={hub}
              href={contextLink('#/market', { zone })}
              className={`legend-item ${colorClass}`}
              onClick={(e) => {
                e.preventDefault();
                openMarketForHub(hub);
              }}
              title={`View ${hub} in Market`}
            >
              <i className={`legend-line ${colorClass}`} />
              <span>{hub}</span>
            </a>
          );
        })}
        {hasLambda && (
          <span className="legend-item lambda">
            <i className="legend-line lambda" />
            <span>system lambda</span>
          </span>
        )}
        {hasDayAhead && (
          <span className="legend-item forecast">
            <i className="legend-line forecast" />
            <span>Day-ahead (DA)</span>
          </span>
        )}
      </div>

      <div className="live-grid-charts">
        <div className="live-grid-main-chart" role="img" aria-label="Real-time ERCOT hub prices and system lambda">
          <div className="chart-header">
            <h4>Hub Prices & System Lambda <span className="unit-label">($/MWh)</span></h4>
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
                    formatter={(val, name) => {
                      if (val === null || val === undefined) return ['—', name];
                      const label = name === 'daForecast' ? 'Day-ahead' : name === 'lambda' ? 'System lambda' : String(name);
                      return [`$${Number(val).toFixed(2)} $/MWh`, label];
                    }}
                    contentStyle={{
                      background: 'var(--surface)',
                      border: '1px solid var(--line)',
                      color: 'var(--text)',
                      fontSize: 12,
                      borderRadius: 'var(--r-2)',
                    }}
                    isAnimationActive={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="HB_HOUSTON"
                    name="HB_HOUSTON"
                    stroke="var(--accent)"
                    strokeWidth={2}
                    dot={false}
                    connectNulls={false}
                    isAnimationActive={false}
                    style={{ cursor: 'pointer' }}
                    onClick={() => openMarketForHub('HB_HOUSTON')}
                  />
                  <Line
                    type="monotone"
                    dataKey="HB_NORTH"
                    name="HB_NORTH"
                    stroke="var(--info)"
                    strokeWidth={2}
                    dot={false}
                    connectNulls={false}
                    isAnimationActive={false}
                    style={{ cursor: 'pointer' }}
                    onClick={() => openMarketForHub('HB_NORTH')}
                  />
                  <Line
                    type="monotone"
                    dataKey="HB_SOUTH"
                    name="HB_SOUTH"
                    stroke="var(--down)"
                    strokeWidth={2}
                    dot={false}
                    connectNulls={false}
                    isAnimationActive={false}
                    style={{ cursor: 'pointer' }}
                    onClick={() => openMarketForHub('HB_SOUTH')}
                  />
                  <Line
                    type="monotone"
                    dataKey="HB_WEST"
                    name="HB_WEST"
                    stroke="var(--muted)"
                    strokeWidth={2}
                    dot={false}
                    connectNulls={false}
                    isAnimationActive={false}
                    style={{ cursor: 'pointer' }}
                    onClick={() => openMarketForHub('HB_WEST')}
                  />
                  {hasLambda && (
                    <Line
                      type="monotone"
                      dataKey="lambda"
                      name="system lambda"
                      stroke="var(--map-border)"
                      strokeWidth={2}
                      dot={false}
                      connectNulls={false}
                      isAnimationActive={false}
                    />
                  )}
                  {hasDayAhead && (
                    <Line
                      type="monotone"
                      dataKey="daForecast"
                      name="Day-ahead"
                      stroke="var(--info)"
                      strokeWidth={2}
                      strokeDasharray="4 4"
                      dot={false}
                      connectNulls={false}
                      isAnimationActive={false}
                    />
                  )}
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="empty">{loading ? 'Connecting to ERCOT live grid…' : 'No ERCOT price observations yet'}</div>
            )}
          </div>
        </div>

        <div className="live-grid-demand-chart" role="img" aria-label="ERCOT Total Demand and today's peak">
          <div className="chart-header">
            <h4>ERCOT Total Demand <span className="unit-label">(MW)</span></h4>
            {todayPeak !== null && (
              <span className="peak-badge">Today's peak: <strong className="num">{todayPeak.toLocaleString('en-US', { maximumFractionDigits: 0 })} MW</strong></span>
            )}
          </div>
          <div className="series-note">NP3-565-CD LZ rollup</div>
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
                    formatter={(val) => {
                      if (val === null || val === undefined) return ['—', 'Demand'];
                      return [`${Number(val).toLocaleString('en-US', { maximumFractionDigits: 1 })} MW`, 'Demand'];
                    }}
                    contentStyle={{
                      background: 'var(--surface)',
                      border: '1px solid var(--line)',
                      color: 'var(--text)',
                      fontSize: 12,
                      borderRadius: 'var(--r-2)',
                    }}
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
                    name="Demand"
                    stroke="var(--accent)"
                    strokeWidth={2}
                    dot={false}
                    connectNulls={false}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="empty">{loading ? 'Connecting to ERCOT live grid…' : 'No ERCOT demand observations yet'}</div>
            )}
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
