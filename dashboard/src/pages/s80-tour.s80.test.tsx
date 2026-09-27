// @vitest-environment jsdom
/* S80 red tests: story hero, first-run checklist and grouped navigation (DEC-GM-128).
   s80-replay-days.json: public HTTP response of GET /v1/replay/days from a
   local backend running the S69 replay engine (dataset day 2026-08-26),
   retrieved 2026-09-26T22:36:44Z, stored unchanged.
   SHA-256 25dede5fb5f94fa30264eda35d216c5f495f95cf303d2cf71eda99fc3f111c81.
   Every other route reuses s63-exchange.json (provenance in
   Overview.s63.test.tsx). Peak: LZ_WEST, 2026-08-27T03:00Z = 10:00 PM CDT on
   26 August, $798.50/MWh. No wall-clock assertions. */
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
// @ts-ignore Vitest supports JSON imports.
import exchange from '../fixtures/s63-exchange.json';
// @ts-ignore Vitest supports JSON imports.
import replayDays from '../fixtures/s80-replay-days.json';
import App from '../App';
import Overview from './Overview';

type Replay = 'served' | 'missing' | 'failing';
let replay: Replay;
const GODSEYE = 'https://views.example.test/godseye/';

beforeEach(() => {
  replay = 'served';
  localStorage.clear();
  window.location.hash = '#/';
  vi.stubEnv('VITE_GODSEYE_URL', GODSEYE);
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const path = new URL(String(input), 'http://localhost').pathname;
    if (path === '/v1/replay/days') {
      if (replay === 'failing') throw new TypeError('Failed to fetch');
      if (replay === 'missing') return { ok: false, status: 404, json: async () => ({ error: { code: 'NOT_FOUND', message: 'Not Found' } }) };
      return { ok: true, status: 200, json: async () => replayDays };
    }
    const body = (exchange as Record<string, unknown>)[path];
    return { ok: body !== undefined, status: body === undefined ? 404 : 200, json: async () => body ?? { error: { code: 'NOT_FOUND', message: 'Not found' } } };
  }));
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  window.location.hash = '';
});

const go = (hash: string) => act(() => {
  window.location.hash = hash;
  window.dispatchEvent(new Event('hashchange'));
});

async function storyHero() {
  const hero = await screen.findByRole('region', { name: /Texas home batteries, paid to help when the grid is tight\./ });
  await waitFor(() => expect(hero.getAttribute('aria-busy')).toBe('false'));
  return hero;
}

const priceLike = /\$\s?\d|MWh/;

