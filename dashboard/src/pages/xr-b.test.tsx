// @vitest-environment jsdom
/* XR-B extras repair (DEC-GM-152), dashboard slice. One red test per owned
   behavioural finding: review 1 and 4, UX F1, F3, F5, F6, F7, F8, F9, F10, F11.
   Live-grid rows come from fixtures/livegrid.json (real Worker captures run
   through the backend parsers; see livegrid.PROVENANCE.md). Clocks are frozen
   at the capture time; waits key on rendered state. */
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
// @ts-ignore TS2732: Vitest loads JSON; the frozen tsconfig omits resolveJsonModule.
import livegrid from '../fixtures/livegrid.json';
// @ts-ignore TS2732: Vitest loads JSON; the frozen tsconfig omits resolveJsonModule.
import overview from '../fixtures/overview.json';
// @ts-ignore TS2732: Vitest loads JSON; the frozen tsconfig omits resolveJsonModule.
import replayFixture from '../fixtures/replay.json';
// @ts-ignore TS2732: Vitest loads JSON; the frozen tsconfig omits resolveJsonModule.
import catalog from '../fixtures/catalog-days.json';
// @ts-ignore TS2732: Vitest loads JSON; the frozen tsconfig omits resolveJsonModule.
import onboarding from '../fixtures/onboarding.json';
import App from '../App';
import Overview from './Overview';
import Predictions from './Predictions';
import Replay from './Replay';
import Sandbox from './Sandbox';

type Init = { method?: string; body?: string };
type Reply = { ok: boolean; status: number; headers: Headers; json: () => Promise<unknown>; text: () => Promise<string> };
const reply = (status: number, body: unknown, headers: Record<string, string> = {}): Reply =>
  ({ ok: status < 400, status, headers: new Headers(headers), json: async () => body, text: async () => '' });
const notFound = (path: string) => reply(404, { error: { code: 'NOT_FOUND', message: path } });

const CAPTURE = Date.parse('2026-09-27T03:55:00Z');
const series = (livegrid as { series: Record<string, unknown[]> }).series;
const CONTRACT_KEYS = [
  'SNAPSHOT-HUBS:HB_HOUSTON', 'SNAPSHOT-HUBS:HB_NORTH', 'SNAPSHOT-HUBS:HB_SOUTH', 'SNAPSHOT-HUBS:HB_WEST',
  'SNAPSHOT-SCED:lambda', 'NP4-190-CD:HB_HUBAVG', 'SNAPSHOT-DEMAND:ERCOT',
];

let historyUrls: URL[];
let historyRows: (key: string) => unknown[];

/** Overview stub: fixture GETs, history rows by report_id:zone. */
function overviewFetch(input: RequestInfo | URL): Reply {
  const url = new URL(String(input), 'http://localhost');
  if (url.pathname === '/v1/signals/history') {
    historyUrls.push(url);
    return reply(200, historyRows(`${url.searchParams.get('report_id')}:${url.searchParams.get('zone')}`));
  }
  const body = (overview as Record<string, unknown>)[url.pathname];
  return body === undefined ? notFound(url.pathname) : reply(200, body);
}

/** Let the panel's startup wait and spaced reads run on the frozen clock. Short steps:
    each act() exit commits React updates, whose effects schedule the next timers. */
const settle = async (ms = 10_000) => { for (let t = 0; t < ms; t += 250) await act(() => vi.advanceTimersByTimeAsync(250)); };

async function livePanel() {
  render(<Overview />);
  await settle();
  return await screen.findByRole('region', { name: /live grid/i });
}

beforeEach(() => {
  localStorage.clear();
  window.location.hash = '#/';
  historyUrls = [];
  historyRows = key => series[key] ?? [];
  vi.useFakeTimers({ now: CAPTURE, shouldAdvanceTime: true });
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} });
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => overviewFetch(input)));
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  window.location.hash = '';
});

