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
  // ADR-0009 B: circuit breaker. Present on every grant from /mandates/{id}/state.
  suspended_at?: string | null;
  suspend_reason?: "STRIKES" | "MANUAL" | null;
  strikes_in_window?: number;
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
  suspended?: boolean; // true when this refusal tripped the circuit breaker (ADR-0009 B4)
};

export type AgentResponse = { interpretation: Interpretation; decision: Decision | null };

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public retryAfter?: number) {
    super(message);
  }
}

// Codes after which the key can no longer be used: the session is dropped and the user returns to sign-in.
const AUTH_LOST = new Set(["KEY_EXPIRED", "PRINCIPAL_DISABLED"]);
let onAuthLost: ((code: string) => void) | null = null;
export function setAuthLostHandler(fn: ((code: string) => void) | null) {
  onAuthLost = fn;
}

// Friendly text for the codes the user can act on; everything else is shown as the server sent it.
export function describeError(e: unknown, fallback: string): string {
  if (!(e instanceof ApiError)) return fallback;
  switch (e.code) {
    case "RATE_LIMITED":
      return e.retryAfter !== undefined
        ? `Too many requests. Wait ${e.retryAfter} s, then try again.`
        : "Too many requests. Wait a moment, then try again.";
    case "KEY_EXPIRED":
      return "Your API key has expired. Get a new key from the administrator, then sign in again.";
    case "PRINCIPAL_DISABLED":
      return "This account has been disabled. Contact the administrator.";
    case "GRANT_SUSPENDED":
      return "This grant is suspended, so it cannot spend. The mandate owner can reinstate it.";
    default:
      return `${e.code}: ${e.message}`;
  }
}

// Reasons on a rejected transaction that deserve a plain-language gloss. Unknown codes are shown unchanged.
const REASON_TEXT: Record<string, string> = {
  GRANT_SUSPENDED: "GRANT_SUSPENDED · this grant (or one above it) is suspended",
};
export const reasonText = (r: string) => REASON_TEXT[r] ?? r;

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
    // Errors arrive as {code, message} (kernel) or {detail: {code, message}} / {detail: "text"} (API layer).
    const d = data?.detail && typeof data.detail === "object" ? data.detail : undefined;
    const detail = typeof data?.detail === "string" ? data.detail : undefined;
    const code = data?.code ?? d?.code ?? "HTTP_" + res.status;
    const ra = Number.parseInt(res.headers.get("Retry-After") ?? "", 10);
    if (res.status === 401 && AUTH_LOST.has(code)) onAuthLost?.(code);
    throw new ApiError(res.status, code, data?.message ?? d?.message ?? detail ?? res.statusText,
      Number.isFinite(ra) ? ra : undefined);
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

// ADR-0009 A4 (frozen). last_anchor is null until a confirmed on-chain anchor exists.
export type Integrity = {
  mandate_id: string;
  chain_key: string;
  ok: boolean;
  length: number;
  head_seq: number;
  head_hash: string;
  broken_at: number | null;
  reason: string | null;
  verified_at: string;
  last_anchor: {
    anchor_id: number;
    seq: number;
    head_hash: string;
    tx_hash: string | null;
    status: string;
    explorer_url: string | null;
    matches: boolean;
  } | null;
};
export const getIntegrity = (key: string, mandateId: string) =>
  api<Integrity>(key, `/mandates/${encodeURIComponent(mandateId)}/integrity`);

export type Me = { principal_id: string; name: string; kind: string };
export type RotatedKey = { api_key: string; key_expires_at: string | null };
export const rotateKey = (key: string) => api<RotatedKey>(key, "/me/rotate-key", { method: "POST", body: {} });
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

export type SimSide = { violated: boolean; summary: string; metrics: Record<string, unknown> };
export type SimResult = {
  scenario: string;
  title: string;
  what_it_proves: string;
  informational: boolean;
  duration_ms: number;
  naive: SimSide;
  kernel: SimSide;
};
export const listScenarios = (key: string) => api<{ scenarios: string[] }>(key, "/simulation/scenarios");
export const runScenario = (key: string, scenario: string) =>
  api<SimResult>(key, "/simulation/run", { method: "POST", body: { scenario } });
