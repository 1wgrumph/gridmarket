/** DEC-GM-113 amendment 11: single-window flexibility, backup hours and fleet MW. Pure maths; the replay-day value always comes from POST /v1/replay. */

export type HomeSpec = {
  capacityKwh: number; initialSocKwh: number; maxDischargeKw: number;
  etaRoundTrip: number; reservePct: number; loadKw: number; horizonHours: number;
};
export type HomeEstimate = {
  reserveKwh: number; flexibilityKwh: number;
  backupHours: number | null; backupKwh: number;
  warnings: ('reserve_not_yet_met' | 'power_insufficient' | 'not_applicable')[];
};

export function estimateHome(spec: HomeSpec): HomeEstimate {
  const eta = Math.sqrt(spec.etaRoundTrip);
  const reserveKwh = spec.capacityKwh * spec.reservePct / 100;
  const warnings: HomeEstimate['warnings'] = [];
  const flexibilityKwh = reserveKwh > spec.initialSocKwh
    ? 0
    : Math.min(spec.maxDischargeKw * spec.horizonHours, eta * Math.max(spec.initialSocKwh - reserveKwh, 0));
  if (reserveKwh > spec.initialSocKwh) warnings.push('reserve_not_yet_met');
  const backupKwh = eta * Math.min(spec.initialSocKwh, reserveKwh);
  let backupHours: number | null;
  if (spec.loadKw === 0) {
    backupHours = null;
    warnings.push('not_applicable');
  } else if (spec.loadKw > spec.maxDischargeKw) {
    backupHours = null;
    warnings.push('power_insufficient');
  } else {
    backupHours = backupKwh / spec.loadKw;
  }
  return { reserveKwh, flexibilityKwh, backupHours, backupKwh, warnings };
}

export function fleetMw({ perHomeKwh, homes, horizonHours, maxDischargeKw }: {
  perHomeKwh: number; homes: number; horizonHours: number; maxDischargeKw: number;
}): { mw: number; durationHours: number } {
  return {
    mw: Math.min(homes * perHomeKwh / horizonHours / 1000, homes * maxDischargeKw / 1000),
    durationHours: horizonHours,
  };
}
