// @vitest-environment jsdom
/* RP-B stretch repair (DEC-GM-147): one focused file for the owned dashboard
   findings. TE F1 + UX F1 (checklist ticks on real replay actions), review 3
   (fleet POST omits household_load), UX F2 (sandbox honours zone/hour),
   F3 (replay zone/head URL-backed), F5 (one UNAVAILABLE rule), F6 (rounded
   scores), F7 (empty states act + link docs), F8 (why-card formatting),
   F9 (replay eyebrow), F11 (one working SDK snippet). Red before the fix. */
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from 'vitest';
// @ts-ignore TS2732: resolveJsonModule is off in the frozen tsconfig; vitest/vite load JSON at runtime.
import replayFixture from '../fixtures/replay.json';
// @ts-ignore TS2732: Vitest loads JSON; the frozen tsconfig omits resolveJsonModule.
import exchange from '../fixtures/s63-exchange.json';
// @ts-ignore TS2732: Vitest loads JSON; the frozen tsconfig omits resolveJsonModule.
import onboarding from '../fixtures/onboarding.json';
import Shell from '../components/Shell';
import Overview from './Overview';
import Predictions from './Predictions';
import Replay from './Replay';
import Sandbox from './Sandbox';

const completed = (): number[] => {
  try {
    const value = JSON.parse(localStorage.getItem('gm-first-steps') ?? '{}');
    return Array.isArray(value.completed) ? value.completed : [];
  } catch { return []; }
};

/* ---------- Replay: checklist, fleet load, zone/head URL, why card, eyebrow ---------- */

