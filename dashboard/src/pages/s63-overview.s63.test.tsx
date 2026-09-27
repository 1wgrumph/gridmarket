// @vitest-environment jsdom
/* S63-T red tests: UX-01 (home bot values), UX-02 (bounded activity feed,
   compact anomaly status), UX-15 (home arrangement). Fetch is stubbed with
   fixed timestamps; no wall-clock assertions. */
import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Overview from './Overview';

let responses: Record<string, unknown>;

const priceSignal = (zone: string, value: number) => ({
  report_id: 'NP6-905-CD', zone, value, unit: '$/MWh', interval_start: '2026-09-26T15:00:00Z',
  interval_minutes: 5, published_at: '2026-09-26T15:05:00Z', fetched_at: '2026-09-26T15:05:01Z',
  age_s: 12, stale: false,
});

const prediction = (zone: string, score: number) => ({
  zone, delivery_hour: '2026-09-26T18:00:00Z', score, level: 'High', confidence: 0.6,
  expected_value: 12.5, market_price: 10.0,
  drivers: [{ factor: 'price spread', contribution: 4.25, detail: 'Day-ahead above real-time' }],
  disclaimer: 'Simulation estimate, not guaranteed profit.', generated_at: '2026-09-26T15:00:00Z',
});

const activityItem = (id: number) => ({
  id: `evt-${id}`, type: 'fill', label: `bot-${id % 6}`, symbol: 'FLEX-LZ_HOUSTON-18',
  side: id % 2 ? 'buy' : 'sell', quantity: 1, price_cents: 1000 + id, reason: null,
  created_at: `2026-09-26T15:${String(59 - (id % 60)).padStart(2, '0')}:00Z`,
  entry_type: 'fill', subject_id: `trade-${id}`,
});

