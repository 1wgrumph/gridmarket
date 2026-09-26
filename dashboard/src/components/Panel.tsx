import type { ReactNode } from 'react';
import { Card } from '@astryxdesign/core';

/** Titled glass panel; `state` replaces the body while data is loading or failed. */
export default function Panel({ title, state, children, className }: {
  title: string; state?: { loading: boolean; error: string | null }; children: ReactNode; className?: string;
}) {
  return <Card className={`gm-panel ${className ?? ''}`} padding={4}>
    <h2 className="gm-panel-title">{title}</h2>
    {state?.error ? <p className="gm-muted" role="alert">Feed unavailable; retrying every 2 s.</p>
      : state?.loading ? <p className="gm-muted">Loading…</p>
      : children}
  </Card>;
}
