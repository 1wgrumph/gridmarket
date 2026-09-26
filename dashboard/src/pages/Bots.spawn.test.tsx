// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
// @ts-ignore TS2732: Vitest loads JSON; the frozen tsconfig omits resolveJsonModule.
import fixture from '../fixtures/zones.json';
import Bots from './Bots';

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'] });
  vi.setSystemTime(new Date(fixture.clock));
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const body = (fixture as Record<string, unknown>)[new URL(String(input), 'http://localhost').pathname];
    return { ok: body !== undefined, status: body === undefined ? 404 : 200,
      json: async () => body ?? { error: { code: 'NOT_FOUND', message: 'Not found' } } };
  }));
});

afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); });

it('S58-E01 empty admin key shows an accessible inline spawn hint without posting', async () => {
  render(<Bots />);
  const bots = await screen.findByRole('region', { name: 'All bots' });
  await within(bots).findByRole('link', { name: 'bot-0' });
  const panel = await screen.findByRole('region', { name: /Owner.*spawn bots/i });
  const key = await within(panel).findByLabelText('Admin key');
  expect((key as HTMLInputElement).value).toBe('');
  fireEvent.click(await within(panel).findByRole('button', { name: 'Spawn bots' }));
  const hint = await within(panel).findByText('Enter the admin key to spawn bots');
  expect(hint.closest('[role="alert"], [aria-live="polite"], [aria-live="assertive"]')).not.toBeNull();
  expect(vi.mocked(fetch).mock.calls.some(([path, init]) => String(path).includes('/v1/admin/bots') && init?.method === 'POST')).toBe(false);
});
