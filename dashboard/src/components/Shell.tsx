import type { ReactNode } from 'react';

const navigation = [
  ['#/', 'Overview'], ['#/market', 'Market'], ['#/predictions', 'Predictions'],
  ['#/providers', 'Providers'], ['#/bots', 'Bots'], ['#/sandbox', 'Sandbox'], ['#/spec', 'Spec'],
] as const;

export default function Shell({ children }: { children: ReactNode }) {
  return <div style={{ minHeight: '100vh', background: '#0b1721', color: '#eaf8fb', fontFamily: 'system-ui, sans-serif' }}>
    <header style={{ padding: '1rem', borderBottom: '1px solid #376170' }}>
      <strong>GridMarket</strong>
      <nav aria-label="Main navigation" style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', marginTop: '1rem' }}>
        {navigation.map(([href, label]) => <a key={href} href={href} style={{ color: '#7ce7ee' }}>{label}</a>)}
      </nav>
    </header>
    <main style={{ padding: '1rem', maxWidth: '72rem', margin: 'auto' }}>{children}</main>
  </div>;
}