describe('S80 Overview hero', () => {
  it('S80-01 leads with the product sentence as the page heading and the C8 subline', async () => {
    render(<Overview/>);
    const hero = await storyHero();
    expect(within(hero).getByRole('heading', { level: 1, name: /Texas home batteries, paid to help when the grid is tight\./ })).toBeTruthy();
    expect(within(hero).getByText('A simulated flexibility exchange running on real ERCOT conditions.')).toBeTruthy();
  });

  it('S80-02 offers a primary Start the 3-minute tour action before a secondary Try the sandbox link', async () => {
    render(<Overview/>);
    const hero = await storyHero();
    const tour = within(hero).getByRole('link', { name: 'Start the 3-minute tour' });
    const sandbox = within(hero).getByRole('link', { name: 'Try the sandbox' });
    expect(tour.getAttribute('href')).toBe('#/tour');
    expect(sandbox.getAttribute('href')).toBe('#/sandbox');
    expect(tour.compareDocumentPosition(sandbox) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("S80-03 the replay card states the replay day's peak price, point and interval from the API", async () => {
    render(<Overview/>);
    const hero = await storyHero();
    await waitFor(() => expect(hero.textContent).toMatch(/\$798\.50/));
    expect(hero.textContent).toMatch(/Wednesday, August 26, 2026/);
    expect(hero.textContent).toMatch(/West Texas/);
    expect(hero.textContent).toMatch(/10:00\s?PM CT/);
    expect(within(hero).getByRole('link', { name: /Watch batteries play that day/ }).getAttribute('href')).toBe('#/replay?day=2026-08-26');
  });

  it.each<Replay>(['missing', 'failing'])('S80-04 the replay card omits the number when the replay API is %s', async mode => {
    replay = mode;
    render(<Overview/>);
    const hero = await storyHero();
    await waitFor(() => expect(vi.mocked(fetch).mock.calls.some(([url]) => String(url).includes('/v1/replay/days'))).toBe(true));
    expect(within(hero).getByRole('link', { name: /Watch batteries play that day/ }).getAttribute('href')).toBe('#/replay?day=2026-08-26');
    expect(hero.textContent).not.toMatch(priceLike);
  });
});

describe('S80 first-run checklist', () => {
  it('S80-05 legacy tour redirects to the Overview checklist with three real task links', async () => {
    window.location.hash = '#/tour';
    render(<App/>);
    const checklist = await screen.findByRole('region', { name: 'Your first 3 minutes' });
    await waitFor(() => expect(window.location.hash).toBe('#/?start=1'));
    const links = within(checklist).getAllByRole('link');
    expect(links.map(a => a.textContent)).toEqual(['See the real day', 'Change the outcome', 'Place a first order']);
    expect(links.map(a => a.getAttribute('href'))).toEqual(['#/replay?day=2026-08-26', '#/replay?day=2026-08-26&step=2', '#/sandbox']);
    expect(screen.queryByRole('region', { name: 'Guided tour' })).toBeNull();
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
  });

  it('S80-06 dismissal persists; Start here reopens and focuses the checklist', async () => {
    render(<App/>);
    let panel = await screen.findByRole('region', { name: 'Your first 3 minutes' });
    fireEvent.click(within(panel).getByRole('button', { name: 'Dismiss checklist' }));
    expect(screen.queryByRole('region', { name: 'Your first 3 minutes' })).toBeNull();
    go('#/market'); go('#/');
    expect(screen.queryByRole('region', { name: 'Your first 3 minutes' })).toBeNull();
    go('#/tour');
    panel = await screen.findByRole('region', { name: 'Your first 3 minutes' });
    await waitFor(() => expect(document.activeElement).toBe(within(panel).getByRole('heading', { name: 'Your first 3 minutes' })));
  });

  it('S80-07 opening a destination does not falsely complete a checklist action', async () => {
    render(<App/>);
    go('#/replay?day=2026-08-26');
    const main = screen.getByRole('main');
    expect(await within(main).findByText(/Step 1 of 3/)).toBeTruthy();
    expect(within(main).getByRole('link', { name: /Next: Change the outcome/ }).getAttribute('href')).toBe('#/replay?day=2026-08-26&step=2');
    go('#/');
    const panel = await screen.findByRole('region', { name: 'Your first 3 minutes' });
    expect(within(panel).queryByText('Complete')).toBeNull();
  });

  it('S80-08 the checklist still works when browser storage is blocked', async () => {
    const read = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('Storage blocked'); });
    const write = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('Storage blocked'); });
    try {
      render(<App/>);
      const panel = await screen.findByRole('region', { name: 'Your first 3 minutes' });
      fireEvent.click(within(panel).getByRole('button', { name: 'Dismiss checklist' }));
      expect(screen.queryByRole('region', { name: 'Your first 3 minutes' })).toBeNull();
    } finally { read.mockRestore(); write.mockRestore(); }
  });

  it("S80-09 hides the God's Eye link when VITE_GODSEYE_URL is unset", async () => {
    vi.stubEnv('VITE_GODSEYE_URL', '');
    render(<App/>);
    await storyHero();
    expect(screen.queryByRole('link', { name: /God's Eye/ })).toBeNull();
  });

  it('S80-10 Replay has an honest lane state and contextual next steps', async () => {
    window.location.hash = '#/replay?day=2026-08-26&step=2';
    render(<App/>);
    const main = screen.getByRole('main');
    expect(within(main).getByText(/Replay arrives with the full build/)).toBeTruthy();
    expect(within(main).getByRole('link', { name: /Next: Place a first order/ }).getAttribute('href')).toBe('#/sandbox');
  });
});

const label = (a: HTMLElement) => (a.textContent ?? '').replace(/^\d+\s*/, '').trim();

describe('S80 navigation', () => {
  it('S80-11 primary links are Overview, Start here, Replay, Market and Judge sandbox; More groups the rest', async () => {
    render(<App/>);
    const nav = screen.getByRole('navigation', { name: 'Primary' });
    const more = within(nav).getByRole('button', { name: 'More' });
    fireEvent.click(more);
    const group = within(nav).getByRole('group', { name: 'More pages' });
    expect(more.getAttribute('aria-controls')).toBe(group.id);
    const inGroup = new Set(within(group).getAllByRole('link'));
    const primary = within(nav).getAllByRole('link').filter(a => !inGroup.has(a));
    expect(primary.map(label)).toEqual(['Overview', 'Start here', 'Replay', 'Market', 'Judge sandbox']);
    expect(primary.map(a => a.getAttribute('href'))).toEqual(['#/', '#/tour', '#/replay', '#/market', '#/sandbox']);
    expect([...inGroup].map(label)).toEqual(['Predictions', 'Providers', 'Bots', 'Spec']);
    expect([...inGroup].map(a => a.getAttribute('href'))).toEqual(['#/predictions', '#/providers', '#/bots', '#/spec']);
  });

  it('S80-12 More is a disclosure button with aria-expanded', async () => {
    render(<App/>);
    const nav = screen.getByRole('navigation', { name: 'Primary' });
    const more = within(nav).getByRole('button', { name: 'More' });
    expect(more.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(more);
    expect(more.getAttribute('aria-expanded')).toBe('true');
    fireEvent.click(more);
    expect(more.getAttribute('aria-expanded')).toBe('false');
  });

  it('S80-13 on a More page the group opens and marks the current page', async () => {
    window.location.hash = '#/bots';
    render(<App/>);
    const nav = screen.getByRole('navigation', { name: 'Primary' });
    expect(within(nav).getByRole('button', { name: 'More' }).getAttribute('aria-expanded')).toBe('true');
    const group = within(nav).getByRole('group', { name: 'More pages' });
    expect(within(group).getByRole('link', { name: /Bots/ }).getAttribute('aria-current')).toBe('page');
  });

  it('S80-14 routes have a title and carry zone and time through navigation', async () => {
    window.location.hash = '#/predictions?zone=LZ_HOUSTON&hour=2026-08-27T03%3A00%3A00Z';
    render(<App/>);
    await waitFor(() => expect(document.title).toMatch(/Predictions.*LZ_HOUSTON.*GridMarket/));
    const nav = screen.getByRole('navigation', { name: 'Primary' });
    for (const name of ['Overview', 'Replay', 'Market']) {
      const href = within(nav).getByRole('link', { name: new RegExp(name) }).getAttribute('href')!;
      const params = new URLSearchParams(href.split('?')[1]);
      expect(params.get('zone')).toBe('LZ_HOUSTON');
      expect(params.get('hour')).toBe('2026-08-27T03:00:00Z');
    }
    expect(within(nav).getAllByRole('link').filter(a => a.getAttribute('aria-current') === 'page')).toHaveLength(1);
  });
});
