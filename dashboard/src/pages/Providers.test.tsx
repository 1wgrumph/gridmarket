// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import App from '../App';
import fixture from '../fixtures/providers.json';

type Responses = Record<string, unknown>;
type Call = { path: string; init?: RequestInit };
let responses: Responses;
let calls: Call[];

const PROVIDERS_URL = '/v1/providers';
const HEALTH_URL = '/v1/providers/health';
const OUTAGE_ACTIVE = /outage active|outage:\s*(yes|active|on)/i;
const OUTAGE_NONE = /no outage|outage:\s*(no|none|off)/i;
const FROZEN_NOW = new Date('2026-09-26T13:00:00Z').getTime();
const outageUrl = (id: string) => `/v1/admin/providers/${id}/outage`;

function visitProviders() {
  window.location.hash = '#/providers';
  render(<App />);
}

function healthRows(): Array<Record<string, unknown>> {
  return responses[HEALTH_URL] as Array<Record<string, unknown>>;
}

function outageCalls(id?: string) {
  return calls.filter(c => (id ? c.path === outageUrl(id) : c.path.includes('/outage')));
}

function authOf(call: Call): unknown {
  const headers = call.init?.headers as Record<string, string> | undefined;
  return headers?.Authorization ?? headers?.authorization;
}

function keyInput(): HTMLElement {
  return screen.queryByLabelText(/admin key/i) ?? screen.getByPlaceholderText(/admin key/i);
}

async function settled() {
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
}

beforeEach(() => {
  calls = [];
  responses = structuredClone(fixture) as Responses;
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    calls.push({ path, init });
    const body = responses[path];
    return { ok: body !== undefined, status: body === undefined ? 404 : 200, json: async () => body ?? { error: { code: 'NOT_FOUND', message: 'Not found' } } };
  }));
});

afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); window.location.hash = ''; });

describe('Providers page', () => {
  it('SEIT-GM-UI-04 shows both providers with customer and online-asset counts', async () => {
    visitProviders();
    expect((await screen.findAllByText('Base Simulation')).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('LoneStar Storage').length).toBeGreaterThanOrEqual(1);
    for (const n of [/\b40\b/, /\b38\b/, /\b20\b/, /\b17\b/]) {
      expect(screen.getAllByText(n).length).toBeGreaterThanOrEqual(1);
    }
  });

  it('SEIT-GM-UI-04 shows heartbeat age in seconds per provider from the fixture', async () => {
    vi.useFakeTimers();
    vi.setSystemTime(FROZEN_NOW);
    visitProviders();
    await settled();
    expect(screen.getAllByText(/4\s*s/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/47\s*s/).length).toBeGreaterThanOrEqual(1);
    cleanup();
    healthRows().find(r => r.provider_id === 'base_sim')!.last_heartbeat = '2026-09-26T12:59:51Z';
    visitProviders();
    await settled();
    expect(screen.getAllByText(/9\s*s/).length).toBeGreaterThanOrEqual(1);
    expect(screen.queryAllByText(/4\s*s/).length).toBe(0);
  });

  it('SEIT-GM-UI-04 shows health probability and band per provider', async () => {
    visitProviders();
    expect((await screen.findAllByText('LoneStar Storage')).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/0\.08|8\s*%/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/0\.92|92\s*%/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/\blog\b/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/\balert\b/i).length).toBeGreaterThanOrEqual(1);
  });

  it('SEIT-GM-UI-04 shows outage state per provider from the fixture', async () => {
    visitProviders();
    expect((await screen.findAllByText('LoneStar Storage')).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(OUTAGE_ACTIVE)).toHaveLength(1);
    expect(screen.getAllByText(OUTAGE_NONE)).toHaveLength(1);
    cleanup();
    for (const row of healthRows()) { row.outage_active = true; row.outage_until = '2026-09-26T13:10:00Z'; }
    visitProviders();
    expect((await screen.findAllByText('LoneStar Storage')).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(OUTAGE_ACTIVE)).toHaveLength(2);
  });

  it('SEIT-GM-UI-04 shows a fallback when a provider health entry is missing', async () => {
    responses[HEALTH_URL] = healthRows().filter(r => r.provider_id !== 'lonestar');
    visitProviders();
    expect((await screen.findAllByText('LoneStar Storage')).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/unknown|unavailable|error|could not load|not available/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/\b40\b/).length).toBeGreaterThanOrEqual(1);
  });

  it('SEIT-GM-UI-04 refreshes provider data within two seconds', async () => {
    vi.useFakeTimers();
    visitProviders();
    await act(async () => { await vi.advanceTimersByTimeAsync(2001); });
    expect(calls.filter(c => c.path === PROVIDERS_URL).length).toBeGreaterThanOrEqual(2);
  });

  it('SEIT-GM-PROV-03 start outage posts active true with the typed admin key only', async () => {
    visitProviders();
    expect((await screen.findAllByText('LoneStar Storage')).length).toBeGreaterThanOrEqual(1);
    fireEvent.change(keyInput(), { target: { value: 'gm_admin_typed_1' } });
    fireEvent.click(screen.getByRole('button', { name: /start outage[\s\S]*lone/i }));
    await act(async () => {});
    const posts = outageCalls('lonestar');
    expect(posts.length).toBeGreaterThanOrEqual(1);
    const last = posts[posts.length - 1];
    expect(last.init?.method).toBe('POST');
    expect(String(last.init?.body)).toBe(JSON.stringify({ active: true }));
    expect(authOf(last)).toBe('Bearer gm_admin_typed_1');
    for (const c of calls.filter(c => !c.path.includes('/outage'))) expect(authOf(c)).toBeUndefined();
  });

  it('SEIT-GM-PROV-03 end outage posts active false with the retyped key, never a stored key', async () => {
    visitProviders();
    expect((await screen.findAllByText('LoneStar Storage')).length).toBeGreaterThanOrEqual(1);
    fireEvent.change(keyInput(), { target: { value: 'gm_admin_first' } });
    fireEvent.click(screen.getByRole('button', { name: /start outage[\s\S]*lone/i }));
    await act(async () => {});
    fireEvent.change(keyInput(), { target: { value: 'gm_admin_second' } });
    fireEvent.click(screen.getByRole('button', { name: /end outage[\s\S]*lone/i }));
    await act(async () => {});
    const posts = outageCalls('lonestar');
    expect(posts.length).toBeGreaterThanOrEqual(2);
    expect(authOf(posts[0])).toBe('Bearer gm_admin_first');
    expect(authOf(posts[posts.length - 1])).toBe('Bearer gm_admin_second');
    expect(String(posts[posts.length - 1].init?.body)).toBe(JSON.stringify({ active: false }));
  });

  it('SEIT-GM-PROV-03 outage buttons without a typed key send no authorized request', async () => {
    visitProviders();
    expect((await screen.findAllByText('LoneStar Storage')).length).toBeGreaterThanOrEqual(1);
    fireEvent.click(screen.getByRole('button', { name: /start outage[\s\S]*lone/i }));
    await act(async () => {});
    for (const c of outageCalls()) expect(authOf(c) ?? '').toBe('');
  });
});
