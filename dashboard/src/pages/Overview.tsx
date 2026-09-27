import { lazy, Suspense, useEffect, useRef, useState, type CSSProperties } from 'react';
import type { Activity, Bot, MarketProduct, MarketStatus, Prediction, ProductDetail, Provider, RouterCheck, Signal, Trade } from '../api';
import { parseTime } from '../format';
import { useBots, useResource } from '../hooks';
import { Disclosures } from '../components/Shell';
import Icon from '../components/Icon';
import Panel from '../components/Panel';
import { missingInputs } from '../components/predictionInputs';
import { useReplayPeak } from '../components/replayPeak';
import FirstSteps from '../components/FirstSteps';
import { contextLink, setViewQuery, useViewQuery } from '../components/navigation';
import ZoneDetail from '../components/ZoneDetail';
import ZoneMap, { zoneName, mapZones } from '../components/ZoneMap';

const PriceChart = lazy(() => import('../components/PriceChart'));
type Resource = { data: unknown; error: string | null; loading: boolean };

const central = (options: Intl.DateTimeFormatOptions) => new Intl.DateTimeFormat('en-US', { timeZone: 'America/Chicago', ...options });
const hourFormat = central({ hour: 'numeric' });
const clockFormat = central({ hour: '2-digit', minute: '2-digit', hour12: false });
const dateFormat = central({ day: 'numeric', month: 'short', year: 'numeric' });
const usd = (value: number) => !Number.isFinite(value) ? 'Unavailable' : `${value < 0 ? '−' : ''}$${Math.abs(value).toFixed(Math.abs(value) < 1 && value !== 0 ? 4 : 2)}`;
const mw = (value: number) => `${value < 0 ? '−' : ''}${Math.abs(value).toLocaleString('en-US', { maximumFractionDigits: 1 })}`;
const upperZones = ['AEN', 'CPS', 'LCRA', 'RAYBN'];
const zoneTitle = (zone: string) => {
  const name = zoneName(zone);
  const title = /^[A-Z]+$/.test(name) && !upperZones.includes(name) ? name.charAt(0) + name.slice(1).toLowerCase() : name;
  return zone.startsWith('HB_') ? `${title} hub` : title;
};

function StaleTag({ res }: { res: Resource }) {
  return res.error && res.data ? <span className="stale">Stale · last known</span> : null;
}
function Empty({ loading, label = 'No observations yet' }: { loading: boolean; label?: string }) {
  return <div className={`empty ${loading ? 'loading' : ''}`}>{loading ? 'Connecting to the exchange…' : label}</div>;
}

function BookRows({ levels, side, max }: { levels: ProductDetail['orders']; side: 'ask' | 'bid'; max: number }) {
  return <>{levels.map(level => <tr key={`${side}-${level.price_cents}`} className={`book-level ${side}`}>
    <td>{side === 'ask' ? 'Sell' : 'Buy'}</td><td className="num">{usd(level.price_cents / 100)}</td>
    <td className="depth num"><i style={{ width: `${level.quantity / max * 100}%` }}/><span>{level.quantity}</span></td>
  </tr>)}</>;
}

function OrderBook({ symbol }: { symbol: string }) {
  const detail = useResource<ProductDetail>(`/v1/market/${encodeURIComponent(symbol)}`);
  const orders = detail.data?.orders ?? [];
  const asks = orders.filter(o => o.side === 'sell').sort((a, b) => a.price_cents - b.price_cents);
  const bids = orders.filter(o => o.side === 'buy').sort((a, b) => b.price_cents - a.price_cents);
  if (detail.loading || detail.error) return <Empty loading={detail.loading} label="Order book unavailable"/>;
  const max = Math.max(1, ...orders.map(o => o.quantity));
  const spread = asks.length && bids.length ? asks[0].price_cents - bids[0].price_cents : null;
  return <table className="book-table">
    <thead><tr><th>Side</th><th>Price</th><th>Credits</th></tr></thead>
    <tbody>
      {!orders.length && <tr><td colSpan={3}>No resting orders</td></tr>}
      <>{!asks.length && <tr><td colSpan={3}>No sell orders</td></tr>}</><BookRows levels={[...asks].reverse()} side="ask" max={max}/>
      <tr className="spread"><td colSpan={3}><span><Icon name="left-right"/> Spread</span><strong className="num">{spread == null ? 'Unavailable · requires bids and sell orders' : usd(spread / 100)}</strong></td></tr>
      <>{!bids.length && <tr><td colSpan={3}>No bids</td></tr>}</><BookRows levels={bids} side="bid" max={max}/>
    </tbody>
  </table>;
}

