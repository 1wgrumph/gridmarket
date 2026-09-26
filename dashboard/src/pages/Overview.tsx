/// <reference types="vite/client" />
import { lazy, Suspense, useState, type CSSProperties } from 'react';
import type { Activity, Bot, MarketProduct, MarketStatus, Prediction, ProductDetail, Provider, Signal, Trade } from '../api';
import { useResource } from '../hooks';
import { Disclosures } from '../components/Shell';
import Icon from '../components/Icon';
import Panel from '../components/Panel';
import ZoneMap, { zoneName } from '../components/ZoneMap';

const PriceChart = lazy(() => import('../components/PriceChart'));
type Resource = { data: unknown; error: string | null; loading: boolean };

const central = (options: Intl.DateTimeFormatOptions) => new Intl.DateTimeFormat('en-US', { timeZone: 'America/Chicago', ...options });
const hourFormat = central({ hour: 'numeric' });
const clockFormat = central({ hour: '2-digit', minute: '2-digit', hour12: false });
const dateFormat = central({ day: 'numeric', month: 'short', year: 'numeric' });
/** Backend timestamps are ISO 8601 or SQLite UTC text ("YYYY-MM-DD HH:MM:SS"). */
const parseTime = (value: string) => Date.parse(value.includes('T') ? value : `${value.replace(' ', 'T')}Z`);
const usd = (value: number) => `${value < 0 ? '−' : ''}$${Math.abs(value).toFixed(Math.abs(value) < 1 && value !== 0 ? 4 : 2)}`;
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
  if (!orders.length) return <Empty loading={detail.loading} label={detail.error ? 'Order book unavailable' : 'No resting orders'}/>;
  const max = Math.max(1, ...orders.map(o => o.quantity));
  const spread = asks.length && bids.length ? asks[0].price_cents - bids[0].price_cents : null;
  return <table className="book-table">
    <thead><tr><th>Side</th><th>Price</th><th>Credits</th></tr></thead>
    <tbody>
      <BookRows levels={[...asks].reverse()} side="ask" max={max}/>
      <tr className="spread"><td colSpan={3}><span><Icon name="left-right"/> Spread</span><strong className="num">{spread == null ? '—' : usd(spread / 100)}</strong></td></tr>
      <BookRows levels={bids} side="bid" max={max}/>
    </tbody>
  </table>;
}

function groupBy<T>(rows: T[], key: (row: T) => string) {
  const groups = new Map<string, T[]>();
  for (const row of rows) groups.set(key(row), [...groups.get(key(row)) ?? [], row]);
  return groups;
}

