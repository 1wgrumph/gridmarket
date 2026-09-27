// @vitest-environment jsdom
/* S63-T red tests: UX-03 price-chart ticks. Chart ticks need measured layout:
   ResizeObserver and getBoundingClientRect are stubbed to a fixed 600x300
   (S59 pattern). Fixed timestamps; no wall-clock assertions. */
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Overview from '../pages/Overview';

let responses: Record<string, unknown>;
let originalRect: typeof Element.prototype.getBoundingClientRect;

const BASE = Date.parse('2026-09-26T10:00:00Z');

beforeEach(() => {
  window.location.hash = '#/';
  responses = {
    '/v1/signals': [],
    '/v1/market/history': [],
    '/v1/market/status': { status: 'open', anomalies: [] },
    '/v1/providers': [],
    '/v1/predictions': [],
    '/v1/market': [],
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

async function pricePanel() {
  const panel = await screen.findByRole('region', { name: /the price of flexibility/i });
  await waitFor(() => expect(panel.getAttribute('aria-busy')).toBe('false'));
  return panel;
}

describe('S63-T UX-03 price-chart ticks', () => {
  // Tick counts (6 at 1280, 4 at 390), no accumulation across polls and no
  // overlap need a real layout engine: jsdom renders at most 6 stable ticks
  // for 100 trades with working hover/keyboard tooltips, so those clauses are
  // browser-verified items for the implementer (see the S63-T report).
  it('UX-03 a flat series is explained, never faked', async () => {
    responses['/v1/market/history'] = Array.from({ length: 20 }, (_, i) => ({
      id: `t${i}`, product_id: 'p1', buy_order_id: 'b', sell_order_id: 's',
      quantity: 1, price_cents: 1000, created_at: new Date(BASE + i * 60_000).toISOString(),
    }));
    render(<Overview />);
    const panel = await pricePanel();
    expect(await within(panel).findByText(/price unchanged since \d{2}:\d{2}(:\d{2})? CT/i)).toBeTruthy();
  });

});
