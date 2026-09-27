import { useEffect, useState, type CSSProperties } from 'react';
import { Button, TextInput } from '@astryxdesign/core';
import { send, type Provider, type RouterCheck } from '../api';
import { centralTime, query, useViewQuery } from '../components/navigation';
import Panel from '../components/Panel';
import { useProviderHealth, useProviders, useResource, useSignals } from '../hooks';

type Health = {
  id: string; online: boolean; last_heartbeat: string | null;
  online_assets: number; outage_active: boolean;
};

// Design v2 (DEC-GM-062): styles.css tokens only; page-specific layout stays inline so styles.css is untouched.
const chip: CSSProperties = { display: 'inline-block', fontSize: 11, lineHeight: 1.6, fontWeight: 500, letterSpacing: 'var(--track-caps)', border: '1px solid var(--line)', borderRadius: 'var(--r-1)', padding: '1px 4px', color: 'var(--muted)' };
const bandStyle: Record<RouterCheck['band'], CSSProperties> = {
  log: chip,
  review: { ...chip, color: 'var(--warning)', borderColor: 'var(--warning)' },
  alert: { ...chip, color: 'var(--warning)', borderColor: 'var(--warning)', background: 'var(--warn-bg)' },
};
const providerGrid: CSSProperties = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(240px, 100%), 1fr))', gap: '20px 32px', padding: '0 18px 18px' };
const providerHead: CSSProperties = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, minHeight: 34 };
const rows: CSSProperties = { listStyle: 'none', margin: 0, padding: 0 };
const rowStyle: CSSProperties = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, minHeight: 34, borderTop: '1px solid var(--line)', fontSize: 11 };
const label: CSSProperties = { color: 'var(--muted)' };
const value: CSSProperties = { fontSize: 13, fontWeight: 500, letterSpacing: 'var(--track-tight)' };
const status: CSSProperties = { display: 'inline-flex', alignItems: 'center', gap: 7, fontSize: 11 };
const unknownDot: CSSProperties = { background: 'var(--muted)' };
const alertLine: CSSProperties = { margin: '0 18px 12px' };
const actions: CSSProperties = { display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 12 };
const panelBody: CSSProperties = { display: 'flex', flexDirection: 'column', gap: 12, padding: '0 18px 18px' };
const cardHighlight: CSSProperties = { outline: '2px solid var(--accent)', outlineOffset: 4, borderRadius: 'var(--r-2)' };

function PanelEmpty({ state }: { state: { loading: boolean; error: string | null } }) {
  return state.error ? <p className="empty" role="alert">Feed unavailable; retrying every 2 s.</p> : <div style={providerGrid}><p className="empty loading" style={{ minHeight: 320 }}>Loading…</p></div>;
}

