import type { ReactNode } from 'react';

/** Numbered section panel; the aria-label makes it a named region. */
export default function Panel({ title, index, meta, className = '', busy, children }: {
  title: string; index: string; meta?: ReactNode; className?: string; busy?: boolean; children: ReactNode;
}) {
  return <section className={`panel ${className}`} aria-label={title} aria-busy={busy}>
    <div className="panel-head"><h2><span className="section-index">{index}</span>{title}</h2>{meta && <span className="panel-meta">{meta}</span>}</div>
    {children}
  </section>;
}
