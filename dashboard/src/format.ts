/** SQLite timestamps without an offset are UTC, as are the API's ISO timestamps. */
export const parseTime = (value: string) => Date.parse(
  /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value) ? value : `${value.replace(' ', 'T')}Z`,
);
const central = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/Chicago', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
});
export const centralTime = (value: string) => Number.isFinite(parseTime(value))
  ? `${central.format(parseTime(value))} CT` : 'Time unavailable';
export const usd = (value?: number | null) => typeof value === 'number' && Number.isFinite(value)
  ? `${value < 0 ? '−' : ''}${Math.abs(value).toLocaleString('en-US', { style: 'currency', currency: 'USD' })}`
  : 'Unavailable';
