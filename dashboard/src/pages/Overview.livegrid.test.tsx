// @vitest-environment jsdom
/**
 * Overview Live Grid panel tests (DEC-GM-142).
 * Verifies real ERCOT signals plotted as live charts with history from
 * GET /v1/signals/history (bounded 48 h):
 * 1. Panel header says 'Real ERCOT data' with source, last published time, 24 h / 48 h picker.
 * 2. Real-time prices for HB_HOUSTON, HB_NORTH, HB_SOUTH, HB_WEST (SNAPSHOT-HUBS), system lambda
 *    (SNAPSHOT-SCED), and the HB_HUBAVG day-ahead dashed line (NP4-190-CD). XR-B, DEC-GM-152.
 * 3. ERCOT actual demand (SNAPSHOT-DEMAND:ERCOT) against today's peak as a small second chart.
 * 4. Clicking hub line or legend item opens Market filtered to that zone (FLOW-027).
 * 5. 'Download CSV' button exports exactly plotted series with header row.
 */
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
// @ts-ignore TS2732: Vitest loads JSON; frozen tsconfig omits resolveJsonModule.
import fixture from '../fixtures/overview.json';
// @ts-ignore TS2732: Vitest loads JSON; frozen tsconfig omits resolveJsonModule.
import livegrid from '../fixtures/livegrid.json';
import Overview from './Overview';

// XR-B (DEC-GM-152): rows for the keys the backend stores, from real Worker captures
// run through the backend parsers (fixtures/livegrid.PROVENANCE.md).
const mockHistoryData = (livegrid as { series: Record<string, unknown[]> }).series;
const CAPTURE = Date.parse('2026-09-27T03:55:00Z');
// Short steps: each act() exit commits React updates, whose effects schedule the next timers.
const settle = async () => { for (let t = 0; t < 10_000; t += 250) await act(() => vi.advanceTimersByTimeAsync(250)); };

let requestedUrls: string[] = [];
let failFirstDemand = true;

beforeEach(() => {
  window.location.hash = '#/';
  requestedUrls = [];
  failFirstDemand = true;
  vi.useFakeTimers({ now: CAPTURE, shouldAdvanceTime: true });
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
      if (key === 'SNAPSHOT-DEMAND:ERCOT' && failFirstDemand) {
        failFirstDemand = false;
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
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  window.location.hash = '';
});

describe('Live grid panel (X1 extras wave, DEC-GM-142)', () => {
  it('1. renders panel header with "Real ERCOT data", source, last published time in Central Time, and 24 h picker default', async () => {
    render(<Overview />);
    await settle();
    const panel = await screen.findByRole('region', { name: /live grid/i });
    expect(panel).toBeDefined();

    const panelScope = within(panel);
    expect(await panelScope.findByText(/Real ERCOT data/i)).toBeDefined();
    expect((await panelScope.findAllByText(/ERCOT/i)).length).toBeGreaterThan(0);
    // Central time formatting on published time
    // Latest snapshot publication (2026-09-27T03:53:40Z) in Central Time.
    expect(await panelScope.findByText('Sep 26, 10:53 PM CT')).toBeDefined();

    // Range picker defaults to 24 h
    const btn24 = await panelScope.findByRole('button', { name: /24\s*h/i });
    const btn48 = await panelScope.findByRole('button', { name: /48\s*h/i });
    expect(btn24).toBeDefined();
    expect(btn48).toBeDefined();
    expect(btn24.getAttribute('aria-pressed')).toBe('true');
  });

  it('2. fetches and plots real-time prices for hubs and system lambda plus day-ahead dashed line', async () => {
    render(<Overview />);
    await settle();
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

  it('3. renders ERCOT actual demand against today\'s peak as a small second chart', async () => {
    render(<Overview />);
    await settle();
    const panel = await screen.findByRole('region', { name: /live grid/i });
    const panelScope = within(panel);

    expect(await panelScope.findByRole('heading', { name: /ERCOT actual demand/i })).toBeDefined();
    expect(await panelScope.findByText(/today's peak|peak/i)).toBeDefined();
    expect((await panelScope.findAllByText(/MW/i)).length).toBeGreaterThan(0);
    // Peak of the captured SNAPSHOT-DEMAND series on the capture's Central day.
    expect(await panelScope.findByText(/76,715\s*MW/i)).toBeDefined();
  });

  it('4. clicking a hub line or legend item opens Market filtered to that zone (FLOW-027)', async () => {
    render(<Overview />);
    await settle();
    const panel = await screen.findByRole('region', { name: /live grid/i });
    const panelScope = within(panel);

    const houstonItem = await panelScope.findByText(/HB_HOUSTON/i);
    fireEvent.click(houstonItem);

    // URL context carry: opens Market filtered to Houston zone (LZ_HOUSTON)
    expect(window.location.hash).toContain('/market');
    expect(window.location.hash).toMatch(/zone=(?:LZ_HOUSTON|HB_HOUSTON)/);
  });

  it('5. "Download CSV" button exports exactly the plotted series with the required header row', async () => {
    const blobs: string[] = [];
    vi.stubGlobal('URL', Object.assign(class extends URL {}, {
      createObjectURL: (blob: { parts?: string[] }) => { blobs.push(String(blob.parts?.join(''))); return 'blob:mock-csv'; },
      revokeObjectURL: () => {},
    }));
    const RealBlob = Blob;
    vi.stubGlobal('Blob', class extends RealBlob { parts: string[]; constructor(parts: string[], o?: BlobPropertyBag) { super(parts, o); this.parts = parts; } });
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

    render(<Overview />);
    await settle();
    const panel = await screen.findByRole('region', { name: /live grid/i });
    const panelScope = within(panel);
    // Await loaded data (rule 3): the CSV must cover the plotted series.
    await panelScope.findByText(/76,715\s*MW/i);
    fireEvent.click(panelScope.getByRole('button', { name: /download csv/i }));
    await panelScope.findByText(/^Downloaded gridmarket-live-grid-24h-/);

    const lines = blobs[0].trim().split('\r\n');
    expect(lines[0]).toBe('interval_start_utc,interval_start_central,series,report_id,subject,value,unit,published_at_utc,source');
    // Every stored row of every plotted series, one CSV row each.
    const total = Object.values(mockHistoryData).reduce((n, rows) => n + rows.length, 0);
    expect(lines.length - 1).toBe(total);
    for (const label of ['HB_HOUSTON', 'HB_NORTH', 'HB_SOUTH', 'HB_WEST', 'system lambda', 'HB_HUBAVG day-ahead', 'ERCOT actual demand'])
      expect(lines.some(l => l.split(',')[2] === label)).toBe(true);
    expect(blobs[0]).toContain(',ERCOT actual demand,SNAPSHOT-DEMAND,ERCOT,66285,MW,');
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
    await settle();
    // Loaded: the demand peak is the last series read.
    await screen.findByText(/76,715\s*MW/i);
    expect(historyCalls).toBe(7);
    expect(maxInFlight).toBe(1);
  });
});
