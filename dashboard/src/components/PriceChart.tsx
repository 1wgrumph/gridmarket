import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

export type PricePoint = { at: number; price?: number; forecast?: number };
const time = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Chicago', hour: '2-digit', minute: '2-digit', hour12: false });
const timeSeconds = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Chicago', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
const exactTime = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Chicago', dateStyle: 'short', timeStyle: 'medium', hour12: false });
const tick = { fill: 'var(--muted)', fontSize: 11 };

/** Tick clock: seconds when the series spans under an hour, else HH:MM. Trades clustered within minutes share HH:MM labels; seconds keep the ticks distinct. */
export function tickClock(data: PricePoint[]) {
  const span = data.length ? Math.max(...data.map(d => d.at)) - Math.min(...data.map(d => d.at)) : 0;
  return span < 3600_000 ? timeSeconds : time;
}

/** Served trade prices over time, plus served day-ahead signals as the forecast series. */
export default function PriceChart({ data }: { data: PricePoint[] }) {
  const forecast = data.some(d => d.forecast != null);
  const clock = tickClock(data);
  const observed = data.filter(d => d.price != null);
  const flat = observed.length > 1 && observed.every(d => d.price === observed[0].price);
  const times = data.map(d => d.at);
  const first = Math.min(...times), last = Math.max(...times);
  const candidates = first === last ? [first] : Array.from({ length: 4 }, (_, i) => first + (last - first) * i / 3);
  const ticks = candidates.filter((at, i) => i === 0 || clock.format(at) !== clock.format(candidates[i - 1]));
  return <>{flat && <p className="chart-flat">Price unchanged since {time.format(observed[0].at)} CT</p>}<ResponsiveContainer width="100%" height="100%" minWidth={0}>
    <LineChart data={data} margin={{ top: 24, right: 18, left: -8, bottom: 2 }} accessibilityLayer>
      <CartesianGrid stroke="var(--line)" vertical={false} strokeDasharray="2 4"/>
      <XAxis ticks={ticks} minTickGap={20} dataKey="at" type="number" scale="time" domain={['dataMin', 'dataMax']} tickFormatter={at => clock.format(at)} axisLine={false} tickLine={false} tick={tick}/>
      <YAxis domain={['auto', 'auto']} tickFormatter={v => `$${v}`} axisLine={false} tickLine={false} tick={tick}/>
      <Tooltip labelFormatter={at => `${exactTime.format(Number(at))} CT`} formatter={(value, name) => name === 'Forecast' ? [`$${Number(value).toFixed(2)} / MWh`, 'Day-ahead'] : [`$${Number(value).toFixed(2)} / Flex Credit`, 'Trade']} contentStyle={{ background: 'var(--surface)', border: '1px solid var(--line)', color: 'var(--text)', fontSize: 12, borderRadius: 'var(--r-2)' }} itemStyle={{ color: 'var(--text)' }} isAnimationActive={false}/>
      <Line type="monotone" dataKey="price" name="Trade" stroke="var(--accent)" strokeWidth={3} dot={{ r: 3, fill: 'var(--accent)' }} connectNulls isAnimationActive={false}/>
      {forecast && <Line type="monotone" dataKey="forecast" name="Forecast" stroke="var(--info)" strokeWidth={2} strokeDasharray="4 4" dot={{ r: 2, fill: 'var(--info)' }} connectNulls isAnimationActive={false}/>}
    </LineChart>
  </ResponsiveContainer></>;
}