function groupBy<T>(rows: T[], key: (row: T) => string) {
  const groups = new Map<string, T[]>();
  for (const row of rows) groups.set(key(row), [...groups.get(key(row)) ?? [], row]);
  return groups;
}

/** God's Eye deep link `#/?zone=<LZ_ZONE>`; unknown values are ignored. */
const zoneFromHash = () => {
  const zone = new URLSearchParams(window.location.hash.split('?')[1] ?? '').get('zone');
  return zone && mapZones.includes(zone) ? zone : null;
};

export default function Overview() {
  const signals = useResource<Signal[]>('/v1/signals');
  const history = useResource<Trade[]>('/v1/market/history');
  const status = useResource<MarketStatus>('/v1/market/status');
  const providers = useResource<Provider[]>('/v1/providers');
  const predictions = useResource<Prediction[]>('/v1/predictions');
  const market = useResource<MarketProduct[]>('/v1/market');
  const bots = useBots();
  const params = useViewQuery();
  const activity = useResource<Activity[]>('/v1/market/activity');
  const checks = useResource<{ checks: RouterCheck[] }>('/v1/router');
  // /v1/bots is not served in phase 1b (404); its panel says so instead of raising the outage banner.
  const resources = [signals, history, status, providers, predictions, market, activity];
  const firstError = resources.find(r => r.error)?.error;
  const [paused, setPaused] = useState(false);

  const [selectedZone, setSelectedZone] = useState<string | null>(zoneFromHash);
  useEffect(() => { setSelectedZone(zoneFromHash()); }, [params]);
  const zoneTrigger = useRef<SVGElement | HTMLElement | null>(null);
  const closeZone = () => {
    setSelectedZone(null);
    zoneTrigger.current?.focus({ preventScroll: true });
    const q = window.location.hash.indexOf('?');
    if (q >= 0) {
      const params = new URLSearchParams(window.location.hash.slice(q + 1));
      if (params.has('zone')) {
        params.delete('zone');
        const rest = params.toString();
        window.location.hash = window.location.hash.slice(0, q) + (rest ? `?${rest}` : '');
      }
    }
  };
  const hasPrices = signals.data?.some(s => s.report_id === 'NP6-905-CD' && mapZones.includes(s.zone));
  const nextWindow = params.get('hour') || predictions.data?.map(p => p.delivery_hour).sort()[0];
  const lead = predictions.data?.filter(p => p.delivery_hour === nextWindow && (!params.get('zone') || p.zone === params.get('zone'))).reduce<Prediction | undefined>((best, p) => !best || p.score > best.score ? p : best, undefined);
  const delivery = lead ? hourFormat.format(new Date(lead.delivery_hour)) : '—';
  const product = market.data?.find(p => p.zone === lead?.zone && p.delivery_hour === lead?.delivery_hour && p.symbol.startsWith('FLEX-')) ?? market.data?.find(p => p.zone === lead?.zone && p.delivery_hour === lead?.delivery_hour) ?? market.data?.[0];
  const marketLink = contextLink('#/market', { symbol: product?.symbol, zone: product?.zone, hour: product?.delivery_hour });
  const scoreOf = (zone: string) => predictions.data?.find(p => p.zone === zone && p.delivery_hour === lead?.delivery_hour)?.score;
  const zones = [...new Set([...(predictions.data ?? []).map(p => p.zone), ...(signals.data ?? []).map(s => s.zone)])]
    .filter(zone => mapZones.includes(zone))
    .sort((a, b) => (scoreOf(b) ?? -1) - (scoreOf(a) ?? -1));
  const signalsByZone = groupBy(signals.data ?? [], s => s.zone);
  const esr = (signals.data ?? []).filter(s => s.report_id === 'ESR').sort((a, b) => a.published_at < b.published_at ? -1 : 1);
  const latestEsr = esr[esr.length - 1];
  const trades = (history.data ?? []).map(t => ({ at: parseTime(t.created_at), price: t.price_cents / 100 })).sort((a, b) => a.at - b.at);
  // System load sums the latest load forecast per zone; the LZ rows already aggregate the raw weather zones.
  const loadRows = (signals.data ?? []).filter(s => s.report_id === 'NP3-565-CD');
  const loadPool = loadRows.some(s => s.zone.startsWith('LZ_')) ? loadRows.filter(s => s.zone.startsWith('LZ_')) : loadRows;
  const systemLoad = [...groupBy(loadPool, s => s.zone).values()].map(rows => rows.reduce((a, b) => b.published_at > a.published_at ? b : a));
  const systemLoadMw = systemLoad.reduce((sum, s) => sum + s.value, 0);
  const forecastRows = (signals.data ?? []).filter(s => s.report_id === 'NP4-190-CD' && s.zone === (product?.zone ?? lead?.zone));
  const latestForecast = forecastRows.reduce<Signal | undefined>((max, s) => !max || s.published_at > max.published_at ? s : max, undefined);
  const chartData = [...trades, ...forecastRows.map(s => ({ at: parseTime(s.interval_start), forecast: s.value }))].sort((a, b) => a.at - b.at);
  const anomalies = (status.data?.anomalies ?? []) as { id?: string; kind?: string; detail?: string | null; subject_id?: string; created_at?: string }[];
  const providerName = (id: string) => providers.data?.find(p => p.id === id)?.display_name ?? id;
  const views = import.meta.env.VITE_GODSEYE_URL as string | undefined;
  const replay = useReplayPeak();
  const signalLink = (subject?: string | null, symbol?: string | null, at?: string, label?: string) => {
    const check = checks.data?.checks.find(c => c.check_id === subject);
    const object = check?.subject ?? subject ?? '';
    const product = market.data?.find(p => p.symbol === symbol || p.id === object || p.id === history.data?.find(t => t.id === object)?.product_id);
    if (product) return contextLink('#/market', { symbol: product.symbol, zone: product.zone, hour: product.delivery_hour, at });
    const zone = object.split(':')[0];
    if (mapZones.includes(zone)) return contextLink('#/', { zone, hour: object.includes(':') ? object.slice(object.indexOf(':') + 1) : nextWindow, at });
    if (providers.data?.some(p => p.id === object)) return contextLink('#/providers', { provider: object, at });
    const bot = bots.data?.find(b => b.id === object || b.id === label);
    if (bot) return contextLink(`#/bots/${encodeURIComponent(bot.id)}`, { at });
    return contextLink('#/market', { symbol: symbol ?? undefined, event: subject ?? undefined, at });
  };

  return <>
    <section className="story" aria-labelledby="story-title" aria-busy={replay.loading}>
      <div className="story-copy">
        <h1 id="story-title"><span className="story-kicker">Overview</span> Texas home batteries, paid to help when the grid is tight.</h1>
        <p className="story-subline">A simulated flexibility exchange running on real ERCOT conditions.</p>
        <p className="story-body">Homes promise to hold back or share battery power in the hours Texas runs short. Traders and AI agents buy those promises. Real grid prices decide what they were worth.</p>
        <div className="story-actions"><a className="action-primary" href={contextLink('#/tour')}>Start the 3-minute tour</a><a className="action-secondary" href={contextLink('#/sandbox')}>Try the sandbox</a></div>
      </div>
      <div className="story-replay">
        <p className="story-replay-label">Replay a real day{replay.peak && ` · ${replay.peak.day}`}</p>
        {replay.peak
          ? <><p className="story-price"><strong className="num">{replay.peak.price}</strong> /MWh</p><p>Real-time power price in {replay.peak.place} at {replay.peak.time}, the day's highest.</p></>
          : <p>Simulated home batteries face one real Texas grid day, hour by hour.</p>}
        <a href={contextLink('#/replay', { day: '2026-08-26' })}>Watch batteries play that day <Icon name="up-right"/></a>
      </div>
    </section>
    <FirstSteps/>
    <div className="page-heading">
      <div><p className="eyebrow">THE MARKET, AT A GLANCE</p><h2 className="page-title">Grid overview<span className="title-period">.</span></h2></div>
      <span className="market-status"><span className={`status-dot ${firstError ? 'warning' : ''}`}/>{firstError ? 'Connection interrupted' : status.data ? `Simulation ${status.data.status === 'open' ? 'running' : status.data.status}` : 'Connecting'}<span className="market-date">{dateFormat.format(Date.now()).toUpperCase()}</span></span>
    </div>
    <div className={`connection-line ${firstError ? 'has-error' : ''}`} role="status">{firstError
      ? <><strong>API unreachable, retrying</strong><span>{firstError}. {resources.some(r => r.data) ? 'Last-known data retained. Updates retry every 2 seconds.' : 'Awaiting the first successful response. Retrying every 2 seconds.'}</span></>
      : <><span className="mini-line"/> Independent providers. One shared market.</>}</div>

    <div className="overview-summary">
      <section className="hero" aria-label="Next delivery prediction" aria-busy={predictions.loading}>
        <div className="prediction">
          <div className="hero-top"><span className="eyebrow">01 / NEXT DELIVERY WINDOW</span><StaleTag res={predictions}/><span className="prediction-tag">SCARCITY OUTLOOK</span></div>
          <h2>{lead ? zoneTitle(lead.zone) : 'Awaiting predictions'}{lead && <span className="delivery"> / {delivery}</span>}</h2>
          <div className="hero-actions"><a className="judge-button" href={marketLink}>View this market</a><a href={contextLink('#/sandbox')}>Try sandbox</a></div>
          <div className="prediction-numbers">
            <div className="scarcity-number"><strong>{hasPrices ? lead?.score ?? '—' : '—'}{hasPrices && lead && <span>%</span>}</strong><span>predicted scarcity</span></div>
            <div className="value-comparison">
              <div><span>Expected value</span><strong>{lead ? usd(lead.expected_value) : '—'}</strong></div>
              <span className="value-divider">/</span>
              <div><span>Current future</span><strong>{lead?.market_price != null ? usd(lead.market_price) : '—'}</strong></div>
              <span className="value-unit">per Flex Credit</span>
            </div>
          </div>
          <div className="factors">{hasPrices && lead?.drivers.length
            ? [...lead.drivers].sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution)).slice(0, 3).map(d => <span key={d.factor} ><Icon name={d.contribution >= 0 ? 'up-right' : 'down-right'}/>{d.factor}</span>)
            : <span>{predictions.loading ? 'Reading prediction factors…' : 'No prediction factors available'}</span>}</div>
          <p className="estimate-note">Simulation estimate{lead?.drivers.some(d => missingInputs(d.factor, lead.zone, signals.data ?? []).length) && ' · incomplete inputs'}, not guaranteed profit. Scarcity is a heuristic percentage, not a calibrated probability.</p>
          <details className="estimate-details"><summary>Why this estimate?</summary><p>Simulation estimates use incomplete inputs when any required signal is missing. Missing inputs are not measured zeros.</p><ul>{lead?.drivers.map(d => <li key={d.factor}>{d.factor}: {missingInputs(d.factor, lead.zone, signals.data ?? []).length ? `Inputs not reported: ${missingInputs(d.factor, lead.zone, signals.data ?? []).join(', ')}` : d.detail}</li>)}</ul></details>
        </div>
        <div className="map-panel">
          <div className="map-heading"><span className="eyebrow">SCARCITY ACROSS TEXAS</span><button className="motion-toggle" aria-pressed={paused} onClick={() => setPaused(!paused)} aria-label={paused ? 'Resume map motion' : 'Pause map motion'}>{paused ? 'Play' : 'Pause'}</button></div>
          <ZoneMap selectedZone={selectedZone} deliveryHour={lead?.delivery_hour} predictions={hasPrices ? (predictions.data ?? []).filter(p => p.delivery_hour === lead?.delivery_hour) : []} paused={paused || !!firstError} onSelect={(zone, trigger) => { zoneTrigger.current = trigger; setSelectedZone(zone); setViewQuery({ zone, hour: nextWindow }); }}/>
          <div className="map-data-status">{hasPrices ? `Grid feed connected${!systemLoad.length ? ' · pending inputs: system load' : ''}` : 'Grid feed pending · ERCOT price inputs not yet received'}</div>
          <div className="map-footer"><span>Schematic · ERCOT load zones</span>{views && <a href={views} target="_blank" rel="noreferrer">Open God's Eye <Icon name="up-right"/></a>}</div>
        </div>
      </section>
      <section className="number-strip" aria-label="Market key numbers">
        {systemLoad.length > 0 && <div><span>System load</span><strong>{systemLoadMw.toLocaleString('en-US', { maximumFractionDigits: 0 })} <small>MW</small></strong><span>ERCOT demand{systemLoad.some(s => s.stale) && ' · Stale'}</span></div>}
        <div><span>Open interest </span><strong>{status.data?.open_interest ?? '—'}</strong><span> Unsettled Flex Credits</span></div>
        <div><span>Open products</span><strong>{market.error ? '—' : market.loading ? '…' : market.data?.filter(p => p.status === 'open').length ?? 0}</strong><span>SPOT + FLEX</span></div>
        <div><span>Active traders</span><strong>{status.data?.active_traders ?? '—'}</strong><span>Exchange participants</span></div>
        <div className="provider-stat"><span>Participants by provider</span>
          <span>{providers.data?.length ? providers.data.map((p, i) => <span key={p.id}>{i > 0 && ' / '}<b>{p.display_name}</b>{p.participants != null && <> · {p.participants}</>}</span>) : providers.loading ? 'Loading providers…' : providers.error ? 'Providers unavailable' : 'No providers enabled'}</span></div>
        {firstError && (predictions.data || providers.data) && <span className="strip-stale">Stale · last-known snapshot</span>}
      </section>
    </div>
    {selectedZone && <ZoneDetail deliveryHour={nextWindow} key={selectedZone} zone={selectedZone} title={zoneTitle(selectedZone)} predictions={predictions} signals={signals} market={market} onClose={closeZone}/>}
    <Disclosures/>

    <div className="market-grid">
      <Panel title="The price of flexibility" index="02" className="price-panel" busy={history.loading} meta={<><StaleTag res={history}/><span>TRADES · $ / FLEX CREDIT</span></>}>
        <a className="panel-link" href={marketLink}>View market</a><div className="chart-caption"><span><i className="legend-line actual"/>Trade price history</span><span><i className="legend-line forecast"/>{latestForecast ? `Day-ahead forecast ${usd(latestForecast.value)}` : 'Day-ahead: no observations'}</span></div>
        <div className="chart" role="img" aria-label={trades.length ? `Traded Flex Credit prices: ${trades.length} most recent trades, last ${usd(trades[trades.length - 1].price)}.${latestForecast ? ` Day-ahead forecast latest ${usd(latestForecast.value)}.` : ''}` : latestForecast ? `Day-ahead forecast: ${forecastRows.length} hourly prices, latest ${usd(latestForecast.value)}.` : 'No trades yet.'}>
          {trades.length || forecastRows.length ? <Suspense fallback={<Empty loading/>}><PriceChart data={chartData}/></Suspense> : <Empty loading={history.loading} label="No trades yet"/>}
        </div>
        <p className="chart-foot"><span>Most recent {trades.length} trades</span><span>{latestForecast ? `Day-ahead ${usd(latestForecast.value)} /MWh` : 'Hourly forecast series not served yet'}</span></p>
      </Panel>
      <Panel title="Live order book" index="03" className="book-panel" busy={market.loading} meta={<><StaleTag res={market}/><span>{product ? `${zoneTitle(product.zone).toUpperCase()} · ${hourFormat.format(new Date(product.delivery_hour))}` : 'NO PRODUCT'}</span></>}>
        <p className="panel-subtitle">Simulated $ / Flex Credit · <a href={marketLink}>View market</a></p>
        <div className="book-body">{product ? <OrderBook symbol={product.symbol}/> : <Empty loading={market.loading} label="No open products"/>}</div>
        <div className="panel-end"><span className="status-dot"/><span>Updates every 2 seconds</span></div>
      </Panel>
      <Panel title="Across the load zones" index="04" className="zones-panel" busy={signals.loading} meta={<><StaleTag res={signals}/><span>SPP · $/MWh</span></>}>
        <div className="zone-body">{zones.length ? <table className="zone-table">
          <thead><tr><th scope="col">Zone</th><th scope="col">RT $/MWh</th><th scope="col" className="trend-column">Last hours</th><th scope="col">Scarcity</th><th scope="col">Published</th></tr></thead>
          <tbody>{zones.map(zone => {
            const score = hasPrices ? scoreOf(zone) : undefined;
            const zoneSignals = signalsByZone.get(zone) ?? [];
            const rt = zoneSignals.find(s => s.report_id === 'NP6-905-CD');
            const latest = zoneSignals.reduce<Signal | undefined>((max, s) => !max || s.published_at > max.published_at ? s : max, undefined);
            return <tr key={zone} style={{ '--heat': Math.min(1, Math.max(0, ((score ?? 0) - 30) / 60)) } as CSSProperties}>
              <th scope="row"><a href={contextLink('#/', { zone, hour: nextWindow })}>{zoneTitle(zone)}</a>{zone === lead?.zone && <span className="zone-focus" aria-label="Highest scarcity"> <Icon name="up-right"/></span>}</th>
              <td><strong className="num">{rt ? usd(rt.value) : '—'}</strong></td>
              <td className="trend-column muted">—</td>
              <td className="num">{score == null ? '—' : `${score}%`}</td>
              <td>{zoneSignals.some(s => s.stale) && <span className="stale">Stale</span>} {latest ? <time className="num" dateTime={latest.published_at} title={new Date(latest.published_at).toLocaleString()}>{clockFormat.format(new Date(latest.published_at))}</time> : '—'}</td>
            </tr>;
          })}</tbody>
        </table> : <Empty loading={signals.loading || predictions.loading}/>}</div>
        <div className="panel-end"><span>Central time</span><span>{zones.length} zones served</span></div>
      </Panel>
      <Panel title="Bots setting the pace" index="05" className="bots-panel" busy={bots.loading} meta={<span>P&L · SIMULATED</span>}>
        <div className="bots-body">{bots.data?.length ? <table className="bot-table">
          <thead><tr><th>Trader</th><th>Provider</th><th>P&L</th></tr></thead>
          <tbody>{[...bots.data].sort((a, b) => (Number.isFinite(b.pnl) ? b.pnl : -Infinity) - (Number.isFinite(a.pnl) ? a.pnl : -Infinity)).slice(0, 6).map((b, i) => <tr key={b.id}>
            <td><a href={`#/bots/${encodeURIComponent(b.id)}`} className="bot-identity"><span className="avatar">{Number.isFinite(b.pnl) ? String(i + 1).padStart(2, '0') : '—'}</span><span><strong>{b.id}</strong><small>{b.bot_type}</small></span></a></td>
            <td><span className="provider-name">{providerName(b.provider_id)}</span></td>
            <td className={`num ${!Number.isFinite(b.pnl) ? 'muted' : b.pnl < 0 ? 'down-text' : 'up-text'}`}>{Number.isFinite(b.pnl) && b.pnl >= 0 ? '+' : ''}{usd(b.pnl)}</td>
          </tr>)}</tbody>
        </table> : <Empty loading={bots.loading} label={bots.error ? 'Bots not yet available' : 'No bots yet'}/>}</div>
        <div className="panel-end"><span>Ranked by simulated P&L</span><a href="#/bots">All traders <Icon name="up-right"/></a></div>
      </Panel>
      <Panel title="Market anomalies" index="06" className={`risk-panel ${!anomalies.length ? 'risk-empty' : ''}`} busy={status.loading} meta={<><StaleTag res={status}/><span>{anomalies.length} REPORTED</span></>}>
        <p className="panel-subtitle">Anomalies reported by the market status feed</p>
        <div className="risk-events">{anomalies.length
          ? anomalies.map((a, i) => <article key={a.id ?? i} className="risk-event"><div><span className="event-code">{(a.kind ?? 'anomaly').replaceAll('_', ' ')}</span><h3><a href={signalLink(a.subject_id, null, a.created_at)}>{a.detail ?? 'No detail provided'}</a></h3></div></article>)
          : <p role="status">{status.loading ? 'Checking anomalies…' : 'No anomalies reported'}</p>}</div>
      </Panel>
      <Panel title="Exchange tape" index="07" className="activity-panel" busy={activity.loading} meta={<><StaleTag res={activity}/><span>RECENT ACTIVITY</span></>}>
        <div className="activity-scroll" role="log" aria-label="Latest exchange activity" tabIndex={0}>{activity.data?.length ? [...groupBy(activity.data, a => a.symbol ?? '—')].map(([symbol, events]) => <div key={symbol} className="tape-group">
          <div className="tape-symbol">{symbol}</div>
          <ul className="activity-feed">{events.map(a => <li key={a.id}>
            <span className={`tape-kind ${a.type}`}>{a.type.toUpperCase()}</span>
            <strong><a href={signalLink(a.subject_id, a.symbol, a.created_at, a.label)}>{a.label}</a></strong>
            <span className="tape-detail">{a.quantity != null && a.price_cents != null && <span>{a.side} {a.quantity} @ ${(a.price_cents / 100).toFixed(2)}</span>}{a.reason && <span className="tape-reason">{a.reason.replaceAll('_', ' ').toLowerCase()}</span>}</span>
            <time dateTime={a.created_at}>{clockFormat.format(parseTime(a.created_at))}</time>
          </li>)}</ul>
        </div>) : <Empty loading={activity.loading} label="No activity yet"/>}</div>
      </Panel>
      <Panel title="Texas batteries charging now" index="08" className="esr-panel" busy={signals.loading} meta={<><StaleTag res={signals}/><span>ESR · MW</span></>}>
        {latestEsr ? <div className="esr-body">
          <div className="esr-value">
            <strong className="num">{mw(latestEsr.value)} <small>MW</small></strong>
            <span>{latestEsr.value < 0 ? 'discharging to the grid' : latestEsr.value > 0 ? 'charging from the grid' : 'idle'}{latestEsr.stale && <> · <span className="stale">Stale</span></>}</span>
          </div>
          <span>Grid-scale batteries · negative MW = discharging</span>
        </div> : <div className="esr-body"><Empty loading={signals.loading} label="Battery data not yet available"/></div>}
        <div className="panel-end"><span>System-wide · ERCOT</span><span>{latestEsr ? <time className="num" dateTime={latestEsr.interval_start} title={new Date(latestEsr.published_at).toLocaleString()}>{clockFormat.format(new Date(latestEsr.interval_start))} CT</time> : 'Awaiting first poll'}</span></div>
      </Panel>
      <section className="panel judge-panel" aria-labelledby="judge-title">
        <p className="eyebrow">09 / SANDBOX</p>
        <h2 id="judge-title">Trade it yourself<span className="title-period">.</span></h2>
        <p>Developers get a sandbox key and <strong>$1,000</strong> of simulated funds. Orders show up on this page within 2 s.</p>
        <code className="judge-code">client.buy("FLEX-LZ_HOUSTON-18", 2)</code>
        <a className="judge-button" href={contextLink('#/sandbox')}>Get API key <Icon name="up-right"/></a>
      </section>
    </div>
  </>;
}
