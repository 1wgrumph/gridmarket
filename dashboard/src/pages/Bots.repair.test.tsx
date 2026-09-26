// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import Bots from './Bots';
import BotProfile from './BotProfile';

// Recorded from backend bots_api.py: GET /v1/bots lists only these five fields (no cash, no P&L).
const liveBots = [
  { id: 'bot-1', bot_index: 0, bot_type: 'market maker', provider_id: 'base_sim', dormant: false },
  { id: 'bot-2', bot_index: 1, bot_type: 'saver', provider_id: 'base_sim', dormant: true },
];
// GET /v1/bots/diversity returns coverage, entropy, and points.
const liveDiversity = { coverage: 0.857, entropy: 2.61, points: [{ risk_appetite: 0.8, patience: 0.3 }, { risk_appetite: 0.4, patience: 0.7 }] };
// GET /v1/bots/{id}: traits keep population.py's spaced names; economy.stats adds cash..dormant.
// balance_history is the per-fill/deposit ledger series AC-GM-UI-03 asks for (review F6).
const liveProfile = {
  id: 'bot-1', bot_type: 'market maker', blend: { 'market maker': 1 }, provider_id: 'base_sim',
  traits: { 'risk appetite': 0.8, patience: 0.3, 'reaction delay': 12 },
  household: { batteries: [13.5], zone: 'LZ_NORTH', reserve_pct: 0.2, schedule: Array(24).fill(0.1) }, employed: false, pay: 40,
  cash: 1000, balance: [1000, 1000], trades: 0, losses: 0, loss_share: 0, worst_loss: 0, pnl: 0, net_worth: 1000, dormant: false,
  balance_history: [{ at: '2026-09-26T13:00:00Z', balance: 1000 }, { at: '2026-09-26T13:30:00Z', balance: 1040 }, { at: '2026-09-26T13:31:00Z', balance: 1012.5 }],
};

let responses: Record<string, unknown>;
let calls: { path: string; init?: RequestInit }[];

beforeEach(() => {
  calls = [];
  responses = { '/v1/bots': liveBots, '/v1/bots/diversity': liveDiversity, '/v1/bots/bot-1': liveProfile, '/v1/admin/bots': { spawned: 1 } };
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    calls.push({ path: String(input), init });
    const body = responses[String(input)];
    return { ok: body !== undefined, status: body === undefined ? 404 : 200, json: async () => body ?? { error: { code: 'NOT_FOUND', message: 'Not found' } } };
  }));
});

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('Bots repair phase 1b', () => {
  it('F3 renders the live /v1/bots rows, which carry no cash', async () => {
    render(<Bots />);
    expect(await screen.findByText('bot-1')).toBeTruthy();
    expect(screen.getByText('bot-2')).toBeTruthy();
    expect(screen.getByText('50%')).toBeTruthy();
  });

  it('F4 renders coverage, entropy, and points from /v1/bots/diversity', async () => {
    render(<Bots />);
    expect(await screen.findByText('86%')).toBeTruthy();
    expect(screen.getByText('2.61 bits')).toBeTruthy();
  });

  it('F9 sends the spawn seed as a string', async () => {
    render(<Bots />);
    fireEvent.change(screen.getByLabelText(/admin key/i), { target: { value: 'k' } });
    fireEvent.change(screen.getByLabelText(/seed/i), { target: { value: '123' } });
    fireEvent.click(screen.getByRole('button', { name: /spawn/i }));
    await waitFor(() => expect(calls.some(c => c.path === '/v1/admin/bots')).toBe(true));
    const body = JSON.parse(String(calls.find(c => c.path === '/v1/admin/bots')!.init?.body));
    expect(body).toEqual({ count: 1, seed: '123' });
  });

  it('F5 reads the spaced "risk appetite" trait key', async () => {
    render(<BotProfile id="bot-1" />);
    await screen.findByText('Risk appetite');
    expect(screen.getByText('Risk appetite').nextSibling?.textContent).toBe('80%');
  });

  it('F6 charts balance_history, not the two-number balance tuple', async () => {
    render(<BotProfile id="bot-1" />);
    expect(await screen.findByRole('img', { name: 'Simulated balance, 3 points.' })).toBeTruthy();
    expect(screen.queryByText('No balance history served.')).toBeNull();
  });
});
