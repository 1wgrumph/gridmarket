import { Component, useState, type ReactNode } from 'react';
import { Badge, Button, Table } from '@astryxdesign/core';
import Panel from '../components/Panel';
import { useMarket, useResource } from '../hooks';
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

const list = <T,>(value: unknown): T[] => Array.isArray(value) ? value : [];

function bookOf(detail: ProductDetail | null): { bids: Level[]; asks: Level[] } {
  if (Array.isArray(detail?.orders)) {
    const orders = list<Level & { side: string }>(detail.orders);
    // Best bid (highest price) first; asks already ascend from the best ask.
    return { bids: orders.filter(o => o.side === 'buy').reverse(), asks: orders.filter(o => o.side === 'sell') };
  }
  return { bids: list(detail?.book?.bids), asks: list(detail?.book?.asks) };
}

const usd = (cents: number) => `$${(cents / 100).toFixed(2)}`;
const time = (iso: string) => iso.replace('T', ' ').replace(/:\d\dZ$/, 'Z');

/** Lets a wide table scroll sideways on phones (Astryx scroll wrapper) without widening the page grid. */
const Wide = ({ children }: { children: ReactNode }) => <div style={{ contain: 'inline-size' }}>{children}</div>;

function Depth({ title, levels }: { title: string; levels: Level[] }) {
  return <div>
    <h3 className="gm-panel-title">{title}</h3>
    <ul className="gm-rows">
      {levels.length ? levels.map(l => <li key={l.price_cents}><span className="gm-num">{l.quantity} @ {usd(l.price_cents)}</span></li>)
        : <li className="gm-muted">—</li>}
    </ul>
  </div>;
}

function Board({ products }: { products: MarketProduct[] }) {
  const [picked, setPicked] = useState(products[0].symbol);
  const selected = products.some(p => p.symbol === picked) ? picked : products[0].symbol;
  const detail = useResource<ProductDetail>(`/v1/market/${encodeURIComponent(selected)}`);
  const productId = products.find(p => p.symbol === selected)?.id ?? '';
  const history = useResource<Trade[]>(`/v1/market/history?product_id=${encodeURIComponent(productId)}`);
  // Hold the table until the selected book arrives so products and depth appear together.
  if (detail.loading) return <p className="gm-muted">Loading…</p>;
  const book = bookOf(detail.data);
  // The live detail carries no trades; the public history route does.
  const inline = Array.isArray(detail.data?.recent_trades);
  const trades = inline ? list<Trade>(detail.data?.recent_trades) : list<Trade>(history.data);
  const tradeState = inline ? detail : history;
  return <>
    <Panel title="Products">
      <Wide><Table<MarketProduct> style={{ minWidth: '34rem' }} data={products} idKey="id" density="compact" hasHover columns={[
        { key: 'symbol', header: 'Symbol', renderCell: p => <span className="gm-code">{p.symbol}</span> },
        { key: 'zone', header: 'Zone' },
        { key: 'delivery_hour', header: 'Delivery', renderCell: p => <time dateTime={p.delivery_hour}>{time(p.delivery_hour)}</time> },
        { key: 'status', header: 'Status', renderCell: p => <Badge variant={p.status === 'open' ? 'success' : 'neutral'} label={p.status} /> },
        { key: 'book', header: '', renderCell: p => <Button label={p.symbol === selected ? 'Shown' : 'Show book'} size="sm"
          variant={p.symbol === selected ? 'primary' : 'secondary'} onClick={() => setPicked(p.symbol)} /> },
      ]} /></Wide>
    </Panel>
    <div className="gm-stats">
      <Panel title="Book depth" state={detail}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
          <Depth title="Bids" levels={book.bids} />
          <Depth title="Asks" levels={book.asks} />
        </div>
      </Panel>
      <Panel title="Recent trades" state={tradeState} className="gm-span-2">
        <ul className="gm-rows">
          {trades.map(t => <li key={t.id}>
            <span className="gm-muted"><time dateTime={t.created_at}>{time(t.created_at)}</time></span>
            <span className="gm-num">{t.quantity} @ {usd(t.price_cents)}</span>
          </li>)}
        </ul>
        {trades.length === 0 && <p className="gm-muted">No trades yet.</p>}
      </Panel>
    </div>
  </>;
}

/** Page-level boundary: a bad response shape shows an alert here instead of blanking the whole app. */
class MarketBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state: { error: Error | null } = { error: null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  render() {
    return this.state.error ? <section className="gm-page">
      <div className="gm-page-head"><h1>Market</h1></div>
      <p className="gm-muted" role="alert">Market view failed to render: {this.state.error.message}</p>
    </section> : this.props.children;
  }
}

function MarketPage() {
  const market = useMarket();
  const products = list<MarketProduct>(market.data);
  return <section className="gm-page">
    <div className="gm-page-head"><h1>Market</h1></div>
    {products.length ? <Board products={products} />
      : <Panel title="Products" state={market}><p className="gm-muted">No products listed.</p></Panel>}
  </section>;
}

export default function Market() {
  return <MarketBoundary><MarketPage /></MarketBoundary>;
}
