// @vitest-environment jsdom
/* S58-fix Overview honesty pass, rendered from dashboard/src/fixtures/honest.json
   with fetch stubbed (no network). With-data is the fixture as served; no-data
   cases override responses before render. Scoped queries only; no wall-clock
   assertions; RTL timeouts stay real. */
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
// @ts-ignore TS2732: Vitest loads JSON; the frozen tsconfig omits resolveJsonModule.
import fixture from '../fixtures/honest.json';
import Overview from './Overview';

let responses: Record<string, unknown>;
let marketState: 'loaded' | 'loading' | 'error';

beforeEach(() => {
  window.location.hash = '#/';
  responses = structuredClone(fixture);
  marketState = 'loaded';
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const path = new URL(String(input), 'http://localhost').pathname;
    if (path === '/v1/market' && marketState === 'loading') return new Promise(() => {});
    if (path === '/v1/market' && marketState === 'error') {
      return { ok: false, status: 503, json: async () => ({ error: { code: 'UNAVAILABLE', message: 'Market unavailable' } }) };
    }
    const body = responses[path];
    return { ok: body !== undefined, status: body === undefined ? 404 : 200,
      json: async () => body ?? { error: { code: 'NOT_FOUND', message: 'Not found' } } };
  }));
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  window.location.hash = '';
});

async function overview() {
  render(<Overview />);
  const zones = await screen.findByRole('region', { name: 'Across the load zones' });
  await waitFor(() => expect(zones.getAttribute('aria-busy')).toBe('false'));
  return zones;
}

async function stat(label: string) {
  const strip = await screen.findByRole('region', { name: 'Market key numbers' });
  return (await within(strip).findByText(label)).parentElement!;
}

async function openHouston() {
  await overview();
  const hero = await screen.findByRole('region', { name: 'Next delivery prediction' });
  await waitFor(() => expect(hero.getAttribute('aria-busy')).toBe('false'));
  fireEvent.click(await within(hero).findByRole('button', { name: /Houston zone details/i }));
  return screen.findByRole('region', { name: /Houston zone details/i });
}

it('S58FIX-01 zone detail without ERCOT prices hides the baseline score and drivers', async () => {
  responses['/v1/signals'] = [];
  const detail = await openHouston();
  expect(await within(detail).findByText('Baseline only: waiting for live ERCOT data')).toBeTruthy();
  expect(await within(detail).findByText('Drivers appear when live ERCOT inputs arrive')).toBeTruthy();
  expect(detail.textContent).toContain('—');
  expect(detail.textContent).not.toMatch(/\d+(?:\.\d+)?\s*%/);
  expect(await within(detail).findAllByText(/not reported/i)).toHaveLength(5);
});

it('S58FIX-01b zone detail with ERCOT prices is unchanged', async () => {
  const detail = await openHouston();
  await waitFor(() => expect(detail.textContent).toMatch(/72\.4\s*%/));
  expect(await within(detail).findByText(/^HIGH$/i)).toBeTruthy();
  expect(detail.textContent).toMatch(/confidence/i);
  expect(await within(detail).findByText('DA SPP $45.10 vs RT mean $38.42')).toBeTruthy();
  expect(await within(detail).findByText('NERC 5x16 on-peak hour')).toBeTruthy();
});

it('S58FIX-02 drivers with missing inputs report not reported from zone signals', async () => {
  const detail = await openHouston();
  const drivers = (await within(detail).findByText('DA SPP $45.10 vs RT mean $38.42')).closest('.zone-drivers') as HTMLElement;
  await waitFor(() => expect(within(drivers).getAllByText('not reported')).toHaveLength(3));
  expect(within(drivers).queryByText(/Load 0 MW/)).toBeNull();
  expect(within(drivers).queryByText(/Outage capacity 2,310 MW/)).toBeNull();
  expect(within(drivers).queryByText(/Temperature reading unavailable/)).toBeNull();
  expect(within(detail).queryByText(/Temperature reading unavailable/)).toBeNull();
});

it('S58FIX-03 system load sums the latest load zones without double counting', async () => {
  await overview();
  const load = await stat('System load');
  await waitFor(() => expect(load.querySelector('strong')?.textContent).toContain('25,040'));
  expect(load.textContent).toContain('25,040 MW');
  expect(load.textContent).not.toContain('46,040');
  expect(await within(load).findByText(/stale/i)).toBeTruthy();
  expect(load.textContent?.toLowerCase()).not.toContain('unavailable');
});

it('S58FIX-03b system load without load signals waits for ERCOT', async () => {
  responses['/v1/signals'] = [];
  await overview();
  const load = await stat('System load');
  await waitFor(() => expect(load.querySelector('strong')?.textContent).toBe('—'));
  expect(load.textContent).toContain('Waiting for ERCOT');
});

it('S58FIX-04 open products counts open rows with honest loading and error states', async () => {
  await overview();
  const products = await stat('Open products');
  await waitFor(() => expect(products.querySelector('strong')?.textContent).toBe('3'));
  expect(screen.queryByText('Open interest')).toBeNull();
  expect(products.textContent?.toLowerCase()).not.toContain('unavailable');
});

it('S58FIX-04b open products loading and error placeholders', async () => {
  marketState = 'loading';
  await overview();
  const loading = await stat('Open products');
  await waitFor(() => expect(loading.querySelector('strong')?.textContent).toBe('…'));
  cleanup();
  window.location.hash = '#/';
  marketState = 'error';
  render(<Overview />);
  const failed = await stat('Open products');
  await waitFor(() => expect(failed.querySelector('strong')?.textContent).toBe('—'));
});

it('S58FIX-05 price legend draws served day-ahead signals as the forecast', async () => {
  await overview();
  const panel = await screen.findByRole('region', { name: /the price of flexibility/i });
  await waitFor(() => expect(panel.getAttribute('aria-busy')).toBe('false'));
  expect(await within(panel).findByText('Day-ahead forecast $44.02')).toBeTruthy();
  expect(panel.textContent).toContain('Day-ahead $44.02 /MWh');
  expect(panel.querySelector('.chart')?.getAttribute('aria-label')).toMatch(/day-ahead forecast latest \$44\.02/i);
  expect(panel.textContent?.toLowerCase()).not.toContain('unavailable');
});

it('S58FIX-05b price legend without day-ahead signals waits for ERCOT', async () => {
  responses['/v1/signals'] = [];
  await overview();
  const panel = await screen.findByRole('region', { name: /the price of flexibility/i });
  expect(await within(panel).findByText('Day-ahead: waiting for ERCOT')).toBeTruthy();
  expect(panel.textContent?.toLowerCase()).not.toContain('unavailable');
});

it('S58FIX-06 zones footer keeps central time and the zone count only', async () => {
  await overview();
  const panel = await screen.findByRole('region', { name: /across the load zones/i });
  const foot = panel.querySelector('.panel-end')!;
  expect(foot.textContent).toContain('Central time');
  expect(foot.textContent).toContain('3 zones served');
  expect(foot.textContent?.toLowerCase()).not.toContain('trend series');
  expect(foot.textContent?.toLowerCase()).not.toContain('unavailable');
});
