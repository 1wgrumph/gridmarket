import { createElement, type ReactNode } from 'react';
import Panel from '../components/Panel';
import { specification } from './SpecDoc';

// Keep repository-relative links as text; the document itself is available here.
function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g).map((part, i) => {
    if (part.startsWith('**')) return <strong key={i}>{part.slice(2, -2)}</strong>;
    if (part.startsWith('`')) return <code key={i}>{part.slice(1, -1)}</code>;
    const link = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(part);
    return link ? link[1] : part;
  });
}

export default function Spec() {
  return <section className="gm-page">
    <div className="gm-page-head"><h1>Specification</h1></div>
    <Panel title="Generated document" index="01">
      {specification ? <article className="spec-document" aria-label="GridMarket specification">{specification.split(/\n\n+/).map((block, i) => {
        const heading = /^(#{1,6}) (.+)$/.exec(block);
        if (heading) return createElement(`h${Math.min(6, heading[1].length + 1)}`, { key: i }, inline(heading[2]));
        const lines = block.split('\n');
        if (lines.length > 1 && lines[0].startsWith('|') && /^\|[\s:|\-]+$/.test(lines[1])) {
          const cells = (line: string) => line.replace(/^\||\|$/g, '').split('|').map(c => c.trim());
          return <div className="table-scroll" tabIndex={0} aria-label="Specification table" key={i}><table><thead><tr>{cells(lines[0]).map((c, j) => <th key={j}>{inline(c)}</th>)}</tr></thead><tbody>{lines.slice(2).map((line, j) => <tr key={j}>{cells(line).map((c, k) => <td key={k}>{inline(c)}</td>)}</tr>)}</tbody></table></div>;
        }
        if (lines.every(line => /^\s*[-*] /.test(line))) return <ul key={i}>{lines.map((line, j) => <li key={j}>{inline(line.replace(/^\s*[-*] /, ''))}</li>)}</ul>;
        if (block.startsWith('```')) return <pre key={i}>{block.replace(/^```[^\n]*\n/, '').replace(/\n```$/, '')}</pre>;
        return <p key={i}>{inline(block.replace(/^> /gm, ''))}</p>;
      })}</article> : <p>Published with the final release.</p>}
      <p><a href="/docs">API documentation</a> · <a href="#/sandbox">Try the sandbox</a></p>
    </Panel>
  </section>;
}