describe('RP-B Replay (fixture: replay.json)', () => {
  let fetchMock: Mock;
  let servedBaseline: unknown;

  beforeEach(() => {
    localStorage.clear();
    servedBaseline = (replayFixture as { baseline: unknown }).baseline;
    window.location.hash = '#/replay?day=2026-08-26';
    fetchMock = vi.fn(async (input: string, init?: { method?: string; body?: string }) => {
      const path = (input.startsWith('http') ? new URL(input).pathname : input).split('?')[0];
      const query = input.includes('?') ? new URL(input, 'http://x').searchParams : new URLSearchParams();
      if (path === '/v1/replay/days') return { ok: true, status: 200, json: async () => (replayFixture as { days: unknown }).days };
      if (path === '/v1/replay' && (init?.method ?? 'GET') === 'POST') {
        const body = JSON.parse(String(init?.body ?? '{}')) as { disruptions?: unknown[]; fleet: { assets: unknown[] } };
        if (body.fleet.assets.length === 1) return { ok: true, status: 200, json: async () => (replayFixture as { homeValue: unknown }).homeValue };
        const run = (body.disruptions?.length ?? 0) > 0 ? (replayFixture as { scenario: unknown }).scenario : servedBaseline;
        return { ok: true, status: 200, json: async () => run };
      }
      if (path.startsWith('/v1/replay/') && path.endsWith('/decisions')) {
        const timeline = (servedBaseline as { timeline: { interval_start: string; decisions: { strategy: string; decision_time: string }[] }[] }).timeline;
        const decisions = timeline.flatMap(step => step.decisions)
          .filter(d => d.strategy === query.get('strategy') && d.decision_time >= (query.get('start') ?? '') && d.decision_time < (query.get('end') ?? ''));
        return { ok: true, status: 200, json: async () => ({ run_id: 'x', decisions }) };
      }
      if (path === '/v1/signals') return { ok: true, status: 200, json: async () => [] };
      return { ok: false, status: 404, json: async () => ({ error: { code: 'NOT_FOUND', message: path } }) };
    });
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  async function loaded() {
    render(<Replay />);
    const board = await screen.findByRole('region', { name: /scoreboard · baseline/i });
    await within(board).findByRole('row', { name: /battery-aware/i });
    return board;
  }

  async function scenarioReady() {
    const form = await screen.findByRole('region', { name: /disruptions/i });
    const from = within(form).getByRole('combobox', { name: /window start/i }) as HTMLSelectElement;
    await waitFor(() => expect(from.value).not.toBe(''), { timeout: 5000 });
    return form;
  }

  const replayPosts = () => fetchMock.mock.calls
    .filter(([path, init]) => path === '/v1/replay' && init?.method === 'POST')
    .map(([, init]) => JSON.parse(String(init.body)) as { fleet: Record<string, unknown> });

  it('RPB-F1a Play marks step 1 only', async () => {
    await loaded();
    const chart = await screen.findByRole('region', { name: /prices and playback/i });
    fireEvent.click(within(chart).getByRole('button', { name: /^play$/i }));
    expect(completed()).toContain(1);
    expect(completed()).not.toContain(2);
  });

  it('RPB-F1a2 scrubbing the playback slider marks step 1', async () => {
    await loaded();
    const chart = await screen.findByRole('region', { name: /prices and playback/i });
    const slider = within(chart).getByRole('slider', { name: /playback position/i }) as HTMLInputElement;
    fireEvent.change(slider, { target: { value: '10' } });
    expect(completed()).toContain(1);
  });

  it('RPB-F1b a disruption run marks step 2', async () => {
    await loaded();
    const form = await scenarioReady();
    fireEvent.click(within(form).getByRole('button', { name: /run scenario/i }));
    await screen.findByRole('region', { name: /baseline versus scenario/i }, { timeout: 5000 });
    expect(completed()).toContain(2);
  });

  it('RPB-F1c a changed reserve plus Rerun the day marks step 2', async () => {
    render(<Replay />);
    const panel = await screen.findByRole('region', { name: /your turn/i });
    await within(panel).findByText(/flexibility to sell/i);
    expect(completed()).not.toContain(2);
    const slider = within(panel).getByRole('slider', { name: /reserve/i });
    fireEvent.change(slider, { target: { value: '10' } });
    const postsBefore = replayPosts().length;
    fireEvent.click(within(panel).getByRole('button', { name: /rerun the day/i }));
    await waitFor(() => expect(replayPosts().length).toBeGreaterThan(postsBefore));
    await waitFor(() => expect(completed()).toContain(2));
  });

  it('RPB-F1d an unchanged Rerun the day does not mark step 2', async () => {
    // ORC-8 (DEC-GM-152): each wait keys on observable state (the nth one-home value
    // POST answered and the panel idle again), never on elapsed time. The ceiling only
    // bounds a genuine hang; a loaded machine just takes longer to reach the state.
    const HANG = { timeout: 30_000 };
    const valuePosts = () => replayPosts().filter(p => (p.fleet.assets as unknown[]).length === 1).length;
    render(<Replay />);
    const panel = await screen.findByRole('region', { name: /your turn/i }, HANG);
    const settled = (posts: number) => waitFor(() => {
      expect(valuePosts()).toBe(posts);
      expect(panel.getAttribute('aria-busy')).toBe('false');
      expect(within(panel).getByText(/\+\$0\.81/)).toBeTruthy();
    }, HANG);
    await settled(1);
    expect(completed()).not.toContain(2);
    fireEvent.click(within(panel).getByRole('button', { name: /rerun the day/i }));
    await settled(2);
    expect(completed()).not.toContain(2);
  }, 70_000);

  it('RPB-F1e Rerun baseline alone does not mark step 2', async () => {
    await loaded();
    const form = await screen.findByRole('region', { name: /disruptions/i });
    fireEvent.click(within(form).getByRole('button', { name: /rerun baseline/i }));
    const header = await screen.findByRole('region', { name: /replay day/i });
    await waitFor(() => expect(header.textContent).toContain('RUN'));
    expect(completed()).not.toContain(2);
  });

  it('RPB-R3 fleet POSTs omit household_load (engine supplies the 1.2 kW contract profile)', async () => {
    await loaded();
    const form = await scenarioReady();
    fireEvent.click(within(form).getByRole('button', { name: /run scenario/i }));
    await screen.findByRole('region', { name: /baseline versus scenario/i }, { timeout: 5000 });
    const posts = replayPosts();
    expect(posts.length).toBeGreaterThanOrEqual(2);
    for (const post of posts) expect(post.fleet).not.toHaveProperty('household_load');
  });

  it('RPB-F3a ?zone= restores the replay zone', async () => {
    window.location.hash = '#/replay?day=2026-08-26&zone=LZ_WEST';
    await loaded();
    const header = await screen.findByRole('region', { name: /replay day/i });
    const zone = within(header).getByRole('combobox', { name: /^zone$/i }) as HTMLSelectElement;
    expect(zone.value).toBe('LZ_WEST');
    expect(replayPosts()[0].fleet).toMatchObject({ zone: 'LZ_WEST' });
  });

  it('RPB-F3b changing the zone writes it back to the URL', async () => {
    await loaded();
    const header = await screen.findByRole('region', { name: /replay day/i });
    fireEvent.change(within(header).getByRole('combobox', { name: /^zone$/i }), { target: { value: 'LZ_SOUTH' } });
    await waitFor(() => expect(window.location.hash).toContain('zone=LZ_SOUTH'));
  });

  it('RPB-F3c ?head= restores the playback position and the slider writes it back', async () => {
    window.location.hash = '#/replay?day=2026-08-26&head=55';
    await loaded();
    const chart = await screen.findByRole('region', { name: /prices and playback/i });
    const slider = within(chart).getByRole('slider', { name: /playback position/i }) as HTMLInputElement;
    await waitFor(() => expect(slider.value).toBe('55'));
    expect(completed()).not.toContain(1);
    fireEvent.change(slider, { target: { value: '10' } });
    await waitFor(() => expect(window.location.hash).toContain('head=10'));
  });

  it('RPB-F3d ?dstart=/?dend= restore the disruption window', async () => {
    await loaded();
    const form = await screen.findByRole('region', { name: /disruptions/i });
    const from = within(form).getByRole('combobox', { name: /window start/i }) as HTMLSelectElement;
    fireEvent.change(from, { target: { value: '76' } });
    await waitFor(() => expect(window.location.hash).toContain('dstart='));
    const saved = window.location.hash;
    cleanup();
    window.location.hash = saved;
    render(<Replay />);
    const board = await screen.findByRole('region', { name: /scoreboard · baseline/i });
    await within(board).findByRole('row', { name: /battery-aware/i });
    const form2 = await screen.findByRole('region', { name: /disruptions/i });
    await waitFor(() => expect((within(form2).getByRole('combobox', { name: /window start/i }) as HTMLSelectElement).value).toBe('76'));
  });

  it('RPB-F8 the why card rounds numbers and truncates long vectors', async () => {
    const mutated = structuredClone(replayFixture) as { baseline: { timeline: { decisions: { inputs: { name: string; value: string }[] }[] }[] } };
    for (const step of mutated.baseline.timeline) {
      for (const decision of step.decisions) {
        for (const input of decision.inputs) {
          if (input.name === 'dam_q25') input.value = '28.180000000000007';
        }
      }
    }
    servedBaseline = mutated.baseline;
    await loaded();
    const lanes = await screen.findByRole('region', { name: /strategy lanes/i });
    const lane = within(lanes).getByRole('group', { name: /battery-aware lane/i });
    fireEvent.click(within(lane).getAllByRole('button')[0]);
    const why = await screen.findByRole('region', { name: /why this decision/i });
    await waitFor(() => expect(why.textContent).toMatch(/battery-aware/i));
    expect(why.textContent).toContain('28.18, 26.5, 26.7, …');
    expect(why.textContent).not.toContain('28.180000000000007');
    expect(why.textContent).not.toContain('28.18,26.5,26.7,28.85');
  });

  it('RPB-F9 the replay eyebrow matches the nav number', async () => {
    await loaded();
    expect(await screen.findByText('03 / HISTORICAL REPLAY')).toBeTruthy();
  });
});

/* ---------- Predictions: one UNAVAILABLE rule, rounded scores ---------- */

describe('RP-B Predictions UNAVAILABLE + rounding', () => {
  beforeEach(() => {
    window.location.hash = '#/predictions';
    const predictions = [
      { zone: 'LZ_WEST', delivery_hour: '2026-09-26T18:00:00Z', score: 48.27969377353135, level: 'UNAVAILABLE', confidence: 0.1, expected_value: 0, market_price: null, drivers: [], disclaimer: 'Simulation estimate.', generated_at: '2026-09-26T15:00:00Z' },
      { zone: 'LZ_HOUSTON', delivery_hour: '2026-09-26T18:00:00Z', score: 72.44, level: 'High', confidence: 0.6, expected_value: 12.5, market_price: 10.0, drivers: [{ factor: 'price spread', contribution: 4.25, detail: 'Day-ahead above real-time' }], disclaimer: 'Simulation estimate.', generated_at: '2026-09-26T15:00:00Z' },
    ];
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), 'http://localhost').pathname;
      const body = path === '/v1/predictions' ? predictions
        : path === '/v1/router' ? { checks: [], brier: {}, jev_enabled: false }
        : path === '/v1/signals' ? [] : undefined;
      return { ok: body !== undefined, status: body === undefined ? 404 : 200,
        json: async () => body ?? { error: { code: 'NOT_FOUND', message: 'Not found' } } };
    }));
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('RPB-F5a no score beside UNAVAILABLE; RPB-F6 fractional scores round to one decimal', async () => {
    render(<Predictions />);
    const panel = await screen.findByRole('region', { name: /zone scores/i });
    const cards = await within(panel).findAllByRole('article');
    expect(cards).toHaveLength(2);
    const west = cards.find(c => c.textContent?.includes('LZ_WEST'))!;
    const houston = cards.find(c => c.textContent?.includes('LZ_HOUSTON'))!;
    expect(west.textContent).toContain('UNAVAILABLE');
    expect(west.textContent).not.toContain('48.27');
    expect(houston.textContent).toContain('72.4%');
  });
});

