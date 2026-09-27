/** Typed HTTP boundary for the frozen public routes. */
export type ApiError = { status?: number; retryAfter?: string; error: { code: string; message: string } };
export type MarketStatus = { status: string; anomalies: unknown[]; open_interest?: number; active_traders?: number };
export type Signal = { report_id: string; zone: string; value: number; unit: string; interval_start: string; interval_minutes: number; published_at: string; fetched_at: string; age_s: number; stale: boolean };
export type SignalHistoryRow = { interval_start: string; interval_end: string; value: number; unit: string; published_at: string; stale: boolean };
export type Activity = { id: string; type: string; label: string; symbol: string | null; side: string | null; quantity: number | null; price_cents: number | null; reason: string | null; created_at: string; entry_type: string; subject_id: string | null };
export type Trade = { id: string; product_id: string; buy_order_id: string; sell_order_id: string; quantity: number; price_cents: number; created_at: string };
export type BookLevel = { side: 'buy' | 'sell'; price_cents: number; quantity: number };
export type PageResponse<T> = { items: T[] };
export type MarketProduct = { id: string; symbol: string; zone: string; delivery_hour: string; status: string };
export type ProductDetail = MarketProduct & { orders: BookLevel[] };
export type Prediction = { zone: string; delivery_hour: string; score: number; level: string; confidence: number; expected_value: number; market_price: number | null; drivers: { factor: string; contribution: number; detail: string }[]; disclaimer: string; generated_at: string };
export type Provider = { id: string; display_name: string; online: boolean; participants?: number };
export type Bot = { id: string; bot_type: string; provider_id: string; cash: number; net_worth: number; pnl: number; losses: number; dormant: boolean };
export type RouterCheck = { check_id: string; family: 'market' | 'health'; subject: string; probability: number; band: 'log' | 'review' | 'alert'; baseline: boolean; jev_probability: number | null };
export type ReplayDay = {
  day: string; timezone: string; quarters: number; gaps: string[]; synthetic: boolean;
  claims_external_observation: boolean; label: string; availability_mode: string; availability_note: string;
  peak_rt_price: { point: string; interval_start: string; interval_end: string; value: number; unit: string };
  dataset_digest: string;
};
export type ReplayInput = {
  name: string; value: string | number; unit: string; source: string;
  interval_start: string; interval_end: string; published_at: string; available_at: string; quality: string;
};
export type ReplayDecision = {
  strategy: string; asset_id: string; decision_time: string; action: string; kw: string;
  delivery_start: string; delivery_end: string; reason: string; policy_version: string;
  config: { zone?: string; state_snapshot?: { soc_kwh?: string } };
  inputs: ReplayInput[];
};
export type ReplaySettlement = {
  strategy: string; asset_id: string; delivery_start: string; delivery_end: string;
  requested_kwh: string; accepted_kwh: string; delivered_kwh: string; shortfall_kwh: string; cause: string | null;
};
export type ReplayStep = { interval_start: string; interval_end: string; decisions: ReplayDecision[]; settlements: ReplaySettlement[] };
export type ReplayScore = {
  strategy: string; net_value_cents: number; cash_net_cents: number; energy_value_cents: number;
  charging_cost_cents: number; flexibility_bonus_cents: number; shortfall_penalty_cents: number;
  opening_energy_value_cents: number; terminal_energy_value_cents: number;
  energy_delivered_kwh: string; requested_kwh: string; accepted_kwh: string; delivered_kwh: string;
  shortfall_kwh: string; self_supply_kwh: string; min_reserve_kwh: string; observed_min_soc_kwh: string;
  start_soc_kwh: string; end_soc_kwh: string; reserve_breach_count: number;
  attempted_reserve_violations: number; failed_commitments: number;
};
export type FleetRow = {
  interval_start: string; interval_end: string; soc_kwh: string; spp: string;
  charge_kw: string; offered_kwh: string; accepted_kwh: string; delivered_kwh: string;
  self_supply_kwh: string; shortfall_kwh: string; failed_commitments: number;
};
export type ReplayAsset = {
  asset_id: string; provider_id: string; capacity_kwh: string; initial_soc_kwh: string;
  min_reserve_kwh: string; max_charge_kw: string; max_discharge_kw: string; eta_round_trip: string;
};
export type ReplayRun = {
  run_id: string; day: string; label: string; claims_external_observation: boolean; disclaimer: string;
  availability_mode: string; availability_note: string;
  binding: {
    day: string; seed: number; strategies: string[];
    fleet: { zone: string; label: string; assets: ReplayAsset[] };
    disruptions: { type: string; provider_id?: string; source?: string; start: string; end: string }[];
  };
  scoreboard: ReplayScore[]; timeline: ReplayStep[];
  /** S69b body: fleet aggregates per strategy, DAM-selected procurement hours, sample home. */
  fleet_timeline: Record<string, FleetRow[]>;
  procurement_hours: string[];
  sample_asset_id: string;
  strategy_rules: Record<string, { display_name: string; rules: string }>;
};

export async function get<T>(path: string, key?: string): Promise<T> {
  const response = await fetch(path, { headers: key ? { Authorization: `Bearer ${key}` } : {} });
  if (!response.ok) throw await responseError(response);
  return await response.json() as T;
}

export async function send<T>(method: 'POST' | 'DELETE', path: string, body?: unknown, key?: string, idempotencyKey?: string): Promise<T> {
  const response = await fetch(path, {
    method,
    headers: { 'Content-Type': 'application/json', ...(key ? { Authorization: `Bearer ${key}` } : {}), ...(idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) throw await responseError(response);
  return await response.json() as T;
}

/** Edge proxies may return HTML or empty bodies instead of the API envelope. */
async function responseError(response: Response): Promise<ApiError> {
  const fallback = { code: `HTTP_${response.status}`, message: `Service unavailable (HTTP ${response.status})` };
  let error = fallback;
  try {
    const body = await response.json();
    if (typeof body?.error?.message === 'string' && typeof body?.error?.code === 'string') error = body.error;
  } catch { /* Keep the readable HTTP status for non-JSON edge errors. */ }
  return { error, status: response.status, retryAfter: response.headers?.get('Retry-After') ?? undefined };
}
export type ReplayPeak = { point: string; interval_start: string; interval_end: string; value: number; unit: string };
export type ReplayDays = { days: { day: string; timezone: string; peak_rt_price: ReplayPeak | null }[] };
