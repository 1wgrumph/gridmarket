import { useEffect, useRef } from 'react';
import type { MarketProduct, Prediction, Signal } from '../api';
import Panel from './Panel';
import { Stale as StaleTag } from '../pages/Market';

type Feed<T> = { data: T[] | null; error: string | null; loading: boolean };
const reports = [
  ['NP6-905-CD', 'SPP'], ['NP4-190-CD', 'Day-ahead price'],
  ['NP3-565-CD', 'Load forecast'], ['NP3-233-CD', 'Outage capacity'], ['NWS-ALERTS', 'NWS alerts'],
];
const scored = ['LZ_NORTH', 'LZ_WEST', 'LZ_HOUSTON', 'LZ_SOUTH'];
const hour = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Chicago', hour: 'numeric' });

export default function ZoneDetail({ zone, title, predictions, signals, market, onClose }: {
  zone: string; title: string; predictions: Feed<Prediction>; signals: Feed<Signal>; market: Feed<MarketProduct>; onClose: () => void;
}) {
  const close = useRef<HTMLButtonElement>(null);
  useEffect(() => { close.current?.focus({ preventScroll: true }); }, []);
  const prediction = predictions.data?.filter(p => p.zone === zone).sort((a, b) => a.delivery_hour.localeCompare(b.delivery_hour))[0];
  const products = market.data?.filter(p => p.zone === zone && p.status === 'open' && p.symbol.startsWith('FLEX-')) ?? [];
  return <div className="zone-detail" onKeyDown={e => { if (e.key === 'Escape') { e.preventDefault(); onClose(); } }}>
    <Panel title={`${title} zone details`} index="01" meta={<button ref={close} onClick={onClose} className="motion-toggle">Close</button>}>
      <div className="zone-detail-body">
        <StaleTag feed={predictions}/>
        {!scored.includes(zone) ? <p>Not scored: the model covers the four largest load zones</p> : prediction ? <>
          <p><strong>{prediction.score}%</strong> scarcity · <span>{prediction.level}</span> · Confidence {Math.round(prediction.confidence * 100)}%</p>
          <p>Delivery <time dateTime={prediction.delivery_hour}>{hour.format(new Date(prediction.delivery_hour))} CT</time></p>
          <ul className="zone-drivers">{prediction.drivers.map(d => <li key={d.factor}><strong>{d.factor}</strong> · {d.contribution}<p>{d.detail}</p></li>)}</ul>
        </> : <p>{predictions.loading ? 'Loading prediction…' : predictions.error ? 'Prediction unavailable' : 'Prediction not reported'}</p>}
        <h3>Latest signals</h3><StaleTag feed={signals}/>
        <ul className="zone-signals">{reports.map(([report, label]) => {
          const signal = signals.data?.filter(s => s.zone === zone && s.report_id === report).sort((a, b) => b.published_at.localeCompare(a.published_at))[0];
          const price = report === 'NP6-905-CD' || report === 'NP4-190-CD';
          return <li key={report}><strong>{label}</strong>{' '}<span>{signal ? <>
            {signal.value.toLocaleString('en-US', { minimumFractionDigits: price ? 2 : 0, maximumFractionDigits: price ? 2 : 1 })} {price ? '$/MWh' : signal.unit}
            {' · '}{signal.age_s}s ago {signal.stale && <span className="stale">Stale</span>}
          </> : signals.loading ? 'Loading…' : signals.error ? 'Signal unavailable' : 'not reported'}</span></li>;
        })}</ul>
        <h3>Open Flex Credit products</h3><StaleTag feed={market}/>
        {products.length ? <ul className="zone-products">{products.map(p => <li key={p.symbol}><span>{p.symbol}</span> · <time dateTime={p.delivery_hour}>{hour.format(new Date(p.delivery_hour))} CT</time></li>)}</ul>
          : <p>{market.loading ? 'Loading products…' : market.error ? 'Products unavailable' : 'No open FLEX products'}</p>}
        <a href="#/market">Open in Market</a>
      </div>
    </Panel>
  </div>;
}
