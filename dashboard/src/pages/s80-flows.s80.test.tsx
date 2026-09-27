// @vitest-environment jsdom
/* S80 / UX-01, UX-18, FLOW-022. Public HTTP captures from a local seeded backend.
   s80-tour.json: GET routes are its keys; retrieved 2026-09-26T22:51:53Z.
   Transformation: first two bots and their profiles; first twelve product details.
   List rows carry the served economy fields (blend, cash, net_worth, pnl,
   trades, losses) copied from their profiles per the /v1/bots contract.
   SHA256 60d15f4af768f32d9110cdd78bc37bae48af373dffb02eee6b4ae8f5e12cc3ea.
   s80-sandbox.json: POST keys, crossing sell/buy at 10 cents, GET orders, fourth key
   returns 429; retrieved 2026-09-26T22:52:49Z. Replaced key with a non-credential;
   retained one traded product, set test clock three hours before delivery.
   SHA256 19541ea9f5825a4a9cba64c14e559a246d0c207464fa7538e3fbe2498d1b6702. */
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
// @ts-ignore Vitest loads JSON.
import exchange from '../fixtures/s80-tour.json';
// @ts-ignore Vitest loads JSON.
import sandbox from '../fixtures/s80-sandbox.json';
import App from '../App';
let filled: boolean;
let limited: boolean;
beforeEach(() => {
  filled = false; limited = false;
  localStorage.clear(); window.location.hash = '#/';
  vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'] });
  vi.setSystemTime(new Date(sandbox.clock));
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(String(input), 'http://localhost').pathname;
    if (path === '/v1/sandbox/keys' && limited) return { ok: false, status: 429, headers: new Headers({ 'Retry-After': sandbox.rate_limit.retryAfter }), json: async () => sandbox.rate_limit.body };
    let body = (exchange as Record<string, unknown>)[path];
    if (path === '/v1/sandbox/keys') body = sandbox[path];
    if (path === '/v1/orders') {
      if (init?.method === 'POST') { filled = true; body = sandbox['POST /v1/orders']; }
      else body = filled ? sandbox['/v1/orders'] : [];
    }
    if (path === '/v1/market') body = sandbox[path];
    return { ok: body !== undefined, status: body === undefined ? 404 : 200, json: async () => body ?? { error: { message: 'Not found' } }, text: async () => '' };
  }));
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); window.location.hash = ''; });
const go = (hash: string) => act(() => { window.location.hash = hash; window.dispatchEvent(new Event('hashchange')); });

it('UX-01 summary and profile use the same public economy, with no invalid numeric text', async () => {
  render(<App/>);
  const id = exchange['/v1/bots'][0].id;
  const leaderboard = await screen.findByRole('region', { name: 'Bots setting the pace' });
  const row = await within(leaderboard).findByRole('row', { name: new RegExp(id) });
  expect(row.textContent).not.toMatch(/NaN|Infinity|Unavailable/);
  const profile = (exchange as unknown as Record<string, { pnl: number }>)[`/v1/bots/${id}`];
  const formatted = profile.pnl.toLocaleString('en-US', { style: 'currency', currency: 'USD' });
  expect(row.textContent).toContain(formatted);
  go('#/bots');
  const bots = await screen.findByRole('region', { name: 'All bots' });
  const summary = await within(bots).findByRole('row', { name: new RegExp(id) });
  expect(summary.textContent).toContain(formatted);
  go(`#/bots/${id}`);
  const performance = await screen.findByRole('region', { name: 'Performance' });
  await waitFor(() => expect(within(performance).getByText('P&L').nextElementSibling?.textContent).toBe(formatted));
});

it('FLOW-022 a filled first order ticks only the sandbox checklist item and survives navigation', async () => {
  render(<App/>);
  go('#/sandbox');
  const panel = await screen.findByRole('region', { name: 'Get a key' });
  fireEvent.click(within(panel).getByRole('button', { name: 'Get a sandbox key' }));
  await within(panel).findByText(sandbox['/v1/sandbox/keys'].api_key);
  fireEvent.click(within(panel).getByRole('button', { name: 'Place a first order' }));
  const orders = await screen.findByRole('region', { name: 'Your orders' });
  await within(orders).findByText('filled');
  expect(within(orders).getByRole('link', { name: 'Review your progress' })).toBeTruthy();
  go('#/');
  let checklist = await screen.findByRole('region', { name: 'Your first 3 minutes' });
  expect(within(checklist).getAllByText('Complete')).toHaveLength(1);
  expect(within(checklist).getByRole('link', { name: 'Place a first order' }).parentElement?.textContent).toContain('Complete');
  cleanup(); render(<App/>);
  checklist = await screen.findByRole('region', { name: 'Your first 3 minutes' });
  expect(within(checklist).getAllByText('Complete')).toHaveLength(1);
});

it('UX-18 the captured key rate limit gives its retry delay next to key creation', async () => {
  limited = true; window.location.hash = '#/sandbox'; render(<App/>);
  const panel = await screen.findByRole('region', { name: 'Get a key' });
  fireEvent.click(within(panel).getByRole('button', { name: 'Get a sandbox key' }));
  const error = await within(panel).findByRole('alert');
  expect(error.textContent).toContain(`${sandbox.rate_limit.retryAfter} seconds`);
  expect(error.compareDocumentPosition(within(panel).getByRole('button', { name: 'Place a first order' })) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});