describe('XR-B live grid (review 1, F3, F6, F7, F8, F10)', () => {
  it('review 1 + F3: reads the stored snapshot and poll keys, titles actual demand, and names the day-ahead hub', async () => {
    const panel = await livePanel();
    await within(panel).findByText(/76,715\s*MW/);
    const asked = historyUrls.map(u => `${u.searchParams.get('report_id')}:${u.searchParams.get('zone')}`);
    expect(new Set(asked)).toEqual(new Set(CONTRACT_KEYS));
    expect(within(panel).getByRole('heading', { name: /ERCOT actual demand/i })).toBeTruthy();
    expect(within(panel).queryByText(/total demand|NP3-565-CD/i)).toBeNull();
    const legend = within(panel).getByRole('group', { name: /grid series/i });
    expect(within(legend).getByText(/HB_HUBAVG day-ahead/i)).toBeTruthy();
    expect(within(legend).getByText(/system lambda/i)).toBeTruthy();
  });

  it('F6: empty live grid says what to do, links the setup docs, and disables CSV', async () => {
    historyRows = () => [];
    const panel = await livePanel();
    const prices = await within(panel).findByText(/No ERCOT price observations yet/i);
    expect(prices.textContent).toMatch(/GRIDMARKET_WORKER_URL/);
    expect(within(prices).getByRole('link', { name: /setup docs/i }).getAttribute('href')).toBe('#/spec');
    const demand = within(panel).getByText(/No ERCOT demand observations yet/i);
    expect(within(demand).getByRole('link', { name: /setup docs/i })).toBeTruthy();
    expect((within(panel).getByRole('button', { name: /download csv/i }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('F7: the series legend is a group, not a navigation landmark', async () => {
    const panel = await livePanel();
    await within(panel).findByText(/76,715\s*MW/);
    expect(within(panel).queryAllByRole('navigation')).toHaveLength(0);
    const legend = within(panel).getByRole('group', { name: /grid series/i });
    expect(within(legend).getByRole('link', { name: /HB_WEST/ }).getAttribute('href')).toContain('#/market');
  });

  it('F8: the 48 h range is written to the URL and restored on reload', async () => {
    let panel = await livePanel();
    fireEvent.click(within(panel).getByRole('button', { name: /48\s*h/i }));
    await waitFor(() => expect(window.location.hash).toContain('range=48'));
    cleanup();
    historyUrls = [];
    panel = await livePanel();
    expect(within(panel).getByRole('button', { name: /48\s*h/i }).getAttribute('aria-pressed')).toBe('true');
    await waitFor(() => expect(historyUrls.length).toBeGreaterThan(0));
    const span = Date.parse(historyUrls[0].searchParams.get('end')!) - Date.parse(historyUrls[0].searchParams.get('start')!);
    expect(span).toBe(48 * 3600_000);
  });

  it('F10: the CSV uses the shared export convention (CRLF, Central stamps, gridmarket name, API query, status)', async () => {
    const blobs: string[] = [];
    vi.stubGlobal('URL', Object.assign(class extends URL {}, {
      createObjectURL: (blob: { parts?: string[] }) => { blobs.push(String(blob.parts?.join(''))); return 'blob:x'; },
      revokeObjectURL: () => {},
    }));
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    const RealBlob = Blob;
    vi.stubGlobal('Blob', class extends RealBlob { parts: string[]; constructor(parts: string[], o?: BlobPropertyBag) { super(parts, o); this.parts = parts; } });
    const panel = await livePanel();
    await within(panel).findByText(/76,715\s*MW/);
    expect(within(panel).getByRole('button', { name: /copy api query/i }).getAttribute('title')).toContain('/v1/signals/history?report_id=SNAPSHOT-HUBS');
    fireEvent.click(within(panel).getByRole('button', { name: /download csv/i }));
    const status = await within(panel).findByText(/^Downloaded gridmarket-live-grid-24h-2026-09-26\.csv$/);
    expect(status.getAttribute('role')).toBe('status');
    const csv = blobs[0];
    expect(csv.split('\r\n')[0]).toBe('interval_start_utc,interval_start_central,series,report_id,subject,value,unit,published_at_utc,source');
    expect(csv).toContain('2026-09-27T03:53:40Z,2026-09-26 22:53:40 CDT,ERCOT actual demand,SNAPSHOT-DEMAND,ERCOT,66285,MW,2026-09-27T03:53:40Z,');
    expect(csv).toContain('HB_HUBAVG day-ahead,NP4-190-CD,HB_HUBAVG,37.85');
    expect(csv).not.toMatch(/[^\r]\n/);
  });
});

describe('XR-B F5 cold Overview load against the per-IP bucket', () => {
  it('no 429 when history reads share the bucket with the first polls (20-token non-public clamp)', async () => {
    // Model of api.py Boundary: one anonymous IP bucket; public GETs refill 30/s up to 60,
    // every other request clamps it to 20 and refills 10/s; a request below 1 token is 429.
    const PUBLIC = ['/v1/market', '/v1/predictions', '/v1/signals', '/v1/providers', '/v1/router', '/v1/bots'];
    let tokens = 20;
    let at = Date.now();
    const statuses: number[] = [];
    const take = (path: string) => {
      const pub = PUBLIC.some(p => path === p || path.startsWith(p + '/'));
      const [rate, burst] = pub ? [30, 60] : [10, 20];
      const now = Date.now();
      tokens = Math.min(burst, tokens + (now - at) / 1000 * rate);
      at = now;
      if (tokens < 1) return false;
      tokens -= 1;
      return true;
    };
    // Cold page load: index.html, the entry script, the stylesheet and the preloaded font.
    for (const asset of ['/', '/assets/index.js', '/assets/index.css', '/fonts/inter-latin-var.woff2']) take(asset);
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), 'http://localhost').pathname;
      if (!take(path)) { statuses.push(429); return reply(429, { error: { code: 'RATE_LIMITED', message: 'Rate limited' } }, { 'Retry-After': '1' }); }
      const r = overviewFetch(input);
      statuses.push(r.status);
      return r;
    }));
    render(<Overview />);
    const panel = await screen.findByRole('region', { name: /live grid/i });
    await settle(30_000);
    await within(panel).findByText(/76,715\s*MW/);
    expect(historyUrls.length).toBe(CONTRACT_KEYS.length);
    expect(statuses.filter(s => s === 429)).toEqual([]);
  });
});

