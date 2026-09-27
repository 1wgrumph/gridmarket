import { Component, useRef, useState, type ReactNode } from 'react';
import { centralTime, contextLink, setViewQuery, useViewQuery } from '../components/navigation';
import Panel from '../components/Panel';
import { useMarket, useResource } from '../hooks';
import { usd as dollars } from '../format';
import type { Activity, MarketProduct } from '../api';

type Level = { price_cents: number; quantity: number };
type Trade = { id: string; quantity: number; price_cents: number; created_at: string };
/**
 * GET /v1/market/{symbol} returns the product plus `orders`: open depth aggregated per side and price,
 * ascending by price. `book` and `recent_trades` are the older recorded fixture shape; every field is
 * optional so an absent or malformed shape renders as an empty book instead of throwing.
 */
type ProductDetail = MarketProduct & {
  orders?: (Level & { side: string })[];
  book?: { bids?: Level[]; asks?: Level[] };
  recent_trades?: Trade[];
};
type Feed = { data: unknown; error: string | null; loading: boolean };

const list = <T,>(value: unknown): T[] => Array.isArray(value) ? value : [];

function bookOf(detail: ProductDetail | null): { bids: Level[]; asks: Level[] } {
  if (Array.isArray(detail?.orders)) {
    const orders = list<Level & { side: string }>(detail.orders);
    // Best bid (highest price) first; asks already ascend from the best ask.
    return { bids: orders.filter(o => o.side === 'buy').reverse(), asks: orders.filter(o => o.side === 'sell') };
  }
  return { bids: list(detail?.book?.bids), asks: list(detail?.book?.asks) };
}

const usd = (cents: number) => dollars(cents / 100);
const time = centralTime;

/** Panel-meta tag: the last poll failed and the panel still shows last-known data. Shared by the phase 1b pages. */
export const Stale = ({ feed }: { feed: Feed }) => feed.error && feed.data ? <span className="stale">Stale · last known</span> : null;

/** Body of a polled panel: last-known data wins; otherwise a loading or unavailable line in the same geometry. */
export function FeedBody({ feed, unavailable = 'Feed unavailable · retrying every 2 seconds', reserve = '', children }: { feed: Feed; unavailable?: string; reserve?: string; children: ReactNode }) {
  return feed.data ? <>{children}</>
    : <div className={`empty${feed.loading ? ` loading ${reserve}`.trimEnd() : ''}`}>{feed.loading ? 'Connecting to the exchange…' : unavailable}</div>;
}

/** Page title in the Overview heading pattern: eyebrow, display title, decorative turf period kept out of the accessible name. */
export function PageHeading({ eyebrow, title, children }: { eyebrow: string; title: string; children?: ReactNode }) {
  return <div className="page-heading">
    <div><p className="eyebrow">{eyebrow}</p><h1>{title}<span className="title-period" aria-hidden="true">.</span></h1></div>
    {children}
  </div>;
}

function Depth({ title, side, levels, max, unavailable }: { title: string; side: 'bid' | 'ask'; levels: Level[]; max: number; unavailable: boolean }) {
  return <div>
    <h3 className="sub-head">{title}</h3>
    <ul className={`depth-list ${side}`}>
      {levels.length ? levels.map(l => <li key={l.price_cents}>
        <i style={{ width: `${l.quantity / max * 100}%` }}/><span>{l.quantity} @ {usd(l.price_cents)}</span>
      </li>) : <li className="none">{unavailable ? 'Order book unavailable' : side === 'bid' ? 'No bids' : 'No sell orders'}</li>}
    </ul>
  </div>;
}

