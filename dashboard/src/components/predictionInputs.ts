import type { Signal } from '../api';

/** Report presence is conservative: latest signals cannot establish full delivery-hour coverage. */
export function missingInputs(factor: string, zone: string, signals: Signal[]) {
  const reports: Record<string, string[]> = {
    'price spread': ['NP4-190-CD', 'NP6-905-CD'], 'load pressure': ['NP3-565-CD'],
    'outage pressure': ['NP3-233-CD'], 'congestion pressure': ['NP6-905-CD', 'NP6-86-CD'],
    'heat stress': ['NWS-TEMP'], 'weather alert': ['NWS-ALERTS'], 'peak period': [],
  };
  return (reports[factor.toLowerCase().replace(/[_-]+/g, ' ').trim()] ?? [])
    .filter(report => !signals.some(s => s.report_id === report && (s.zone === zone || report === 'NP6-86-CD')))
    .map(report => ({ 'NP4-190-CD': 'day-ahead price', 'NP6-905-CD': 'real-time price',
      'NP3-565-CD': 'load forecast', 'NP3-233-CD': 'outage capacity', 'NP6-86-CD': 'grid constraints',
      'NWS-TEMP': 'temperature', 'NWS-ALERTS': 'weather alerts' }[report] ?? report));
}
