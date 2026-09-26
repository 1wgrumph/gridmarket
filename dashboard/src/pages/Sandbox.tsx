import { useEffect, useState } from 'react';
import { Button, CodeBlock } from '@astryxdesign/core';
import Panel from '../components/Panel';
import { get, send, type ApiError } from '../api';
import { FeedBody, PageHeading, Stale } from './Market';

type SandboxKey = { account_id: string; api_key: string; label: string };
type Order = { id: string; product_id: string; side: string; quantity: number; remaining_qty: number; price_cents: number; status: string; created_at: string };

const reason = (e: unknown) => (e as ApiError)?.error?.message ?? String(e);
const time = (iso: string) => iso.replace('T', ' ').replace(/:\d\dZ$/, 'Z');

const snippet = (origin: string) => `# GridMarket Python SDK (sdk/python, stdlib only)
import os, uuid
from gridmarket import Client

gm = Client(base_url="${origin}", api_key=os.environ["GRIDMARKET_API_KEY"])
product = gm.market()[0]
order = {"product_id": product["id"], "side": "buy", "quantity": 1, "price_cents": 4200}
print(gm.place_order(order, str(uuid.uuid4())))
print(gm.orders())`;

/** Polls the caller's orders with the sandbox key held in page memory only. */
function Orders({ apiKey }: { apiKey: string }) {
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    const load = () => get<Order[]>('/v1/orders', apiKey)
      .then(value => { if (active) { setOrders(value); setError(null); } })
      .catch(e => { if (active) setError(reason(e)); });
    load();
    const timer = window.setInterval(load, 2000);
    return () => { active = false; window.clearInterval(timer); };
  }, [apiKey]);
  const feed = { data: orders, error, loading: orders === null && error === null };
  return <Panel title="Your orders" index="03" className="span-all" busy={feed.loading} meta={<><Stale feed={feed}/><span>UPDATES EVERY 2 SECONDS</span></>}>
    <FeedBody feed={feed}>
      {orders?.length ? <div className="table-scroll"><table className="data-table">
        <thead><tr><th scope="col">Order</th><th scope="col">Placed</th><th scope="col" className="end">Details</th><th scope="col">Status</th></tr></thead>
        <tbody>{orders.map(o => <tr key={o.id}>
          <td><span className="code">{o.id}</span></td>
          <td className="muted"><time dateTime={o.created_at}>{time(o.created_at)}</time></td>
          <td className={`end num ${o.side === 'buy' ? 'bid' : 'ask'}`}>{o.side} {o.quantity} @ ${(o.price_cents / 100).toFixed(2)}</td>
          <td><span className={`tag ${o.status === 'open' ? 'info' : ''}`}>{o.status}</span></td>
        </tr>)}</tbody>
      </table></div> : <div className="empty">No orders yet.</div>}
    </FeedBody>
  </Panel>;
}

export default function Sandbox() {
  const [label, setLabel] = useState('');
  const [key, setKey] = useState<SandboxKey | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const requestKey = async () => {
    setBusy(true);
    setError(null);
    try { setKey(await send<SandboxKey>('POST', '/v1/sandbox/keys', label.trim() ? { label: label.trim() } : {})); }
    catch (e) { setError(reason(e)); }
    finally { setBusy(false); }
  };

  return <>
    <PageHeading eyebrow="06 / DEVELOPER SANDBOX" title="Judge sandbox"/>
    <div className="page-grid">
      <Panel title="Get a key" index="01" meta={<span>$1,000 SIMULATED</span>}>
        <p className="panel-copy">A sandbox account starts with $1,000.00 of simulated funds. The key is shown once and kept only in this page's memory.</p>
        <div className="form-row">
          <label className="field">Label (optional)<input value={label} onChange={e => setLabel(e.target.value)} placeholder="Judge" style={{ width: '16rem', maxWidth: '100%' }}/></label>
          <Button label="Get a sandbox key" variant="primary" isLoading={busy} onClick={requestKey}/>
        </div>
        {error && <p className="form-result warning-text" role="alert">{error}</p>}
        {key && <div className="key-box">
          <p className="muted">Account {key.account_id} · copy this key now; it is not shown again.</p>
          <code className="judge-code">{key.api_key}</code>
        </div>}
      </Panel>
      <Panel title="SDK snippet" index="02" meta={<span>PYTHON 3</span>}>
        <p className="panel-copy">Set GRIDMARKET_API_KEY to your key, then run this with Python 3.</p>
        <div className="snippet"><CodeBlock code={snippet(window.location.origin)} language="python" hasCopyButton isWrapped size="sm"/></div>
      </Panel>
      {key ? <Orders key={key.api_key} apiKey={key.api_key}/>
        : <Panel title="Your orders" index="03" className="span-all"><div className="empty">Get a sandbox key to see your orders here.</div></Panel>}
    </div>
  </>;
}
