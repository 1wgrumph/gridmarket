// @vitest-environment jsdom
/* S55 ESR battery tile, rendered from dashboard/src/fixtures/esr.json
   with fetch stubbed (no network). Scoped queries only. */
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from "vitest";
// @ts-ignore TS2732: resolveJsonModule is off in the frozen tsconfig; vitest/vite load JSON at runtime.
import fixture from "../fixtures/esr.json";
import Overview from "./Overview";

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
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("S55 ESR battery tile (fixture: esr.json)", () => {
  it("renders the latest ESR MW value with a sparkline", async () => {
    render(<Overview />);
    const tile = await screen.findByRole("region", { name: /texas batteries charging now/i });
    expect(await within(tile).findByText(/812\.5/)).toBeTruthy();
    expect(within(tile).getByText((_, el) => el?.tagName === "SMALL" && (el.textContent ?? "").includes("MW"))).toBeTruthy();
    expect(tile.querySelector("svg.esr-spark")).not.toBeNull();
  });

  it("shows a quiet unavailable state with no ESR signal", async () => {
    fetchMock.mockImplementation(async () => ({ ok: true, status: 200, json: async () => [] }));
    render(<Overview />);
    const tile = await screen.findByRole("region", { name: /texas batteries charging now/i });
    expect(await within(tile).findByText(/battery data not yet available/i)).toBeTruthy();
    expect(within(tile).queryByText(/error/i)).toBeNull();
  });
});
