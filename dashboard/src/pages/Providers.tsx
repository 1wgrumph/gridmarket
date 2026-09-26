import { useState } from 'react';
import { Badge, Button, TextInput } from '@astryxdesign/core';
import { send, type Provider, type RouterCheck } from '../api';
import Panel from '../components/Panel';
import { useProviderHealth, useProviders, useResource } from '../hooks';

type Health = {
  provider_id: string; online: boolean; last_heartbeat: string | null;
  customers: number; online_assets: number; outage_active: boolean;
};
const bandVariant = { log: 'neutral', review: 'warning', alert: 'error' } as const;

export default function Providers() {
  const providers = useProviders();
  const health = useProviderHealth();
  const router = useResource<{ checks: RouterCheck[] }>('/v1/router');
  const [adminKey, setAdminKey] = useState('');
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState('');
  const [failed, setFailed] = useState(false);

  async function outage(provider: Provider, active: boolean) {
    if (!adminKey.trim() || pending) return;
    const key = adminKey;
    setAdminKey('');
    setPending(true);
    setNotice('');
    setFailed(false);
    try {
      await send('POST', `/v1/admin/providers/${encodeURIComponent(provider.id)}/outage`, { active }, key);
      setNotice(`${provider.display_name}: outage ${active ? 'start' : 'end'} accepted. Status refreshes every 2 s.`);
    } catch {
      setFailed(true);
      setNotice(`${provider.display_name}: outage request failed. Check your admin key and try again.`);
    } finally {
      setPending(false);
    }
  }

  return <section className="gm-page">
    <div className="gm-page-head"><h1>Providers</h1></div>
    <p className="gm-muted">Simulated provider health · refreshes every 2 s</p>

    <Panel title="Provider health" state={providers}>
      {providers.data?.length === 0 && <p className="gm-muted">No providers available.</p>}
      {health.error && <p role="alert" className="gm-muted">Provider health unavailable; retrying every 2 s.</p>}
      {router.error && <p role="alert" className="gm-muted">Health checks unavailable; retrying every 2 s.</p>}
      <div className="gm-zones">
        {(providers.data ?? []).map(provider => {
          const row = health.error ? undefined : (health.data as Health[] | null)?.find(h => h.provider_id === provider.id);
          const check = router.error ? undefined : router.data?.checks.find(c => c.family === 'health' && c.subject === provider.id);
          const heartbeat = row?.last_heartbeat ? Date.parse(row.last_heartbeat) : NaN;
          return <article className="gm-zone" key={provider.id}>
            <header>
              <h3>{provider.display_name}</h3>
              <Badge variant={row ? (row.online ? 'success' : 'error') : 'neutral'} label={row ? (row.online ? 'Online' : 'Offline') : 'Unknown'} />
            </header>
            <ul className="gm-rows">
              <li><span>Customers</span><span className="gm-num">{row?.customers ?? 'Unavailable'}</span></li>
              <li><span>Online assets</span><span className="gm-num">{row?.online_assets ?? 'Unavailable'}</span></li>
              <li><span>Heartbeat age</span><span className="gm-num">{Number.isFinite(heartbeat) ? `${Math.max(0, Math.floor((Date.now() - heartbeat) / 1000))} s` : 'Unavailable'}</span></li>
              <li><span>Health probability</span><span className="gm-num">{check ? `${(check.probability * 100).toFixed(0)}%` : 'Unavailable'}</span></li>
              <li><span>Band</span>{check ? <Badge variant={bandVariant[check.band]} label={check.band} /> : <span className="gm-num">Unavailable</span>}</li>
              <li><span>{row ? (row.outage_active ? 'Outage active' : 'No outage') : 'Outage: unknown'}</span></li>
            </ul>
            {check?.baseline && <p className="gm-muted gm-note">baseline rules</p>}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.75rem' }}>
              <Button label={`Start outage · ${provider.display_name}`} isDisabled={!adminKey.trim() || pending} onClick={() => void outage(provider, true)}>Start outage</Button>
              <Button label={`End outage · ${provider.display_name}`} isDisabled={!adminKey.trim() || pending} onClick={() => void outage(provider, false)}>End outage</Button>
            </div>
          </article>;
        })}
      </div>
    </Panel>

    <Panel title="Owner outage controls">
      <TextInput label="Admin key" placeholder="Enter admin key" type="password" value={adminKey} onChange={setAdminKey} isDisabled={pending} width="100%" description="Type your key for each outage action. It is cleared when sent and never saved." />
      {pending && <p role="status" className="gm-muted gm-note">Sending outage request…</p>}
      {notice && <p role={failed ? 'alert' : 'status'} className="gm-muted gm-note">{notice}</p>}
    </Panel>
  </section>;
}
