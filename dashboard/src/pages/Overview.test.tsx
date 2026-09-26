// @vitest-environment jsdom
/* S04 red tests: phase 1a Overview page + app shell, rendered from
   dashboard/src/fixtures/overview.json with fetch stubbed (no network).
   The pragma pins jsdom because `make red-green` runs vitest from the repo
   root, where dashboard/vite.config.ts is not auto-loaded. */
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from "vitest";
// @ts-ignore TS2732: resolveJsonModule is off in the frozen tsconfig; vitest/vite load JSON at runtime.
import manifest from "../../package.json";
import App, { routes } from "../App";
import Shell from "../components/Shell";
// @ts-ignore TS2732: see above.
import fixture from "../fixtures/overview.json";
import Overview from "./Overview";

const VIEWS_URL = "https://views.example.test/godseye/";

type Signal = { report_id: string; zone: string; value: number; published_at: string; stale: boolean };
type Prediction = { zone: string; score: number; level: string };
type Activity = { id: string; type: string; label: string; symbol: string; side: string; quantity: number; price_cents: number; reason?: string; created_at: string };
type Provider = { id: string; display_name: string };
type Bot = { id: string; provider_id: string };

const signals = fixture["/v1/signals"] as unknown as Signal[];
const predictions = fixture["/v1/predictions"] as unknown as Prediction[];
const activity = fixture["/v1/market/activity"] as unknown as Activity[];
const providers = fixture["/v1/providers"] as unknown as Provider[];
const bots = fixture["/v1/bots"] as unknown as Bot[];
const marketStatus = fixture["/v1/market/status"] as unknown as { status: string };

let fetchMock: Mock;

