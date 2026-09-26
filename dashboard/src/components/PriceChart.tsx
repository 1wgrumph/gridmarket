import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

export type PricePoint = { at: number; price: number };
const time = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Chicago', hour: '2-digit', minute: '2-digit', hour12: false });
const tick = { fill: 'var(--muted)', fontSize: 11 };

/** Served trade prices over time; no forecast series is drawn because none is served. */
export default function PriceChart({ data }: { data: PricePoint[] }) {
  return <ResponsiveContainer width="100%" height="100%" minWidth={0}>
    <LineChart data={data} margin={{ top: 24, right: 18, left: -8, bottom: 2 }} accessibilityLayer>
      <CartesianGrid stroke="var(--line)" vertical={false} strokeDasharray="2 4"/>
      <XAxis dataKey="at" type="number" scale="time" domain={['dataMin', 'dataMax']} tickFormatter={at => time.format(at)} axisLine={false} tickLine={false} tick={tick}/>
      <YAxis domain={['auto', 'auto']} tickFormatter={v => `$${v}`} axisLine={false} tickLine={false} tick={tick}/>
      <Tooltip labelFormatter={at => `${time.format(Number(at))} CT`} formatter={value => [`$${Number(value).toFixed(2)} / Flex Credit`, 'Trade']} contentStyle={{ background: 'var(--surface)', border: '1px solid var(--line)', color: 'var(--text)', fontSize: 12, borderRadius: 'var(--r-2)' }} itemStyle={{ color: 'var(--text)' }} isAnimationActive={false}/>
      <Line type="monotone" dataKey="price" name="Trade" stroke="var(--accent)" strokeWidth={3} dot={{ r: 3, fill: 'var(--accent)' }} isAnimationActive={false}/>
    </LineChart>
  </ResponsiveContainer>;
}
