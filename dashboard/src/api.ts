/** Typed HTTP boundary for the frozen public routes. */
export type ApiError = { error: { code: string; message: string } };
export type MarketStatus = { status: string };
export type PageResponse<T> = { items: T[] };
export type MarketProduct = { id: string; symbol: string; zone: string; delivery_hour: string; status: string };
export type Prediction = { zone: string; delivery_hour: string; score: number; level: string; confidence: number; expected_value: number; market_price: number | null; drivers: { factor: string; contribution: number; detail: string }[]; disclaimer: string; generated_at: string };
export type Provider = { id: string; display_name: string; online: boolean };
export type Bot = { id: string; bot_type: string; provider_id: string; cash: number; net_worth: number; pnl: number; losses: number; dormant: boolean };
export type RouterCheck = { check_id: string; family: 'market' | 'health'; subject: string; probability: number; band: 'log' | 'review' | 'alert'; baseline: boolean; jev_probability: number | null };

export async function get<T>(path: string, key?: string): Promise<T> {
  const response = await fetch(path, { headers: key ? { Authorization: `Bearer ${key}` } : {} });
  if (!response.ok) throw await response.json() as ApiError;
  return await response.json() as T;
}

export async function send<T>(method: 'POST' | 'DELETE', path: string, body?: unknown, key?: string, idempotencyKey?: string): Promise<T> {
  const response = await fetch(path, {
    method,
    headers: { 'Content-Type': 'application/json', ...(key ? { Authorization: `Bearer ${key}` } : {}), ...(idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) throw await response.json() as ApiError;
  return await response.json() as T;
}