/* ---------- Overview: UNAVAILABLE rule, empty state, snippet ---------- */

describe('RP-B Overview (fixture: s63-exchange.json)', () => {
  let responses: Record<string, unknown>;

  beforeEach(() => {
    window.location.hash = '#/';
    responses = structuredClone(exchange) as Record<string, unknown>;
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), 'http://localhost').pathname;
      const body = responses[path];
      return { ok: body !== undefined, status: body === undefined ? 404 : 200,
        json: async () => body ?? { error: { code: 'NOT_FOUND', message: 'Not found' } } };
    }));
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    window.location.hash = '';
  });

  const prices = [
    { report_id: 'NP6-905-CD', zone: 'LZ_HOUSTON', value: 45.2, unit: '$/MWh', interval_start: '2026-09-26T18:00:00Z', interval_minutes: 15, published_at: '2026-09-26T18:05:00Z', fetched_at: '2026-09-26T18:05:00Z', age_s: 1, stale: false },
  ];

  it('RPB-F5b Overview hides the score when the level is UNAVAILABLE despite prices', async () => {
    responses['/v1/signals'] = prices;
    responses['/v1/predictions'] = ((exchange as Record<string, unknown>)['/v1/predictions'] as { level: string }[]).map(p => ({ ...p, level: 'UNAVAILABLE' }));
    render(<Overview />);
    const zones = await screen.findByRole('region', { name: 'Across the load zones' });
    await waitFor(() => expect(zones.getAttribute('aria-busy')).toBe('false'));
    const rows = within(zones).getAllByRole('row').slice(1);
    expect(rows.length).toBeGreaterThan(0);
    for (const row of rows) {
      const cells = within(row).getAllByRole('cell');
      expect(cells[2].textContent).toBe('—');
    }
    expect(zones.textContent).not.toMatch(/\d+(?:\.\d+)?\s*%/);
    const hero = await screen.findByRole('region', { name: 'Next delivery prediction' });
    const scarcity = within(hero).getByText('predicted scarcity').closest('div')!;
    expect(scarcity.textContent).toContain('—');
    expect(scarcity.textContent).not.toMatch(/46/);
  });

  it('RPB-F7a the battery empty state names the Worker setting and links docs', async () => {
    responses['/v1/signals'] = prices;
    render(<Overview />);
    const panel = await screen.findByRole('region', { name: /texas batteries charging now/i });
    expect(await within(panel).findByText(/Battery data not yet available/)).toBeTruthy();
    expect(panel.textContent).toContain('GRIDMARKET_WORKER_URL');
    const docs = within(panel).getByRole('link', { name: /setup docs/i }) as HTMLAnchorElement;
    expect(docs.getAttribute('href')).toBe('#/spec');
  });

  it('RPB-F11a the Overview sample uses the working SDK call shape', async () => {
    render(<Overview />);
    const judge = await screen.findByRole('region', { name: /trade it yourself/i });
    expect(judge.textContent).not.toContain('FLEX-LZ_HOUSTON-18');
    expect(judge.textContent).toContain('client.buy(product["id"], quantity=1, price_cents=10)');
  });
});

