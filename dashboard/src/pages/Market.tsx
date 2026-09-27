import { Component, useEffect, useRef, useState, type ReactNode } from 'react';
import Panel from '../components/Panel';
import { useMarket, useResource } from '../hooks';
import { centralTime as time, usd as dollars } from '../format';
import type { MarketProduct } from '../api';

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

function Depth({ title, side, levels, max }: { title: string; side: 'bid' | 'ask'; levels: Level[]; max: number }) {
  return <div>
    <h3 className="sub-head">{title}</h3>
    <ul className={`depth-list ${side}`}>
      {levels.length ? levels.map(l => <li key={l.price_cents}>
        <i style={{ width: `${l.quantity / max * 100}%` }}/><span>{l.quantity} @ {usd(l.price_cents)}</span>
      </li>) : <li className="none">—</li>}
    </ul>
  </div>;
}

function Board({ products }: { products: MarketProduct[] }) {
  const [zone, setZone] = useState('');
  const [window, setWindow] = useState('');
  const [type, setType] = useState('');
  const [limit, setLimit] = useState(12);
  const focusBook = useRef(false);
  const [picked, setPicked] = useState(products[0].symbol);
  const selected = products.find(p => p.symbol === picked) ?? products[0];
  const filtered = products.filter(p => (!zone || p.zone === zone) && (!window || p.delivery_hour === window) && (!type || p.symbol.split('-')[0] === type));
  return <div className="page-grid market-board">
    <Panel title="Products" index="01" className="market-products" meta={<span>{products.length} LISTED</span>}>
      <div className="form-row">
        <label className="field">Zone<select value={zone} onChange={e => { setZone(e.target.value); setLimit(12); }}><option value="">All zones</option>{[...new Set(products.map(p => p.zone))].map(z => <option key={z}>{z}</option>)}</select></label>
        <label className="field">Delivery window<select value={window} onChange={e => { setWindow(e.target.value); setLimit(12); }}><option value="">All windows</option>{[...new Set(products.map(p => p.delivery_hour))].map(w => <option key={w} value={w}>{time(w)}</option>)}</select></label>
        <label className="field">Product type<select value={type} onChange={e => { setType(e.target.value); setLimit(12); }}><option value="">All types</option>{[...new Set(products.map(p => p.symbol.split('-')[0]))].map(t => <option key={t}>{t}</option>)}</select></label>
      </div>
      <div className="table-scroll"><table className="data-table">
        <thead><tr><th scope="col">Symbol</th><th scope="col">Zone</th><th scope="col">Delivery</th><th scope="col">Status</th><th scope="col" className="end"><span className="sr-only">Book</span></th></tr></thead>
        <tbody>{filtered.slice(0, limit).map(p => <tr key={p.id} className={p === selected ? 'selected' : ''}>
          <td><strong>{p.symbol.startsWith('FLEX-') ? 'Flex Credit future' : 'Spot credit'}</strong><br/><small>{p.symbol}</small></td>
          <td>{p.zone}</td>
          <td><time dateTime={p.delivery_hour} title={`${p.delivery_hour} (UTC offset)`}>{time(p.delivery_hour)}</time></td>
          <td><span className={`tag ${p.status === 'open' ? 'up' : ''}`}>{p.status}</span></td>
          <td className="end"><button type="button" className="show-book" aria-pressed={p === selected} onClick={() => { focusBook.current = true; setPicked(p.symbol); }}>{p === selected ? 'Shown' : 'Show book'}</button></td>
        </tr>)}</tbody>
      </table></div>
      <div className="panel-end"><span>{Math.min(limit, filtered.length)} of {filtered.length} products</span>{limit < filtered.length && <button type="button" onClick={() => setLimit(n => n + 12)}>Show more</button>}</div>
    </Panel>
    <SelectedBook key={selected.symbol} selected={selected} focus={focusBook.current}/>

  </div>;
}

function SelectedBook({ selected, focus }: { selected: MarketProduct; focus: boolean }) {
  const bookResult = useRef<HTMLDivElement>(null);
  const detail = useResource<ProductDetail>(`/v1/market/${encodeURIComponent(selected.symbol)}`);
  const history = useResource<Trade[]>(`/v1/market/history?product_id=${encodeURIComponent(selected.id)}`);
  useEffect(() => {
    if (focus && !detail.loading) {
      bookResult.current?.focus();
      bookResult.current?.scrollIntoView?.({ block: 'nearest' });
    }
  }, [focus, detail.loading]);
  const book = bookOf(detail.data);
  const max = Math.max(1, ...[...book.bids, ...book.asks].map(l => l.quantity));
  const spread = book.bids.length && book.asks.length ? book.asks[0].price_cents - book.bids[0].price_cents : null;
  // The live detail carries no trades; the public history route does.
  const inline = Array.isArray(detail.data?.recent_trades);
  const trades = inline ? list<Trade>(detail.data?.recent_trades) : list<Trade>(history.data);
  const tradeFeed = inline ? detail : history;
  const where = `${selected.zone} · ${time(selected.delivery_hour)}`;
  return <div className="market-detail" role="region" aria-label={`Selected market ${selected.symbol}`}>
    <Panel title="Book depth" index="02" busy={detail.loading} meta={<><Stale feed={detail}/><span>{where}</span></>}>
      <div ref={bookResult} tabIndex={-1} className="panel-copy">Selected product: {selected.symbol} · {where}</div>
      <p className="panel-subtitle">Resting orders · simulated $ / Flex Credit</p>
      <div className="depth-sides">
        <Depth title="Bids" side="bid" levels={book.bids} max={max}/>
        <Depth title="Asks" side="ask" levels={book.asks} max={max}/>
      </div>
      {spread != null && <div className="panel-end"><span>Spread</span><strong className="num">{usd(spread)}</strong></div>}
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

const heading = <PageHeading eyebrow="02 / FLEX CREDIT FUTURES" title="Market"/>;

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
  const products = list<MarketProduct>(market.data);
  return <>
    {heading}
    {products.length ? <Board products={products}/>
      : <div className="page-grid"><Panel title="Products" index="01" className="span-all" busy={market.loading}>
        <FeedBody feed={market} reserve="reserve-market-products"><div className="empty">No products listed.</div></FeedBody>
      </Panel></div>}
  </>;
}

export default function Market() {
  return <MarketBoundary><MarketPage/></MarketBoundary>;
}
