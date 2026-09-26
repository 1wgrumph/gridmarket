// @vitest-environment jsdom
/* S63-T red tests: UX-06 (book beside selection), UX-14 (honest market
   controls, one-sided books), UX-16 (market filters, readable times, bounded
   browsing). Fetch is stubbed with fixed timestamps; no wall-clock assertions. */
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Market from './Market';

let responses: Record<string, unknown>;

const product = (id: string, symbol: string, zone: string, hour: string) => ({
  id, symbol, zone, delivery_hour: `2026-09-26T${hour}:00:00Z`, status: 'open',
});

const detail = (id: string, symbol: string, zone: string, orders: unknown[]) => ({
  id, symbol, zone, delivery_hour: '2026-09-26T18:00:00Z', status: 'open', orders,
});

const PRODUCTS = [
  product('p1', 'FLEX-LZ_HOUSTON-2026092618', 'LZ_HOUSTON', '18'),
  product('p2', 'SPOT-LZ_NORTH-2026092618', 'LZ_NORTH', '18'),
  product('p3', 'FLEX-LZ_SOUTH-2026092619', 'LZ_SOUTH', '19'),
];

beforeEach(() => {
  responses = {
    '/v1/market': PRODUCTS,
    '/v1/market/FLEX-LZ_HOUSTON-2026092618': detail('p1', 'FLEX-LZ_HOUSTON-2026092618', 'LZ_HOUSTON', [
      { side: 'sell', price_cents: 4300, quantity: 2 },
      { side: 'buy', price_cents: 4100, quantity: 3 },
    ]),
    '/v1/market/SPOT-LZ_NORTH-2026092618': detail('p2', 'SPOT-LZ_NORTH-2026092618', 'LZ_NORTH', [
      { side: 'sell', price_cents: 4400, quantity: 1 },
    ]),
    '/v1/market/FLEX-LZ_SOUTH-2026092619': detail('p3', 'FLEX-LZ_SOUTH-2026092619', 'LZ_SOUTH', [
      { side: 'buy', price_cents: 4000, quantity: 5 },
    ]),
  };
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input), 'http://localhost');
    const body = responses[url.pathname + url.search] ?? responses[url.pathname];
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

async function productsPanel() {
  // Board replaces the loading Products panel once data lands; re-query after.
  await screen.findByRole('region', { name: 'Products' });
  await waitFor(() => {
    const ready = screen.getAllByRole('region', { name: 'Products' })
      .some(panel => panel.getAttribute('aria-busy') !== 'true');
    expect(ready).toBe(true);
  });
  return screen.getAllByRole('region', { name: 'Products' })
    .find(panel => panel.getAttribute('aria-busy') !== 'true')!;
}

describe('S63-T UX-06 selected product and book visible together', () => {
  it('UX-06 choosing a book moves focus to the book result', async () => {
    render(<Market />);
    const panel = await productsPanel();
    await within(panel).findByText('FLEX-LZ_HOUSTON-2026092618');
    const show = within(panel).getAllByRole('button', { name: /show book/i })[0];
    fireEvent.click(show);
    const book = await screen.findByRole('region', { name: /book depth/i });
    await waitFor(() => expect(book.contains(document.activeElement)).toBe(true));
  });

  it('UX-06 book result names the selected product', async () => {
    render(<Market />);
    const panel = await productsPanel();
    await within(panel).findByText('FLEX-LZ_HOUSTON-2026092618');
    const show = within(panel).getAllByRole('button', { name: /show book/i })[0];
    fireEvent.click(show);
    const book = await screen.findByRole('region', { name: /SPOT-LZ_NORTH-2026092618/ });
    expect(book.textContent).toContain('LZ_NORTH');
  });
});

describe('S63-T UX-14 honest market controls and one-sided books', () => {
  it('UX-14 product symbols are real detail links or lose link styling', async () => {
    render(<Market />);
    const panel = await productsPanel();
    await within(panel).findByText('FLEX-LZ_HOUSTON-2026092618');
    for (const symbol of ['FLEX-LZ_HOUSTON-2026092618', 'SPOT-LZ_NORTH-2026092618']) {
      const node = within(panel).getByText(symbol);
      const link = node.closest('a');
      expect(link ?? !node.classList.contains('code')).toBeTruthy();
    }
  });

  it('UX-14 one-sided books say so and explain why the spread is unavailable', async () => {
    render(<Market />);
    const panel = await productsPanel();
    await within(panel).findByText('FLEX-LZ_HOUSTON-2026092618');
    // p2 (SPOT-LZ_NORTH) has asks and no bids.
    const show = within(panel).getAllByRole('button', { name: /show book/i })[0];
    fireEvent.click(show);
    const book = await screen.findByRole('region', { name: /book depth/i });
    expect(await within(book).findByText(/no bids/i)).toBeTruthy();
    const spread = within(book).getByText(/spread/i).closest('div, p, li, td, section')!;
    expect(spread.textContent).toMatch(/spread/i);
    expect(spread.textContent).toMatch(/unavailable|one-sided|single-sided|missing/i);
  });
});

describe('S63-T UX-16 market browsing', () => {
  it('UX-16 offers zone, delivery-window and product-type filters', async () => {
    render(<Market />);
    await productsPanel();
    expect(screen.getByRole('combobox', { name: /zone/i })).toBeTruthy();
    expect(screen.getByRole('combobox', { name: /delivery|window/i })).toBeTruthy();
    expect(screen.getByRole('combobox', { name: /product type|type/i })).toBeTruthy();
  });

  it('UX-16 filters narrow the product list', async () => {
    render(<Market />);
    const panel = await productsPanel();
    await within(panel).findByText('FLEX-LZ_HOUSTON-2026092618');
    fireEvent.change(screen.getByRole('combobox', { name: /zone/i }), { target: { value: 'LZ_NORTH' } });
    await waitFor(() => {
      expect(within(panel).queryByText('FLEX-LZ_HOUSTON-2026092618')).toBeNull();
      expect(within(panel).getByText('SPOT-LZ_NORTH-2026092618')).toBeTruthy();
    });
  });

  it('UX-16 delivery times read as Central Time first, raw UTC as secondary detail', async () => {
    render(<Market />);
    const panel = await productsPanel();
    const row = await within(panel).findByRole('row', { name: /FLEX-LZ_HOUSTON/i });
    const time = within(row).getByRole('time');
    expect(time.textContent).toMatch(/CT|CDT|CST/);
    expect(`${time.getAttribute('title')} ${time.closest('td')!.textContent}`).toMatch(/Z\b|UTC/);
  });

  it('UX-16 product browsing is bounded with a way to reach more', async () => {
    const many = Array.from({ length: 60 }, (_, i) =>
      product(`px${i}`, `FLEX-LZ_HOUSTON-202609${String(26 + Math.floor(i / 24)).padStart(2, '0')}${String(i % 24).padStart(2, '0')}`, 'LZ_HOUSTON', '18'));
    responses['/v1/market'] = many;
    responses['/v1/market/FLEX-LZ_HOUSTON-2026092600'] = detail('px0', many[0].symbol, 'LZ_HOUSTON', []);
    render(<Market />);
    const panel = await productsPanel();
    await within(panel).findByText(many[0].symbol);
    const rows = within(panel).getAllByRole('row').slice(1);
    expect(rows.length).toBeLessThan(60);
    expect(
      within(panel).queryByRole('button', { name: /more|next|show all/i })
      ?? screen.queryByRole('navigation', { name: /product pages|pagination/i }),
    ).not.toBeNull();
  });
});
