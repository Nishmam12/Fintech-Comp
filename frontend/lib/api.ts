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
  // Untrusted model output (null for non-agent requests). Render as plain text only.
  proposal?: Proposal | null;
  // Null until a real transfer exists. Use as returned; never build explorer URLs client-side.
  explorer_url?: string | null;
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

export type TrailStep = {
  step: string;
  outcome?: string;
  provider?: string;
  model_id?: string;
  prompt_version?: string;
  cost_micro?: number;
  [k: string]: unknown;
};

export type Proposal = {
  request_type: string;
  amount_minor: number | null;
  currency: string | null;
  recipient: string | null;
  category: string | null;
  purpose: string | null;
  evidence: { field: string; quote: string }[];
  missing_fields: string[];
  ambiguities: string[];
  conflicts: string[];
  needs_human_review: boolean;
  explanation: string;
};

export type Interpretation = {
  status: "ok" | "needs_review" | "unresolved" | "rejected_input";
  proposal: Proposal | null;
  reasons: string[];
  trail: TrailStep[];
};

export type Decision = {
  transaction_id: string;
  state: string;
  reason: string | null;
  review_reason?: string | null;
  replayed: boolean;
};

export type AgentResponse = { interpretation: Interpretation; decision: Decision | null };

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

async function once(key: string, path: string, init?: { method?: "GET" | "POST"; body?: unknown }) {
  try {
    return await fetch(`${API_BASE}${path}`, {
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
}

export async function api<T>(
  key: string,
  path: string,
  init?: { method?: "GET" | "POST"; body?: unknown },
): Promise<T> {
  let res = await once(key, path, init);
  // The hosted database sometimes drops an idle pooled connection, which surfaces as one 5xx.
  // Reads are idempotent, so retry a GET once; writes are never retried here.
  if (res.status >= 500 && (init?.method ?? "GET") === "GET") res = await once(key, path, init);
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

export type Bucket = {
  bucket: string;
  cap_micro_usd: number;
  reserved_micro: number;
  spent_micro: number;
  remaining_micro: number;
};
export type BudgetSnapshot = { month: string; buckets: Bucket[] };

export type AuditEvent = {
  id: number;
  kind: string;
  actor_principal_id: string | null;
  subject_id: string | null;
  detail: Record<string, unknown> | null;
  created_at: string;
};

// Display-only: integer micro-USD (1 USD = 1,000,000) written as dollars with six decimals, by string slicing.
export function microUsd(micro: number): string {
  const neg = micro < 0;
  const s = Math.abs(micro).toString().padStart(7, "0");
  return `${neg ? "-" : ""}$${s.slice(0, -6)}.${s.slice(-6)}`;
}

export type Me = { principal_id: string; name: string; kind: string };
export type MandateSummary = {
  id: string;
  currency: string;
  total: number;
  status: string;
  expires_at: string;
  created_at: string;
  role: "owner" | "holder";
};
export const getMe = (key: string) => api<Me>(key, "/me");
export const listMandates = (key: string) => api<{ mandates: MandateSummary[] }>(key, "/mandates");
