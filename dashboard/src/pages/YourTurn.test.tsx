// @vitest-environment jsdom
/* S72 Your-turn section, rendered from dashboard/src/fixtures/replay.json
   (S69b capture; see replay.PROVENANCE.md). Fetch is stubbed: GET days and
   POST baseline/scenario serve the captured runs; a 1-asset POST serves the
   captured homeValue run; GET decisions filters the baseline trace. */
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from "vitest";
// @ts-ignore TS2732: resolveJsonModule is off in the frozen tsconfig; vitest/vite load JSON at runtime.
import fixture from "../fixtures/replay.json";
import Replay from "./Replay";

type Step = { interval_start: string; interval_end: string; decisions: { strategy: string; decision_time: string }[] };
const runs = fixture as {
  days: unknown; baseline: { run_id: string; timeline: Step[] };
  scenario: unknown; homeValue: { run_id: string; scoreboard: { net_value_cents: number }[] };
};

let fetchMock: Mock;

beforeEach(() => {
  window.location.hash = "#/replay?day=2026-08-26&panel=your-turn";
  fetchMock = vi.fn(async (input: string, init?: { method?: string; body?: string }) => {
    const path = (input.startsWith("http") ? new URL(input).pathname : input).split("?")[0];
    const query = input.includes("?") ? new URL(input, "http://x").searchParams : new URLSearchParams();
    if (path === "/v1/replay/days") return { ok: true, status: 200, json: async () => runs.days };
    if (path === "/v1/replay" && (init?.method ?? "GET") === "POST") {
      const body = JSON.parse(String(init?.body ?? "{}")) as { disruptions?: unknown[]; fleet: { assets: unknown[] } };
      if (body.fleet.assets.length === 1) return { ok: true, status: 200, json: async () => runs.homeValue };
      const run = (body.disruptions?.length ?? 0) > 0 ? runs.scenario : runs.baseline;
      return { ok: true, status: 200, json: async () => run };
    }
    if (path.startsWith("/v1/replay/") && path.endsWith("/decisions")) {
      const strategy = query.get("strategy");
      const start = query.get("start") ?? "";
      const end = query.get("end") ?? "";
      const decisions = runs.baseline.timeline.flatMap(step => step.decisions)
        .filter(d => d.strategy === strategy && d.decision_time >= start && d.decision_time < end);
      return { ok: true, status: 200, json: async () => ({ run_id: runs.baseline.run_id, decisions }) };
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

async function yourTurn() {
  render(<Replay />);
  const panel = await screen.findByRole("region", { name: /your turn/i });
  await within(panel).findByText(/flexibility to sell/i);
  return panel;
}

describe("S72 Your turn (fixture: replay.json)", () => {
  it("shows one simulated home's flexibility, replay-day value and backup at the URL reserve", async () => {
    window.location.hash = "#/replay?day=2026-08-26&panel=your-turn&reserve=40&homes=1000";
    const panel = await yourTurn();
    const slider = within(panel).getByRole("slider", { name: /reserve/i }) as HTMLInputElement;
    expect(slider.value).toBe("40");
    expect(panel.textContent).toMatch(/13\.5 kWh battery/);
    expect(panel.textContent).toMatch(/simulated/);
    // A11 at 40%: flex 1.3 kWh, backup 4.3 h at the stated 1.2 kW load.
    await waitFor(() => expect(panel.textContent).toMatch(/1\.3\s*kWh/));
    expect(panel.textContent).toMatch(/4\.3\s*h/);
    // Day value comes from the replay API: the captured 1-home run nets +81c.
    await within(panel).findByText(/\+\$0\.81/);
    const posts = fetchMock.mock.calls.filter(([path, init]) =>
      path === "/v1/replay" && init?.method === "POST" &&
      (JSON.parse(String(init.body)) as { fleet: { assets: unknown[] } }).fleet.assets.length === 1);
    expect(posts.length).toBeGreaterThanOrEqual(1);
    const payload = JSON.parse(String(posts[0][1].body)) as { fleet: { assets: { min_reserve_kwh: string }[] } };
    expect(payload.fleet.assets[0].min_reserve_kwh).toBe("5.4");
  });

  it("moves the outputs with the slider and keeps the state in the URL", async () => {
    const panel = await yourTurn();
    const slider = within(panel).getByRole("slider", { name: /reserve/i }) as HTMLInputElement;
    fireEvent.change(slider, { target: { value: "0" } });
    await waitFor(() => expect(panel.textContent).toMatch(/6\.4\s*kWh/));
    await waitFor(() => expect(window.location.hash).toContain("reserve=0"));
    fireEvent.change(slider, { target: { value: "100" } });
    await waitFor(() => expect(panel.textContent).toMatch(/reserve not yet met/i));
    expect(panel.textContent).toMatch(/starting charge/);
    await within(panel).findByText(/unavailable/);
  });

  it("scales the fleet estimate with the homes control and labels it technical", async () => {
    window.location.hash = "#/replay?day=2026-08-26&panel=your-turn&reserve=40&homes=1000";
    const panel = await yourTurn();
    // 1000 homes x 1.28 kWh over 4 h = 0.3 MW.
    await waitFor(() => expect(panel.textContent).toMatch(/0\.3\s*MW for 4 hours/));
    expect(panel.textContent).toMatch(/technical estimate, not a grid effect/);
    const homes = within(panel).getByRole("slider", { name: /homes in the fleet/i }) as HTMLInputElement;
    expect(homes.value).toBe("1000");
    fireEvent.change(homes, { target: { value: "5000" } });
    await waitFor(() => expect(panel.textContent).toMatch(/1\.6\s*MW for 4 hours/));
    await waitFor(() => expect(window.location.hash).toContain("homes=5000"));
  });

  it("ends the result with rerun, compare and sandbox next steps", async () => {
    const panel = await yourTurn();
    await within(panel).findByText(/\+\$0\.81/);
    const steps = within(panel).getByRole("list", { name: /next steps/i });
    expect(within(steps).getByRole("button", { name: /rerun the day/i })).toBeTruthy();
    expect(within(steps).getByRole("link", { name: /compare with the baseline/i })).toBeTruthy();
    const sandbox = within(steps).getByRole("link", { name: /sandbox order/i }) as HTMLAnchorElement;
    expect(sandbox.getAttribute("href")).toBe("#/sandbox");
  });

  it("reads a non-sample home through the decisions endpoint", async () => {
    render(<Replay />);
    await screen.findByRole("region", { name: /scoreboard · baseline/i });
    const why = await screen.findByRole("region", { name: /why this decision/i });
    const home = within(why).getByRole("combobox", { name: /home/i }) as HTMLSelectElement;
    fireEvent.change(home, { target: { value: "home-7" } });
    await waitFor(() => expect(fetchMock.mock.calls.some(([path]) =>
      String(path).includes("/decisions") && String(path).includes("asset=home-7"))).toBe(true));
    await waitFor(() => expect(why.textContent).toMatch(/battery-aware/i));
  });

  it("draws the served real-time curve, procurement window, self-supply lane and 1,000 homes", async () => {
    render(<Replay />);
    await screen.findByRole("region", { name: /replay day/i });
    const lanesFirst = await screen.findByRole("region", { name: /strategy lanes/i });
    await waitFor(() => expect(lanesFirst.textContent).toMatch(/1,000 simulated homes/i));
    const chart = await screen.findByRole("region", { name: /prices and playback/i });
    expect(chart.textContent).toMatch(/real-time/i);
    // DAM-selected procurement: 7 PM-11 PM CT.
    expect(chart.textContent).toMatch(/procurement 7:00 PM–11:00 PM CT/i);
    const lanes = await screen.findByRole("region", { name: /strategy lanes/i });
    expect(within(lanes).getByText(/self-supply/i)).toBeTruthy();
  });
});
