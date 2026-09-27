// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import App from '../App';
import { centralStamp, toCsv, utcStamp } from '../csv';
import fixture from '../fixtures/x5-export.json';

// Fixture captured from a local backend; provenance is in fixture._provenance.
const HOUSTON = 'FLEX-LZ_HOUSTON-2026-09-27-00';
let responses: Record<string, unknown>;
let calls: string[];
let downloads: { name: string; blob: Blob }[];

beforeEach(() => {
  calls = [];
  downloads = [];
  responses = structuredClone(fixture) as Record<string, unknown>;
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date('2026-09-27T01:30:00Z')); // 2026-09-26 20:30 CDT
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    calls.push(path);
    const body = responses[path];
    return { ok: body !== undefined, status: body === undefined ? 404 : 200, json: async () => body ?? { error: { code: 'NOT_FOUND', message: 'Not found' } } };
  }));
  let pending: Blob | null = null;
  URL.createObjectURL = vi.fn((blob: Blob) => { pending = blob; return 'blob:x5'; });
  URL.revokeObjectURL = vi.fn();
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
    downloads.push({ name: this.download, blob: pending! });
  });
});

afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals(); window.location.hash = ''; });

// jsdom's Blob has no text(); FileReader reads it.
const textOf = (blob: Blob) => new Promise<string>(resolve => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.readAsText(blob); });
const rowsOf = async (blob: Blob) => (await textOf(blob)).trimEnd().split('\r\n').map(line => line.split(','));

async function download(panel: HTMLElement, name: string) {
  fireEvent.click(within(panel).getByRole('button', { name }));
  await waitFor(() => expect(downloads).toHaveLength(1));
  return { name: downloads[0].name, rows: await rowsOf(downloads[0].blob) };
}

describe('X5 CSV exports', () => {
  it('X5-CSV-01 formats cells: quoting, missing as empty, UTC and Central Time stamps', () => {
    expect(toCsv(['a', 'b', 'c'], [['x,y', null, 'say "hi"'], [0, undefined, -1.5]]))
      .toBe('a,b,c\r\n"x,y",,"say ""hi"""\r\n0,,-1.5\r\n');
    expect(utcStamp('2026-09-27 01:28:06')).toBe('2026-09-27T01:28:06Z');
    expect(centralStamp('2026-09-27 01:28:06')).toBe('2026-09-26 20:28:06 CDT');
    expect(centralStamp('2026-12-01T18:00:00+00:00')).toBe('2026-12-01 12:00:00 CST');
    expect(utcStamp('not a time')).toBe('');
  });

  it('X5-CSV-02 Market exports the selected product trades beside the trade list', async () => {
    window.location.hash = `#/market?symbol=${HOUSTON}`;
    render(<App/>);
    const panel = await screen.findByRole('region', { name: 'Recent trades' });
    await within(panel).findByText('2 @ $0.42');
    const { name, rows } = await download(panel, 'Download CSV');
    expect(name).toBe(`gridmarket-trades-${HOUSTON}-2026-09-26.csv`);
    expect(rows[0]).toEqual(['trade_id', 'product_id', 'zone', 'delivery_hour_utc', 'delivery_hour_central', 'traded_at_utc', 'traded_at_central', 'quantity', 'price_cents', 'price_usd', 'value_cents', 'value_usd', 'source']);
    expect(rows).toHaveLength(3);
    const two = rows.find(r => r[7] === '2')!;
    expect(two.slice(1, 12)).toEqual([HOUSTON, 'LZ_HOUSTON', '2026-09-27T05:00:00Z', '2026-09-27 00:00:00 CDT', '2026-09-27T01:28:06Z', '2026-09-26 20:28:06 CDT', '2', '42', '0.42', '84', '0.84']);
    expect(two[12]).toMatch(/simulated/i);
  });

  it('X5-CSV-03 Market exports recent trades across all products from the public history route', async () => {
    window.location.hash = `#/market?symbol=${HOUSTON}`;
    render(<App/>);
    const panel = await screen.findByRole('region', { name: 'Recent trades' });
    await within(panel).findByText('2 @ $0.42');
    const { name, rows } = await download(panel, 'Download CSV · all products');
    expect(calls).toContain('/v1/market/history');
    expect(name).toBe('gridmarket-trades-all-products-2026-09-26.csv');
    expect(rows.slice(1).map(r => r[1]).sort()).toEqual([HOUSTON, HOUSTON, 'FLEX-LZ_NORTH-2026-09-27-00']);
    expect(rows.find(r => r[1] === 'FLEX-LZ_NORTH-2026-09-27-00')!.slice(7, 12)).toEqual(['3', '37', '0.37', '111', '1.11']);
  });

  it('X5-CSV-04 Judge sandbox exports your orders with cents, dollars, UTC and Central Time', async () => {
    window.location.hash = '#/sandbox';
    render(<App/>);
    fireEvent.change(await screen.findByLabelText('Continue with an existing key'), { target: { value: 'gm_fixture_not_a_credential' } });
    fireEvent.click(screen.getByRole('button', { name: 'Use existing key' }));
    const panel = await screen.findByRole('region', { name: 'Your orders' });
    await within(panel).findByText('buy 1 @ $0.12');
    const { name, rows } = await download(panel, 'Download CSV');
    expect(name).toBe('gridmarket-sandbox-orders-2026-09-26.csv');
    expect(rows[0]).toEqual(['order_id', 'product_id', 'side', 'quantity', 'remaining_qty', 'price_cents', 'price_usd', 'status', 'placed_at_utc', 'placed_at_central', 'source']);
    expect(rows).toHaveLength(5);
    expect(rows.find(r => r[0] === '538bfa1987cb4e3bacc605f6661bb018')!.slice(1, 10))
      .toEqual(['FLEX-LZ_NORTH-2026-09-27-00', 'buy', '1', '1', '12', '0.12', 'open', '2026-09-27T01:28:06Z', '2026-09-26 20:28:06 CDT']);
  });

  it('X5-CSV-05 Bot profile exports balance history and settled P&L beside the chart', async () => {
    window.location.hash = '#/bots/bot_0';
    render(<App/>);
    const panel = await screen.findByRole('region', { name: 'Balance history' });
    const { name, rows } = await download(panel, 'Download CSV');
    expect(name).toBe('gridmarket-bot-bot_0-2026-09-26.csv');
    expect(rows[0]).toEqual(['bot_id', 'record', 'at_utc', 'at_central', 'cents', 'usd', 'source']);
    expect(rows[1].slice(0, 6)).toEqual(['bot_0', 'balance', '2026-09-27T01:27:54Z', '2026-09-26 20:27:54 CDT', '52238', '522.38']);
    expect(rows[2].slice(0, 6)).toEqual(['bot_0', 'settled_pnl_total', '2026-09-27T01:30:00Z', '2026-09-26 20:30:00 CDT', '0', '0.00']);
    expect(rows[2][6]).toMatch(/simulated/i);
  });
});
