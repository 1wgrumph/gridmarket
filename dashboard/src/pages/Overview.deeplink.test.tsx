// @vitest-environment jsdom
/* S61b: God's Eye deep link `<origin>/#/?zone=<LZ_ZONE>` ("Trade this zone")
   opens the Overview with that zone's detail panel open and focused. Fixture
   follows zones.json; date and polling are controlled; RTL timeouts stay real. */
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
// @ts-ignore TS2732: Vitest loads JSON; the frozen tsconfig omits resolveJsonModule.
import fixture from '../fixtures/zones.json';
import App from '../App';
import Overview from './Overview';

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'] });
  vi.setSystemTime(new Date(fixture.clock));
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const path = new URL(String(input), 'http://localhost').pathname;
    const body = (fixture as Record<string, unknown>)[path];
    return { ok: body !== undefined, status: body === undefined ? 404 : 200,
      json: async () => body ?? { error: { code: 'NOT_FOUND', message: 'Not found' } } };
  }));
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  window.location.hash = '';
});

async function loadedHero() {
  const hero = await screen.findByRole('region', { name: 'Next delivery prediction' });
  await waitFor(() => expect(hero.getAttribute('aria-busy')).toBe('false'));
  return hero;
}

it('S61b-01 deeplink renders the Overview with that zone detail open and focused', async () => {
  window.location.hash = '#/?zone=LZ_HOUSTON';
  render(<App />);
  expect(await screen.findByRole('heading', { name: /grid overview/i })).toBeTruthy();
  await loadedHero();
  const detail = await screen.findByRole('region', { name: /Houston zone details/i });
  await waitFor(() => expect(detail.contains(document.activeElement)).toBe(true));
  // Same panel as clicking the zone: score, drivers and Market link.
  await waitFor(() => expect(detail.textContent).toMatch(/72\.4\s*%/));
  expect(await within(detail).findByText('price spread')).toBeTruthy();
  expect((await within(detail).findByRole('link', { name: 'Open in Market' })).getAttribute('href')).toBe('#/market');
  // Overview stays the current route with one disclosure line.
  const nav = screen.getByRole('navigation', { name: /primary/i });
  expect(within(nav).getByRole('link', { name: /overview/i }).getAttribute('aria-current')).toBe('page');
  expect(await within(screen.getByRole('main')).findAllByText(/simulated forward flexibility contracts/i)).toHaveLength(1);
});

it('S61b-02 unknown zone value is ignored', async () => {
  window.location.hash = '#/?zone=LZ_NOPE';
  render(<App />);
  expect(await screen.findByRole('heading', { name: /grid overview/i })).toBeTruthy();
  await loadedHero();
  expect(screen.queryByRole('region', { name: /zone details/i })).toBeNull();
});

it('S61b-03 closing the panel clears the zone parameter without a reload', async () => {
  window.location.hash = '#/?zone=LZ_HOUSTON';
  render(<App />);
  await loadedHero();
  const detail = await screen.findByRole('region', { name: /Houston zone details/i });
  fireEvent.click(await within(detail).findByRole('button', { name: /close/i }));
  await waitFor(() => expect(detail.isConnected).toBe(false));
  expect(window.location.hash).toBe('#/');
  expect(screen.getByRole('heading', { name: /grid overview/i })).toBeTruthy();
  await screen.findByRole('region', { name: 'Next delivery prediction' });
});

it('S61b-04 plain hash opens no panel and leaves the hash alone', async () => {
  window.location.hash = '#/';
  render(<Overview />);
  await loadedHero();
  expect(screen.queryByRole('region', { name: /zone details/i })).toBeNull();
  expect(window.location.hash).toBe('#/');
});
