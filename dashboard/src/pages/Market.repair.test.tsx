// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import Market from './Market';

// Recorded from GET /v1/market/{symbol} (backend market.py `detail`): product row plus `orders`,
// open depth aggregated by side and price, ascending by price. No `book`, no `recent_trades`.
const product = { id: 'product-1', symbol: 'NORTH-20260926-14', zone: 'NORTH', delivery_hour: '2026-09-26T14:00:00Z', status: 'open' };
const liveDetail = {
  ...product,
  orders: [
    { side: 'buy', price_cents: 4000, quantity: 5 },
    { side: 'buy', price_cents: 4100, quantity: 3 },
    { side: 'sell', price_cents: 4300, quantity: 2 },
  ],
};
const trade = { id: 'trade-7', product_id: 'product-1', buy_order_id: 'b', sell_order_id: 's', quantity: 1, price_cents: 4200, created_at: '2026-09-26T13:01:00Z' };

let responses: Record<string, unknown>;

beforeEach(() => {
  responses = { '/v1/market': [product], '/v1/market/history?product_id=product-1': [trade] };
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const body = responses[String(input)];
    return { ok: body !== undefined, status: body === undefined ? 404 : 200, json: async () => body ?? { error: { code: 'NOT_FOUND', message: 'Not found' } } };
  }));
});

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('Market repair S51-repair', () => {
  it('renders the live /v1/market/{symbol} shape: orders split into bids and asks, trades from history', async () => {
    responses['/v1/market/NORTH-20260926-14'] = liveDetail;
    render(<Market />);
    expect(await screen.findByText('3 @ $41.00')).toBeTruthy();
    expect(screen.getByText('2 @ $43.00')).toBeTruthy();
    expect(await screen.findByText('1 @ $42.00')).toBeTruthy();
    const bids = screen.getAllByText(/@ \$4[01]\.00/).map(n => n.textContent);
    expect(bids).toEqual(['3 @ $41.00', '5 @ $40.00']);
  });

  it('renders an empty book instead of crashing when the detail has neither orders nor book', async () => {
    responses['/v1/market/NORTH-20260926-14'] = product;
    delete responses['/v1/market/history?product_id=product-1'];
    render(<Market />);
    expect(await screen.findByText('Book depth')).toBeTruthy();
    expect(screen.getAllByText('—')).toHaveLength(2);
    expect(screen.queryByText(/failed to render/)).toBeNull();
  });

  it('contains a render error inside the page boundary', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    responses['/v1/market/NORTH-20260926-14'] = liveDetail;
    responses['/v1/market/history?product_id=product-1'] = [{ id: 'bad', quantity: 1, price_cents: 1 }];
    render(<Market />);
    expect((await screen.findByRole('alert')).textContent).toMatch(/Market view failed to render/);
  });
});
