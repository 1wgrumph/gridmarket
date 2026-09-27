/* S72 A11 estimate maths: amendment-11 equations for one simulated home and
   fleet MW scaling. Expected values are hand-computed from the amendment
   text (eta_d = sqrt(0.9)), not from the implementation. */
import { describe, expect, it } from "vitest";
import { estimateHome, fleetMw } from "./estimate";

const HOME = {
  capacityKwh: 13.5, initialSocKwh: 6.75, maxDischargeKw: 5,
  etaRoundTrip: 0.9, loadKw: 1.2, horizonHours: 4,
};
const ETA = Math.sqrt(0.9);

describe("S72 estimateHome (A11)", () => {
  it("computes flexibility and backup at 40% reserve", () => {
    const e = estimateHome({ ...HOME, reservePct: 40 });
    expect(e.reserveKwh).toBeCloseTo(5.4, 10);
    expect(e.flexibilityKwh).toBeCloseTo(Math.min(20, ETA * 1.35), 10);
    expect(e.flexibilityKwh).toBeCloseTo(1.2807, 4);
    expect(e.backupHours).toBeCloseTo((ETA * 5.4) / 1.2, 10);
    expect(e.backupHours).toBeCloseTo(4.2691, 4);
    expect(e.warnings).toEqual([]);
  });

  it("offers the whole charge at 0% reserve and no backup", () => {
    const e = estimateHome({ ...HOME, reservePct: 0 });
    expect(e.flexibilityKwh).toBeCloseTo(ETA * 6.75, 10);
    expect(e.backupHours).toBe(0);
    expect(e.warnings).toEqual([]);
  });

  it("warns and zeroes flexibility when reserve sits above starting charge", () => {
    const e = estimateHome({ ...HOME, reservePct: 100 });
    expect(e.reserveKwh).toBeCloseTo(13.5, 10);
    expect(e.flexibilityKwh).toBe(0);
    expect(e.warnings).toContain("reserve_not_yet_met");
    // Backed-up energy is limited to the current charge.
    expect(e.backupHours).toBeCloseTo((ETA * 6.75) / 1.2, 10);
  });

  it("caps flexibility by discharge power over short windows", () => {
    const e = estimateHome({ ...HOME, reservePct: 0, horizonHours: 0.25 });
    expect(e.flexibilityKwh).toBeCloseTo(5 * 0.25, 10);
  });

  it("returns not_applicable for zero load and warns on excessive load", () => {
    const zero = estimateHome({ ...HOME, reservePct: 40, loadKw: 0 });
    expect(zero.backupHours).toBeNull();
    expect(zero.warnings).toContain("not_applicable");
    const heavy = estimateHome({ ...HOME, reservePct: 40, loadKw: 6 });
    expect(heavy.backupHours).toBeNull();
    expect(heavy.warnings).toContain("power_insufficient");
  });

  it("scales fleet MW over the stated window, capped by online power", () => {
    const perHome = estimateHome({ ...HOME, reservePct: 40 }).flexibilityKwh;
    const fleet = fleetMw({ perHomeKwh: perHome, homes: 1000, horizonHours: 4, maxDischargeKw: 5 });
    expect(fleet.mw).toBeCloseTo((1000 * perHome) / 4 / 1000, 10);
    expect(fleet.mw).toBeCloseTo(0.3202, 4);
    expect(fleet.durationHours).toBe(4);
    const capped = fleetMw({ perHomeKwh: 100, homes: 10000, horizonHours: 4, maxDischargeKw: 5 });
    expect(capped.mw).toBe(50);
  });
});
