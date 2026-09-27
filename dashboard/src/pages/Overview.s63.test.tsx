// @vitest-environment jsdom
/* R7-08 / UX-20 corpus: public HTTP responses from a local seeded backend,
   retrieved 2026-09-26T21:54:50.130939+00:00.
   Signal input: existing esr.json and zones.json corpora (including LZ_LCRA).
   Source routes are JSON keys; transformation: retain first delivery window
   for market and predictions; omit bot feed. All retained rows are unchanged.
   s63-exchange.json SHA-256: 47edf16cbf6abe3fbfc9109f2311f86acb9e9116a74f71246b1b9f0a51f9766c */
import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
// @ts-ignore Vitest supports JSON imports.
import fixture from '../fixtures/s63-exchange.json';
import Overview from './Overview';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it('R7-08 shows exactly the four market load zones; UX-20 preserves measured MW, CT time and stale state without a sparkline', async () => {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const body = (fixture as Record<string, unknown>)[new URL(String(input), 'http://localhost').pathname];
    return { ok: body !== undefined, json: async () => body ?? { error: { message: 'Not found' } } };
  }));
  render(<Overview/>);
  const zones = await screen.findByRole('region', { name: 'Across the load zones' });
  await within(zones).findByRole('rowheader', { name: /Houston/ });
  expect(within(zones).getAllByRole('rowheader').map(e => e.textContent?.trim()).sort()).toEqual(['Houston', 'North', 'South', 'West']);
  const esr = await screen.findByRole('region', { name: 'Texas batteries charging now' });
  expect(await within(esr).findByText(/812\.5/)).toBeTruthy();
  expect(within(esr).getByText('Stale')).toBeTruthy();
  expect(within(esr).getByText('09:00 CT')).toBeTruthy();
  expect(within(esr).queryByRole('img')).toBeNull();
});
