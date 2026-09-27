// @vitest-environment jsdom
/* God's Eye on the homepage: hero action, feature section with the live embed
   and nav entry, all keyed on VITE_GODSEYE_URL (contract C8: absent when unset).
   Routes reuse s63-exchange.json and s80-replay-days.json (provenance in
   Overview.s63.test.tsx and s80-tour.s80.test.tsx). */
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
// @ts-ignore Vitest supports JSON imports.
import exchange from '../fixtures/s63-exchange.json';
// @ts-ignore Vitest supports JSON imports.
import replayDays from '../fixtures/s80-replay-days.json';
import App from '../App';

const GODSEYE = 'https://views.example.test/godseye/';

beforeEach(() => {
  localStorage.clear();
  window.location.hash = '#/';
  vi.stubEnv('VITE_GODSEYE_URL', GODSEYE);
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const path = new URL(String(input), 'http://localhost').pathname;
    const body = path === '/v1/replay/days' ? replayDays : (exchange as Record<string, unknown>)[path];
    return { ok: body !== undefined, status: body === undefined ? 404 : 200, json: async () => body ?? { error: { code: 'NOT_FOUND', message: 'Not found' } } };
  }));
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  window.location.hash = '';
});

async function storyHero() {
  const hero = await screen.findByRole('region', { name: /Texas home batteries, paid to help when the grid is tight\./ });
  await waitFor(() => expect(hero.getAttribute('aria-busy')).toBe('false'));
  return hero;
}

const external = (link: HTMLElement) => {
  expect(link.getAttribute('href')).toBe(GODSEYE);
  expect(link.getAttribute('target')).toBe('_blank');
  expect(link.getAttribute('rel')).toBe('noreferrer');
};

describe("God's Eye on the homepage", () => {
  it('hero offers a named God\'s Eye action next to the tour, opening in a new tab', async () => {
    render(<App/>);
    const hero = await storyHero();
    const actions = within(hero).getAllByRole('link').filter(a => a.closest('.story-actions'));
    expect(actions.map(a => a.textContent?.trim())).toEqual(['Start the 3-minute tour', "Open God's Eye: live Texas grid", 'Try the sandbox']);
    const action = within(hero).getByRole('link', { name: "Open God's Eye: live Texas grid" });
    external(action);
    expect(action.className).toContain('action-secondary');
  });

  it('feature section sits directly under the hero, above the first-steps checklist, with the live embed', async () => {
    render(<App/>);
    const hero = await storyHero();
    const section = screen.getByRole('region', { name: /^God's Eye ?\.$/ });
    expect(hero.nextElementSibling).toBe(section);
    expect(section.nextElementSibling).toBe(screen.getByRole('region', { name: 'Your first 3 minutes' }));
    expect(within(section).getByText('SEE TEXAS LIVE')).toBeTruthy();
    expect(within(section).getByRole('heading', { level: 2, name: /^God's Eye ?\.$/ })).toBeTruthy();
    expect(within(section).getByText('Live ERCOT demand, prices and all 643 Texas power plants on a 3D map, with GridMarket trades streaming in.')).toBeTruthy();
    const open = within(section).getByRole('link', { name: "Open God's Eye full screen" });
    external(open);
    expect(open.className).toContain('action-primary');
    const tour = within(section).getByRole('link', { name: 'Watch 26 Aug in 3D' });
    expect(tour.getAttribute('href')).toBe('https://views.example.test/replay/#start');
    expect(tour.getAttribute('target')).toBe('_blank');
    expect(tour.getAttribute('rel')).toBe('noreferrer');
    expect(tour.className).toContain('action-secondary');
    expect(open.nextElementSibling).toBe(tour);
    const frame = within(section).getByTitle("God's Eye: live Texas grid");
    expect(frame.tagName).toBe('IFRAME');
    expect(frame.getAttribute('src')).toBe(GODSEYE);
    expect(frame.getAttribute('loading')).toBe('lazy');
    expect(frame.hasAttribute('allowfullscreen')).toBe(true);
  });

  it('nav entry follows Replay, opens God\'s Eye externally and is never the current page', async () => {
    render(<App/>);
    await storyHero();
    const nav = screen.getByRole('navigation', { name: 'Primary' });
    const entry = within(nav).getByRole('link', { name: "God's Eye" });
    external(entry);
    expect(entry.className).toBe('nav-external');
    expect(within(nav).getByRole('link', { name: /Replay/ }).nextElementSibling).toBe(entry);
    expect(entry.hasAttribute('aria-current')).toBe(false);
    expect(nav.querySelectorAll('[aria-current]').length).toBe(1);
  });

  it('keeps the map footer link alongside the new entry points', async () => {
    render(<App/>);
    await storyHero();
    external(screen.getByRole('link', { name: /^Open God's Eye$/ }));
  });

  it('shows no hero action, section or nav entry when VITE_GODSEYE_URL is unset', async () => {
    vi.stubEnv('VITE_GODSEYE_URL', '');
    render(<App/>);
    const hero = await storyHero();
    expect(screen.queryByRole('region', { name: /^God's Eye ?\.$/ })).toBeNull();
    expect(screen.queryByTitle("God's Eye: live Texas grid")).toBeNull();
    expect(screen.queryByRole('link', { name: /God's Eye/ })).toBeNull();
    expect(screen.queryByRole('link', { name: /in 3D/ })).toBeNull();
    expect(within(hero).getAllByRole('link').filter(a => a.closest('.story-actions')).map(a => a.textContent?.trim())).toEqual(['Start the 3-minute tour', 'Try the sandbox']);
  });
});
