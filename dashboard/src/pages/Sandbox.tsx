import { useEffect, useState, type CSSProperties } from 'react';
import { Button, CodeBlock } from '@astryxdesign/core';
import { completeFirstStep, StepBanner } from '../components/FirstSteps';
import { contextLink } from '../components/navigation';
import { centralTime as time, parseTime } from '../format';
import { useMarket, useResource } from '../hooks';
import Panel from '../components/Panel';
import { get, send, type ApiError, type MarketProduct } from '../api';
import { FeedBody, PageHeading, Stale } from './Market';

type SandboxKey = { account_id: string; api_key: string; label: string };
type Order = { id: string; product_id: string; side: string; quantity: number; remaining_qty: number; price_cents: number; status: string; created_at: string };

const reason = (e: unknown) => (e as ApiError)?.error?.message ?? (e instanceof Error ? e.message : String(e));
// 44px touch targets at every width; the custom property inherits into the Astryx buttons.
const tall = { '--size-element-md': '44px' } as CSSProperties;
// Reserve two lines for text that changes when the key or order appears, so nothing below shifts.
const twoLines: CSSProperties = { minHeight: '2lh' };
// Served from docs/llm/ only once those lanes land; a 404 hides the panel.
const KIT = [
  { path: '/kit/system-prompt.md', title: 'LLM prompt kit', meta: 'SYSTEM PROMPT', copy: 'Paste this into your LLM as its system prompt.' },
  { path: '/kit/mcp.md', title: 'MCP snippet', meta: 'LOCAL MCP', copy: 'Add this to your MCP client to trade through a local MCP server.' },
];

/** The open future (FLEX) product with the earliest delivery hour still ahead. */
const nextFuture = (products: MarketProduct[]) => products
  .filter(p => p.symbol.startsWith('FLEX-') && p.status === 'open' && parseTime(p.delivery_hour) > Date.now())
  .sort((a, b) => a.delivery_hour.localeCompare(b.delivery_hour))[0];

const snippet = (origin: string) => `# GridMarket Python SDK (sdk/python, stdlib only)
import os, uuid
from gridmarket import Client

gm = Client(base_url="${origin}", api_key=os.environ["GRIDMARKET_API_KEY"])
product = gm.market()[0]
order = {"product_id": product["id"], "side": "buy", "quantity": 1, "price_cents": 10}
print(gm.place_order(order, str(uuid.uuid4())))
print(gm.orders())`;

function OrderProduct({ product }: { product: MarketProduct }) {
  return <><span>{product.symbol}</span><br/>{product.zone.replace('LZ_', '').toLowerCase().replace(/^./, c => c.toUpperCase())} · Delivery {time(product.delivery_hour)}</>;
}

/** The market list contains only open products; old orders retain their public detail route. */
function ClosedOrderProduct({ id }: { id: string }) {
  const product = useResource<MarketProduct>(`/v1/market/${encodeURIComponent(id)}`, 60_000);
  return product.data ? <OrderProduct product={product.data}/> : <>Product {id} · {product.loading ? 'loading delivery details' : 'zone and delivery unavailable'}</>;
}

