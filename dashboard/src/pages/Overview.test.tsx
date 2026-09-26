// @vitest-environment jsdom
/* S04 and S52a Overview page + app shell, rendered from
   dashboard/src/fixtures/overview.json with fetch stubbed (no network).
   The pragma pins jsdom because `make red-green` runs vitest from the repo
   root, where dashboard/vite.config.ts is not auto-loaded. */
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
// @ts-ignore TS2307: Node types are absent from the frozen tsconfig; Vitest resolves this import.
import { readFileSync } from "node:fs";
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from "vitest";
// @ts-ignore TS2732: resolveJsonModule is off in the frozen tsconfig; vitest/vite load JSON at runtime.
import manifest from "../../package.json";
import App, { routes } from "../App";
import Shell from "../components/Shell";
// @ts-ignore TS2732: see above.
import fixture from "../fixtures/overview.json";
import Overview from "./Overview";
const styles = readFileSync("src/styles.css", "utf8");

const VIEWS_URL = "https://views.example.test";

type Signal = { report_id: string; zone: string; value: number; published_at: string; stale: boolean };
type Prediction = { zone: string; score: number; level: string };
type Activity = { id: string; type: string; label: string; symbol: string; side: string; quantity: number; price_cents: number; reason?: string; created_at: string };
type Provider = { id: string; display_name: string };

const signals = fixture["/v1/signals"] as unknown as Signal[];
const predictions = fixture["/v1/predictions"] as unknown as Prediction[];
const activity = fixture["/v1/market/activity"] as unknown as Activity[];
const providers = fixture["/v1/providers"] as unknown as Provider[];
const marketStatus = fixture["/v1/market/status"] as unknown as { status: string };
const market = fixture["/v1/market"] as { symbol: string }[];
const book = fixture["/v1/market/FLEX-LZ_HOUSTON-18"] as { orders: { side: string; price_cents: number; quantity: number }[] };

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
    expect(document.body.textContent).toMatch(new RegExp(fresh.zone.replace(/^LZ_/, ""), "i"));
    expect(document.querySelectorAll("time[datetime]").length).toBeGreaterThan(0);
    expect(document.body.textContent).toMatch(new RegExp(staleSignal.zone.replace(/^LZ_/, ""), "i"));
    expect(screen.getByText(/stale/i)).toBeTruthy();
  });

  it("[SEIT-GM-UI-01] renders zone scores", async () => {
    render(<Overview />);
    const top = predictions[0] as Prediction;
    expect((await screen.findAllByText(new RegExp(top.zone.replace(/^LZ_/, ""), "i"))).length).toBeGreaterThan(0);
    expect((await screen.findAllByText(new RegExp(String(top.score).replace(".", "\\.")))).length).toBeGreaterThan(0);
  });

  it("[SEIT-GM-UI-01] renders provider names without inventing participant counts", async () => {
    render(<Overview />);
    const first = providers[0] as Provider;
    expect(await screen.findByText(new RegExp(first.display_name))).toBeTruthy();
    for (const provider of providers) expect(screen.getByText(provider.display_name)).toBeTruthy();
  });

  it("[SEIT-GM-UI-01] stats cards show market status", async () => {
    render(<Overview />);
    expect(await screen.findByText(new RegExp(`^Market ${marketStatus.status}$`, "i"), { selector: ".market-status" })).toBeTruthy();
  });

  it("[SEIT-GM-UI-01] renders activity feed with judge-labelled order", async () => {
    render(<Overview />);
    const judge = activity.find((e) => e.label === "judge") as Activity;
    expect(await screen.findByText(/judge/i)).toBeTruthy();
    expect(screen.getByText(new RegExp(judge.symbol))).toBeTruthy();
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
    expect(screen.queryByText(/feed unavailable/i)).toBeNull();
    expect(screen.queryByText(/^\d+ bots$/)).toBeNull();
  });

  it("[SEIT-GM-UI-01] links to Godseye from VITE_VIEWS_URL", async () => {
    vi.stubEnv("VITE_VIEWS_URL", VIEWS_URL);
    render(<Overview />);
    const link = (await screen.findByRole("link", { name: /(?:3d views|explore in 3d)/i })) as HTMLAnchorElement;
    expect(link.getAttribute("href")).toBe(`${VIEWS_URL}/godseye/`);
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

  it("[SEIT-GM-UI-06] shell theme switch selects light and dark", async () => {
    render(
      <Shell>
        <p>probe</p>
      </Shell>,
    );
    expect(await screen.findByText("probe")).toBeTruthy();
    const control = screen.getByRole("radiogroup", { name: /color theme/i });
    const light = within(control).getByRole("radio", { name: /light/i });
    const dark = within(control).getByRole("radio", { name: /dark/i });
    fireEvent.click(light);
    expect(light.getAttribute("aria-checked")).toBe("true");
    fireEvent.click(dark);
    expect(dark.getAttribute("aria-checked")).toBe("true");
  });
});

