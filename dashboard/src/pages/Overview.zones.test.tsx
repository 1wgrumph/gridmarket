// @vitest-environment jsdom
/* S58: endpoint corpus follows overview.json/esr.json, api.ts and the market
   generator's KIND-zone-YYYYMMDDHH format. participants is the approved additive
   provider field. market_list serves open rows only; SignalStore.current serves
   one latest row per report/zone. Date and polling are controlled; RTL timeouts
   stay real. */
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
// @ts-ignore TS2732: Vitest loads JSON; the frozen tsconfig omits resolveJsonModule.
import fixture from '../fixtures/zones.json';
import Overview from './Overview';

let responses: Record<string, unknown>;
let botsState: 'loaded' | 'loading' | 'error';
const zones = ['North', 'West', 'Houston', 'South', 'LCRA', 'RAYBN', 'AEN', 'CPS'];
const lead = fixture['/v1/predictions'][1];

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'] });
  vi.setSystemTime(new Date(fixture.clock));
  window.location.hash = '#/';
  responses = structuredClone(fixture);
  botsState = 'loaded';
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const path = new URL(String(input), 'http://localhost').pathname;
    if (path === '/v1/bots' && botsState === 'loading') return new Promise(() => {});
    if (path === '/v1/bots' && botsState === 'error') {
      return { ok: false, status: 503, json: async () => ({ error: { code: 'UNAVAILABLE', message: 'Bots unavailable' } }) };
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
  const table = await screen.findByRole('region', { name: 'Across the load zones' });
  await waitFor(() => expect(table.getAttribute('aria-busy')).toBe('false'));
  const hero = await screen.findByRole('region', { name: 'Next delivery prediction' });
  await waitFor(() => expect(hero.getAttribute('aria-busy')).toBe('false'));
  return hero;
}

async function stat(label: string) {
  const strip = await screen.findByRole('region', { name: 'Market key numbers' });
  return (await within(strip).findByText(label)).parentElement!;
}

async function openHouston() {
  const hero = await overview();
  fireEvent.click(await within(hero).findByRole('button', { name: /Houston zone details/i }));
  return screen.findByRole('region', { name: /Houston zone details/i });
}

it('S58-A01 all eight map zones are named, focusable controls and open details by click', async () => {
  const hero = await overview();
  for (const zone of zones) {
    const control = await within(hero).findByRole('button', { name: new RegExp(`^${zone} zone details$`, 'i') });
    expect(control.tabIndex).toBeGreaterThanOrEqual(0);
    control.focus();
    expect(document.activeElement).toBe(control);
    fireEvent.click(control);
    const detail = await screen.findByRole('region', { name: new RegExp(`${zone} zone details`, 'i') });
    await waitFor(() => expect(detail.contains(document.activeElement)).toBe(true));
    fireEvent.click(await within(detail).findByRole('button', { name: /close/i }));
    await waitFor(() => expect(detail.isConnected).toBe(false));
    expect(document.activeElement).toBe(control);
    expect(window.location.hash).toBe('#/');
  }
});

it.each(['Enter', ' '])('S58-A02 keyboard %j opens a zone; Escape closes and returns focus', async (key) => {
  const hero = await overview();
  const control = await within(hero).findByRole('button', { name: /North zone details/i });
  control.focus();
  const down = fireEvent.keyDown(control, { key, code: key === ' ' ? 'Space' : 'Enter' });
  const up = fireEvent.keyUp(control, { key, code: key === ' ' ? 'Space' : 'Enter' });
  // jsdom does not synthesize a native button's keyboard click. Supply that
  // browser default only for a real, enabled button whose event wasn't canceled;
  // SVG/ARIA controls must implement their own keyboard activation.
  if (control instanceof HTMLButtonElement && !control.disabled && down && up) fireEvent.click(control);
  const detail = await screen.findByRole('region', { name: /North zone details/i });
  await waitFor(() => expect(detail.contains(document.activeElement)).toBe(true));
  fireEvent.keyDown(document.activeElement!, { key: 'Escape', code: 'Escape' });
  await waitFor(() => expect(detail.isConnected).toBe(false));
  expect(document.activeElement).toBe(control);
  expect(window.location.hash).toBe('#/');
});

