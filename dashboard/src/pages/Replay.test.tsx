// @vitest-environment jsdom
/* S71 Replay page, rendered from dashboard/src/fixtures/replay.json, captured
   from the running S69b backend (see replay.PROVENANCE.md). Fetch is stubbed:
   GET /v1/replay/days serves the captured day list, POST /v1/replay serves the
   captured baseline or scenario run by disruption count (a 1-asset POST serves
   the captured homeValue run), GET decisions filters the baseline trace. */
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from "vitest";
// @ts-ignore TS2732: resolveJsonModule is off in the frozen tsconfig; vitest/vite load JSON at runtime.
import fixture from "../fixtures/replay.json";
// @ts-ignore TS2732: resolveJsonModule is off in the frozen tsconfig; vitest/vite load JSON at runtime.
import catalogDays from "../fixtures/catalog-days.json";
import App from "../App";
import Replay from "./Replay";

type Day = { day: string; availability_mode: string };
type Row = { strategy: string; net_value_cents: number; failed_commitments: number };
type Step = { interval_start: string; interval_end: string; decisions: { strategy: string; decision_time: string }[] };

const days = (fixture as { days: { days: Day[] } }).days.days;
const baseline = (fixture as { baseline: { run_id: string; disclaimer: string; availability_mode: string; scoreboard: Row[]; timeline: Step[] } }).baseline;
const scenario = (fixture as { scenario: { run_id: string; scoreboard: Row[] } }).scenario;
const homeValue = (fixture as { homeValue: unknown }).homeValue;
const money = (cents: number) => `${cents < 0 ? "−" : "+"}$${(Math.abs(cents) / 100).toFixed(2)}`;

let fetchMock: Mock;