describe("S52a design v2 Overview and rail", () => {
  it("rail links to every static App route", async () => {
    render(<App />);
    const rail = await screen.findByRole("navigation", { name: /primary/i });
    for (const route of routes.filter((route) => !route.includes(":"))) {
      expect(rail.querySelector(`a[href="${route}"]`)).not.toBeNull();
    }
  });

  it("prediction headline presents the highest served scarcity score and delivery", async () => {
    render(<Overview />);
    const card = await screen.findByRole("region", { name: /next delivery prediction/i });
    const lead = predictions.reduce((best, item) => item.score > best.score ? item : best);
    expect(card.textContent?.toLowerCase()).toContain(lead.zone.replace(/^LZ_|^HB_/, "").toLowerCase());
    expect(card.textContent).toContain(String(lead.score));
    expect(card.textContent).toMatch(/expected value/i);
  });

  it("key-number strip marks fields absent from backend as unavailable", async () => {
    render(<Overview />);
    const strip = await screen.findByRole("region", { name: /market key numbers/i });
    for (const label of ["System load", "Open interest", "Active traders", "Participants by provider"]) {
      const item = within(strip).getByText(label).parentElement;
      expect(item?.textContent?.toLowerCase()).toContain("unavailable");
    }
    expect(strip.textContent).toContain(String(predictions[0].score));
  });

  it("disclosure is one expandable line with the complete AC-GM-UI-02 text", async () => {
    render(<App />);
    const disclosure = await screen.findByText(/simulated forward flexibility contracts/i);
    const details = disclosure.closest("details");
    expect(details).not.toBeNull();
    expect(details?.open).toBe(false);
    fireEvent.click(within(details as HTMLElement).getByText(/details/i));
    expect(details?.open).toBe(true);
    expect(details?.textContent).toMatch(/not regulated commodity futures/i);
    expect(details?.textContent).toMatch(/not a renewable energy certificate/i);
    expect(details?.textContent).toMatch(/cryptocurrency/i);
    expect(details?.textContent).toMatch(/claim on specific electrons/i);
  });

  it("price-chart region uses served trade history without a fabricated forecast", async () => {
    render(<Overview />);
    const panel = await screen.findByRole("region", { name: /the price of flexibility/i });
    expect(panel.textContent).toMatch(/price|history/i);
    expect(panel.textContent).toMatch(/unavailable/i);
    expect(fetchMock.mock.calls.some(([path]) => String(path).includes("/v1/market/history"))).toBe(true);
  });

  it("zone table has one row per served zone and scarcity percentages", async () => {
    render(<Overview />);
    const panel = await screen.findByRole("region", { name: /across the load zones/i });
    const rows = within(panel).getAllByRole("row");
    const zones = new Set([...predictions.map((item) => item.zone), ...signals.map((item) => item.zone)]);
    expect(rows).toHaveLength(zones.size + 1); // one heading row, one data row per served zone
    for (const item of predictions) {
      const row = rows.find((candidate) => candidate.textContent?.toLowerCase().includes(item.zone.replace(/^LZ_|^HB_/, "").toLowerCase()));
      expect(row?.textContent).toContain(`${item.score}%`);
    }
  });

  it("order book shows spread from the real detail orders shape", async () => {
    render(<Overview />);
    const panel = await screen.findByRole("region", { name: /live order book/i });
    const spread = await within(panel).findByRole("row", { name: /spread/i });
    const bid = book.orders.find((order) => order.side === "buy")!;
    const ask = book.orders.find((order) => order.side === "sell")!;
    expect(spread.textContent).toContain(((ask.price_cents - bid.price_cents) / 100).toFixed(2));
    expect(fetchMock.mock.calls.some(([path]) => String(path).includes(`/v1/market/${market[0].symbol}`))).toBe(true);
  });

  it("bots panel says not yet available while the backend returns 404", async () => {
    render(<Overview />);
    const panel = await screen.findByRole("region", { name: /bots setting the pace/i });
    expect(panel.textContent).toMatch(/not yet available/i);
    expect(fetchMock.mock.calls.some(([path]) => String(path).includes("/v1/bots"))).toBe(true);
  });

  it("anomalies panel follows status.anomalies rather than activity rejects", async () => {
    render(<Overview />);
    const panel = await screen.findByRole("region", { name: /anomalies|guardrails/i });
    expect(panel.textContent).toMatch(/no anomalies|none reported/i);
    expect(panel.textContent).not.toMatch(/ORDER_TOO_LARGE|contained/i);
  });

  it("sidebar shows freshness and an API-key call to action", async () => {
    render(<App />);
    const sidebar = await screen.findByRole("complementary");
    expect(sidebar.textContent).toMatch(/ERCOT data/i);
    expect(sidebar.textContent).toMatch(/published|stale|unavailable/i);
    const key = within(sidebar).getByRole("link", { name: /get api key/i });
    expect(key.getAttribute("href")).toBe("#/sandbox");
  });

  it("one outage banner keeps the last-known prediction", async () => {
    vi.useFakeTimers();
    render(<Overview />);
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(document.body.textContent?.toLowerCase()).toContain(predictions[0].zone.replace(/^LZ_/, "").toLowerCase());
    const previous = fetchMock.getMockImplementation() as (input: string) => Promise<unknown>;
    fetchMock.mockImplementation((input: string) => input.includes("/v1/market/status")
      ? Promise.resolve({ ok: false, status: 503, json: async () => ({ error: { code: "UNAVAILABLE", message: "Service unavailable" } }) })
      : previous(input));
    await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
    expect(screen.getAllByText(/API unreachable, retrying/i)).toHaveLength(1);
    expect(document.body.textContent?.toLowerCase()).toContain(predictions[0].zone.replace(/^LZ_/, "").toLowerCase());
  });

  it("zone map identifies served zones and offers a static pause state", async () => {
    render(<Overview />);
    const map = await screen.findByRole("img", { name: /ercot load zones/i });
    expect(map.getAttribute("aria-label")).toContain(String(predictions[0].score));
    const pause = screen.getByRole("button", { name: /pause map motion/i });
    fireEvent.click(pause);
    expect(screen.getByRole("button", { name: /resume map motion/i }).getAttribute("aria-pressed")).toBe("true");
    expect(styles).toMatch(/prefers-reduced-motion\s*:\s*reduce/);
    expect(styles).toMatch(/animation\s*:\s*none/);
  });

  it("API error objects render their readable message", async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 503, json: async () => ({ error: { code: "UNAVAILABLE", message: "Service unavailable" } }) });
    render(<Overview />);
    expect(await screen.findByText(/Service unavailable/i)).toBeTruthy();
    expect(document.body.textContent).not.toContain("[object Object]");
  });

  it("theme switch offers dark and light choices", async () => {
    render(<Shell><p>probe</p></Shell>);
    expect(await screen.findByText("probe")).toBeTruthy();
    const control = screen.getByRole("radiogroup", { name: /color theme/i });
    expect(within(control).getByText(/^dark$/i)).toBeTruthy();
    expect(within(control).getByText(/^light$/i)).toBeTruthy();
  });

  it("Explore in 3D link appears only with VITE_VIEWS_URL", async () => {
    vi.stubEnv("VITE_VIEWS_URL", "");
    const view = render(<Overview />);
    expect(await screen.findByText(new RegExp(predictions[0].zone))).toBeTruthy();
    expect(screen.queryByRole("link", { name: /explore in 3d/i })).toBeNull();
    vi.stubEnv("VITE_VIEWS_URL", VIEWS_URL);
    view.unmount();
    render(<Overview />);
    const link = await screen.findByRole("link", { name: /explore in 3d/i });
    expect(link.getAttribute("href")).toBe(`${VIEWS_URL}/godseye/`);
  });

  it("fixture badge appears only with VITE_FIXTURES=1", async () => {
    vi.stubEnv("VITE_FIXTURES", "");
    const view = render(<Shell><p>probe</p></Shell>);
    expect(await screen.findByText("probe")).toBeTruthy();
    expect(screen.queryByText(/illustrative fixtures/i)).toBeNull();
    view.unmount();
    vi.stubEnv("VITE_FIXTURES", "1");
    render(<Shell><p>probe</p></Shell>);
    expect(screen.getByText(/illustrative fixtures/i)).toBeTruthy();
  });

  it("shell and Overview share one status and signals poll", async () => {
    render(<App />);
    expect(await screen.findByText(providers[0].display_name)).toBeTruthy();
    for (const path of ["/v1/market/status", "/v1/signals"]) {
      expect(fetchMock.mock.calls.filter(([input]) => input === path)).toHaveLength(1);
    }
  });
});
