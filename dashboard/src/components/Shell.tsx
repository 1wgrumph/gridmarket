import { useEffect, useState, type ReactNode } from 'react';
import { Theme } from '@astryxdesign/core/theme';
import { SegmentedControl, SegmentedControlItem } from '@astryxdesign/core/SegmentedControl';
import { gridmarketTheme } from '../theme';
import { useSignals } from '../hooks';
import Icon from './Icon';
import '../styles.css';

const nav = [
  ['#/', 'Overview', '01'], ['#/market', 'Market', '02'], ['#/predictions', 'Predictions', '03'], ['#/providers', 'Providers', '04'],
  ['#/bots', 'Bots', '05'], ['#/sandbox', 'Judge sandbox', '06'], ['#/spec', 'Spec', '07'],
] as const;
const central = (options: Intl.DateTimeFormatOptions) => new Intl.DateTimeFormat('en-US', { timeZone: 'America/Chicago', ...options });
const clockFormat = central({ hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
const dayFormat = central({ weekday: 'long', day: 'numeric', month: 'long' });
const publishFormat = central({ hour: 'numeric', minute: '2-digit', timeZoneName: 'short' });
type Mode = 'dark' | 'light' | 'system';

/** AC-GM-UI-02 disclosure as one expandable line. */
export function Disclosures() {
  return <details className="disclosure">
    <summary><span>Simulated forward flexibility contracts, not regulated commodity futures. A Flex Credit is not a renewable energy certificate, a cryptocurrency, or a claim on specific electrons.</span><strong>Details <Icon name="plus"/></strong></summary>
    <p>Real ERCOT market information provides context. Accounts, batteries, orders, cash and settlement in this exchange are simulated. Scarcity is a heuristic simulation estimate and does not guarantee profit.</p>
  </details>;
}

export default function Shell({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<Mode>(() => {
    const saved = localStorage.getItem('gm-theme');
    return saved === 'light' || saved === 'system' ? saved : 'dark';
  });
  const [menu, setMenu] = useState(false);
  const [route, setRoute] = useState(window.location.hash || '#/');
  const [now, setNow] = useState(Date.now());
  const signals = useSignals();
  useEffect(() => {
    const update = () => { setRoute(window.location.hash || '#/'); setMenu(false); };
    window.addEventListener('hashchange', update);
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => { window.removeEventListener('hashchange', update); window.clearInterval(timer); };
  }, []);
  const fixtures = import.meta.env.VITE_FIXTURES === '1';
  const latest = signals.data?.reduce<string | undefined>((max, s) => !max || s.published_at > max ? s.published_at : max, undefined);
  const stale = signals.data?.filter(s => s.stale).length ?? 0;
  const freshness = signals.error ? 'Stale · connection lost'
    : latest ? `Published ${publishFormat.format(new Date(latest))}${stale ? ` · ${stale} stale` : ''}`
    : 'Publish time unavailable';
  return <Theme theme={gridmarketTheme} mode={mode}>
    <a className="skip-link" href="#main" onClick={event => { event.preventDefault(); document.getElementById('main')?.focus(); }}>Skip to main content</a>
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-row">
          <a href="#/" className="brand" aria-label="Home"><svg viewBox="0 0 28 28" aria-hidden="true"><path d="M3 3h9v9H3zm13 0h9v9h-9zM3 16h9v9H3zm13 0h9v9h-9z"/><path className="brand-cut" d="m17 17 7 7m0-7-7 7"/></svg><span>GridMarket<span className="brand-sub">ENERGY · EXCHANGE</span></span></a>
          <button className="menu-toggle" aria-expanded={menu} aria-controls="sidebar-content" onClick={() => setMenu(!menu)}>{menu ? 'Close' : 'Menu'}</button>
        </div>
        <div id="sidebar-content" className={`sidebar-content ${menu ? 'is-open' : ''}`}>
          <p className="eyebrow nav-caption">THE EXCHANGE</p>
          <nav aria-label="Primary">{nav.map(([href, label, number]) => {
            const current = href === '#/' ? route === '#/' : route === href || route.startsWith(`${href}/`);
            return <a key={href} href={href} className={current ? 'selected' : ''} aria-current={current ? 'page' : undefined}><span className="nav-number">{number}</span>{label}{current && <span className="nav-arrow"><Icon name="up-right"/></span>}</a>;
          })}</nav>
          <div className="sidebar-bottom">
            <div className="market-clock"><p className="eyebrow">MARKET CLOCK · TEXAS</p><time className="num">{clockFormat.format(now)}<small> CT</small></time><span>{dayFormat.format(now)}</span></div>
            <div className="freshness"><span className={`status-dot ${signals.error || stale ? 'warning' : ''}`}/><div><strong>ERCOT data</strong><p>{freshness}</p><span className="tiny">Polling every 2 seconds</span></div></div>
            <a className="judge-cta" href="#/sandbox"><span>YOUR TURN TO TRADE</span><strong>Get API key <Icon name="up-right"/></strong><small>$1,000 simulated cash to start</small></a>
            <p className="sidebar-foot">BASE / AITX HACKATHON<span>FINAL EDITION · 2026</span></p>
          </div>
        </div>
      </aside>
      <div className="workspace">
        <header className="masthead">
          <span className="eyebrow">TEXAS FLEXIBILITY EXCHANGE</span>
          <div className="header-controls">
            <span className="fixture-tag">{fixtures ? 'ILLUSTRATIVE FIXTURES' : 'SIMULATED MARKET'}</span>
            <SegmentedControl label="Color theme" value={mode} onChange={value => { setMode(value as Mode); localStorage.setItem('gm-theme', value); }} size="sm">
              <SegmentedControlItem value="dark" label="Dark"/><SegmentedControlItem value="light" label="Light"/><SegmentedControlItem value="system" label="Auto"/>
            </SegmentedControl>
          </div>
        </header>
        <main id="main" tabIndex={-1}>{children}{route !== '#/' && <Disclosures/>}</main>
        <footer className="page-footer"><span>Real grid context. Simulated energy markets.</span><span>GridMarket</span></footer>
      </div>
    </div>
  </Theme>;
}
