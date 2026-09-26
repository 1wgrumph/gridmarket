import { useState, type ReactNode } from 'react';
import { Banner, Button } from '@astryxdesign/core';
import { Theme, defineTheme } from '@astryxdesign/core/theme';
import '../styles.css';

const mono = 'ui-monospace, "JetBrains Mono", "SFMono-Regular", Menlo, Consolas, monospace';

/** Control-room palette shared with the 3D views; tuples are [light, dark]. */
const gridTheme = defineTheme({
  name: 'gridmarket',
  tokens: {
    '--color-accent': ['#0e7490', '#22d3ee'],
    '--color-text-accent': ['#0e7490', '#7ce7ee'],
    '--color-on-accent': ['#ffffff', '#04121a'],
    '--color-background-body': ['#eef4f7', '#060e15'],
    '--color-background-surface': ['#ffffff', '#0b1721'],
    '--color-background-card': ['#ffffff', '#0d1c28'],
    '--color-background-muted': ['#e3edf1', '#112433'],
    '--color-border': ['#c6d7df', '#1d3847'],
    '--color-border-emphasized': ['#8fb0bd', '#376170'],
    '--color-text-primary': ['#0b1721', '#eaf8fb'],
    '--color-text-secondary': ['#3f5b67', '#8fb3bf'],
    '--color-success': ['#1f8a50', '#5fdd91'],
    '--color-warning': ['#9a6a00', '#f2c14e'],
    '--color-error': ['#c2410c', '#ff7a45'],
    '--color-on-success': ['#ffffff', '#04121a'],
    '--color-on-warning': ['#ffffff', '#1a1200'],
    '--color-on-error': ['#ffffff', '#1a0800'],
    '--font-family-heading': mono,
    '--font-family-code': mono,
  },
});

const navigation = [
  ['#/', 'Overview'], ['#/market', 'Market'], ['#/predictions', 'Predictions'],
  ['#/providers', 'Providers'], ['#/bots', 'Bots'], ['#/sandbox', 'Sandbox'], ['#/spec', 'Spec'],
] as const;

export default function Shell({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<'dark' | 'light'>('dark');
  const next = mode === 'dark' ? 'light' : 'dark';
  const route = window.location.hash || '#/';
  return <Theme theme={gridTheme} mode={mode}>
    <div className="gm-shell">
      <header className="gm-header">
        <strong className="gm-brand">GRID<span>MARKET</span></strong>
        <nav aria-label="Main navigation" className="gm-nav">
          {navigation.map(([href, label]) => {
            const current = href === '#/' ? route === '#/' : route.startsWith(href);
            return <a key={href} href={href} aria-current={current ? 'page' : undefined}>{label}</a>;
          })}
        </nav>
        <Button label={`Switch to ${next} mode`} variant="secondary" size="sm" onClick={() => setMode(next)} />
      </header>
      <div className="gm-disclosures">
        <Banner status="info" title="Disclosures" collapsible={false}>
          <ul>
            <li>Future products are simulated forward flexibility contracts, not regulated commodity futures.</li>
            <li>A Flex Credit is not a renewable energy certificate, a cryptocurrency, or a claim on specific electrons.</li>
            <li>Zone scores are a simulation estimate, not guaranteed profit.</li>
          </ul>
        </Banner>
      </div>
      <main className="gm-main">{children}</main>
    </div>
  </Theme>;
}
