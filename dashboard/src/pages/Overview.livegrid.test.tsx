// @vitest-environment jsdom
/**
 * Overview Live Grid panel tests (DEC-GM-142).
 * Verifies real ERCOT signals plotted as live charts with history from
 * GET /v1/signals/history (bounded 48 h):
 * 1. Panel header says 'Real ERCOT data' with source, last published time, 24 h / 48 h picker.
 * 2. Real-time prices for HB_HOUSTON, HB_NORTH, HB_SOUTH, HB_WEST, system lambda, and day-ahead dashed line.
 * 3. ERCOT-total demand against today's peak as a small second chart.
 * 4. Clicking hub line or legend item opens Market filtered to that zone (FLOW-027).
 * 5. 'Download CSV' button exports exactly plotted series with header row.
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
// @ts-ignore TS2732: Vitest loads JSON; frozen tsconfig omits resolveJsonModule.
import fixture from '../fixtures/overview.json';
import Overview from './Overview';

type HistoryRow = {
  interval_start: string;
  interval_end: string;
  value: number;
  unit: string;
  published_at: string;
  stale: boolean;
};

const BASE_TIME = '2026-09-26T14:00:00Z';
const PUBLISHED_TIME = '2026-09-26T14:04:10Z';

function makeHourRows(count: number, baseValue: number, unit = '$/MWh', stepMinutes = 60): HistoryRow[] {
  const base = Date.parse(BASE_TIME);
  const rows: HistoryRow[] = [];
  for (let i = count; i >= 1; i--) {
    const startMs = base - i * stepMinutes * 60_000;
    const endMs = startMs + stepMinutes * 60_000;
    rows.push({
      interval_start: new Date(startMs).toISOString(),
      interval_end: new Date(endMs).toISOString(),
      value: baseValue + (count - i) * 1.5,
      unit,
      published_at: PUBLISHED_TIME,
      stale: false,
    });
  }
  return rows;
}

const mockHistoryData: Record<string, HistoryRow[]> = {
  'NP6-905-CD:HB_HOUSTON': makeHourRows(24, 45.0),
  'NP6-905-CD:HB_NORTH': makeHourRows(24, 48.0),
  'NP6-905-CD:HB_SOUTH': makeHourRows(24, 42.0),
  'NP6-905-CD:HB_WEST': makeHourRows(24, 52.0),
  'NP6-905-CD:lambda': makeHourRows(24, 38.0),
  'NP4-190-CD:HB_HOUSTON': makeHourRows(24, 44.0),
  'NP4-190-CD:HB_NORTH': makeHourRows(24, 47.0),
  // NP3-565-CD stores per-LZ rollups; the panel sums them to the ERCOT total.
  'NP3-565-CD:LZ_HOUSTON': makeHourRows(24, 17000.0, 'MW'),
  'NP3-565-CD:LZ_NORTH': makeHourRows(24, 20000.0, 'MW'),
  'NP3-565-CD:LZ_SOUTH': makeHourRows(24, 18000.0, 'MW'),
  'NP3-565-CD:LZ_WEST': makeHourRows(24, 13000.0, 'MW'),
};

let requestedUrls: string[] = [];
let failFirstLzNorth = true;

beforeEach(() => {
  window.location.hash = '#/';
  requestedUrls = [];
  failFirstLzNorth = true;
  vi.stubGlobal('ResizeObserver', class {
    observe() {}
    unobserve() {}
    disconnect() {}
  });

  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const urlStr = String(input);
    requestedUrls.push(urlStr);
    const parsed = new URL(urlStr, 'http://localhost');
    const path = parsed.pathname;

    if (path === '/v1/signals/history') {
      const reportId = parsed.searchParams.get('report_id') ?? '';
      const zone = parsed.searchParams.get('zone') ?? '';
      const key = `${reportId}:${zone}`;
      // The Overview burst can 429; the panel retries once (Retry-After 0).
      if (key === 'NP3-565-CD:LZ_NORTH' && failFirstLzNorth) {
        failFirstLzNorth = false;
        return {
          ok: false,
          status: 429,
          headers: { get: () => '0' },
          json: async () => ({ error: { code: 'RATE_LIMITED', message: 'Slow down' } }),
        };
      }
      const data = mockHistoryData[key] ?? [];
      return {
        ok: true,
        status: 200,
        json: async () => data,
      };
    }

    const body = (fixture as Record<string, unknown>)[path];
    if (body === undefined) {
      return { ok: false, status: 404, json: async () => ({ error: { code: 'NOT_FOUND', message: path } }) };
    }
    return { ok: true, status: 200, json: async () => body };
  }));
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  window.location.hash = '';
});

describe('Live grid panel (X1 extras wave, DEC-GM-142)', () => {
  it('1. renders panel header with "Real ERCOT data", source, last published time in Central Time, and 24 h picker default', async () => {
    render(<Overview />);
    const panel = await screen.findByRole('region', { name: /live grid/i });
    expect(panel).toBeDefined();

    const panelScope = within(panel);
    expect(await panelScope.findByText(/Real ERCOT data/i)).toBeDefined();
    expect((await panelScope.findAllByText(/ERCOT/i)).length).toBeGreaterThan(0);
    // Central time formatting on published time
    expect(await panelScope.findByText(/CT/i)).toBeDefined();

    // Range picker defaults to 24 h
    const btn24 = await panelScope.findByRole('button', { name: /24\s*h/i });
    const btn48 = await panelScope.findByRole('button', { name: /48\s*h/i });
    expect(btn24).toBeDefined();
    expect(btn48).toBeDefined();
    expect(btn24.getAttribute('aria-pressed')).toBe('true');
  });

  it('2. fetches and plots real-time prices for hubs and system lambda plus day-ahead dashed line', async () => {
    render(<Overview />);
    const panel = await screen.findByRole('region', { name: /live grid/i });
    const panelScope = within(panel);

    // Verify all 5 required real-time series and day-ahead are represented in the legend/chart
    expect((await panelScope.findAllByText(/HB_HOUSTON/i)).length).toBeGreaterThan(0);
    expect((await panelScope.findAllByText(/HB_NORTH/i)).length).toBeGreaterThan(0);
    expect((await panelScope.findAllByText(/HB_SOUTH/i)).length).toBeGreaterThan(0);
    expect((await panelScope.findAllByText(/HB_WEST/i)).length).toBeGreaterThan(0);
    expect((await panelScope.findAllByText(/system lambda/i)).length).toBeGreaterThan(0);
    expect((await panelScope.findAllByText(/day-ahead/i)).length).toBeGreaterThan(0);

    // Verify /v1/signals/history calls were made
    await waitFor(() => {
      const historyCalls = requestedUrls.filter(u => u.includes('/v1/signals/history'));
      expect(historyCalls.length).toBeGreaterThanOrEqual(4);
    });
  });

  it('3. renders ERCOT-total demand against today\'s peak as a small second chart', async () => {
    render(<Overview />);
    const panel = await screen.findByRole('region', { name: /live grid/i });
    const panelScope = within(panel);

    expect(await panelScope.findByText(/ERCOT Total Demand|Demand/i)).toBeDefined();
    expect(await panelScope.findByText(/today's peak|peak/i)).toBeDefined();
    expect((await panelScope.findAllByText(/MW/i)).length).toBeGreaterThan(0);
    // Peak is the max of the summed LZ rollups: 68000 + 4 * 23 * 1.5 = 68138.
    expect(await panelScope.findByText(/68,138\s*MW/i)).toBeDefined();
  });

  it('4. clicking a hub line or legend item opens Market filtered to that zone (FLOW-027)', async () => {
    render(<Overview />);
    const panel = await screen.findByRole('region', { name: /live grid/i });
    const panelScope = within(panel);

    const houstonItem = await panelScope.findByText(/HB_HOUSTON/i);
    fireEvent.click(houstonItem);

    // URL context carry: opens Market filtered to Houston zone (LZ_HOUSTON)
    expect(window.location.hash).toContain('/market');
    expect(window.location.hash).toMatch(/zone=(?:LZ_HOUSTON|HB_HOUSTON)/);
  });

  it('5. "Download CSV" button exports exactly the plotted series with the required header row', async () => {
    const createObjectURL = vi.fn().mockReturnValue('blob:mock-csv');
    const revokeObjectURL = vi.fn();
    (globalThis as any).URL.createObjectURL = createObjectURL;
    (globalThis as any).URL.revokeObjectURL = revokeObjectURL;
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

    render(<Overview />);
    const panel = await screen.findByRole('region', { name: /live grid/i });
    const panelScope = within(panel);

    const downloadBtn = await panelScope.findByRole('button', { name: /download csv/i });
    expect(downloadBtn).toBeDefined();
    // Await loaded data (rule 3): the CSV must cover the plotted series.
    await panelScope.findByText(/68,138\s*MW/i);

    let capturedBlob: Blob | null = null;
    vi.spyOn(globalThis, 'Blob').mockImplementation(function (content: any, options: any) {
      capturedBlob = { content, options } as any;
      return capturedBlob as any;
    });

    fireEvent.click(downloadBtn);

    expect(createObjectURL).toHaveBeenCalled();
    expect(capturedBlob).not.toBeNull();
    const csvText = (capturedBlob as any).content.join('');
    const lines = csvText.trim().split('\n');
    expect(lines[0].trim()).toBe('timestamp_utc,timestamp_ct,series,value,unit,published_at');
    expect(lines.length).toBeGreaterThan(1);
    // Data rows contain expected units and series
    expect(csvText).toContain('HB_HOUSTON');
    expect(csvText).toContain('$/MWh');
    // Demand rows carry the summed ERCOT total (last interval: 68138 MW).
    expect(csvText).toContain('ERCOT Total Demand');
    expect(csvText).toContain('68138');
  });

  it('6. fetches history series one at a time so the Overview burst stays under the per-IP bucket', async () => {
    let inFlight = 0;
    let maxInFlight = 0;
    let historyCalls = 0;
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const urlStr = String(input);
      const parsed = new URL(urlStr, 'http://localhost');
      if (parsed.pathname === '/v1/signals/history') {
        historyCalls++;
        inFlight++;
        maxInFlight = Math.max(maxInFlight, inFlight);
        await Promise.resolve();
        const key = `${parsed.searchParams.get('report_id')}:${parsed.searchParams.get('zone')}`;
        const data = mockHistoryData[key] ?? [];
        inFlight--;
        return { ok: true, status: 200, json: async () => data };
      }
      const body = (fixture as Record<string, unknown>)[parsed.pathname];
      if (body === undefined) {
        return { ok: false, status: 404, json: async () => ({ error: { code: 'NOT_FOUND', message: parsed.pathname } }) };
      }
      return { ok: true, status: 200, json: async () => body };
    }));
    render(<Overview />);
    // Loaded: the demand peak needs all four LZ rollups summed.
    await screen.findByText(/68,138\s*MW/i, {}, { timeout: 5000 });
    expect(historyCalls).toBe(13);
    expect(maxInFlight).toBe(1);
  });
});