/** Polls the caller's orders with the sandbox key held in page memory only. */
function Orders({ apiKey, label, refresh, index }: { apiKey: string; label: string; refresh: number; index: string }) {
  const market = useMarket();
  const [copyNotice, setCopyNotice] = useState('');
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    const load = () => get<Order[]>('/v1/orders', apiKey)
      .then(value => { if (active) { setOrders(value); setError(null); if (value.some(o => o.status.toLowerCase() === 'filled')) completeFirstStep(3); } })
      .catch(e => { if (active) setError(reason(e)); });
    load();
    const timer = window.setInterval(load, 2000);
    return () => { active = false; window.clearInterval(timer); };
  }, [apiKey, refresh]);
  const feed = { data: orders, error, loading: orders === null && error === null };
  return <Panel title="Your orders" index={index} className="span-all" busy={feed.loading} meta={<><Stale feed={feed}/><span>UPDATES EVERY 2 SECONDS</span></>}>
    <p className="panel-copy">Orders placed with the key labelled <strong>{label}</strong>.</p>
    <FeedBody feed={feed}>
      {orders?.length ? <div className="table-scroll"><table className="data-table">
        <thead><tr><th scope="col">Order</th><th scope="col">Placed</th><th scope="col">Product</th><th scope="col" className="end">Details</th><th scope="col">Status</th></tr></thead>
        <tbody>{orders.map(o => {
          const p = market.data?.find(p => p.id === o.product_id);
          return <tr key={o.id}>
          <td><span className="code" title={o.id}>{o.id.length > 18 ? `${o.id.slice(0, 6)}…${o.id.slice(-4)}` : o.id}</span><button className="copy-id" aria-label={`Copy order ID ${o.id}`} onClick={() => navigator.clipboard.writeText(o.id).then(() => setCopyNotice('Order ID copied'), () => setCopyNotice('Copy unavailable; select the ID to copy it.'))}>Copy</button></td>
          <td className="muted"><time dateTime={o.created_at}>{time(o.created_at)}</time></td>
          <td>{p ? <><a href={contextLink('#/market', { zone: p.zone, hour: p.delivery_hour, symbol: p.symbol })}>{p.symbol}</a><small className="product-id">{p.zone} · Delivery {time(p.delivery_hour)}</small></> : <span>Product {o.product_id} · zone and delivery unavailable</span>}</td>
          <td className={`end num ${o.side === 'buy' ? 'bid' : 'ask'}`}>{o.side} {o.quantity} @ ${(o.price_cents / 100).toFixed(2)}</td>
          <td><span className={`tag ${o.status === 'open' ? 'info' : ''}`}>{o.status}</span></td>
        </tr>; })}</tbody>
      </table></div> : <div className="empty">No orders yet.</div>}
    </FeedBody>
    <p role="status" className="panel-copy">{copyNotice}</p>
    {orders?.some(o => o.status.toLowerCase() === 'filled') && <p className="context-actions">Your order filled. <a href={contextLink('#/market')}>View the market</a> · <a href="/docs">Build with the API</a> · <a href={contextLink('#/tour')}>Review your progress</a></p>}
  </Panel>;
}

