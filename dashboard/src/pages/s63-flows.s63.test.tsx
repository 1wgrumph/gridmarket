// @vitest-environment jsdom
/* S63-T red tests: UX-04 (Spec honesty), UX-13 (Providers content), UX-18
   (sandbox key flow), UX-19 (orders table). Fetch is stubbed with fixed
   data; no wall-clock assertions. */
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Providers from './Providers';
import Sandbox from './Sandbox';
import Spec from './Spec';

type Stub = { status: number; headers?: Record<string, string>; body: unknown };
let responses: Record<string, unknown>;

const PRODUCT = { id: 'prod-1', symbol: 'FLEX-LZ_HOUSTON-2026092618', zone: 'LZ_HOUSTON', delivery_hour: '2026-09-26T18:00:00Z', status: 'open' };
const KEY = { account_id: 'acct-1', api_key: 'gm_test_key_abcdef123456', label: 'Judge' };

function stubFetch() {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), 'http://localhost');
    const method = (init?.method ?? 'GET').toUpperCase();
    const body = responses[`${method} ${url.pathname}`] ?? responses[url.pathname] as Stub | unknown;
    if (body !== undefined && typeof body === 'object' && body !== null && 'status' in body) {
      const stub = body as Stub;
      return {
        ok: stub.status >= 200 && stub.status < 300, status: stub.status,
        headers: new Headers(stub.headers ?? {}),
        json: async () => stub.body,
        text: async () => (typeof stub.body === 'string' ? stub.body : JSON.stringify(stub.body)),
      };
    }
    return {
      ok: body !== undefined, status: body === undefined ? 404 : 200,
      headers: new Headers(),
      json: async () => body ?? { error: { code: 'NOT_FOUND', message: 'Not found' } },
      text: async () => '',
    };
  });
}

beforeEach(() => {
  responses = {};
  vi.stubGlobal('fetch', stubFetch());
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('S63-T UX-04 Spec honesty', () => {
  it('UX-04 shows an honest pre-release state with in-app links, never a dead outbound link', async () => {
    render(<Spec />);
    expect(screen.queryByRole('link', { name: /github/i })).toBeNull();
    expect(screen.getByText(/published with the final release/i)).toBeTruthy();
    expect(screen.getByRole('link', { name: /sandbox/i }).getAttribute('href')).toBe('#/sandbox');
    expect(screen.getByRole('link', { name: /api docs|documentation|sdk/i })).toBeTruthy();
  });
});

describe('S63-T UX-13 Providers content', () => {
  it('UX-13 shows real provider information from the exchange', async () => {
    responses['/v1/providers'] = [
      { id: 'base_sim', display_name: 'Base Simulation', online: true, participants: 3 },
    ];
    render(<Providers />);
    expect(await screen.findByText('Base Simulation')).toBeTruthy();
    expect(screen.getByText(/3|online|participants/i)).toBeTruthy();
  });

  it('UX-13 unconnected health gets an intentional setup state with a next action', async () => {
    responses['/v1/providers'] = [{ id: 'base_sim', display_name: 'Base Simulation' }];
    render(<Providers />);
    await screen.findByText('Base Simulation');
    expect(screen.getByText(/setup|not connected|coming soon/i)).toBeTruthy();
    expect(screen.queryByRole('link') ?? screen.queryByRole('button')).not.toBeNull();
  });
});

describe('S63-T UX-18 sandbox key flow', () => {
  async function keyPanel() {
    render(<Sandbox />);
    return screen.findByRole('region', { name: /get a key/i });
  }

  it('UX-18 rate-limit errors sit beside key creation with the retry time the API gives', async () => {
    responses['POST /v1/sandbox/keys'] = {
      status: 429, headers: { 'Retry-After': '600' },
      body: { error: { code: 'RATE_LIMITED', message: 'Three sandbox keys per hour' } },
    };
    const panel = await keyPanel();
    fireEvent.click(within(panel).getByRole('button', { name: /get a sandbox key/i }));
    const error = await within(panel).findByRole('alert');
    expect(error.textContent).toMatch(/(\d+\s*(minutes?|mins?|seconds?|secs?|s\b))|retry after|try again in/i);
    const place = within(panel).getByRole('button', { name: /place a first order/i });
    expect(error.compareDocumentPosition(place) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('UX-18 the issued key has a Copy key action', async () => {
    responses['POST /v1/sandbox/keys'] = { status: 200, body: KEY };
    const writeText = vi.fn(async (_text: string) => {});
    Object.assign(navigator, { clipboard: { writeText } });
    const panel = await keyPanel();
    fireEvent.click(within(panel).getByRole('button', { name: /get a sandbox key/i }));
    await within(panel).findByText(KEY.api_key);
    fireEvent.click(within(panel).getByRole('button', { name: /copy key/i }));
    expect(writeText).toHaveBeenCalledWith(KEY.api_key);
  });

  it('UX-18 the page says navigating away loses the key', async () => {
    const panel = await keyPanel();
    await within(panel).findByText(/your key appears here/i);
    expect(panel.textContent).toMatch(/navigat|leave|leaving|reload|clos/i);
    expect(panel.textContent).toMatch(/lose|lost|gone|memory/i);
  });

  it('UX-18 an existing key can be continued with', async () => {
    const panel = await keyPanel();
    await within(panel).findByText(/your key appears here/i);
    expect(within(panel).getByLabelText(/existing key|use an? existing|enter.*key|continue with/i)).toBeTruthy();
  });
});

describe('S63-T UX-19 orders table', () => {
  const ORDER = {
    id: 'order-abcdef-1234567890', product_id: 'prod-1', side: 'buy', quantity: 1,
    remaining_qty: 0, price_cents: 10, status: 'FILLED', created_at: '2026-09-26T17:05:00Z',
  };

  beforeEach(() => {
    responses['POST /v1/sandbox/keys'] = { status: 200, body: KEY };
    responses['/v1/orders'] = [ORDER];
    responses['/v1/market'] = [PRODUCT];
  });

  async function ordersPanel() {
    render(<Sandbox />);
    const key = await screen.findByRole('region', { name: /get a key/i });
    fireEvent.click(within(key).getByRole('button', { name: /get a sandbox key/i }));
    await within(key).findByText(KEY.api_key);
    const orders = await screen.findByRole('region', { name: /your orders/i });
    await within(orders).findByText(/Judge/);
    return orders;
  }

  it('UX-19 each row shows product, zone and delivery window', async () => {
    const orders = await ordersPanel();
    const row = (await within(orders).findByText(/buy 1 @ \$0\.10/)).closest('tr')!;
    expect(row.textContent).toContain('FLEX-LZ_HOUSTON-2026092618');
    expect(row.textContent).toMatch(/Houston/i);
    expect(row.textContent).toMatch(/18|6 PM|delivery/i);
  });

  it('UX-19 times read as Central Time and long IDs abbreviate with a copy control', async () => {
    const orders = await ordersPanel();
    const row = (await within(orders).findByText(/buy 1 @ \$0\.10/)).closest('tr')!;
    expect(within(row).getByRole('time').textContent).toMatch(/CT|CDT|CST/);
    const idCell = within(row).getAllByRole('cell')[0];
    expect(idCell.textContent!.length).toBeLessThan(ORDER.id.length);
    expect(within(row).getByRole('button', { name: /copy/i })).toBeTruthy();
  });
});