describe('XR-B track record (review 4, F6)', () => {
  const event = (i: number, probability: number, outcome: boolean) => ({
    subject: `LZ_HOUSTON:2026-09-${String(1 + (i % 28)).padStart(2, '0')}T${String(i % 24).padStart(2, '0')}:00:00+00:00#${i}`,
    zone: 'LZ_HOUSTON', delivery_hour: `2026-09-${String(1 + (i % 28)).padStart(2, '0')}T${String(i % 24).padStart(2, '0')}:00:00+00:00`,
    probability, outcome, brier: (probability - (outcome ? 1 : 0)) ** 2,
    resolves_at: `2026-09-${String(1 + (i % 28)).padStart(2, '0')}T${String(i % 24).padStart(2, '0')}:00:00+00:00`,
  });
  const routerFetch = (history: unknown, router: unknown) => vi.fn(async (input: RequestInfo | URL) => {
    const path = new URL(String(input), 'http://localhost').pathname;
    const body = ({ '/v1/predictions': [], '/v1/signals': [], '/v1/router': router, '/v1/router/history': history } as Record<string, unknown>)[path];
    return body === undefined ? notFound(path) : reply(200, body);
  });

  it('review 4: headline Brier comes from the events listed when the population exceeds the page limit', async () => {
    // 51 resolved: 50 newest perfect (Brier 0) on the page, one older miss (Brier 1) dropped by limit=50.
    const page = Array.from({ length: 50 }, (_, i) => event(i, 1, true));
    const dropped = event(50, 1, false);
    vi.stubGlobal('fetch', routerFetch({ events: page, count: 50, limit: 50 }, {
      checks: [], brier: {}, jev_enabled: false, brier_mean: 0.02,
      brier_events: Object.fromEntries([...page, dropped].map(e => [e.subject, e.brier])),
    }));
    render(<Predictions />);
    const panel = await screen.findByRole('region', { name: /forecast track record/i });
    const headline = await within(panel).findByText(/aggregate brier/i);
    expect(headline.textContent).toMatch(/Aggregate Brier 0\.00 across the 50 resolved events listed/);
  });

  it('F6: empty track record says how forecasts resolve and links the setup docs', async () => {
    vi.stubGlobal('fetch', routerFetch({ events: [], count: 0, limit: 50 }, { checks: [], brier: {}, jev_enabled: false }));
    render(<Predictions />);
    const panel = await screen.findByRole('region', { name: /forecast track record/i });
    const empty = await within(panel).findByText(/not enough resolved forecasts yet: 0 of 20/i);
    expect(empty.textContent).toMatch(/resolve against ERCOT prices once the feed is connected/i);
    expect(within(empty).getByRole('link', { name: /setup docs/i }).getAttribute('href')).toBe('#/spec');
  });
});

