// @vitest-environment jsdom
/* S63-T red tests: UX-10 (zone map honesty), UX-11 (feed vs simulation
   status, estimate labelling), UX-12 (exchange summaries on Home). Fetch is
   stubbed with fixed timestamps; no wall-clock assertions. */
import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../App';
import Overview from './Overview';

let responses: Record<string, unknown>;

const ZONES = ['LZ_HOUSTON', 'LZ_NORTH', 'LZ_SOUTH', 'LZ_WEST'];

const priceSignal = (zone: string) => ({
  report_id: 'NP6-905-CD', zone, value: 45.1, unit: '$/MWh', interval_start: '2026-09-26T15:00:00Z',
  interval_minutes: 5, published_at: '2026-09-26T15:05:00Z', fetched_at: '2026-09-26T15:05:01Z',
  age_s: 12, stale: false,
});

const prediction = (zone: string, hour: number, score: number, drivers = true) => ({
  zone, delivery_hour: `2026-09-26T${String(hour).padStart(2, '0')}:00:00Z`, score,
  level: 'High', confidence: 0.6, expected_value: 12.5, market_price: 10.0,
  drivers: drivers ? [{ factor: 'price spread', contribution: 4.25, detail: 'Day-ahead above real-time' }] : [],
  disclaimer: 'Simulation estimate, not guaranteed profit.', generated_at: '2026-09-26T15:00:00Z',
});

const fullPredictions = () => ZONES.flatMap(zone =>
  Array.from({ length: 26 }, (_, h) => prediction(zone, h, 40 + ((h * 7) % 20))));

beforeEach(() => {
  window.location.hash = '#/';
  responses = {
    '/v1/signals': ZONES.map(priceSignal),
    '/v1/market/history': [],
    '/v1/market/status': { status: 'open', anomalies: [] },
    '/v1/providers': [{ id: 'base_sim', display_name: 'Base Simulation' }],
    '/v1/predictions': [prediction('LZ_HOUSTON', 18, 46)],
    '/v1/market': [{ id: 'p1', symbol: 'FLEX-LZ_HOUSTON-18', zone: 'LZ_HOUSTON', delivery_hour: '2026-09-26T18:00:00Z', status: 'open' }],
    '/v1/market/FLEX-LZ_HOUSTON-18': { orders: [] },
    '/v1/bots': [],
    '/v1/market/activity': [],
  };
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const path = new URL(String(input), 'http://localhost').pathname;
    const body = responses[path];
    return {
      ok: body !== undefined, status: body === undefined ? 404 : 200,
      json: async () => body ?? { error: { code: 'NOT_FOUND', message: 'Not found' } },
    };
  }));
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.location.hash = '';
});

describe('S63-T UX-10 zone map honesty', () => {
  it('UX-10 describes each displayed zone once for the selected window, not once per forecast', async () => {
    responses['/v1/predictions'] = fullPredictions();
    render(<Overview />);
    const map = await screen.findByRole('img', { name: /schematic ercot load zones/i });
    const label = map.getAttribute('aria-label')!;
    expect(label.length).toBeLessThan(1000);
    for (const zone of ['HOUSTON', 'NORTH', 'SOUTH', 'WEST']) {
      expect(label.match(new RegExp(zone, 'g')) ?? []).toHaveLength(1);
    }
  });

  it('UX-10 map has a legend for its fill scale and the selected delivery window', async () => {
    responses['/v1/predictions'] = fullPredictions();
    render(<Overview />);
    const hero = await screen.findByRole('region', { name: /next delivery prediction/i });
    const mapPanel = hero.querySelector('.map-panel') as HTMLElement;
    expect(within(mapPanel).getByText(/legend|fill scale|scarcity scale/i)).toBeTruthy();
    expect(mapPanel.textContent).toMatch(/delivery|window|hour/i);
  });

  it('UX-10 non-market-zone labels (LCRA, AEN, CPS, RAYBN) are explained or removed', async () => {
    render(<Overview />);
    const hero = await screen.findByRole('region', { name: /next delivery prediction/i });
    const mapPanel = hero.querySelector('.map-panel') as HTMLElement;
    for (const name of ['LCRA', 'AEN', 'CPS', 'RAYBN']) {
      const node = within(mapPanel).queryByText(name);
      if (!node) continue; // removed is acceptable
      const group = node.closest('g');
      const documented = group?.querySelector('title, desc');
      const describedBy = group?.getAttribute('aria-describedby');
      const described = describedBy ? document.getElementById(describedBy) : null;
      const legendEntry = within(mapPanel).queryByText(new RegExp(`${name}.*(utility|region|market|scored|not)`, 'i'));
      expect(documented ?? described ?? legendEntry).not.toBeNull();
    }
  });

  it('UX-10 zones are selectable from an equivalent list as well as the map', async () => {
    render(<Overview />);
    await screen.findByRole('region', { name: /next delivery prediction/i });
    const list = screen.queryByRole('listbox', { name: /zone/i })
      ?? screen.queryByRole('radiogroup', { name: /zone/i });
    expect(list).not.toBeNull();
    const options = within(list as HTMLElement).queryAllByRole('option');
    const radios = within(list as HTMLElement).queryAllByRole('radio');
    expect(options.length + radios.length).toBe(4);
  });
});