beforeEach(() => {
  window.location.hash = "#/replay?day=2026-08-26";
  fetchMock = vi.fn(async (input: string, init?: { method?: string; body?: string }) => {
    const path = (input.startsWith("http") ? new URL(input).pathname : input).split("?")[0];
    const query = input.includes("?") ? new URL(input, "http://x").searchParams : new URLSearchParams();
    if (path === "/v1/replay/days") return { ok: true, status: 200, json: async () => (fixture as { days: unknown }).days };
    if (path === "/v1/replay" && (init?.method ?? "GET") === "POST") {
      const body = JSON.parse(String(init?.body ?? "{}")) as { disruptions?: unknown[]; fleet: { assets: unknown[] } };
      if (body.fleet.assets.length === 1) return { ok: true, status: 200, json: async () => homeValue };
      const run = (body.disruptions?.length ?? 0) > 0 ? scenario : baseline;
      return { ok: true, status: 200, json: async () => run };
    }
    if (path.startsWith("/v1/replay/") && path.endsWith("/decisions")) {
      const strategy = query.get("strategy");
      const start = query.get("start") ?? "";
      const end = query.get("end") ?? "";
      const decisions = baseline.timeline.flatMap(step => step.decisions)
        .filter(d => d.strategy === strategy && d.decision_time >= start && d.decision_time < end);
      return { ok: true, status: 200, json: async () => ({ run_id: baseline.run_id, decisions }) };
    }
    if (path === "/v1/signals") return { ok: true, status: 200, json: async () => [] };
    return { ok: false, status: 404, json: async () => ({ error: { code: "NOT_FOUND", message: path } }) };
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
  vi.restoreAllMocks();
});

const esr = (rows: Row[]) => rows.find(row => row.strategy === "esr_informed") as Row;

async function loaded() {
  render(<Replay />);
  const board = await screen.findByRole("region", { name: /scoreboard · baseline/i });
  await within(board).findByRole("row", { name: /battery-aware/i });
  await within(board).findByText(money(esr(baseline.scoreboard).net_value_cents));
  return board;
}

describe("S71 Replay page (fixture: replay.json)", () => {
  it("headers the day with source, availability mode and the honest-labels line", async () => {
    render(<Replay />);
    expect(await screen.findByRole("heading", { name: /^replay$/i })).toBeTruthy();
    const header = await screen.findByRole("region", { name: /replay day/i });
    expect(within(header).getByText(/2026-08-26/)).toBeTruthy();
    expect(await within(header).findByText(/ercot_public_archives/i)).toBeTruthy();
    expect(await within(header).findByText(/^assumed availability$/i)).toBeTruthy();
    await waitFor(() => expect(header.textContent).toContain(baseline.disclaimer));
    expect(header.textContent).toContain(baseline.availability_mode);
  });

  it("scoreboards the served net value, cash net, delivered kWh, backup and failures per strategy", async () => {
    const board = await loaded();
    for (const row of baseline.scoreboard) {
      const name = row.strategy === "esr_informed" ? /battery-aware/i
        : row.strategy === "price_based" ? /price-based/i : /fixed schedule/i;
      const data = await within(board).findByRole("row", { name });
      expect(data.textContent).toContain(money(row.net_value_cents));
      expect(data.textContent).toContain(String(row.failed_commitments));
    }
    expect(board.textContent).toMatch(/cash net/i);
    expect(board.textContent).toMatch(/delivered/i);
  });

  it("plays the day: procurement window, playback head and SoC move together", async () => {
    vi.useFakeTimers();
    render(<Replay />);
    await act(async () => { await vi.advanceTimersByTimeAsync(50); });
    const chart = screen.getByRole("region", { name: /prices and playback/i });
    expect(chart.textContent).toMatch(/hindsight/i);
    expect(chart.textContent).toMatch(/procurement/i);
    const slider = within(chart).getByRole("slider", { name: /playback position/i }) as HTMLInputElement;
    expect(slider.value).toBe("0");
    fireEvent.click(within(chart).getByRole("button", { name: /^play$/i }));
    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
    expect(Number(slider.value)).toBeGreaterThan(0);
    fireEvent.click(within(chart).getByRole("button", { name: /^pause$/i }));
    const lanes = screen.getByRole("region", { name: /strategy lanes/i });
    for (const name of [/fixed schedule lane/i, /price-based lane/i, /battery-aware lane/i]) {
      expect(within(lanes).getByRole("group", { name })).toBeTruthy();
    }
  });

  it("opens the why card for a clicked lane quarter with reason and input times", async () => {
    const board = await loaded();
    expect(board.textContent).toContain(money(esr(baseline.scoreboard).net_value_cents));
    const lanes = await screen.findByRole("region", { name: /strategy lanes/i });
    const lane = within(lanes).getByRole("group", { name: /battery-aware lane/i });
    const cells = within(lane).getAllByRole("button");
    expect(cells.length).toBeGreaterThan(90);
    fireEvent.click(cells[0]);
    const why = await screen.findByRole("region", { name: /why this decision/i });
    await waitFor(() => expect(why.textContent).toMatch(/battery-aware/i));
    expect(why.textContent).toMatch(/available/i);
    expect(why.textContent).toMatch(/published/i);
    // Roving tabindex: one tab stop per lane, arrows move the head.
    expect(cells.filter(cell => cell.getAttribute("tabindex") === "0")).toHaveLength(1);
    fireEvent.keyDown(lane, { key: "ArrowRight" });
    const slider = screen.getByRole("slider", { name: /playback position/i }) as HTMLInputElement;
    expect(Number(slider.value)).toBe(1);
  });

  it("runs a provider-offline scenario, explains the ledger delta, and resets", async () => {
    await loaded();
    const form = await screen.findByRole("region", { name: /disruptions/i });
    fireEvent.click(within(form).getByRole("button", { name: /run scenario/i }));
    const versus = await screen.findByRole("region", { name: /baseline versus scenario/i });
    await waitFor(() => expect(versus.textContent).toContain(money(esr(scenario.scoreboard).net_value_cents)));
    expect(versus.textContent).toContain(money(esr(baseline.scoreboard).net_value_cents));
    expect(versus.textContent).toMatch(/failed commitment/i);
    const posts = fetchMock.mock.calls.filter(([path, init]) => path === "/v1/replay" && init?.method === "POST");
    expect(posts.length).toBeGreaterThanOrEqual(2);
    const scenPost = posts.map(([, init]) => JSON.parse(String(init.body)) as { disruptions: { type: string }[] })
      .find(payload => payload.disruptions.length > 0);
    expect(scenPost?.disruptions[0].type).toBe("provider_offline");
    fireEvent.click(within(form).getByRole("button", { name: /^reset$/i }));
    await waitFor(() => expect(screen.queryByRole("region", { name: /baseline versus scenario/i })).toBeNull());
  });

  it("reruns the identical baseline byte for byte", async () => {
    await loaded();
    const form = await screen.findByRole("region", { name: /disruptions/i });
    fireEvent.click(within(form).getByRole("button", { name: /rerun baseline/i }));
    const header = await screen.findByRole("region", { name: /replay day/i });
    await waitFor(() => expect(header.textContent).toContain(baseline.run_id.slice(0, 12)));
  });

  it("routes #/replay from the app shell with a deep-linked day", async () => {
    expect(days.map(day => day.day)).toContain("2026-08-26");
    render(<App />);
    const rail = await screen.findByRole("navigation", { name: /primary/i });
    const link = within(rail).getByRole("link", { name: /replay/i }) as HTMLAnchorElement;
    expect(link.getAttribute("href")).toBe("#/replay");
    act(() => {
      window.location.hash = "#/replay?day=2026-08-26";
      window.dispatchEvent(new Event("hashchange"));
    });
    expect(await screen.findByRole("heading", { name: /^replay$/i })).toBeTruthy();
  });

  describe("X2b Day picker", () => {
    // @ts-ignore TS2732
    const multiDays = catalogDays as { days: Array<{ day: string; gaps: string[]; peak_rt_price: { value: number; point: string } }> };

    beforeEach(() => {
      // Return the full 6-day catalog for X2b tests
      const originalFetch = fetchMock;
      fetchMock = vi.fn(async (input: string, init?: { method?: string; body?: string }) => {
        const path = (input.startsWith("http") ? new URL(input).pathname : input).split("?")[0];
        if (path === "/v1/replay/days") {
          return { ok: true, status: 200, json: async () => multiDays };
        }
        return originalFetch(input, init);
      });
      vi.stubGlobal("fetch", fetchMock);
    });

    it("lists each catalogued day with date, weekday, peak real-time price, location, and data gaps in the day picker", async () => {
      render(<Replay />);
      const header = await screen.findByRole("region", { name: /replay day/i });
      const table = await within(header).findByRole("table", { name: /catalogued replay days/i });

      // Verify each catalogued day is listed with expected details
      for (const item of multiDays.days) {
        const row = await within(table).findByRole("row", { name: new RegExp(item.day) });
        expect(row).toBeTruthy();
        // Peak price formatted
        expect(within(row).getByText(new RegExp(`\\$${item.peak_rt_price.value.toFixed(2)}`))).toBeTruthy();
        // Location (either LZ point or human name)
        expect(within(row).getByText(new RegExp(item.peak_rt_price.point))).toBeTruthy();
        // Gaps
        const gapsExpected = item.gaps.length ? item.gaps.join(", ") : "None";
        expect(within(row).getByText(new RegExp(gapsExpected, "i"))).toBeTruthy();
      }

      // Check weekdays specifically for key days
      const wedRow = await within(table).findByRole("row", { name: /2026-08-26/ });
      expect(within(wedRow).getByText(/Wednesday/i)).toBeTruthy();
      const sunRow = await within(table).findByRole("row", { name: /2026-08-23/ });
      expect(within(sunRow).getByText(/Sunday/i)).toBeTruthy();
    });

    it("defaults to 2026-08-26 when no day parameter is in the URL", async () => {
      window.location.hash = "#/replay";
      render(<Replay />);
      const header = await screen.findByRole("region", { name: /replay day/i });
      const table = await within(header).findByRole("table", { name: /catalogued replay days/i });
      const row26 = await within(table).findByRole("row", { name: /2026-08-26/ });
      // Row or select button is selected
      expect(row26.className).toContain("selected");
      // And URL hash updates with ?day=2026-08-26
      await waitFor(() => expect(window.location.hash).toContain("day=2026-08-26"));
    });

    it("selecting a day from the picker updates the URL (?day=) and reruns the replay", async () => {
      window.location.hash = "#/replay?day=2026-08-26";
      render(<Replay />);
      const header = await screen.findByRole("region", { name: /replay day/i });
      const table = await within(header).findByRole("table", { name: /catalogued replay days/i });

      // Click to select 2026-07-20
      const targetRow = await within(table).findByRole("row", { name: /2026-07-20/ });
      const selectBtn = within(targetRow).getByRole("button", { name: /replay|select/i });
      fireEvent.click(selectBtn);

      // URL should update to ?day=2026-07-20
      await waitFor(() => expect(window.location.hash).toContain("day=2026-07-20"));

      // POST /v1/replay must be called with day: "2026-07-20"
      await waitFor(() => {
        const posts = fetchMock.mock.calls.filter(([url, init]) =>
          String(url).includes("/v1/replay") && init?.method === "POST"
        );
        const day20Calls = posts.filter(([, init]) => {
          try {
            const body = JSON.parse(String(init?.body ?? "{}"));
            return body.day === "2026-07-20";
          } catch { return false; }
        });
        expect(day20Calls.length).toBeGreaterThan(0);
      });
    });
  });

  describe("God's Eye 3D replay tour link", () => {
    afterEach(() => vi.unstubAllEnvs());

    it("links the header to the 26 Aug 3D tour on the God's Eye origin when VITE_GODSEYE_URL is set", async () => {
      vi.stubEnv("VITE_GODSEYE_URL", "https://views.example.test/godseye/");
      render(<Replay />);
      const link = screen.getByRole("link", { name: "See 26 Aug in 3D (God's Eye)" });
      expect(link.getAttribute("href")).toBe("https://views.example.test/replay/#start");
      expect(link.getAttribute("target")).toBe("_blank");
      expect(link.getAttribute("rel")).toBe("noreferrer");
      expect(link.closest(".page-heading")?.querySelector("h1")?.textContent).toMatch(/^Replay/);
      await screen.findByRole("region", { name: /scoreboard · baseline/i });
    });

    it("shows no 3D tour link when VITE_GODSEYE_URL is unset", async () => {
      vi.stubEnv("VITE_GODSEYE_URL", "");
      render(<Replay />);
      expect(screen.queryByRole("link", { name: /in 3D/ })).toBeNull();
      await screen.findByRole("region", { name: /scoreboard · baseline/i });
    });
  });
});
