import { useEffect, useState } from 'react';

export const query = () => new URLSearchParams(window.location.hash.split('?')[1] ?? '');
export function contextLink(path: string, values: Record<string, string | undefined> = {}) {
  const params = new URLSearchParams();
  for (const name of ['zone', 'hour']) { const value = query().get(name); if (value) params.set(name, value); }
  for (const [name, value] of Object.entries(values)) { if (value) params.set(name, value); else params.delete(name); }
  return path + (params.size ? `?${params}` : '');
}
export function useViewQuery() {
  const [params, setParams] = useState(query);
  useEffect(() => {
    const update = () => setParams(query());
    window.addEventListener('hashchange', update);
    return () => window.removeEventListener('hashchange', update);
  }, []);
  return params;
}
export function setViewQuery(values: Record<string, string | undefined>) {
  const params = query();
  for (const [name, value] of Object.entries(values)) { if (value) params.set(name, value); else params.delete(name); }
  window.location.hash = `${window.location.hash.split('?')[0] || '#/'}${params.size ? `?${params}` : ''}`;
}
export const centralTime = (iso: string) => {
  const at = Date.parse(iso.includes('T') ? iso : `${iso.replace(' ', 'T')}Z`);
  return Number.isFinite(at) ? `${new Date(at).toLocaleString('en-US', { timeZone: 'America/Chicago', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })} CT` : 'Time unavailable';
};
