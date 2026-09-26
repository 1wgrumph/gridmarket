import { useEffect, useState } from 'react';
import { Badge, Button, CodeBlock, TextInput } from '@astryxdesign/core';
import Panel from '../components/Panel';
import { get, send, type ApiError } from '../api';

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
  return <Panel title="Your orders" state={{ loading: orders === null && error === null, error }}>
    <ul className="gm-rows">
      {(orders ?? []).map(o => <li key={o.id}>
        <span className="gm-code">{o.id}</span>
        <span className="gm-muted"><time dateTime={o.created_at}>{time(o.created_at)}</time></span>
        <span className="gm-num">{o.side} {o.quantity} @ ${(o.price_cents / 100).toFixed(2)}</span>
        <Badge variant={o.status === 'open' ? 'cyan' : 'neutral'} label={o.status} />
      </li>)}
    </ul>
    {orders?.length === 0 && <p className="gm-muted">No orders yet.</p>}
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

  return <section className="gm-page">
    <div className="gm-page-head"><h1>Judge sandbox</h1></div>
    <Panel title="1 · Get a key">
      <p className="gm-muted">A sandbox account starts with $1,000.00 of simulated funds. The key is shown once and kept only in this page's memory.</p>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: '0.75rem' }}>
        <TextInput label="Label" isOptional value={label} onChange={setLabel} placeholder="Judge" width="16rem" />
        <Button label="Get a sandbox key" variant="primary" isLoading={busy} onClick={requestKey} />
      </div>
      {error && <p className="gm-reject" role="alert">{error}</p>}
      {key && <div className="gm-note">
        <p className="gm-muted">Account {key.account_id} · copy this key now; it is not shown again.</p>
        <code className="gm-code" style={{ wordBreak: 'break-all' }}>{key.api_key}</code>
      </div>}
    </Panel>
    <Panel title="2 · SDK snippet">
      <p className="gm-muted">Set GRIDMARKET_API_KEY to your key, then run this with Python 3.</p>
      <CodeBlock code={snippet(window.location.origin)} language="python" hasCopyButton isWrapped size="sm" />
    </Panel>
    {key ? <Orders key={key.api_key} apiKey={key.api_key} />
      : <Panel title="Your orders"><p className="gm-muted">Get a sandbox key to see your orders here.</p></Panel>}
  </section>;
}
