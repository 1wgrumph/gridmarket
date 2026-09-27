// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import App from '../App';
import fixture from './phase1b.fixture.json';

type Responses = Record<string, unknown>;
let responses: Responses;
let calls: { path: string; init?: RequestInit }[];

function visit(path: string) {
  window.location.hash = path;
  render(<App />);
}

function setResponse(path: string, body: unknown) { responses[path] = body; }

beforeEach(() => {
  calls = [];
  responses = structuredClone(fixture);
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    calls.push({ path, init });
    const body = responses[path];
    return { ok: body !== undefined, status: body === undefined ? 404 : 200, json: async () => body ?? { error: { code: 'NOT_FOUND', message: 'Not found' } } };
  }));
});

afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); window.location.hash = ''; });

describe('phase 1b dashboard pages', () => {
  it('SEIT-GM-UI-01-PAGES Market shows products, book depth, and recent trades', async () => {
    visit('#/market');
    expect(await screen.findByText('NORTH-20260926-14')).toBeTruthy();
    expect(screen.getByText(/bid/i)).toBeTruthy();
    expect(screen.getByText(/ask/i)).toBeTruthy();
    expect(screen.getByText(/recent trades/i)).toBeTruthy();
    expect(await within(await screen.findByRole('region', { name: 'Recent trades' })).findByText('1 @ $42.00')).toBeTruthy();
  });

  it('SEIT-GM-UI-01-PAGES Market refreshes within two seconds', async () => {
    vi.useFakeTimers();
    visit('#/market');
    await act(async () => { await vi.advanceTimersByTimeAsync(2001); });
    expect(calls.filter(c => c.path === '/v1/market').length).toBeGreaterThanOrEqual(2);
  });

  it('SEIT-GM-UI-01-PAGES Predictions shows signed factors, market check, band, and Brier score', async () => {
    visit('#/predictions');
    const scores = await screen.findByRole('region', { name: /zone scores/i });
    fireEvent.click((await within(scores).findAllByRole('button', { name: /why this estimate/i }))[0]);
    expect(await within(scores).findByText('DART spread')).toBeTruthy();
    expect(screen.getByText('Wind')).toBeTruthy();
    expect(await within(screen.getByText('DART spread').closest('li')!).findByText('+0.18')).toBeTruthy();
    expect(await within(screen.getByText('Wind').closest('li')!).findByText('-0.12')).toBeTruthy();
    expect(screen.getByText('NORTH 14:00')).toBeTruthy();
    expect(screen.getByText(/alert/i)).toBeTruthy();
    expect(screen.getByText(/review/i)).toBeTruthy();
    expect(screen.getByText(/brier/i)).toBeTruthy();
    expect(await within(screen.getByText('NORTH 14:00').closest('tr')!).findByText('0.17')).toBeTruthy();
  });

  it('SEIT-GM-UI-01-PAGES Jev column follows the /v1/router flag', async () => {
    visit('#/predictions');
    await screen.findByText('NORTH 14:00');
    expect(screen.queryByRole('columnheader', { name: /jev/i })).toBeNull();
    cleanup();
    setResponse('/v1/router', { ...fixture['/v1/router'], jev_enabled: true });
    visit('#/predictions');
    expect(await screen.findByRole('columnheader', { name: /jev/i })).toBeTruthy();
  });

  it('SEIT-GM-RULE-02-UI labels every baseline check as baseline rules', async () => {
    visit('#/predictions');
    expect(await screen.findByText('NORTH 14:00')).toBeTruthy();
    expect(screen.getByText('SOUTH 15:00')).toBeTruthy();
    expect(screen.getAllByText(/baseline rules/i)).toHaveLength(2);
  });

  it('SEIT-GM-SCORE-03-UI shows the score disclaimer on Predictions', async () => {
    visit('#/predictions');
    expect(await screen.findByText('Directional score, not financial advice.')).toBeTruthy();
  });

  it('SEIT-GM-UI-01-PAGES Bots shows population and a one-of-two dormant rate', async () => {
    visit('#/bots');
    expect(await screen.findByText('bot-7')).toBeTruthy();
    expect(screen.getAllByText('score follower').length).toBeGreaterThan(0);
    expect(screen.getByText('lonestar')).toBeTruthy();
    expect(screen.getByText('bot-8')).toBeTruthy();
    expect(screen.getByText(/dormant rate/i)).toBeTruthy();
    expect(await within(screen.getByText('Dormant rate').parentElement!).findByText('50%')).toBeTruthy();
  });

  it('SEIT-GM-UI-07 shows coverage, entropy, risk and patience diversity', async () => {
    visit('#/bots');
    expect(await screen.findByText(/trait.space coverage/i)).toBeTruthy();
    expect(screen.getByText(/behavior entropy/i)).toBeTruthy();
    expect(screen.getByText(/risk appetite/i)).toBeTruthy();
    expect(screen.getByText(/patience/i)).toBeTruthy();
  });

  it('SEIT-GM-UI-07 keeps dormant rate when diversity is not yet enabled', async () => {
    delete responses['/v1/bots/diversity'];
    visit('#/bots');
    expect(await screen.findByText(/not yet enabled/i)).toBeTruthy();
    expect(screen.getByText(/dormant rate/i)).toBeTruthy();
    expect(await within(screen.getByText('Dormant rate').parentElement!).findByText('50%')).toBeTruthy();
  });

  it('SEIT-GM-UI-01-PAGES owner spawn sends only the key typed in the form', async () => {
    visit('#/bots');
    fireEvent.change(screen.getByLabelText(/admin key/i), { target: { value: 'typed-admin-key' } });
    fireEvent.change(screen.getByLabelText(/count/i), { target: { value: '2' } });
    fireEvent.click(screen.getByRole('button', { name: /spawn/i }));
    await waitFor(() => expect(calls.some(c => c.path === '/v1/admin/bots')).toBe(true));
    const request = calls.find(c => c.path === '/v1/admin/bots')!;
    expect(request.init?.method).toBe('POST');
    expect(new Headers(request.init?.headers).get('Authorization')).toBe('Bearer typed-admin-key');
    expect(JSON.parse(String(request.init?.body))).toMatchObject({ count: 2 });
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });

  it('SEIT-GM-UI-03 bot profile shows traits, economy, performance, and balance history', async () => {
    visit('#/bots/bot-7');
    expect(await screen.findByText(/risk appetite/i)).toBeTruthy();
    for (const label of [/patience/i, /score follower/i, /saver/i, /household/i, /^(?:Not )?employed$/i, /pay/i, /balance/i, /trades/i, /losses/i, /worst loss/i, /dormant/i]) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
    expect(await within(screen.getByText('Loss share').parentElement!).findByText('25%')).toBeTruthy();
    expect(screen.getByText(/P&L/i)).toBeTruthy();
    expect(await within(screen.getByText('Cash').parentElement!).findByText('$912.00')).toBeTruthy();
    expect(await within(screen.getByText('P&L').parentElement!).findByText('$24.00')).toBeTruthy();
    expect(screen.queryByText(/\$?64(?:\.00)?\b/)).toBeNull();
  });

  it('SEIT-GM-UI-01-PAGES Judge sandbox gets a key, shows SDK snippet and keyed orders', async () => {
    visit('#/sandbox');
    fireEvent.click(screen.getByRole('button', { name: /get a sandbox key/i }));
    expect(await screen.findByText('gm_fixture_only_key')).toBeTruthy();
    const keyCall = calls.find(c => c.path === '/v1/sandbox/keys');
    expect(keyCall?.init?.method).toBe('POST');
    expect(new Headers(keyCall?.init?.headers).has('Authorization')).toBe(false);
    expect(screen.getAllByText(/SDK/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/your orders/i)).toBeTruthy();
    expect(await screen.findByText('order-7')).toBeTruthy();
    const orderCall = calls.find(c => c.path === '/v1/orders');
    expect(new Headers(orderCall?.init?.headers).get('Authorization')).toBe('Bearer gm_fixture_only_key');
  });

  it('SEIT-GM-UI-01-PAGES Spec renders the generated GridMarket specification (UX-04)', () => {
    visit('#/spec');
    const doc = screen.getByRole('article', { name: /gridmarket specification/i });
    expect(within(doc).getByRole('heading', { name: 'GridMarket Architecture Specification' })).toBeTruthy();
  });
});
