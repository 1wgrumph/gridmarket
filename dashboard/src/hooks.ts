import { useEffect, useState } from 'react';
import { get, type Activity, type Bot, type MarketProduct, type MarketStatus, type Prediction, type Provider, type RouterCheck, type Signal } from './api';

type Snapshot = { path: string; data: unknown; error: string | null };
type Poll = Snapshot & { listeners: Set<() => void>; timer: number };

/** One poll per path: components that read the same path share its fetches and last-known data. */
const polls = new Map<string, Poll>();
/** First loads still in flight; lets a burst of secondary reads wait for the page's first polls. */
const firstLoads = new Set<Promise<void>>();
export const pollsSettled = () => Promise.allSettled([...firstLoads]).then(() => undefined);

function subscribe(path: string, intervalMs: number, listener: () => void) {
  let poll = polls.get(path);
  if (!poll) {
    const created: Poll = { path, data: null, error: null, listeners: new Set(), timer: 0 };
    let pending = false;
    const load = () => {
      if (pending) return;
      pending = true;
      return get(path)
      .then(value => { created.data = value; created.error = null; })
      .catch((reason: { error?: { message?: string } }) => { created.error = reason?.error?.message ?? String(reason); })
      .finally(() => { pending = false; created.listeners.forEach(notify => notify()); });
    };
    created.timer = window.setInterval(load, intervalMs);
    polls.set(path, poll = created);
    const first = load()!;
    firstLoads.add(first);
    first.finally(() => firstLoads.delete(first));
  }
  poll.listeners.add(listener);
  return () => {
    poll.listeners.delete(listener);
    if (poll.listeners.size === 0) { window.clearInterval(poll.timer); polls.delete(path); }
  };
}

export function useResource<T>(path: string, intervalMs = 2000) {
  const [snapshot, setSnapshot] = useState<Snapshot>(() => polls.get(path) ?? { path, data: null, error: null });
  useEffect(() => subscribe(path, intervalMs, () => {
    const poll = polls.get(path);
    if (poll) setSnapshot({ path, data: poll.data, error: poll.error });
  }), [path, intervalMs]);
  const current = snapshot.path !== path ? { data: null, error: null } : snapshot;
  const data = current.data as T | null;
  return { data, error: current.error, loading: data === null && current.error === null };
}

export const useMarket = () => useResource<MarketProduct[]>('/v1/market');
export const useMarketStatus = () => useResource<MarketStatus>('/v1/market/status');
export const useMarketActivity = () => useResource<Activity[]>('/v1/market/activity');
export const usePredictions = () => useResource<Prediction[]>('/v1/predictions');
export const useSignals = () => useResource<Signal[]>('/v1/signals');
export const useProviders = () => useResource<Provider[]>('/v1/providers');
export const useProviderHealth = () => useResource<unknown[]>('/v1/providers/health');
export const useRouterChecks = () => useResource<RouterCheck[]>('/v1/router');
export const useBots = () => useResource<Bot[]>('/v1/bots');
export const useBotProfile = (id: string) => useResource<Bot>(`/v1/bots/${id}`);
export const useBotDiversity = () => useResource<unknown>('/v1/bots/diversity');
