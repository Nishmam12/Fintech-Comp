// Typed client for the Budget Kernel API. Every value shown in the UI comes from these responses.
// Everything string-typed here may be model- or user-derived: render it as plain text only.

export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Scope = {
  categories: string[];
  recipients: string[];
  per_tx_limit: number;
  can_delegate: boolean;
  window_limit?: number;
  window_seconds?: number;
  review_above?: number;
};

export type Grant = {
  id: string;
  parent_id: string | null;
  depth: number;
  holder_principal_id: string;
  available: number;
  reserved: number;
  settled: number;
  status: string;
  expires_at: string;
  scope: Scope;
  window_used?: number;
};

export type Transaction = {
  id: string;
  grant_id: string;
  amount: number;
  currency: string;
  recipient: string;
  category: string;
  state: string;
  reject_reason: string | null;
  review_reason: string | null;
  reserve_expires_at: string | null;
  created_at: string;
};

export type MandateState = {
  mandate: {
    id: string;
    currency: string;
    total: number;
    protected_reserve: number;
    expires_at: string;
    owner_principal_id: string;
    [k: string]: unknown;
  };
  grants: Grant[];
  transactions: Transaction[];
  invariants: { ok: boolean; violations: unknown[] };
};

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

export async function api<T>(
  key: string,
  path: string,
  init?: { method?: "GET" | "POST"; body?: unknown },
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: init?.method ?? "GET",
      headers: {
        Authorization: `Bearer ${key}`,
        ...(init?.body !== undefined ? { "Content-Type": "application/json" } : {}),
      },
      body: init?.body !== undefined ? JSON.stringify(init.body) : undefined,
    });
  } catch {
    throw new ApiError(0, "NETWORK", "Cannot reach the API");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof data?.detail === "string" ? data.detail : undefined;
    throw new ApiError(res.status, data?.code ?? "HTTP_" + res.status, data?.message ?? detail ?? res.statusText);
  }
  return data as T;
}

export const getState = (key: string, mandateId: string) =>
  api<MandateState>(key, `/mandates/${encodeURIComponent(mandateId)}/state`);

// Display-only formatting of an integer minor-unit amount the API returned (no floats, no arithmetic on money).
export function money(minor: number, currency = "USD"): string {
  const neg = minor < 0;
  const s = Math.abs(minor).toString().padStart(3, "0");
  const whole = s.slice(0, -2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${neg ? "-" : ""}${whole}.${s.slice(-2)} ${currency.trim()}`;
}