it('S58-A03 scored detail uses the lead hour and exposes score, level, confidence and every driver', async () => {
  const detail = await openHouston();
  await waitFor(() => expect(detail.textContent).toMatch(/72\.4\s*%/));
  expect(await within(detail).findByText(/^HIGH$/i)).toBeTruthy();
  expect(detail.textContent).toMatch(/confidence/i);
  expect(detail.textContent).toMatch(/86\s*%|0\.86/);
  for (const driver of lead.drivers) {
    expect(await within(detail).findByText(driver.factor)).toBeTruthy();
    expect(await within(detail).findByText(driver.detail)).toBeTruthy();
    expect(detail.textContent?.replaceAll('−', '-')).toContain(String(driver.contribution));
  }
  expect(within(detail).queryByText(/91\s*%/)).toBeNull();
});

it('S58-A04 detail shows latest zone signals with units, age and stale state', async () => {
  const detail = await openHouston();
  for (const [label, value, age] of [
    [/^(?:SPP|RT(?: SPP| price)?|real.time(?: SPP| price)?|NP6-905-CD)$/i, /38\.42/, /12\s*s|12\s*sec/i],
    [/^(?:day.ahead(?: price)?|DA(?: price)?|NP4-190-CD)$/i, /45\.10?/, /62\s*s|1\s*m|1\s*min/i],
    [/^(?:load forecast|NP3-565-CD)$/i, /21,?340/, /30\s*s|30\s*sec/i],
    [/^(?:outage(?: capacity)?|NP3-233-CD)$/i, /2,?310/, /stale/i],
    [/^(?:NWS(?: alerts)?|weather alerts|NWS-ALERTS)$/i, /\b2\b/, /30\s*s|30\s*sec/i],
  ] as const) {
    const labelElement = await within(detail).findByText(label);
    const row = labelElement.closest('tr, li, article') ?? labelElement.parentElement!;
    await waitFor(() => expect(row.textContent).toMatch(value));
    expect(row.textContent).toMatch(age);
    if (label.source.includes('price') || label.source.includes('SPP')) expect(row.textContent).toMatch(/\$\s*\/\s*MWh/i);
  }
  expect(detail.textContent).not.toContain('60.75');
});

it('S58-A05 detail lists only open FLEX products for its zone with delivery and Market link', async () => {
  const detail = await openHouston();
  for (const product of fixture['/v1/market']) {
    const shown = product.zone === 'LZ_HOUSTON' && product.status === 'open' && product.symbol.startsWith('FLEX-');
    if (shown) {
      const symbol = await within(detail).findByText(product.symbol);
      const row = symbol.closest('tr, li, article') ?? symbol.parentElement!;
      const hour = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Chicago', hour: 'numeric' }).format(new Date(product.delivery_hour));
      expect(row.textContent).toContain(hour);
    } else expect(within(detail).queryByText(product.symbol)).toBeNull();
  }
  expect((await within(detail).findByRole('link', { name: 'Open in Market' })).getAttribute('href')).toBe('#/market');
});

it('S58-A06 unscored LCRA explains coverage, retains signals and marks missing reports', async () => {
  const hero = await overview();
  fireEvent.click(await within(hero).findByRole('button', { name: /LCRA zone details/i }));
  const detail = await screen.findByRole('region', { name: /LCRA zone details/i });
  expect(await within(detail).findByText('Not scored: the model covers the four largest load zones')).toBeTruthy();
  expect(await within(detail).findByText(/51\.25/)).toBeTruthy();
  expect(detail.textContent).toMatch(/\$\s*\/\s*MWh/);
  expect(await within(detail).findAllByText(/not reported/i)).toHaveLength(4);
  expect(detail.textContent).not.toMatch(/72\.4\s*%|91\s*%/);
});

