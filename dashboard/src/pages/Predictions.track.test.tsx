// @vitest-environment jsdom
/* X3 red tests: Forecast track record on Predictions. Fetch is stubbed with
   fixed timestamps; no wall-clock assertions. */
import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Predictions from './Predictions';

let responses: Record<string, unknown>;

const event = (zone: string, day: string, probability: number, outcome: boolean) => ({
  subject: `${zone}:2026-09-${day}T14:00:00+00:00`,
  zone,
  delivery_hour: `2026-09-${day}T14:00:00+00:00`,
  probability,
  outcome,
  brier: (probability - (outcome ? 1 : 0)) ** 2,
  resolves_at: `2026-09-${day}T15:00:00+00:00`,
});

const thinHistory = () => ({
  events: [
    event('LZ_HOUSTON', '20', 0.8, true),
    event('LZ_NORTH', '21', 0.2, false),
  ],
  count: 2,
  limit: 50,
});

const richHistory = () => {
  // 20 resolved events: bin 60-80% holds 6 forecasts, 4 of which happened.
  const events = [
    ...Array.from({ length: 6 }, (_, i) =>
      event('LZ_HOUSTON', String(10 + i).padStart(2, '0'), 0.7, i < 4)),
    ...Array.from({ length: 14 }, (_, i) =>
      event('LZ_NORTH', String(10 + i).padStart(2, '0'), 0.3, i < 4)),
  ];
  return { events, count: 20, limit: 50 };
};

const richRouter = () => ({
  checks: [],
  brier: {},
  brier_events: Object.fromEntries(
    richHistory().events.map(e => [e.subject, e.brier])),
  brier_mean: 0.2,
  jev_enabled: false,
});

beforeEach(() => {
  responses = {
    '/v1/predictions': [],
    '/v1/signals': [],
    '/v1/router': { checks: [], brier: {}, jev_enabled: false },
    '/v1/router/history': thinHistory(),
  };
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const path = new URL(String(input), 'http://localhost').pathname
      + new URL(String(input), 'http://localhost').search;
    const key = Object.keys(responses).find(k => path === k || path.startsWith(k + '?')) ?? path;
    const body = responses[key];
    return {
      ok: body !== undefined, status: body === undefined ? 404 : 200,
      headers: { get: () => null },
      json: async () => body ?? { error: { code: 'NOT_FOUND', message: 'Not found' } },
    };
  }));
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function trackPanel() {
  render(<Predictions />);
  return await screen.findByRole('region', { name: /forecast track record/i });
}

describe('X3 forecast track record', () => {
  it('shows an honest empty state when fewer than 20 forecasts resolved', async () => {
    const panel = await trackPanel();
    expect(await within(panel).findByText(/not enough resolved forecasts yet: 2 of 20/i))
      .toBeTruthy();
  });

  it('shows aggregate Brier and sample counts once 20 resolve', async () => {
    responses['/v1/router/history'] = richHistory();
    responses['/v1/router'] = richRouter();
    const panel = await trackPanel();
    // XR-B (DEC-GM-152): the headline is the mean of the 20 listed events (4.2 / 20), not /v1/router brier_mean.
    expect(await within(panel).findByText(/aggregate brier 0\.21/i)).toBeTruthy();
    expect(within(panel).getByText(/the 20 resolved events listed/i)).toBeTruthy();
  });

  it('shows calibration bins with observed frequency and event-level predicted vs happened', async () => {
    responses['/v1/router/history'] = richHistory();
    responses['/v1/router'] = richRouter();
    const panel = await trackPanel();
    const bins = await within(panel).findByRole('table', { name: /calibration/i });
    // 60-80% bin: 6 forecasts, 4 happened -> observed 67%.
    expect(within(bins).getByText(/60[–-]80%/)).toBeTruthy();
    expect(within(bins).getByText(/observed 67%.*n=6|n=6.*observed 67%/i)).toBeTruthy();
    const events = await within(panel).findByRole('table', { name: /resolved events/i });
    const rows = within(events).getAllByRole('row');
    expect(rows.length).toBeGreaterThan(5);
    expect(within(rows[1]).getByText('70%')).toBeTruthy();
    expect(within(rows[1]).getByText(/yes|happened/i)).toBeTruthy();
  });
});
