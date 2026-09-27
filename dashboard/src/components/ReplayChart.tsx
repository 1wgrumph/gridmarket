import { CartesianGrid, Line, LineChart, ReferenceArea, ReferenceDot, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

export type CurvePoint = { at: number; price: number };
export type CurveArea = { from: number; to: number };
const time = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Chicago', hour: '2-digit', minute: '2-digit', hour12: false });
const tick = { fill: 'var(--muted)', fontSize: 11 };

/** Served day-ahead (or real-time, when the run carries it) prices with procurement shading and the playback head. */
export default function ReplayChart({ data, areas, headAt, peak, kind }: {
  data: CurvePoint[]; areas: CurveArea[]; headAt: number | null; peak: { at: number; price: number } | null; kind: string;
}) {
  return <ResponsiveContainer width="100%" height="100%" minWidth={0}>
    <LineChart data={data} margin={{ top: 24, right: 18, left: -8, bottom: 2 }} accessibilityLayer>
      <CartesianGrid stroke="var(--line)" vertical={false} strokeDasharray="2 4"/>
      <XAxis dataKey="at" type="number" scale="time" domain={['dataMin', 'dataMax']} tickFormatter={at => time.format(at)} axisLine={false} tickLine={false} tick={tick}/>
      <YAxis domain={['auto', 'auto']} tickFormatter={v => `$${v}`} axisLine={false} tickLine={false} tick={tick} width={64}/>
      <Tooltip labelFormatter={at => `${time.format(Number(at))} CT`} formatter={value => [`$${Number(value).toFixed(2)} / MWh`, kind]} contentStyle={{ background: 'var(--surface)', border: '1px solid var(--line)', color: 'var(--text)', fontSize: 12, borderRadius: 'var(--r-2)' }} itemStyle={{ color: 'var(--text)' }} isAnimationActive={false}/>
      {areas.map(area => <ReferenceArea key={`${area.from}`} x1={area.from} x2={area.to} fill="var(--secondary)" fillOpacity={1} stroke="none"/>)}
      <Line type="monotone" dataKey="price" name={kind} stroke="var(--accent)" strokeWidth={2.5} dot={false} isAnimationActive={false}/>
      {peak && <ReferenceDot x={peak.at} y={peak.price} r={4} fill="var(--warning)" stroke="var(--surface)"/>}
      {headAt !== null && <ReferenceLine x={headAt} stroke="var(--text)" strokeDasharray="3 3"/>}
    </LineChart>
  </ResponsiveContainer>;
}