beforeEach(() => {
  window.location.hash = "#/";
  fetchMock = vi.fn(async (input: string) => {
    const path = input.startsWith("http") ? new URL(input).pathname : input;
    const body = (fixture as Record<string, unknown>)[path];
    if (body === undefined) {
      return { ok: false, status: 404, json: async () => ({ error: { code: "NOT_FOUND", message: path } }) };
    }
    return { ok: true, status: 200, json: async () => body };
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  cleanup();
  delete document.documentElement.dataset.theme;
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("S04 Overview page and app shell (fixture: overview.json)", () => {
  it("[SEIT-GM-UI-01] renders ERCOT signals with value, publish time, and stale badge", async () => {
    render(<Overview />);
    const fresh = signals.filter((s) => !s.stale)[0] as Signal;
    const staleSignal = signals.filter((s) => s.stale)[0] as Signal;
    expect(await screen.findByText(new RegExp(String(fresh.value).replace(".", "\\.")))).toBeTruthy();
    expect(screen.getByText(new RegExp(fresh.zone))).toBeTruthy();
    expect(screen.getAllByText(/2026-09-26/).length).toBeGreaterThan(0);
    expect(screen.getByText(new RegExp(staleSignal.zone))).toBeTruthy();
    expect(screen.getByText(/stale/i)).toBeTruthy();
  });

  it("[SEIT-GM-UI-01] renders zone scores", async () => {
    render(<Overview />);
    const top = predictions[0] as Prediction;
    expect(await screen.findByText(new RegExp(top.zone))).toBeTruthy();
    expect(screen.getByText(new RegExp(String(top.score).replace(".", "\\.")))).toBeTruthy();
    expect(screen.getByText(new RegExp(top.level))).toBeTruthy();
  });

  it("[SEIT-GM-UI-01] renders participant counts per provider", async () => {
    render(<Overview />);
    const first = providers[0] as Provider;
    expect(await screen.findByText(new RegExp(first.display_name))).toBeTruthy();
    for (const provider of providers) {
      const count = bots.filter((b) => b.provider_id === provider.id).length;
      expect(count).toBeGreaterThan(0);
      const body = document.body.textContent ?? "";
      const near = `[\\s\\S]{0,80}`;
      expect(body).toMatch(new RegExp(`${provider.display_name}${near}${count}|${count}${near}${provider.display_name}`));
    }
  });

  it("[SEIT-GM-UI-01] stats cards show market status", async () => {
    render(<Overview />);
    expect(await screen.findByText(new RegExp(`\\b${marketStatus.status}\\b`, "i"))).toBeTruthy();
  });

  it("[SEIT-GM-UI-01] renders activity feed with judge-labelled order and rejection reason", async () => {
    render(<Overview />);
    const judge = activity.find((e) => e.label === "judge") as Activity;
    const rejected = activity.find((e) => e.type === "reject") as Activity;
    expect(await screen.findByText(/judge/i)).toBeTruthy();
    expect(screen.getByText(new RegExp(judge.symbol))).toBeTruthy();
    expect(screen.getByText(new RegExp(rejected.reason ?? "NO-REASON-IN-FIXTURE"))).toBeTruthy();
    expect(screen.getByText(`${judge.side} ${judge.quantity} @ $${(judge.price_cents / 100).toFixed(2)}`)).toBeTruthy();
  });

  it("[SEIT-GM-UI-01] participants render providers and mark bots not yet available when /v1/bots is 404", async () => {
    const serve = fetchMock.getMockImplementation() as (input: string) => Promise<unknown>;
    fetchMock.mockImplementation(async (input: string) =>
      input.includes("/v1/bots")
        ? { ok: false, status: 404, json: async () => ({ error: { code: "NOT_FOUND", message: input } }) }
        : serve(input),
    );
    render(<Overview />);
    expect(await screen.findByText(/bots not yet available/i)).toBeTruthy();
    for (const provider of providers) expect(screen.getByText(provider.display_name)).toBeTruthy();
    expect(screen.getByText(new RegExp(`${providers.length} providers`))).toBeTruthy();
    expect(screen.queryByText(/feed unavailable/i)).toBeNull();
    expect(screen.queryByText(/^\d+ bots$/)).toBeNull();
  });

  it("[SEIT-GM-UI-01] links to the 3D views from VITE_VIEWS_URL", async () => {
    vi.stubEnv("VITE_VIEWS_URL", VIEWS_URL);
    render(<Overview />);
    const link = (await screen.findByRole("link", { name: /3d views/i })) as HTMLAnchorElement;
    expect(link.getAttribute("href")).toBe(VIEWS_URL);
  });

  it("[SEIT-GM-UI-01] shell navigates to every frozen page route without login", async () => {
    expect(routes).toEqual(
      expect.arrayContaining(["#/", "#/market", "#/predictions", "#/providers", "#/bots", "#/bots/:id", "#/sandbox", "#/spec"]),
    );
    render(<App />);
    const nav: Array<[string, RegExp]> = [
      ["#/", /overview/i],
      ["#/market", /market/i],
      ["#/predictions", /predictions/i],
      ["#/providers", /providers/i],
      ["#/bots", /bots/i],
      ["#/sandbox", /sandbox/i],
      ["#/spec", /spec/i],
    ];
    for (const [href, name] of nav) {
      const link = (await screen.findByRole("link", { name })) as HTMLAnchorElement;
      expect(link.getAttribute("href")).toBe(href);
    }
    expect(screen.queryByText(/log in|sign in|password/i)).toBeNull();
    const pages: Array<[string, RegExp]> = [
      ["#/", /overview/i],
      ["#/market", /market/i],
      ["#/predictions", /predictions/i],
      ["#/providers", /providers/i],
      ["#/bots", /^bots$/i],
      ["#/bots/demo-bot-1", /bot profile/i],
      ["#/sandbox", /sandbox/i],
      ["#/spec", /spec/i],
    ];
    for (const [hash, heading] of pages) {
      act(() => {
        window.location.hash = hash;
        window.dispatchEvent(new Event("hashchange"));
      });
      expect(screen.getByRole("heading", { name: heading })).toBeTruthy();
    }
  });

  it("[SEIT-GM-UI-01] polls REST endpoints every 2 seconds", async () => {
    vi.useFakeTimers();
    const setIntervalSpy = vi.spyOn(window, "setInterval");
    render(<Overview />);
    await vi.advanceTimersByTimeAsync(0);
    const statusCalls = () => fetchMock.mock.calls.filter((call) => String(call[0]).includes("/v1/market/status")).length;
    expect(statusCalls()).toBeGreaterThanOrEqual(1);
    await vi.advanceTimersByTimeAsync(2000);
    expect(statusCalls()).toBeGreaterThanOrEqual(2);
    expect(setIntervalSpy).toHaveBeenCalled();
    for (const call of setIntervalSpy.mock.calls) {
      expect(call[1] ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(2000);
    }
  });

  it("[SEIT-GM-UI-02] shell shows the disclosures banner", async () => {
    render(<App />);
    expect(await screen.findByText(/simulated forward flexibility contracts/i)).toBeTruthy();
    expect(screen.getByText(/not regulated commodity futures/i)).toBeTruthy();
    expect(screen.getByText(/not a renewable energy certificate/i)).toBeTruthy();
  });

  it("[SEIT-GM-SCORE-03-UI] zone-score panel renders the score disclaimer", async () => {
    render(<Overview />);
    expect(await screen.findByText(/simulation estimate, not guaranteed profit/i)).toBeTruthy();
  });

  it("[SEIT-GM-UI-06] pins Astryx, Recharts, and React versions", () => {
    const deps = manifest.dependencies as unknown as Record<string, string>;
    expect(deps["@astryxdesign/core"]).toBe("0.6.0");
    expect(deps.recharts).toBe("3.10.1");
    expect(deps.react).toMatch(/19\./);
  });

  it("[SEIT-GM-UI-06] shell theme toggle switches dark and light mode", async () => {
    render(
      <Shell>
        <p>probe</p>
      </Shell>,
    );
    expect(await screen.findByText("probe")).toBeTruthy();
    const toggle = screen.getByRole("button", { name: /theme|dark mode|light mode/i });
    fireEvent.click(toggle);
    expect(document.documentElement.dataset.theme).toBe("light");
    fireEvent.click(toggle);
    expect(document.documentElement.dataset.theme).toBe("dark");
  });
});
