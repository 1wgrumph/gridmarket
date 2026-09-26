import { useState, type ReactNode } from 'react';
import { Badge, Button, Table } from '@astryxdesign/core';
import Panel from '../components/Panel';
import { useMarket, useResource } from '../hooks';
import type { MarketProduct } from '../api';

type Level = { price_cents: number; quantity: number };
type Trade = { id: string; quantity: number; price_cents: number; created_at: string };
type ProductDetail = MarketProduct & { book: { bids: Level[]; asks: Level[] }; recent_trades: Trade[] };

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
  // Hold the table until the selected book arrives so products and depth appear together.
  if (detail.loading) return <p className="gm-muted">Loading…</p>;
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
          <Depth title="Bids" levels={detail.data?.book.bids ?? []} />
          <Depth title="Asks" levels={detail.data?.book.asks ?? []} />
        </div>
      </Panel>
      <Panel title="Recent trades" state={detail} className="gm-span-2">
        <ul className="gm-rows">
          {(detail.data?.recent_trades ?? []).map(t => <li key={t.id}>
            <span className="gm-muted"><time dateTime={t.created_at}>{time(t.created_at)}</time></span>
            <span className="gm-num">{t.quantity} @ {usd(t.price_cents)}</span>
          </li>)}
        </ul>
        {detail.data?.recent_trades.length === 0 && <p className="gm-muted">No trades yet.</p>}
      </Panel>
    </div>
  </>;
}

export default function Market() {
  const market = useMarket();
  return <section className="gm-page">
    <div className="gm-page-head"><h1>Market</h1></div>
    {market.data?.length ? <Board products={market.data} />
      : <Panel title="Products" state={market}><p className="gm-muted">No products listed.</p></Panel>}
  </section>;
}