describe('S63-T UX-11 feed and simulation status honesty', () => {
  it('UX-11 unconnected ERCOT feed shows its real state with a neutral or warning colour', async () => {
    responses['/v1/signals'] = [];
    render(<App />);
    const sidebar = await screen.findByRole('complementary');
    const freshness = within(sidebar).getByText(/ercot feed not connected|awaiting first update/i);
    const dot = freshness.closest('.freshness')!.querySelector('.status-dot')!;
    expect(dot.className).not.toBe('status-dot');
  });

  it('UX-11 simulation status is separate from grid-feed status', async () => {
    render(<Overview />);
    await screen.findByRole('region', { name: /next delivery prediction/i });
    expect(document.body.textContent).toMatch(/simulation (running|live|ok)/i);
    expect(document.body.textContent).toMatch(/(grid|ercot) feed (pending|connected|live|ok)/i);
  });

  it('UX-11 values from incomplete inputs are labelled simulation estimates with incomplete inputs', async () => {
    // Prices served but no weather inputs: the confident-looking score is a default estimate.
    render(<Overview />);
    const hero = await screen.findByRole('region', { name: /next delivery prediction/i });
    await within(hero).findByRole('heading', { name: /houston/i });
    expect(hero.textContent).toMatch(/incomplete inputs/i);
  });

  it('UX-11 missing factor inputs are named as missing, never rendered as measured zeros', async () => {
    responses['/v1/predictions'] = [prediction('LZ_HOUSTON', 18, 46, false)];
    render(<Overview />);
    const hero = await screen.findByRole('region', { name: /next delivery prediction/i });
    await within(hero).findByRole('heading', { name: /houston/i });
    expect(hero.textContent).toMatch(/missing|not reported/i);
  });
});

describe('S63-T UX-12 exchange summaries on Home', () => {
  it('UX-12 strip shows exchange open interest, active traders and per-provider participants', async () => {
    responses['/v1/market/status'] = { status: 'open', anomalies: [], open_interest: 137, active_traders: 41 };
    responses['/v1/providers'] = [
      { id: 'base_sim', display_name: 'Base Simulation', participants: 3 },
      { id: 'lonestar', display_name: 'LoneStar', participants: 7 },
    ];
    delete responses['/v1/bots']; // exchange figures must not depend on the bots feed
    render(<Overview />);
    const strip = await screen.findByRole('region', { name: /market key numbers/i });
    const interest = within(strip).getByText(/open interest/i).closest('div')!;
    expect(interest.textContent).toContain('137');
    const traders = within(strip).getByText(/active traders/i).closest('div')!;
    expect(traders.textContent).toContain('41');
    const participants = within(strip).getByText(/participants by provider/i).closest('div')!;
    expect(participants.textContent).toContain('3');
    expect(participants.textContent).toContain('7');
  });

  it('UX-12 a measured zero renders as zero, distinct from unavailable', async () => {
    responses['/v1/market/status'] = { status: 'open', anomalies: [], open_interest: 0, active_traders: 0 };
    delete responses['/v1/bots'];
    render(<Overview />);
    const strip = await screen.findByRole('region', { name: /market key numbers/i });
    const interest = within(strip).getByText(/open interest/i).closest('div')!;
    expect(interest.textContent).toMatch(/\b0\b/);
    expect(interest.textContent).not.toMatch(/—|unavailable/i);
  });
});
