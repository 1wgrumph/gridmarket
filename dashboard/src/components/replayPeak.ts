import type { ReplayDays } from '../api';
import { useResource } from '../hooks';

const central = (options: Intl.DateTimeFormatOptions) => new Intl.DateTimeFormat('en-US', { timeZone: 'America/Chicago', ...options });
const dayFormat = central({ weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });
const timeFormat = central({ hour: 'numeric', minute: '2-digit' });
const places: Record<string, string> = { LZ_WEST: 'West Texas', LZ_NORTH: 'North Texas', LZ_SOUTH: 'South Texas', LZ_HOUSTON: 'Houston' };

/** The replay day's real-time price peak from GET /v1/replay/days (C8); null while loading or when the API is missing or fails. */
export function useReplayPeak() {
  const days = useResource<ReplayDays>('/v1/replay/days');
  const raw = days.data?.days?.find(d => d.day === '2026-08-26')?.peak_rt_price;
  const start = raw ? Date.parse(raw.interval_start) : NaN;
  const peak = !days.error && raw && Number.isFinite(raw.value) && Number.isFinite(start) ? {
    day: dayFormat.format(start),
    time: `${timeFormat.format(start)} CT`,
    place: places[raw.point] ?? raw.point,
    price: `$${raw.value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
  } : null;
  return { peak, loading: days.loading };
}
