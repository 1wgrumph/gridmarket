// @vitest-environment jsdom
/* S63-T red tests: UX-01 (bots list unavailable states), UX-17 (bots lead
   with population/performance, spawn secondary, labelled load strip). Fetch
   is stubbed with fixed data; no wall-clock assertions. */
import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import BotProfile from './BotProfile';
import Bots from './Bots';

let responses: Record<string, unknown>;

const bot = (id: string, extra: Record<string, unknown> = {}) => ({
  id, bot_index: 0, bot_type: 'maker', provider_id: 'base_sim', dormant: false, ...extra,
});

beforeEach(() => {
  responses = {
    '/v1/bots': [bot('bot_0')],
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
});

async function allBotsPanel() {
  const panel = await screen.findByRole('region', { name: /all bots/i });
  await within(panel).findByRole('row', { name: /bot_0/i });
  return panel;
}

describe('S63-T UX-01 bots list states', () => {
  it('UX-01 an unserved Blend cell shows an explicit unavailable state, never a blank', async () => {
    render(<Bots />);
    const panel = await allBotsPanel();
    const row = within(panel).getByRole('row', { name: /bot_0/i });
    const blend = within(row).getAllByRole('cell')[2];
    expect(blend.textContent?.trim()).not.toBe('');
    expect(blend.textContent).toMatch(/—|unavailable|not available|%/);
  });
});

describe('S63-T UX-17 bots page order and profile strip', () => {
  it('UX-17 owner spawning sits in a secondary admin disclosure below the population stats', async () => {
    render(<Bots />);
    await allBotsPanel();
    const stats = screen.getByRole('region', { name: /population key numbers/i });
    const adminKey = screen.getByLabelText(/admin key/i);
    const details = adminKey.closest('details');
    const discloser = screen.queryByRole('button', { expanded: false });
    const controlled = discloser !== null
      && (document.getElementById(discloser.getAttribute('aria-controls') ?? '')?.contains(adminKey) ?? false);
    expect(details ?? (controlled ? discloser : null)).not.toBeNull();
    const spawnSection = (details ?? adminKey.closest('section')) as HTMLElement;
    expect(stats.compareDocumentPosition(spawnSection) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('UX-17 bots lead with a performance summary next to population', async () => {
    render(<Bots />);
    await allBotsPanel();
    expect(screen.getByRole('region', { name: /performance/i })).toBeTruthy();
  });

  it('UX-17 household load strip has hour labels and a legend or accessible values', async () => {
    responses['/v1/bots/bot_0'] = {
      ...bot('bot_0', { cash: 1012.5, net_worth: 1012.5, pnl: 12.5, losses: 1 }),
      household: { zone: 'LZ_HOUSTON', batteries: [13.5], reserve_pct: 0.2, schedule: Array.from({ length: 24 }, (_, h) => (h % 5) / 4) },
    };
    render(<BotProfile id="bot_0" />);
    const strip = await screen.findByRole('img', { name: /hourly load/i });
    const panel = strip.closest('section') as HTMLElement;
    const numerals = within(panel).queryAllByText(/^(0?[0-9]|1[0-9]|2[0-3])$/)
      .filter(el => !el.classList.contains('section-index'));
    expect(numerals.length).toBeGreaterThanOrEqual(4);
    expect(panel.textContent).toMatch(/legend|low|high|min|max|peak/i);
  });
});