it.each(['empty', 'non-price'])('S58-B01 %s signals hide baseline map scores until price data arrives', async (state) => {
  responses['/v1/signals'] = state === 'empty' ? [] : fixture['/v1/signals'].filter(s => s.report_id !== 'NP6-905-CD' || !s.zone.startsWith('LZ_'));
  const hero = await overview();
  expect(await within(hero).findByText('Waiting for live ERCOT data')).toBeTruthy();
  for (const zone of zones) {
    const control = await within(hero).findByRole('button', { name: new RegExp(`${zone} zone details`, 'i') });
    expect(control.tabIndex).toBeGreaterThanOrEqual(0);
  }
  const map = (await within(hero).findByText(/^NORTH$/i)).closest('svg')!;
  expect(map).not.toBeNull();
  expect(map.textContent?.match(/—/g)).toHaveLength(8);
  expect(map.textContent).not.toMatch(/\d+(?:\.\d+)?\s*%/);
  responses['/v1/signals'] = fixture['/v1/signals'];
  await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
  await waitFor(() => expect(within(hero).queryByText('Waiting for live ERCOT data')).toBeNull());
  await waitFor(() => expect(map.textContent).toMatch(/\d+(?:\.\d+)?\s*%/));
});

it('S58-B02 Highest scarcity and hero hide percentages when ERCOT prices are absent', async () => {
  responses['/v1/signals'] = [];
  const hero = await overview();
  const highest = await stat('Highest scarcity');
  expect(highest.textContent).toContain('—');
  expect(highest.textContent).not.toMatch(/\d+(?:\.\d+)?\s*%/);
  expect(hero.textContent).not.toMatch(/\d+(?:\.\d+)?\s*%/);
});

it('S58-C01 participants show each provider count, including zero', async () => {
  await overview();
  const providers = await stat('Participants by provider');
  for (const provider of fixture['/v1/providers']) {
    await within(providers).findByText(provider.display_name);
    expect(providers.textContent).toMatch(new RegExp(`${provider.display_name}\\s*[:·–-]?\\s*${provider.participants}|${provider.participants}\\s*[:·–-]?\\s*${provider.display_name}`));
  }
  expect(providers.textContent).not.toMatch(/unavailable/i);
});

it('S58-C02 loaded providers without participants show names without invented counts or unavailable', async () => {
  responses['/v1/providers'] = fixture['/v1/providers'].map(({ participants: _count, ...provider }) => provider);
  await overview();
  const providers = await stat('Participants by provider');
  for (const provider of fixture['/v1/providers']) await within(providers).findByText(provider.display_name);
  expect(providers.textContent).not.toMatch(/unavailable|\d/i);
});

it.each(['loaded', 'loading', 'error'] as const)('S58-C03 Active traders %s state uses the non-dormant count or honest placeholder', async (state) => {
  botsState = state;
  await overview();
  const botPanel = await screen.findByRole('region', { name: 'Bots setting the pace' });
  if (state === 'loaded') await within(botPanel).findByRole('link', { name: /bot-0/ });
  if (state === 'error') await within(botPanel).findByText('Bots not yet available');
  const traders = await stat('Active traders');
  await waitFor(() => expect(traders.querySelector('strong')?.textContent).toBe(state === 'loaded' ? '2' : state === 'loading' ? '…' : '—'));
});

it('S58-D01 load-zone table excludes ERCOT ESR and hub rows', async () => {
  await overview();
  const panel = await screen.findByRole('region', { name: 'Across the load zones' });
  await within(panel).findByRole('row', { name: /LCRA/i });
  const names = (await within(panel).findAllByRole('rowheader')).map(row => row.textContent?.trim());
  expect(names).toEqual(expect.arrayContaining(['Houston', 'North', 'LCRA']));
  expect(names).toHaveLength(3);
  expect(names.join(' ')).not.toMatch(/ERCOT|hub/i);
  const esr = await screen.findByRole('region', { name: 'Texas batteries charging now' });
  expect(await within(esr).findByText(/812\.5/)).toBeTruthy();
});
