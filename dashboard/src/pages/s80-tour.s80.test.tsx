// @vitest-environment jsdom
/* S80 red tests: story hero, guided tour and grouped navigation (C8).
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

async function tourStep(n: number) {
  const tour = await screen.findByRole('region', { name: 'Guided tour' });
  await within(tour).findByText(new RegExp(`step ${n} of 4`, 'i'));
  await waitFor(() => expect(tour.getAttribute('aria-busy')).toBe('false'));
  return tour;
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
    expect(within(hero).getByRole('link', { name: /Watch batteries play that day/ }).getAttribute('href')).toBe('#/replay');
  });

  it.each<Replay>(['missing', 'failing'])('S80-04 the replay card omits the number when the replay API is %s', async mode => {
    replay = mode;
    render(<Overview/>);
    const hero = await storyHero();
    await waitFor(() => expect(vi.mocked(fetch).mock.calls.some(([url]) => String(url).includes('/v1/replay/days'))).toBe(true));
    expect(within(hero).getByRole('link', { name: /Watch batteries play that day/ }).getAttribute('href')).toBe('#/replay');
    expect(hero.textContent).not.toMatch(priceLike);
  });
});

const steps: Array<[RegExp, string | null, string | null]> = [
  [/Texas, when the grid is tight/, "Open God's Eye", GODSEYE],
  [/Replay a real day/, 'Open the replay', '#/replay'],
  [/Your turn/, 'Try it in the replay', '#/replay'],
  [/Proof: a live market/, 'Open the judge sandbox', '#/sandbox'],
];

describe('S80 guided tour', () => {
  it('S80-05 four steps, each with progress, one heading with focus, one sentence and exactly one action', async () => {
    window.location.hash = '#/tour';
    render(<App/>);
    for (const [i, [heading, action, href]] of steps.entries()) {
      const tour = await tourStep(i + 1);
      const title = within(tour).getByRole('heading', { level: 1, name: heading });
      await waitFor(() => expect(document.activeElement).toBe(title));
      const actions = within(tour).getAllByRole('link').filter(a => !/skip tour|finish tour/i.test(a.textContent ?? ''));
      expect(actions.map(a => a.textContent)).toEqual([action]);
      expect(actions[0].getAttribute('href')).toBe(href);
      if (i < 3) fireEvent.click(within(tour).getByRole('button', { name: /^Next/ }));
    }
    const last = await tourStep(4);
    expect(within(last).queryByRole('button', { name: /^Next/ })).toBeNull();
    expect(within(last).getByRole('link', { name: 'Finish tour' }).getAttribute('href')).toBe('#/');
  });

  it('S80-06 Back returns focus to the previous step heading; Skip tour and Escape return to the Overview', async () => {
    window.location.hash = '#/tour';
    render(<App/>);
    let tour = await tourStep(1);
    expect((within(tour).getByRole('button', { name: 'Back' }) as HTMLButtonElement).disabled).toBe(true);
    expect(within(tour).getByRole('link', { name: 'Skip tour' }).getAttribute('href')).toBe('#/');
    fireEvent.click(within(tour).getByRole('button', { name: /^Next/ }));
    tour = await tourStep(2);
    fireEvent.click(within(tour).getByRole('button', { name: 'Back' }));
    tour = await tourStep(1);
    const title = within(tour).getByRole('heading', { level: 1, name: steps[0][0] });
    await waitFor(() => expect(document.activeElement).toBe(title));
    fireEvent.keyDown(document.activeElement!, { key: 'Escape' });
    await waitFor(() => expect(window.location.hash).toBe('#/'));
    go('#/');
    await storyHero();
    expect(screen.queryByRole('region', { name: 'Guided tour' })).toBeNull();
  });

  it('S80-07 the hook step states the peak price, point and interval from the API', async () => {
    window.location.hash = '#/tour';
    render(<App/>);
    const tour = await tourStep(1);
    await waitFor(() => expect(tour.textContent).toMatch(/\$798\.50/));
    expect(tour.textContent).toMatch(/West Texas/);
    expect(tour.textContent).toMatch(/10:00\s?PM CT/);
    expect(tour.textContent).toMatch(/August 26, 2026/);
  });

  it.each<Replay>(['missing', 'failing'])('S80-08 the hook step omits the number when the replay API is %s', async mode => {
    replay = mode;
    window.location.hash = '#/tour';
    render(<App/>);
    const tour = await tourStep(1);
    await waitFor(() => expect(vi.mocked(fetch).mock.calls.some(([url]) => String(url).includes('/v1/replay/days'))).toBe(true));
    within(tour).getByRole('heading', { level: 1, name: steps[0][0] });
    expect(tour.textContent).not.toMatch(priceLike);
  });

  it("S80-09 hides the God's Eye link when VITE_GODSEYE_URL is unset", async () => {
    vi.stubEnv('VITE_GODSEYE_URL', '');
    window.location.hash = '#/tour';
    render(<App/>);
    const tour = await tourStep(1);
    expect(within(tour).queryByRole('link', { name: /God's Eye/ })).toBeNull();
  });

  it('S80-10 (lane state) the Replay route says it arrives with the full build', async () => {
    window.location.hash = '#/replay';
    render(<App/>);
    const main = screen.getByRole('main');
    expect(within(main).getByRole('heading', { level: 1, name: /replay/i })).toBeTruthy();
    expect(within(main).getByText(/Replay arrives with the full build/)).toBeTruthy();
  });
});

const label = (a: HTMLElement) => (a.textContent ?? '').replace(/^\d+\s*/, '').trim();

describe('S80 navigation', () => {
  it('S80-11 primary links are Overview, Tour, Replay, Market and Judge sandbox; More groups the rest', async () => {
    render(<App/>);
    const nav = screen.getByRole('navigation', { name: 'Primary' });
    const more = within(nav).getByRole('button', { name: 'More' });
    const group = within(nav).getByRole('group', { name: 'More pages' });
    expect(more.getAttribute('aria-controls')).toBe(group.id);
    const inGroup = new Set(within(group).getAllByRole('link'));
    const primary = within(nav).getAllByRole('link').filter(a => !inGroup.has(a));
    expect(primary.map(label)).toEqual(['Overview', 'Tour', 'Replay', 'Market', 'Judge sandbox']);
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

  it('S80-14 the tour route marks Tour as the current page', async () => {
    window.location.hash = '#/tour?step=2';
    render(<App/>);
    await tourStep(2);
    const nav = screen.getByRole('navigation', { name: 'Primary' });
    expect(within(nav).getByRole('link', { name: /Tour/ }).getAttribute('aria-current')).toBe('page');
  });
});