describe('XR-B Replay URL and title (F1, F11)', () => {
  const replayFetch = vi.fn(async (input: RequestInfo | URL, init?: Init) => {
    const path = new URL(String(input), 'http://localhost').pathname;
    if (path === '/v1/replay/days') return reply(200, catalog);
    if (path === '/v1/replay' && init?.method === 'POST') return reply(200, (replayFixture as { baseline: unknown }).baseline);
    if (path === '/v1/signals') return reply(200, []);
    return notFound(path);
  });

  it('F1: picking a day then leaving Replay writes no Replay params onto the next page', async () => {
    vi.stubGlobal('fetch', replayFetch);
    window.location.hash = '#/replay';
    render(<Replay />);
    const header = await screen.findByRole('region', { name: /replay day/i });
    const select = within(header).getByRole('combobox', { name: /replay day/i }) as HTMLSelectElement;
    await waitFor(() => expect(select.options.length).toBeGreaterThan(1));
    fireEvent.change(select, { target: { value: '2026-07-20' } });
    await waitFor(() => expect(window.location.hash).toContain('day=2026-07-20'));
    await act(async () => { window.location.hash = '#/predictions'; window.dispatchEvent(new HashChangeEvent('hashchange')); });
    await act(() => vi.advanceTimersByTimeAsync(1000));
    expect(window.location.hash).toBe('#/predictions');
  });

  it('F11: the Replay title names the day and zone only', async () => {
    vi.stubGlobal('fetch', replayFetch);
    window.location.hash = '#/replay?day=2026-08-26&zone=LZ_NORTH&reserve=40&homes=1000&dtype=provider_offline&dstart=2026-08-27T00:00:00Z&dend=2026-08-27T01:00:00Z';
    render(<App />);
    await screen.findByRole('region', { name: /replay day/i });
    expect(document.title).toBe('Replay – day: 2026-08-26 – zone: LZ_NORTH – GridMarket');
  });
});

describe('XR-B checklist step 3 (F9)', () => {
  it('F9: a first order that rests open completes "Place a first order"', async () => {
    vi.setSystemTime(new Date('2026-09-26T17:00:00Z'));
    let placed = false;
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: Init) => {
      const path = new URL(String(input), 'http://localhost').pathname;
      const f = onboarding as Record<string, unknown>;
      if (path === '/v1/orders' && init?.method === 'POST') { placed = true; return reply(200, f['POST /v1/orders']); }
      if (path === '/v1/orders') return reply(200, placed ? [f['POST /v1/orders']] : []);
      const body = f[path];
      return body === undefined ? notFound(path) : reply(200, body);
    }));
    render(<Sandbox />);
    const panel = await screen.findByRole('region', { name: 'Get a key' });
    fireEvent.click(within(panel).getByRole('button', { name: 'Get a sandbox key' }));
    await within(panel).findByText((onboarding as { '/v1/sandbox/keys': { api_key: string } })['/v1/sandbox/keys'].api_key);
    fireEvent.click(within(panel).getByRole('button', { name: 'Place a first order' }));
    const orders = await screen.findByRole('region', { name: 'Your orders' });
    await within(orders).findByText('open');
    const steps = JSON.parse(localStorage.getItem('gm-first-steps') ?? '{}');
    expect(steps.completed).toContain(3);
  });
});