export default function Sandbox() {
  const [label, setLabel] = useState('');
  const [key, setKey] = useState<SandboxKey | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [keyError, setKeyError] = useState<string | null>(null);
  const [existing, setExisting] = useState('');
  const [copyNotice, setCopyNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [placing, setPlacing] = useState(false);
  const [placed, setPlaced] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [kit, setKit] = useState<Record<string, string>>({});

  useEffect(() => {
    let active = true;
    for (const { path } of KIT) {
      fetch(path).then(r => r.ok ? r.text() : null)
        .then(text => { if (active && text) setKit(k => ({ ...k, [path]: text })); })
        .catch(() => {});
    }
    return () => { active = false; };
  }, []);

  const requestKey = async () => {
    setBusy(true);
    setKeyError(null);
    try { setKey(await send<SandboxKey>('POST', '/v1/sandbox/keys', label.trim() ? { label: label.trim() } : {})); setPlaced(null); }
    catch (e) {
      const retry = (e as ApiError)?.retryAfter;
      const retryAt = retry && Number.isFinite(Date.parse(retry)) ? time(new Date(retry).toISOString()) : retry;
      setKeyError(`${reason(e)}${retry ? (/^\d+$/.test(retry) ? ` · Try again in ${retry} seconds.` : ` · Retry after ${retryAt}.`) : ''}`);
    }
    finally { setBusy(false); }
  };

  const placeFirstOrder = async () => {
    if (!key) return;
    setPlacing(true);
    setError(null);
    try {
      const product = nextFuture(await get<MarketProduct[]>('/v1/market'));
      if (!product) throw new Error('No future product is open right now; try again at the next hour.');
      await send<Order>('POST', '/v1/orders', { product_id: product.id, side: 'buy', quantity: 1, price_cents: 10 }, key.api_key, crypto.randomUUID());
      setPlaced(`Placed: buy 1 ${product.symbol} @ $0.10.`);
      setRefresh(n => n + 1);
    } catch (e) { setError(reason(e)); }
    finally { setPlacing(false); }
  };

  const served = KIT.filter(k => kit[k.path]);
  const ordersIndex = `0${3 + served.length}`;

  return <>
    <PageHeading eyebrow="05 / DEVELOPER SANDBOX" title="Judge sandbox"/><StepBanner step={3}/>
    <div className="page-grid">
      <Panel title="Get a key" index="01" meta={<span>$1,000 SIMULATED</span>}>
        <p className="panel-copy">A sandbox account starts with $1,000.00 of simulated funds. The key is shown once and kept only in this page's memory. Leaving or reloading loses it; copy it to continue later.</p>
        <div className="form-row" style={tall}>
          <label className="field">Label (optional)<input value={label} onChange={e => setLabel(e.target.value)} placeholder="Judge" style={{ width: '16rem', maxWidth: '100%' }}/></label>
          <Button label="Get a sandbox key" variant="primary" isLoading={busy} onClick={requestKey}/>
        </div>
        <p className="form-result warning-text" role={keyError ? 'alert' : undefined} aria-live="polite" style={twoLines}>{keyError}</p>
        <div className="form-row"><label className="field">Continue with an existing key<input type="password" autoComplete="off" value={existing} onChange={e => setExisting(e.target.value)}/></label><button className="action-secondary" disabled={!existing.trim()} onClick={() => { setKey({ api_key: existing.trim(), account_id: 'Existing account', label: 'Existing key' }); setExisting(''); }}>Use existing key</button></div>
        <div className="key-box">
          <p className="muted" style={twoLines}>{key ? <>Account {key.account_id} · copy this key now; it is not shown again.</> : 'Your key appears here.'}</p>
          <code className="judge-code">{key?.api_key ?? '\u00a0'}</code>
          <button className="action-secondary" disabled={!key} onClick={() => key && navigator.clipboard.writeText(key.api_key).then(() => setCopyNotice('Key copied'), () => setCopyNotice('Copy unavailable; select your key and copy it.'))}>Copy key</button><span role="status">{copyNotice}</span>
        </div>
        <div className="form-row" style={tall}>
          <Button label="Place a first order" variant="secondary" isDisabled={!key} isLoading={placing} onClick={placeFirstOrder}/>
        </div>
        <p className={`form-result ${error ? 'warning-text' : 'muted'}`} role={error ? 'alert' : undefined} aria-live="polite" style={twoLines}>{error ?? placed ?? 'Buys 1 credit of the next future product at $0.10.'}</p>
        {key && <p className="context-actions">Key ready. Place your first order above or <a href="/docs">explore the API</a>.</p>}
      </Panel>
      <Panel title="SDK snippet" index="02" meta={<span>PYTHON 3</span>}>
        <p className="panel-copy">Set GRIDMARKET_API_KEY to your key, then run this with Python 3.</p>
        <div className="snippet"><CodeBlock code={snippet(window.location.origin)} language="python" hasCopyButton isWrapped size="sm"/></div>
      </Panel>
      {served.map((k, i) => <Panel key={k.path} title={k.title} index={`0${3 + i}`} meta={<span>{k.meta}</span>}>
        <p className="panel-copy">{k.copy}</p>
        <div className="snippet"><CodeBlock code={kit[k.path]!} language="markdown" hasCopyButton isWrapped size="sm"/></div>
      </Panel>)}
      {key ? <Orders key={key.api_key} apiKey={key.api_key} label={key.label} refresh={refresh} index={ordersIndex}/>
        : <Panel title="Your orders" index={ordersIndex} className="span-all"><div className="empty">Get a sandbox key to see your orders here.</div></Panel>}
    </div>
  </>;
}
