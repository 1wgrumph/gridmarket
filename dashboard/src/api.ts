/** Typed HTTP boundary for the frozen public routes. */
export type ApiError = { status?: number; retryAfter?: string; error: { code: string; message: string } };
export type MarketStatus = { status: string; anomalies: unknown[] };
export type Signal = { report_id: string; zone: string; value: number; unit: string; interval_start: string; interval_minutes: number; published_at: string; fetched_at: string; age_s: number; stale: boolean };
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