export default function Providers() {
  const providers = useProviders();
  const health = useProviderHealth();
  const router = useResource<{ checks: RouterCheck[] }>('/v1/router');
  const signals = useSignals();
  const params = useViewQuery();
  const hashMatch = typeof window !== 'undefined' && window.location.hash.match(/#provider-([a-zA-Z0-9_-]+)/);
  const selectedProvider = params.get('provider') || (hashMatch ? hashMatch[1] : null);
  const providerReady = !!providers.data;
  useEffect(() => {
    if (providerReady && selectedProvider) {
      const el = document.getElementById(`provider-${selectedProvider}`);
      if (el) {
        el.scrollIntoView?.({ block: 'nearest' });
        el.focus();
      }
    }
  }, [providerReady, selectedProvider]);
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

  return <>
    <div className="page-heading"><div><h1>Providers</h1></div></div>
    <div className="connection-line"><span className="mini-line"/> Simulated provider health · refreshes every 2 s</div>

    {params.get('at') && <p className="panel-copy">Selected event: {centralTime(params.get('at')!)}. Provider status below is current.</p>}
    <div className="market-grid">
      <Panel title="Provider health" index="01" busy={providers.loading}>
        {providers.error || providers.loading ? <PanelEmpty state={providers}/> : <>
          {providers.data?.length === 0 && <p className="empty">No providers available.</p>}
          {health.error && <p role="alert" className="connection-line has-error" style={alertLine}>Provider health unavailable; retrying every 2 s.</p>}
          {router.error && <p role="alert" className="connection-line has-error" style={alertLine}>Health checks unavailable; retrying every 2 s.</p>}
          <div style={providerGrid}>
            {(providers.data ?? []).map(provider => {
              const row = health.error ? undefined : (health.data as Health[] | null)?.find(h => h.id === provider.id);
              const check = router.error ? undefined : router.data?.checks.find(c => c.family === 'health' && c.subject === provider.id);
              const heartbeat = row?.last_heartbeat ? Date.parse(row.last_heartbeat) : NaN;
              return <article key={provider.id} id={`provider-${provider.id}`} tabIndex={-1} style={selectedProvider === provider.id ? cardHighlight : undefined}>
                <header style={providerHead}>
                  <h3 style={{ fontSize: 16, fontWeight: 500, letterSpacing: 'var(--track-tight)' }}>{provider.display_name}</h3>
                  <span style={status}><span className={`status-dot ${row && !row.online ? 'warning' : ''}`} style={row ? undefined : unknownDot}/>{row ? (row.online ? 'Online' : 'Offline') : 'Unknown'}</span>
                </header>
                <ul style={rows}>
                  <li style={rowStyle}><span style={label}>Customers</span><span className="num" style={value}>{(provider as Provider & { participants?: number }).participants ?? 'Unavailable'}</span></li>
                  <li style={rowStyle}><span style={label}>Online assets</span><span className="num" style={value}>{row?.online_assets ?? 'Unavailable'}</span></li>
                  <li style={rowStyle}><span style={label}>Heartbeat age</span><span className="num" style={value}>{Number.isFinite(heartbeat) ? `${Math.max(0, Math.floor((Date.now() - heartbeat) / 1000))} s` : 'Unavailable'}</span></li>
                  <li style={rowStyle}><span style={label}>Health probability</span><span className="num" style={value}>{check ? `${(check.probability * 100).toFixed(0)}%` : 'Unavailable'}</span></li>
                  <li style={rowStyle}><span style={label}>Band</span>{check ? <span style={bandStyle[check.band]}>{check.band}</span> : <span className="num" style={value}>Unavailable</span>}</li>
                  <li style={rowStyle}><span style={row?.outage_active ? { color: 'var(--warning)', fontWeight: 500 } : label}>{row ? (row.outage_active ? 'Outage active' : 'No outage') : 'Outage: unknown'}</span></li>
                </ul>
                {check?.baseline && <p className="tiny" style={{ marginTop: 8 }}>baseline rules</p>}
                {!row?.last_heartbeat && <p className="tiny">Health setup: not connected yet. <a href="/docs">API documentation</a> · <a href="#/sandbox">Try the sandbox</a></p>}
                <div style={actions}>
                  <Button label={`Start outage · ${provider.display_name}`} isDisabled={!adminKey.trim() || pending} onClick={() => void outage(provider, true)}>Start outage</Button>
                  <Button label={`End outage · ${provider.display_name}`} isDisabled={!adminKey.trim() || pending} onClick={() => void outage(provider, false)}>End outage</Button>
                </div>
              </article>;
            })}
            {(() => {
              const workerCheck = router.error ? undefined : router.data?.checks.find(c => c.family === 'health' && c.subject === 'worker');
              const gridSignals = signals.data?.filter(s => s.report_id === 'ESR' || s.report_id.startsWith('NP'));
              const latestSignal = gridSignals?.map(s => s.fetched_at).sort().pop();
              const workerSignal = signals.data?.find(s => s.report_id === 'health/worker' || s.report_id === 'worker' || s.zone === 'worker');
              const latestTime = workerSignal?.fetched_at || latestSignal;
              const isStale = workerSignal ? workerSignal.stale : gridSignals?.some(s => s.stale);
              const workerAge = latestTime ? Math.max(0, Math.floor((Date.now() - Date.parse(latestTime)) / 1000)) : null;
              const workerStatus = signals.loading ? 'Connecting…' : signals.error ? 'Unavailable' : latestTime ? (isStale ? 'Stale' : 'Online') : 'Waiting for ERCOT';
              return <article id="provider-worker" tabIndex={-1} style={selectedProvider === 'worker' ? cardHighlight : undefined}>
                <header style={providerHead}>
                  <h3 style={{ fontSize: 16, fontWeight: 500, letterSpacing: 'var(--track-tight)' }}>Data worker (ERCOT)</h3>
                  <span style={status}><span className={`status-dot ${(!latestTime || isStale || workerCheck?.band === 'alert') ? 'warning' : ''}`} style={latestTime ? undefined : unknownDot}/>{workerStatus}</span>
                </header>
                <ul style={rows}>
                  <li style={rowStyle}><span style={label}>Feed status</span><span className="num" style={value}>{workerStatus}</span></li>
                  <li style={rowStyle}><span style={label}>Feed freshness</span><span className="num" style={value}>{workerAge !== null ? `${workerAge} s` : 'not configured'}</span></li>
                  <li style={rowStyle}><span style={label}>Health probability</span><span className="num" style={value}>{workerCheck ? `${(workerCheck.probability * 100).toFixed(0)}%` : 'Unavailable'}</span></li>
                  <li style={rowStyle}><span style={label}>Band</span>{workerCheck ? <span style={bandStyle[workerCheck.band]}>{workerCheck.band}</span> : <span className="num" style={value}>Unavailable</span>}</li>
                  <li style={rowStyle}><span style={label}>Signals reported</span><span className="num" style={value}>{gridSignals && gridSignals.length > 0 ? gridSignals.length : 'Waiting for ERCOT'}</span></li>
                </ul>
                {workerCheck?.baseline && <p className="tiny" style={{ marginTop: 8 }}>baseline rules</p>}
                {!latestTime && <p className="tiny">Feed status: not configured · Waiting for ERCOT.</p>}
              </article>;
            })()}
          </div>
        </>}
      </Panel>

      <Panel title="Owner outage controls" index="02">
        <div style={panelBody}>
          <TextInput label="Admin key" placeholder="Enter admin key" type="password" value={adminKey} onChange={setAdminKey} isDisabled={pending} width="100%" description="Type your key for each outage action. It is cleared when sent and never saved." />
          {pending && <p role="status" className="tiny">Sending outage request…</p>}
          {notice && <p role={failed ? 'alert' : 'status'} className={failed ? 'connection-line has-error' : 'tiny'} style={failed ? { margin: 0 } : undefined}>{notice}</p>}
        </div>
      </Panel>
    </div>
  </>;
}
