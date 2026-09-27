import { useState } from 'react';
import { parseTime } from './format';

type Cell = string | number | null | undefined;

/** RFC 4180 CSV with a header row; a missing value is an empty cell, never 0. */
export function toCsv(header: string[], rows: Cell[][]) {
  const cell = (value: Cell) => {
    const text = value == null ? '' : String(value);
    return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  return [header, ...rows].map(row => row.map(cell).join(',')).join('\r\n') + '\r\n';
}

const valid = (value?: string | null) => value != null && Number.isFinite(parseTime(value));
export const utcStamp = (value?: string | null) => valid(value) ? new Date(parseTime(value!)).toISOString().replace(/\.\d{3}Z$/, 'Z') : '';

const central = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/Chicago', year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23', timeZoneName: 'short',
});
const centralParts = (at: number) => Object.fromEntries(central.formatToParts(at).map(p => [p.type, p.value]));
/** Central Time as `YYYY-MM-DD HH:MM:SS CDT|CST`. */
export function centralStamp(value?: string | null) {
  if (!valid(value)) return '';
  const p = centralParts(parseTime(value!));
  return `${p.year}-${p.month}-${p.day} ${p.hour}:${p.minute}:${p.second} ${p.timeZoneName}`;
}
/** Money in cents as integer cents and a plain dollar amount; missing stays empty. */
export const money = (cents?: number | null): Cell[] => typeof cents === 'number' && Number.isFinite(cents)
  ? [Math.round(cents), (cents / 100).toFixed(2)] : ['', ''];

/** `gridmarket-<subject>-<Central date>.csv` */
export function csvName(subject: string) {
  const p = centralParts(Date.now());
  return `gridmarket-${subject.replace(/[^A-Za-z0-9_-]+/g, '_')}-${p.year}-${p.month}-${p.day}.csv`;
}

function save(name: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/csv;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url));
}

export type CsvExport = { label: string; name: () => string; csv: () => string | Promise<string>; disabled?: boolean };

/** Download buttons plus a copyable API query for the data being exported; the status line keeps its height. */
export function ExportActions({ exports, query }: { exports: CsvExport[]; query: string }) {
  const [notice, setNotice] = useState('');
  const run = async (item: CsvExport) => {
    try { const name = item.name(); save(name, await item.csv()); setNotice(`Downloaded ${name}`); }
    catch (e) { setNotice(`Export failed: ${(e as { error?: { message?: string } })?.error?.message ?? String(e)}`); }
  };
  const copy = () => navigator.clipboard.writeText(query)
    .then(() => setNotice(`Copied: ${query}`), () => setNotice(`Copy unavailable. Query: ${query}`));
  return <div className="export-actions">
    {exports.map(item => <button key={item.label} type="button" className="action-secondary" disabled={item.disabled} onClick={() => run(item)}>{item.label}</button>)}
    <button type="button" className="action-secondary" title={query} onClick={copy}>Copy API query</button>
    <p role="status" className="muted">{notice}</p>
  </div>;
}
