// @vitest-environment jsdom
/* S47 Judge sandbox onboarding, rendered from dashboard/src/fixtures/onboarding.json
   with fetch stubbed (no network). The pragma pins jsdom because `make red-green`
   runs vitest from the repo root, where dashboard/vite.config.ts is not auto-loaded. */
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
// @ts-ignore TS2732: resolveJsonModule is off in the frozen tsconfig; vitest/vite load JSON at runtime.
import fixture from '../fixtures/onboarding.json';
import Sandbox from './Sandbox';

type Responses = Record<string, unknown>;
type Call = { path: string; init?: RequestInit };

const NOW = new Date('2026-09-26T17:00:00Z');
const KEY_LABEL = 'Judge';
const PROMPT_KIT = '/kit/system-prompt.md';
const MCP_SNIPPET = '/kit/mcp.md';
const NEXT_FUTURE = 'flex-next';

const sandboxKey = fixture['/v1/sandbox/keys'] as { account_id: string; api_key: string; label: string };
const placedOrder = fixture['POST /v1/orders'] as {
  id: string; product_id: string; side: string; quantity: number; price_cents: number;
};
const promptKit = fixture[PROMPT_KIT] as string;
const mcpSnippet = fixture[MCP_SNIPPET] as string;

let responses: Responses;
let calls: Call[];

function requestPath(input: RequestInfo | URL): string {
  const raw = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
  return (raw.startsWith('http') ? new URL(raw).pathname : raw).split('?')[0];
}

beforeEach(() => {
  calls = [];
  responses = structuredClone(fixture) as Responses;
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = requestPath(input);
    const method = (init?.method ?? 'GET').toUpperCase();
    calls.push({ path, init: { ...init, method } });
    const key = `${method} ${path}`;
    const body = Object.prototype.hasOwnProperty.call(responses, key) ? responses[key] : responses[path];
    const missing = body === undefined;
    if (method === 'POST' && path === '/v1/orders' && !missing) responses['GET /v1/orders'] = [body];
    return {
      ok: !missing,
      status: missing ? 404 : 200,
      json: async () => (missing ? { error: { code: 'NOT_FOUND', message: path } } : body),
      text: async () => (missing ? '' : typeof body === 'string' ? body : JSON.stringify(body)),
    };
  }));
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function sectionOf(node: HTMLElement): HTMLElement {
  const section = node.closest('section');
  if (!section) throw new Error('snippet is not inside a section');
  return section;
}

describe('S47 Judge sandbox onboarding (fixture: onboarding.json)', () => {
  it('[SEIT-GM-UI-05] click 1 shows a working sandbox key and click 2 shows the first order under your orders with the key label within 5s', async () => {
    // price_cents 10 is the bots' price, inside the 0..500 cap; quantity 1 is inside the size cap.
    expect(placedOrder.price_cents).toBe(10);
    expect(placedOrder.quantity).toBe(1);
    expect(sandboxKey.label).toBe(KEY_LABEL);

    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval', 'Date'] });
    vi.setSystemTime(NOW);
    render(<Sandbox />);

    fireEvent.change(screen.getByLabelText(/label \(optional\)/i), { target: { value: KEY_LABEL } });
    fireEvent.click(screen.getByRole('button', { name: /get a sandbox key/i }));

    const keyPanel = await screen.findByRole('region', { name: /get a key/i });
    expect(await within(keyPanel).findByText(sandboxKey.api_key)).toBeTruthy();
    const issued = calls.find(call => call.path === '/v1/sandbox/keys');
    expect(issued?.init?.method).toBe('POST');
    expect(JSON.parse(String(issued?.init?.body))).toMatchObject({ label: KEY_LABEL });

    const place = await screen.findByRole('button', { name: /place a first order/i });
    fireEvent.click(place);
    await waitFor(() => {
      expect(calls.some(call => call.path === '/v1/orders' && call.init?.method === 'POST')).toBe(true);
    });
    const post = calls.find(call => call.path === '/v1/orders' && call.init?.method === 'POST')!;
    expect(new Headers(post.init?.headers).get('Authorization')).toBe(`Bearer ${sandboxKey.api_key}`);
    expect(new Headers(post.init?.headers).get('Idempotency-Key')).toBeTruthy();
    expect(JSON.parse(String(post.init?.body))).toMatchObject({
      product_id: NEXT_FUTURE,
      side: 'buy',
      quantity: 1,
      price_cents: 10,
    });

    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    vi.useRealTimers();
    const orders = await screen.findByRole('region', { name: /your orders/i });
    expect(await within(orders).findByText(/Judge/)).toBeTruthy();
    expect(await within(orders).findByText('order-judge-1')).toBeTruthy();
    expect(await within(orders).findByText(/\$0\.10/)).toBeTruthy();
  });

  it('[SEIT-GM-UI-05] copy buttons exist for the SDK snippet and for each prompt-kit and MCP snippet the fixture serves', async () => {
    render(<Sandbox />);
    for (const snippet of [promptKit, mcpSnippet]) {
      const marker = snippet.split('\n')[0] as string;
      const text = await screen.findByText(marker);
      expect(await within(sectionOf(text)).findByRole('button', { name: /copy code/i })).toBeTruthy();
    }
    const sdk = await screen.findByRole('region', { name: /sdk snippet/i });
    expect(await within(sdk).findByRole('button', { name: /copy code/i })).toBeTruthy();
  });

  it('[SEIT-GM-UI-05] hides copy buttons when a prompt-kit or MCP file returns 404', async () => {
    delete responses[PROMPT_KIT];
    delete responses[MCP_SNIPPET];
    render(<Sandbox />);
    await waitFor(() => {
      const paths = calls.map(call => call.path);
      expect(paths).toContain(PROMPT_KIT);
      expect(paths).toContain(MCP_SNIPPET);
    });
    expect(screen.queryByText('GRIDMARKET_PROMPT_KIT_FIXTURE')).toBeNull();
    expect(screen.queryByText('GRIDMARKET_MCP_SNIPPET_FIXTURE')).toBeNull();
    const copies = screen.queryAllByRole('button', { name: /copy code/i });
    const sdk = screen.getByRole('region', { name: /sdk snippet/i });
    expect(copies).toHaveLength(1);
    expect(sdk.contains(copies[0] as HTMLElement)).toBe(true);
  });
});
