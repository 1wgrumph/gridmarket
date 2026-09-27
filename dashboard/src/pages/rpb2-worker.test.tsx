// @vitest-environment jsdom
/* RP-B2 stretch repair (DEC-GM-147): FLOW-027 / UX F4 worker health check landing.
   Red before the fix. Asserts that the worker health check from /v1/router links
   to #/providers?provider=worker, that Providers renders a 'Data worker (ERCOT)'
   entry with id="provider-worker" stating current health from real dashboard data
   ('Waiting for ERCOT' / 'not configured' when absent; router check probability and band),
   and that existing provider behaviour is preserved. */
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
// @ts-ignore TS2732: Vitest loads JSON; the frozen tsconfig omits resolveJsonModule.
import providerFixture from '../fixtures/providers.json';
import App from '../App';

type Responses = Record<string, unknown>;

describe('RP-B2 FLOW-027: Worker health check landing on Providers (DEC-GM-147)', () => {
  let fetchMock: Mock;
  let responses: Responses;

  beforeEach(() => {
    responses = structuredClone(providerFixture) as Responses;
    responses['/v1/predictions'] = [
      {
        zone: 'LZ_HOUSTON',
        delivery_hour: '2026-09-27T00:00:00Z',
        score: 42,
        level: 'LOW',
        confidence: 0.85,
        expected_value: 0.15,
        market_price: 35.5,
        drivers: [{ factor: 'temperature', contribution: 0.1, detail: 'mild' }],
        disclaimer: 'Simulated heuristic',
        generated_at: '2026-09-26T12:00:00Z',
      },
    ];
    responses['/v1/signals'] = [];
    responses['/v1/market/status'] = { status: 'open', anomalies: [] };

    fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input).split('?')[0];
      const body = responses[path];
      if (body !== undefined) {
        return { ok: true, status: 200, json: async () => body };
      }
      return { ok: false, status: 404, json: async () => ({ error: { code: 'NOT_FOUND', message: path } }) };
    });
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    window.location.hash = '';
  });

  it('FLOW-027a: Predictions worker health check links to #/providers?provider=worker', async () => {
    window.location.hash = '#/predictions';
    render(<App />);

    const workerLink = await screen.findByRole('link', { name: 'worker' });
    expect(workerLink).toBeTruthy();
    const href = workerLink.getAttribute('href') ?? '';
    expect(href).toMatch(/^#\/providers\?.*provider=worker/);
  });

  it('FLOW-027b: Providers renders Data worker (ERCOT) with id="provider-worker"', async () => {
    window.location.hash = '#/providers?provider=worker';
    render(<App />);

    const workerCard = await screen.findByRole('heading', { name: 'Data worker (ERCOT)' });
    const article = workerCard.closest('article');
    expect(article).toBeTruthy();
    expect(article?.id).toBe('provider-worker');
  });

  it('FLOW-027c: Data worker entry states router check probability, band, and baseline rules', async () => {
    window.location.hash = '#/providers?provider=worker';
    render(<App />);

    const heading = await screen.findByRole('heading', { name: 'Data worker (ERCOT)' });
    const article = heading.closest('article')!;
    const card = within(article);

    // From providers.json router check for worker: probability 0.03 (3%), band 'log', baseline true
    expect(card.getByText(/3\s*%/)).toBeTruthy();
    expect(card.getByText(/\blog\b/i)).toBeTruthy();
    expect(card.getByText(/baseline rules/i)).toBeTruthy();
  });

  it('FLOW-027d: Data worker entry shows Waiting for ERCOT and not configured when signals are absent', async () => {
    responses['/v1/signals'] = [];
    window.location.hash = '#/providers?provider=worker';
    render(<App />);

    const heading = await screen.findByRole('heading', { name: 'Data worker (ERCOT)' });
    const article = heading.closest('article')!;
    const card = within(article);

    expect(card.getAllByText(/waiting for ercot/i).length).toBeGreaterThanOrEqual(1);
    expect(card.getAllByText(/not configured/i).length).toBeGreaterThanOrEqual(1);
  });

  it('FLOW-027e: Data worker entry shows Online and freshness when signals are present, preserving provider cards', async () => {
    const fixedNow = new Date('2026-09-26T13:00:00Z').getTime();
    vi.spyOn(Date, 'now').mockReturnValue(fixedNow);

    responses['/v1/signals'] = [
      {
        report_id: 'ESR',
        zone: 'LZ_HOUSTON',
        value: 120,
        unit: 'MW',
        interval_start: '2026-09-26T12:45:00Z',
        interval_minutes: 15,
        published_at: '2026-09-26T12:59:50Z',
        fetched_at: '2026-09-26T12:59:50Z',
        age_s: 10,
        stale: false,
      },
    ];
    window.location.hash = '#/providers?provider=worker';
    render(<App />);

    const heading = await screen.findByRole('heading', { name: 'Data worker (ERCOT)' });
    const article = heading.closest('article')!;
    const card = within(article);

    expect(card.getAllByText(/online/i).length).toBeGreaterThanOrEqual(1);
    expect(card.getByText(/10\s*s/)).toBeTruthy();

    // Verify existing provider cards remain intact
    expect(screen.getByRole('heading', { name: 'Base Simulation' })).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'LoneStar Storage' })).toBeTruthy();
  });
});