/* ---------- Shell: feed empty state ---------- */

describe('RP-B Shell feed state', () => {
  beforeEach(() => {
    window.location.hash = '#/';
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), 'http://localhost').pathname;
      const body = path === '/v1/signals' ? [] : undefined;
      return { ok: body !== undefined, status: body === undefined ? 404 : 200,
        json: async () => body ?? { error: { code: 'NOT_FOUND', message: 'Not found' } } };
    }));
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('RPB-F7b the sidebar names the Worker setting and links docs when the feed is down', async () => {
    render(<Shell><div>child</div></Shell>);
    expect(await screen.findByText(/ERCOT feed not connected/)).toBeTruthy();
    expect(screen.getByText(/GRIDMARKET_WORKER_URL/)).toBeTruthy();
    const docs = screen.getByRole('link', { name: /setup docs/i }) as HTMLAnchorElement;
    expect(docs.getAttribute('href')).toBe('#/spec');
  });
});

/* ---------- Sandbox: carried context, snippet ---------- */

describe('RP-B Sandbox (fixture: onboarding.json)', () => {
  const NOW = new Date('2026-09-26T17:00:00Z');
  let responses: Record<string, unknown>;
  let calls: { path: string; init?: RequestInit }[];

  beforeEach(() => {
    calls = [];
    responses = structuredClone(onboarding) as Record<string, unknown>;
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const raw = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
      const path = (raw.startsWith('http') ? new URL(raw).pathname : raw).split('?')[0];
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

  async function keyed() {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval', 'Date'] });
    vi.setSystemTime(NOW);
    render(<Sandbox />);
    fireEvent.click(screen.getByRole('button', { name: /get a sandbox key/i }));
    const keyPanel = await screen.findByRole('region', { name: /get a key/i });
    await within(keyPanel).findByText(((onboarding as Record<string, unknown>)['/v1/sandbox/keys'] as { api_key: string }).api_key);
    return keyPanel;
  }

  it('RPB-F2 the first order honours carried zone+hour and names the product first', async () => {
    window.location.hash = '#/sandbox?zone=LZ_NORTH&hour=2026-09-26T21:00:00Z';
    const keyPanel = await keyed();
    expect(await within(keyPanel).findByText(/FLEX-LZ_NORTH-2026092621/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /place a first order/i }));
    await waitFor(() => {
      expect(calls.some(call => call.path === '/v1/orders' && call.init?.method === 'POST')).toBe(true);
    });
    const post = calls.find(call => call.path === '/v1/orders' && call.init?.method === 'POST')!;
    expect(JSON.parse(String(post.init?.body))).toMatchObject({ product_id: 'flex-later' });
  });

  it('RPB-F2b the first order honours a carried symbol', async () => {
    window.location.hash = '#/sandbox?symbol=SPOT-LZ_HOUSTON-2026092618';
    await keyed();
    fireEvent.click(screen.getByRole('button', { name: /place a first order/i }));
    await waitFor(() => {
      expect(calls.some(call => call.path === '/v1/orders' && call.init?.method === 'POST')).toBe(true);
    });
    const post = calls.find(call => call.path === '/v1/orders' && call.init?.method === 'POST')!;
    expect(JSON.parse(String(post.init?.body))).toMatchObject({ product_id: 'spot-soon' });
  });

  it('RPB-F11b the sandbox snippet selects the open FLEX product like the README', async () => {
    window.location.hash = '#/sandbox';
    render(<Sandbox />);
    const sdk = await screen.findByRole('region', { name: /sdk snippet/i });
    await waitFor(() => expect(sdk.textContent).toContain('GRIDMARKET_API_KEY'));
    expect(sdk.textContent).toContain('p["status"] == "open"');
    expect(sdk.textContent).toContain('p["symbol"].startswith("FLEX-")');
    expect(sdk.textContent).not.toContain('market()[0]');
  });
});
