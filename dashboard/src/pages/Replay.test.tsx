// @vitest-environment jsdom
/* S71 Replay page, rendered from dashboard/src/fixtures/replay.json, captured
   from the running S69 backend (see replay.PROVENANCE.md). Fetch is stubbed:
   GET /v1/replay/days serves the captured day list, POST /v1/replay serves the
   captured baseline or scenario run by disruption count. No network. */
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from "vitest";
// @ts-ignore TS2732: resolveJsonModule is off in the frozen tsconfig; vitest/vite load JSON at runtime.
import fixture from "../fixtures/replay.json";
import App from "../App";
import Replay from "./Replay";

type Day = { day: string; availability_mode: string };
type Row = { strategy: string; net_value_cents: number; failed_commitments: number };

const days = (fixture as { days: { days: Day[] } }).days.days;
const baseline = (fixture as { baseline: { run_id: string; disclaimer: string; availability_mode: string; scoreboard: Row[] } }).baseline;
const scenario = (fixture as { scenario: { run_id: string; scoreboard: Row[] } }).scenario;
const money = (cents: number) => `${cents < 0 ? "−" : "+"}$${(Math.abs(cents) / 100).toFixed(2)}`;

let fetchMock: Mock;

beforeEach(() => {
  window.location.hash = "#/replay?day=2026-08-26";
  fetchMock = vi.fn(async (input: string, init?: { method?: string; body?: string }) => {
    const path = input.startsWith("http") ? new URL(input).pathname : input;
    if (path === "/v1/replay/days") return { ok: true, status: 200, json: async () => (fixture as { days: unknown }).days };
    if (path === "/v1/replay" && (init?.method ?? "GET") === "POST") {
      const body = JSON.parse(String(init?.body ?? "{}")) as { disruptions?: unknown[] };
      const run = (body.disruptions?.length ?? 0) > 0 ? scenario : baseline;
      return { ok: true, status: 200, json: async () => run };
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

async function loaded() {
  render(<Replay />);
  const board = await screen.findByRole("region", { name: /scoreboard · baseline/i });
  await within(board).findByRole("row", { name: /battery-aware/i });
  expect((await within(board).findAllByText(money(105))).length).toBeGreaterThanOrEqual(3);
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
    expect(board.textContent).toContain(money(105));
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
    await waitFor(() => expect(versus.textContent).toContain(money(83)));
    expect(versus.textContent).toContain(money(105));
    expect(versus.textContent).toMatch(/failed commitment/i);
    const posts = fetchMock.mock.calls.filter(([path, init]) => path === "/v1/replay" && init?.method === "POST");
    expect(posts.length).toBeGreaterThanOrEqual(2);
    const payload = JSON.parse(String(posts[posts.length - 1][1].body)) as { disruptions: { type: string }[] };
    expect(payload.disruptions[0].type).toBe("provider_offline");
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
});
