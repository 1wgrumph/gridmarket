import { useEffect, useState } from 'react';
import { get, type Bot, type MarketProduct, type MarketStatus, type Prediction, type Provider, type RouterCheck } from './api';

export function useResource<T>(path: string, intervalMs = 2000) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    const load = () => get<T>(path).then(value => { if (active) { setData(value); setError(null); } }).catch(reason => { if (active) setError(String(reason)); });
    load();
    const timer = window.setInterval(load, intervalMs);
    return () => { active = false; window.clearInterval(timer); };
  }, [path, intervalMs]);
  return { data, error, loading: data === null && error === null };
}

export const useMarket = () => useResource<MarketProduct[]>('/v1/market');
export const useMarketStatus = () => useResource<MarketStatus>('/v1/market/status');
export const useMarketActivity = () => useResource<unknown[]>('/v1/market/activity');
export const usePredictions = () => useResource<Prediction[]>('/v1/predictions');
export const useSignals = () => useResource<unknown[]>('/v1/signals');
export const useProviders = () => useResource<Provider[]>('/v1/providers');
export const useProviderHealth = () => useResource<unknown[]>('/v1/providers/health');
export const useRouterChecks = () => useResource<RouterCheck[]>('/v1/router');
export const useBots = () => useResource<Bot[]>('/v1/bots');
export const useBotProfile = (id: string) => useResource<Bot>(`/v1/bots/${id}`);
export const useBotDiversity = () => useResource<unknown>('/v1/bots/diversity');