function Board({ products }: { products: MarketProduct[] }) {
  const params = useViewQuery();
  const [local, setLocal] = useState<Record<string, string>>({});
  const filter = (name: string) => (window.location.hash.split('?')[0] === '#/market' ? params.get(name) : local[name]) ?? '';
  const [limit, setLimit] = useState(12);
  const bookFocus = useRef<HTMLHeadingElement>(null);
  const filtered = products.filter(p => (!filter('zone') || p.zone === filter('zone')) && (!filter('hour') || p.delivery_hour === filter('hour')) && (!filter('type') || p.symbol.startsWith(filter('type') + '-')));
  const selected = filtered.find(p => p.symbol === filter('symbol')) ?? filtered[0] ?? products.find(p => p.symbol === filter('symbol')) ?? products[0];
  const update = (name: string, value: string) => { setLocal(v => ({ ...v, [name]: value })); if (window.location.hash.split('?')[0] === '#/market') setViewQuery({ [name]: value }); setLimit(12); };
  const select = (symbol: string) => { update('symbol', symbol); bookFocus.current?.focus(); };

  const detail = useResource<ProductDetail>(`/v1/market/${encodeURIComponent(selected.symbol)}`);
  const history = useResource<Trade[]>(`/v1/market/history?product_id=${encodeURIComponent(selected.id)}`);
  // Hold the board until the selected book arrives so products and depth appear together.
  const book = bookOf(detail.data);
  const max = Math.max(1, ...[...book.bids, ...book.asks].map(l => l.quantity));
  const spread = book.bids.length && book.asks.length ? book.asks[0].price_cents - book.bids[0].price_cents : null;
  // The live detail carries no trades; the public history route does.
  const inline = Array.isArray(detail.data?.recent_trades);
  const trades = inline ? list<Trade>(detail.data?.recent_trades) : list<Trade>(history.data);
  const tradeFeed = inline ? detail : history;
  const where = `${selected.zone} · ${time(selected.delivery_hour)}`;
  return <div className="page-grid market-board">
    <Panel title="Products" index="01" className="products-panel" meta={<span>{products.length} LISTED</span>}>
      <div className="forecast-filters">
        <label>Zone<select value={filter('zone')} onChange={e => update('zone', e.target.value)}><option value="">All zones</option>{[...new Set(products.map(p => p.zone))].map(z => <option key={z}>{z}</option>)}</select></label>
        <label>Delivery window<select value={filter('hour')} onChange={e => update('hour', e.target.value)}><option value="">All windows</option>{[...new Set(products.map(p => p.delivery_hour))].sort().map(h => <option key={h} value={h}>{time(h)}</option>)}</select></label>
        <label>Product type<select value={filter('type')} onChange={e => update('type', e.target.value)}><option value="">All types</option><option value="FLEX">Flex Credit</option><option value="SPOT">Spot</option></select></label>
      </div>
      <div className="table-scroll"><table className="data-table">
        <thead><tr><th scope="col">Symbol</th><th scope="col">Zone</th><th scope="col">Delivery</th><th scope="col">Status</th><th scope="col" className="end"><span className="sr-only">Book</span></th></tr></thead>
        <tbody>{filtered.slice(0, limit).map(p => <tr key={p.id} className={p === selected ? 'selected' : ''}>
          <td><strong>{p.symbol.startsWith('FLEX-') ? 'Flex Credit' : 'Spot'}</strong><small className="product-id">{p.symbol}</small></td>
          <td>{p.zone}</td>
          <td><time dateTime={p.delivery_hour} title={`${p.delivery_hour} (UTC offset)`}>{time(p.delivery_hour)}</time></td>
          <td><span className={`tag ${p.status === 'open' ? 'up' : ''}`}>{p.status}</span></td>
          <td className="end"><button type="button" className="show-book" aria-pressed={p === selected} onClick={() => select(p.symbol)}>{p === selected ? 'Shown' : 'Show book'}</button></td>
        </tr>)}</tbody>
      </table></div>
      {!filtered.length && <p className="panel-copy">No products match these filters. Choose another zone or window.</p>}
      {filtered.length > limit && <button className="action-secondary" onClick={() => setLimit(n => n + 12)}>Show more products</button>}
    </Panel>
    <Panel title="Book depth" index="02" className="selected-book" busy={detail.loading} meta={<><Stale feed={detail}/><span>{where}</span></>}>
      <section aria-label={`Selected product · ${selected.symbol}`}><h3 className="sub-head" ref={bookFocus} tabIndex={-1}>{selected.symbol.startsWith('FLEX-') ? 'Flex Credit' : 'Spot'} · {selected.zone} · {time(selected.delivery_hour)}</h3><p className="panel-copy">Product: {selected.symbol}</p></section>
      <p className="panel-subtitle">Resting orders · simulated $ / Flex Credit</p>
      <div className="depth-sides">
        <Depth title="Bids" side="bid" levels={book.bids} max={max} unavailable={!!detail.error && !detail.data}/>
        <Depth title="Asks" side="ask" levels={book.asks} max={max} unavailable={!!detail.error && !detail.data}/>
      </div>
      <div className="panel-end"><span>Spread {spread == null && (detail.error && !detail.data ? 'unavailable: order book could not be loaded' : 'unavailable: requires buy and sell orders')}</span>{spread != null && <strong className="num">{usd(spread)}</strong>}</div>
      <p className="context-actions"><a href={contextLink('#/predictions', { zone: selected.zone, hour: selected.delivery_hour })}>Why this forecast?</a> · <a href={contextLink('#/sandbox', { zone: selected.zone, hour: selected.delivery_hour })}>Place an order</a></p>
    </Panel>
    <Panel title="Recent trades" index="03" busy={tradeFeed.loading} meta={<><Stale feed={tradeFeed}/><span>{where}</span></>}>
      <div className="market-trades" role="region" aria-label="Recent trade entries" tabIndex={0}>
      <FeedBody feed={tradeFeed} reserve="reserve-market-trades">
        {trades.length ? <ul className="row-list">
          {trades.map(t => <li key={t.id}>
            <time className="muted" dateTime={t.created_at}>{time(t.created_at)}</time>
            <span className="num">{t.quantity} @ {usd(t.price_cents)}</span>
          </li>)}
        </ul> : <div className="empty">No trades yet.</div>}
      </FeedBody>
      </div>
    </Panel>
  </div>;
}

const heading = <PageHeading eyebrow="04 / FLEX CREDIT FUTURES" title="Market"/>;

/** Page-level boundary: a bad response shape shows an alert here instead of blanking the whole app. */
class MarketBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state: { error: Error | null } = { error: null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  render() {
    return this.state.error ? <>
      {heading}
      <p className="connection-line has-error" role="alert">Market view failed to render: {this.state.error.message}</p>
    </> : this.props.children;
  }
}

function MarketPage() {
  const market = useMarket();
  const params = useViewQuery();
  const activity = useResource<Activity[]>('/v1/market/activity');
  const event = activity.data?.find(a => a.subject_id === params.get('event') || a.id === params.get('event'));
  const products = list<MarketProduct>(market.data);
  return <>
    {heading}
    {params.get('at') && <p className="panel-copy">Selected event: {time(params.get('at')!)}{event && ` · ${event.label} · ${event.type}`}. Book and orders below show the current market.</p>}
    {products.length ? <Board products={products}/>
      : <div className="page-grid"><Panel title="Products" index="01" className="span-all" busy={market.loading}>
        <FeedBody feed={market} reserve="reserve-market-products"><div className="empty">No products listed.</div></FeedBody>
      </Panel></div>}
  </>;
}

export default function Market() {
  return <MarketBoundary><MarketPage/></MarketBoundary>;
}
