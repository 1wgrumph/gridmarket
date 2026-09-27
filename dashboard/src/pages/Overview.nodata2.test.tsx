// @vitest-environment jsdom
/* S59 no-data residuals + price-chart ticks, rendered from dashboard/src/fixtures/nodata2.json
   with fetch stubbed (no network). Scoped queries only; fixed fixture clock, no wall-clock
   assertions; RTL timeouts stay real. Chart ticks need measured layout: ResizeObserver and
   getBoundingClientRect are stubbed to a fixed 600x300. */
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
// @ts-ignore TS2732: Vitest loads JSON; the frozen tsconfig omits resolveJsonModule.
import fixture from '../fixtures/nodata2.json';
import Overview from './Overview';
import { tickClock } from '../components/PriceChart';

let responses: Record<string, unknown>;
let originalRect: typeof Element.prototype.getBoundingClientRect;

beforeEach(() => {
  window.location.hash = '#/';
  responses = structuredClone(fixture);
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const path = new URL(String(input), 'http://localhost').pathname;
    const body = responses[path];
    return { ok: body !== undefined, status: body === undefined ? 404 : 200,
      json: async () => body ?? { error: { code: 'NOT_FOUND', message: 'Not found' } } };
  }));
  originalRect = Element.prototype.getBoundingClientRect;
  Element.prototype.getBoundingClientRect = (() => (
    { width: 600, height: 300, top: 0, left: 0, right: 600, bottom: 300, x: 0, y: 0, toJSON: () => ({}) }
  )) as unknown as typeof Element.prototype.getBoundingClientRect;
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} });
});

afterEach(() => {
  cleanup();
  Element.prototype.getBoundingClientRect = originalRect;
  vi.unstubAllGlobals();
  window.location.hash = '';
});

async function zonesPanel() {
  render(<Overview />);
  const zones = await screen.findByRole('region', { name: 'Across the load zones' });
  await waitFor(() => expect(zones.getAttribute('aria-busy')).toBe('false'));
  return zones;
}

async function hero() {
  const hero = await screen.findByRole('region', { name: 'Next delivery prediction' });
  await waitFor(() => expect(hero.getAttribute('aria-busy')).toBe('false'));
  return hero;
}

async function pricePanel() {
  const panel = await screen.findByRole('region', { name: /the price of flexibility/i });
  await waitFor(() => expect(panel.getAttribute('aria-busy')).toBe('false'));
  return panel;
}

it('S59-01 zones Scarcity hides baseline scores without ERCOT prices', async () => {
  responses['/v1/signals'] = [];
  const zones = await zonesPanel();
  const rows = within(zones).getAllByRole('row').slice(1);
  expect(rows.length).toBeGreaterThan(0);
  for (const row of rows) {
    const cells = within(row).getAllByRole('cell');
    expect(cells[2].textContent).toBe('—');
  }
  expect(zones.textContent).not.toMatch(/\d+(?:\.\d+)?\s*%/);
  expect(await screen.findByText('Grid feed pending · ERCOT price inputs not yet received')).toBeTruthy();
});

it('S59-01b zones Scarcity shows served scores with ERCOT prices', async () => {
  const zones = await zonesPanel();
  expect(await within(zones).findByText('72.4%')).toBeTruthy();
  expect(within(zones).queryByText('45.8%')).toBeNull();
  const north = within(zones).getByRole('row', { name: /North/i });
  expect(within(north).getAllByRole('cell')[2].textContent).toBe('—');
});

it('S59-02 hero hides factor chips without ERCOT prices', async () => {
  responses['/v1/signals'] = [];
  render(<Overview />);
  const region = await hero();
  expect(await within(region).findByText('No prediction factors available')).toBeTruthy();
  expect(within(region).queryByText('price spread')).toBeNull();
  expect(await screen.findByText('Grid feed pending · ERCOT price inputs not yet received')).toBeTruthy();
});

it('S59-02b hero shows factor chips with ERCOT prices', async () => {
  render(<Overview />);
  const region = await hero();
  expect(await within(region).findByText('price spread')).toBeTruthy();
  expect(await within(region).findByText('peak-period')).toBeTruthy();
});

it('S59-03 clustered trades get distinct second-precision ticks', async () => {
  responses['/v1/signals'] = (responses['/v1/signals'] as unknown[]).filter(
    (s: unknown) => (s as { report_id: string }).report_id === 'NP6-905-CD');
  render(<Overview />);
  const panel = await pricePanel();
  const ticks = await within(panel).findAllByText(/^\d{2}:\d{2}:\d{2}$/, {}, { timeout: 5000 });
  const labels = ticks.map(t => t.textContent?.trim());
  expect(labels.length).toBeGreaterThan(0);
  expect(new Set(labels).size).toBe(labels.length);
});

it('S59-04 wide series keeps HH:MM ticks', async () => {
  render(<Overview />);
  const panel = await pricePanel();
  const ticks = await within(panel).findAllByText(/^\d{2}:\d{2}$/, {}, { timeout: 5000 });
  expect(ticks.length).toBeGreaterThan(0);
  expect(within(panel).queryByText(/^\d{2}:\d{2}:\d{2}$/)).toBeNull();
});

it('S59-05 tick clock formats clustered instants distinctly', async () => {
  const clustered = ['09:55:05', '09:56:10', '09:57:45', '09:58:30'].map(t => ({ at: Date.parse(`2026-09-26T${t}Z`), price: 50 }));
  const labels = clustered.map(p => tickClock(clustered).format(p.at));
  expect(new Set(labels).size).toBe(labels.length);
  expect(labels[0]).toMatch(/^\d{2}:\d{2}:\d{2}$/);
  const wide = [{ at: Date.parse('2026-09-26T09:55:00Z') }, { at: Date.parse('2026-09-26T12:55:00Z') }];
  expect(tickClock(wide).format(wide[0].at)).toMatch(/^\d{2}:\d{2}$/);
});