export default function Overview() {
  const signals = useResource<Signal[]>('/v1/signals');
  const history = useResource<Trade[]>('/v1/market/history');
  const status = useResource<MarketStatus>('/v1/market/status');
  const providers = useResource<Provider[]>('/v1/providers');
  const predictions = useResource<Prediction[]>('/v1/predictions');
  const market = useResource<MarketProduct[]>('/v1/market');
  const bots = useResource<Bot[]>('/v1/bots');
  const activity = useResource<Activity[]>('/v1/market/activity');
  // /v1/bots is not served in phase 1b (404); its panel says so instead of raising the outage banner.
  const resources = [signals, history, status, providers, predictions, market, activity];
  const firstError = resources.find(r => r.error)?.error;
  const [paused, setPaused] = useState(false);

  const lead = predictions.data?.reduce<Prediction | undefined>((best, p) => !best || p.score > best.score ? p : best, undefined);
  const delivery = lead ? hourFormat.format(new Date(lead.delivery_hour)) : '—';
  const product = market.data?.find(p => p.zone === lead?.zone && p.delivery_hour === lead?.delivery_hour) ?? market.data?.[0];
  const scoreOf = (zone: string) => predictions.data?.find(p => p.zone === zone)?.score;
  const zones = [...new Set([...(predictions.data ?? []).map(p => p.zone), ...(signals.data ?? []).map(s => s.zone)])]
    .sort((a, b) => (scoreOf(b) ?? -1) - (scoreOf(a) ?? -1));
  const signalsByZone = groupBy(signals.data ?? [], s => s.zone);
  const trades = (history.data ?? []).map(t => ({ at: parseTime(t.created_at), price: t.price_cents / 100 })).sort((a, b) => a.at - b.at);
  const anomalies = (status.data?.anomalies ?? []) as { id?: string; kind?: string; detail?: string | null }[];
  const providerName = (id: string) => providers.data?.find(p => p.id === id)?.display_name ?? id;
  const views = import.meta.env.VITE_VIEWS_URL as string | undefined;

  return <>
    <div className="page-heading">
      <div><p className="eyebrow">THE MARKET, AT A GLANCE</p><h1>Grid overview<span className="title-period">.</span></h1></div>
      <span className="market-status"><span className={`status-dot ${firstError ? 'warning' : ''}`}/>{firstError ? 'Connection interrupted' : status.data ? `Market ${status.data.status}` : 'Connecting'}<span className="market-date">{dateFormat.format(Date.now()).toUpperCase()}</span></span>
    </div>
    <div className={`connection-line ${firstError ? 'has-error' : ''}`} role="status">{firstError
      ? <><strong>API unreachable, retrying</strong><span>{firstError}. {resources.some(r => r.data) ? 'Last-known data retained. Updates retry every 2 seconds.' : 'Awaiting the first successful response. Retrying every 2 seconds.'}</span></>
      : <><span className="mini-line"/> Independent providers. One shared market.</>}</div>

    <div className="overview-summary">
      <section className="hero" aria-label="Next delivery prediction" aria-busy={predictions.loading}>
        <div className="prediction">
          <div className="hero-top"><span className="eyebrow">01 / NEXT DELIVERY WINDOW</span><StaleTag res={predictions}/><span className="prediction-tag">SCARCITY OUTLOOK</span></div>
          <h2>{lead ? zoneTitle(lead.zone) : 'Awaiting predictions'}<span className="delivery"> / {delivery}</span></h2>
          <div className="prediction-numbers">
            <div className="scarcity-number"><strong>{lead?.score ?? '—'}<span>%</span></strong><span>predicted scarcity</span></div>
            <div className="value-comparison">
              <div><span>Expected value</span><strong>{lead ? usd(lead.expected_value) : '—'}</strong></div>
              <span className="value-divider">/</span>
              <div><span>Current future</span><strong>{lead?.market_price != null ? usd(lead.market_price) : '—'}</strong></div>
              <span className="value-unit">per Flex Credit</span>
            </div>
          </div>
          <div className="factors">{lead?.drivers.length
            ? [...lead.drivers].sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution)).slice(0, 3).map(d => <span key={d.factor} title={d.detail}><Icon name={d.contribution >= 0 ? 'up-right' : 'down-right'}/>{d.factor}</span>)
            : <span>{predictions.loading ? 'Reading prediction factors…' : 'No prediction factors available'}</span>}</div>
          <p className="estimate-note">Simulation estimate, not guaranteed profit.</p>
        </div>
        <div className="map-panel">
          <div className="map-heading"><span className="eyebrow">SCARCITY ACROSS TEXAS</span><button className="motion-toggle" aria-pressed={paused} onClick={() => setPaused(!paused)} aria-label={paused ? 'Resume map motion' : 'Pause map motion'}>{paused ? 'Play' : 'Pause'}</button></div>
          <ZoneMap predictions={predictions.data ?? []} paused={paused || !!firstError}/>
          <div className="map-footer"><span>Schematic · ERCOT load zones</span>{views && <a href={`${views.replace(/\/$/, '')}/godseye/`} target="_blank" rel="noreferrer">Explore in 3D <Icon name="up-right"/></a>}</div>
        </div>
      </section>
      <section className="number-strip" aria-label="Market key numbers">
        <div><span>System load</span><strong className="unavailable">unavailable</strong><span>ERCOT demand</span></div>
        <div><span>Highest scarcity</span><strong>{lead?.score ?? '—'}<small>%</small></strong><span>{lead ? `${zoneTitle(lead.zone)} · ${delivery}` : 'Awaiting predictions'}</span></div>
        <div><span>Open interest</span><strong className="unavailable">unavailable</strong><span>Flex Credits</span></div>
        <div><span>Active traders</span><strong className="unavailable">unavailable</strong><span>Across the exchange</span></div>
        <div className="provider-stat"><span>Participants by provider</span><strong className="unavailable">unavailable</strong>
          <span>{providers.data?.length ? providers.data.map((p, i) => <span key={p.id}>{i > 0 && ' / '}<b>{p.display_name}</b></span>) : providers.loading ? 'Loading providers…' : providers.error ? 'Providers unavailable' : 'No providers enabled'}</span></div>
        {firstError && (predictions.data || providers.data) && <span className="strip-stale">Stale · last-known snapshot</span>}
      </section>
    </div>
    <Disclosures/>

    <div className="market-grid">
      <Panel title="The price of flexibility" index="02" className="price-panel" busy={history.loading} meta={<><StaleTag res={history}/><span>TRADES · $ / FLEX CREDIT</span></>}>
        <div className="chart-caption"><span><i className="legend-line actual"/>Trade price history</span><span><i className="legend-line forecast"/>Day-ahead forecast unavailable</span></div>
        <div className="chart" role="img" aria-label={trades.length ? `Traded Flex Credit prices: ${trades.length} most recent trades, last ${usd(trades[trades.length - 1].price)}.` : 'No trades yet.'}>
          {trades.length ? <Suspense fallback={<Empty loading/>}><PriceChart data={trades}/></Suspense> : <Empty loading={history.loading} label="No trades yet"/>}
        </div>
        <p className="chart-foot"><span>Most recent {trades.length} trades</span><span>Hourly forecast series not served yet</span></p>
      </Panel>
      <Panel title="Live order book" index="03" className="book-panel" busy={market.loading} meta={<><StaleTag res={market}/><span>{product ? `${zoneTitle(product.zone).toUpperCase()} · ${hourFormat.format(new Date(product.delivery_hour))}` : 'NO PRODUCT'}</span></>}>
        <p className="panel-subtitle">Simulated $ / Flex Credit</p>
        <div className="book-body">{product ? <OrderBook symbol={product.symbol}/> : <Empty loading={market.loading} label="No open products"/>}</div>
        <div className="panel-end"><span className="status-dot"/><span>Updates every 2 seconds</span></div>
      </Panel>
      <Panel title="Across the load zones" index="04" className="zones-panel" busy={signals.loading} meta={<><StaleTag res={signals}/><span>SPP · $/MWh</span></>}>
        <div className="zone-body">{zones.length ? <table className="zone-table">
          <thead><tr><th scope="col">Zone</th><th scope="col">RT $/MWh</th><th scope="col" className="trend-column">Last hours</th><th scope="col">Scarcity</th><th scope="col">Published</th></tr></thead>
          <tbody>{zones.map(zone => {
            const score = scoreOf(zone);
            const zoneSignals = signalsByZone.get(zone) ?? [];
            const rt = zoneSignals.find(s => s.report_id === 'NP6-905-CD');
            const latest = zoneSignals.reduce<Signal | undefined>((max, s) => !max || s.published_at > max.published_at ? s : max, undefined);
            return <tr key={zone} style={{ '--heat': Math.min(1, Math.max(0, ((score ?? 0) - 30) / 60)) } as CSSProperties}>
              <th scope="row">{zoneTitle(zone)}{zone === lead?.zone && <span className="zone-focus" aria-label="Highest scarcity"> <Icon name="up-right"/></span>}</th>
              <td><strong className="num">{rt ? usd(rt.value) : '—'}</strong></td>
              <td className="trend-column muted">—</td>
              <td className="num">{score == null ? '—' : `${score}%`}</td>
              <td>{zoneSignals.some(s => s.stale) && <span className="stale">Stale</span>} {latest ? <time className="num" dateTime={latest.published_at} title={new Date(latest.published_at).toLocaleString()}>{clockFormat.format(new Date(latest.published_at))}</time> : '—'}</td>
            </tr>;
          })}</tbody>
        </table> : <Empty loading={signals.loading || predictions.loading}/>}</div>
        <div className="panel-end"><span>Central time · trend series unavailable</span><span>{zones.length} zones served</span></div>
      </Panel>
      <Panel title="Bots setting the pace" index="05" className="bots-panel" busy={bots.loading} meta={<span>P&L · SIMULATED</span>}>
        <div className="bots-body">{bots.data?.length ? <table className="bot-table">
          <thead><tr><th>Trader</th><th>Provider</th><th>P&L</th></tr></thead>
          <tbody>{[...bots.data].sort((a, b) => b.pnl - a.pnl).slice(0, 6).map((b, i) => <tr key={b.id}>
            <td><a href={`#/bots/${encodeURIComponent(b.id)}`} className="bot-identity"><span className="avatar">{String(i + 1).padStart(2, '0')}</span><span><strong>{b.id}</strong><small>{b.bot_type}</small></span></a></td>
            <td><span className="provider-name">{providerName(b.provider_id)}</span></td>
            <td className={`num ${b.pnl < 0 ? 'down-text' : 'up-text'}`}>{b.pnl >= 0 ? '+' : ''}{usd(b.pnl / 100)}</td>
          </tr>)}</tbody>
        </table> : <Empty loading={bots.loading} label={bots.error ? 'Bots not yet available' : 'No bots yet'}/>}</div>
        <div className="panel-end"><span>Ranked by simulated P&L</span><a href="#/bots">All traders <Icon name="up-right"/></a></div>
      </Panel>
      <Panel title="Market anomalies" index="06" className="risk-panel" busy={status.loading} meta={<><StaleTag res={status}/><span>{anomalies.length} REPORTED</span></>}>
        <p className="panel-subtitle">Anomalies reported by the market status feed</p>
        <div className="risk-events">{anomalies.length
          ? anomalies.map((a, i) => <article key={a.id ?? i} className="risk-event"><div><span className="event-code">{(a.kind ?? 'anomaly').replaceAll('_', ' ')}</span><h3>{a.detail ?? 'No detail provided'}</h3></div></article>)
          : <Empty loading={status.loading} label="No anomalies reported"/>}</div>
      </Panel>
      <Panel title="Exchange tape" index="07" className="activity-panel" busy={activity.loading} meta={<><StaleTag res={activity}/><span>RECENT ACTIVITY</span></>}>
        {activity.data?.length ? [...groupBy(activity.data, a => a.symbol ?? '—')].map(([symbol, events]) => <div key={symbol} className="tape-group">
          <div className="tape-symbol">{symbol}</div>
          <ul className="activity-feed">{events.map(a => <li key={a.id}>
            <span className={`tape-kind ${a.type}`}>{a.type.toUpperCase()}</span>
            <strong>{a.label}</strong>
            <span className="tape-detail">{a.quantity != null && a.price_cents != null && <span>{a.side} {a.quantity} @ ${(a.price_cents / 100).toFixed(2)}</span>}{a.reason && <span className="tape-reason">{a.reason.replaceAll('_', ' ').toLowerCase()}</span>}</span>
            <time dateTime={a.created_at}>{clockFormat.format(parseTime(a.created_at))}</time>
          </li>)}</ul>
        </div>) : <Empty loading={activity.loading} label="No activity yet"/>}
      </Panel>
      <section className="panel judge-panel" aria-labelledby="judge-title">
        <p className="eyebrow">08 / SANDBOX</p>
        <h2 id="judge-title">Trade it yourself<span className="title-period">.</span></h2>
        <p>Developers get a sandbox key and <strong>$1,000</strong> of simulated funds. Orders show up on this page within 2 s.</p>
        <code className="judge-code">client.buy("FLEX-LZ_HOUSTON-18", 2)</code>
        <a className="judge-button" href="#/sandbox">Get API key <Icon name="up-right"/></a>
      </section>
    </div>
  </>;
}
