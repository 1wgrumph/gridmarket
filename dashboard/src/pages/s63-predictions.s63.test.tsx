// @vitest-environment jsdom
/* S63-T red tests: UX-07 (forecast count label), UX-08 (compact prediction
   browsing), UX-11 (one score definition). Fetch is stubbed with fixed
   timestamps; no wall-clock assertions. */
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Predictions from './Predictions';

let responses: Record<string, unknown>;

const ZONES = ['LZ_HOUSTON', 'LZ_NORTH', 'LZ_SOUTH', 'LZ_WEST'];

const prediction = (zone: string, hour: number, score: number) => ({
  zone, delivery_hour: `2026-09-26T${String(hour).padStart(2, '0')}:00:00Z`, score,
  level: 'High', confidence: 0.6, expected_value: 12.5, market_price: 10.0,
  drivers: [
    { factor: 'price spread', contribution: 4.25, detail: 'Day-ahead above real-time' },
    { factor: 'load pressure', contribution: -1.5, detail: 'Load near forecast' },
  ],
  disclaimer: 'Simulation estimate, not guaranteed profit.', generated_at: '2026-09-26T15:00:00Z',
});

const fullPredictions = () => ZONES.flatMap(zone =>
  Array.from({ length: 26 }, (_, h) => prediction(zone, h, 40 + ((h * 7) % 20))));

beforeEach(() => {
  responses = {
    '/v1/predictions': fullPredictions(),
    '/v1/router': { checks: [], brier: {}, jev_enabled: false },
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
});

async function scoresPanel() {
  render(<Predictions />);
  const panel = await screen.findByRole('region', { name: /zone scores/i });
  await within(panel).findByText(/simulation estimate/i);
  return panel;
}

describe('S63-T UX-07 forecast count label', () => {
  it('UX-07 labels the count as forecasts across zones, not zones', async () => {
    const panel = await scoresPanel();
    expect(panel.textContent).toMatch(/104 forecasts across 4 zones/i);
    expect(panel.textContent).not.toMatch(/104\s+zones/i);
  });
});

describe('S63-T UX-08 compact prediction browsing', () => {
  it('UX-08 starts with a zone selector, a delivery-window selector and a compact overview', async () => {
    const panel = await scoresPanel();
    expect(screen.getByRole('combobox', { name: /zone/i })).toBeTruthy();
    expect(screen.getByRole('combobox', { name: /delivery|window/i })).toBeTruthy();
    expect(within(panel).getAllByRole('article').length).toBeLessThanOrEqual(12);
  });

  it('UX-08 factor details open on demand for one selected forecast; the full set stays reachable', async () => {
    const panel = await scoresPanel();
    expect(within(panel).queryAllByText('price spread')).toHaveLength(0);
    const disclosures = within(panel).getAllByRole('button', { expanded: false });
    expect(disclosures.length).toBeGreaterThan(0);
    fireEvent.click(disclosures[0]);
    expect(disclosures[0].getAttribute('aria-expanded')).toBe('true');
    expect(await within(panel).findAllByText('price spread')).toHaveLength(1);
    expect(
      within(panel).queryByRole('button', { name: /show all|all forecasts/i })
      ?? within(panel).queryByRole('link', { name: /show all|all forecasts|view all/i }),
    ).not.toBeNull();
  });
});

describe('S63-T UX-11 one score definition', () => {
  it('UX-11 prediction scores carry the same percent unit as Home scarcity', async () => {
    responses['/v1/predictions'] = [prediction('LZ_HOUSTON', 18, 46)];
    const panel = await scoresPanel();
    expect(await within(panel).findByText(/46\s*%/)).toBeTruthy();
  });
});