beforeEach(() => {
  window.location.hash = '#/';
  responses = {
    '/v1/signals': [priceSignal('LZ_HOUSTON', 45.1)],
    '/v1/market/history': [],
    '/v1/market/status': { status: 'open', anomalies: [] },
    '/v1/providers': [{ id: 'base_sim', display_name: 'Base Simulation' }],
    '/v1/predictions': [prediction('LZ_HOUSTON', 46)],
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

describe('S63-T UX-01 home bot leaderboard values', () => {
  it('UX-01 never renders NaN or Infinity; a missing P&L shows an explicit unavailable state', async () => {
    // Live /v1/bots shape: no economy columns (see backend bots_api.list_bots).
    responses['/v1/bots'] = [{ id: 'bot_0', bot_index: 0, bot_type: 'maker', provider_id: 'base_sim', dormant: false }];
    render(<Overview />);
    const panel = await screen.findByRole('region', { name: /bots setting the pace/i });
    await within(panel).findByRole('row', { name: /bot_0/i });
    expect(panel.textContent).not.toMatch(/NaN|Infinity/);
    expect(within(panel).getByText(/unavailable|not available/i)).toBeTruthy();
  });

  it('UX-01 does not rank unknown P&L as if valid: valid bots first, unknown last and marked', async () => {
    responses['/v1/bots'] = [
      { id: 'bot_nopnl', bot_index: 0, bot_type: 'maker', provider_id: 'base_sim', dormant: false },
      { id: 'bot_ok', bot_index: 1, bot_type: 'taker', provider_id: 'base_sim', dormant: false, cash: 1012.5, net_worth: 1012.5, pnl: 12.5, losses: 0 },
    ];
    render(<Overview />);
    const panel = await screen.findByRole('region', { name: /bots setting the pace/i });
    await within(panel).findByRole('row', { name: /bot_ok/i });
    const rows = within(panel).getAllByRole('row').slice(1);
    expect(rows).toHaveLength(2);
    expect(rows[0].textContent).toContain('bot_ok');
    expect(rows[1].textContent).toContain('bot_nopnl');
    expect(rows[1].textContent).toMatch(/unavailable|not available|—/);
    expect(panel.textContent).not.toMatch(/NaN|Infinity/);
  });
});

describe('S63-T UX-02 bounded home activity and compact anomalies', () => {
  it('UX-02 shows the latest 10-15 activity items with a View all link, or a bounded keyboard-scrollable region', async () => {
    responses['/v1/market/activity'] = Array.from({ length: 30 }, (_, i) => activityItem(i + 1));
    render(<Overview />);
    const panel = await screen.findByRole('region', { name: /exchange tape/i });
    expect(await within(panel).findAllByText('bot-1')).not.toHaveLength(0);
    const items = within(panel).getAllByRole('listitem');
    const capped = items.length >= 10 && items.length <= 15
      && within(panel).queryByRole('link', { name: /view all/i }) !== null;
    const log = within(panel).queryByRole('log');
    const scrollable = log !== null && (log as HTMLElement).tabIndex >= 0;
    expect(capped || scrollable).toBe(true);
  });

  it('UX-02 empty anomalies is a compact one-line status', async () => {
    render(<Overview />);
    const panel = await screen.findByRole('region', { name: /market anomalies/i });
    const status = await within(panel).findByRole('status');
    expect(status.textContent).toMatch(/no anomalies/i);
    expect(status.textContent!.length).toBeLessThan(80);
  });
});

describe('S63-T UX-14 home clickability honesty', () => {
  it('UX-14 hero explains the estimate through a Why disclosure', async () => {
    render(<Overview />);
    const hero = await screen.findByRole('region', { name: /next delivery prediction/i });
    await within(hero).findByRole('heading', { name: /houston/i });
    const disclosure = within(hero).queryByRole('button', { name: /why this estimate/i })
      ?? within(hero).queryByText(/why this estimate/i)?.closest('summary');
    expect(disclosure).toBeTruthy();
  });

  it('UX-14 factor chips are disclosure buttons or plain non-bordered tags', async () => {
    render(<Overview />);
    const hero = await screen.findByRole('region', { name: /next delivery prediction/i });
    const chip = await within(hero).findByText('price spread');
    for (const node of [chip, ...Array.from(chip.parentElement?.children ?? [])]) {
      const el = node as HTMLElement;
      if (el.tagName === 'BUTTON') continue;
      expect(el.tagName).not.toBe('A');
      expect(el.getAttribute('title')).toBeNull();
    }
  });

  it('UX-14 chart and order-book panels carry a View market link', async () => {
    render(<Overview />);
    const price = await screen.findByRole('region', { name: /the price of flexibility/i });
    expect(within(price).getByRole('link', { name: /view market/i })).toBeTruthy();
    const book = await screen.findByRole('region', { name: /live order book/i });
    expect(within(book).getByRole('link', { name: /view market/i })).toBeTruthy();
  });

  it('UX-14 a one-sided home book says so and explains the missing spread', async () => {
    responses['/v1/market/FLEX-LZ_HOUSTON-18'] = {
      orders: [{ side: 'buy', price_cents: 4100, quantity: 3 }],
    };
    render(<Overview />);
    const book = await screen.findByRole('region', { name: /live order book/i });
    expect(await within(book).findByText(/no sell orders/i)).toBeTruthy();
    const spread = within(book).getByText(/spread/i).closest('tr')!;
    expect(spread.textContent).toMatch(/unavailable|one-sided|single-sided|missing/i);
  });
});

describe('S63-T UX-15 home arrangement', () => {
  it('UX-15 hero carries one primary View market link and one sandbox action', async () => {
    render(<Overview />);
    const hero = await screen.findByRole('region', { name: /next delivery prediction/i });
    await within(hero).findByRole('heading', { name: /houston/i });
    expect(await within(hero).findAllByRole('link', { name: /view (this )?market/i })).toHaveLength(1);
    expect(await within(hero).findAllByRole('link', { name: /sandbox|try sandbox/i })).toHaveLength(1);
  });

  it('UX-15 unconnected grid metrics group under one pending-data note', async () => {
    responses['/v1/signals'] = [];
    render(<Overview />);
    const hero = await screen.findByRole('region', { name: /next delivery prediction/i });
    const summary = hero.closest('.overview-summary') as HTMLElement;
    await within(summary).findByText(/predicted scarcity/i);
    const notes = summary.textContent!.match(/waiting|pending|unavailable|awaiting/gi) ?? [];
    expect(notes).toHaveLength(1);
  });
});
