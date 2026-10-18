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
  holder_name?: string | null;
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

// One mapping for transaction states, used by the Mandate list and the Ask decision (BK-513).
// Pending is amber, settled jade, refused brick; colour marks state only.
const TX_STATE: Record<string, { label: string; tone: string }> = {
  proposed: { label: "Held for approval", tone: "text-warn" },
  reserved: { label: "Reserved", tone: "text-warn" },
  submitted: { label: "Sending", tone: "text-warn" },
  settled: { label: "Settled", tone: "text-ok" },
  rejected: { label: "Rejected", tone: "text-bad" },
  released: { label: "Released", tone: "text-muted" },
};
export const txState = (s: string) => TX_STATE[s] ?? { label: s, tone: "" };

// The name a grant card goes by: its holder, falling back to the short id when the API gives no name.
export const grantName = (g: Pick<Grant, "id" | "parent_id" | "holder_name">) =>
  g.parent_id === null ? "Owner's root grant" : (g.holder_name ?? `Grant ${g.id.slice(0, 8)}`);

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
    default:
      return REASON_TEXT[e.code] ?? `${e.code}: ${e.message}`;
  }
}

// Plain-language text for every refusal, review and permission code the kernel and API can emit (BK-514).
// The raw code is never the visible text: reasonTitle() gives it back for a `title` tooltip.
// `npm run check:reasons` fails when a kernel code is missing here.
const REASON_TEXT: Record<string, string> = {
  // Why a request was refused
  MANDATE_FROZEN: "This mandate is frozen, so nothing can be spent.",
  MANDATE_EXPIRED: "This mandate has expired.",
  PATH_BROKEN: "The chain of grants behind this one is incomplete, so the request was refused to be safe.",
  GRANT_REVOKED: "This grant was revoked.",
  GRANT_SUSPENDED: "This grant is suspended.",
  GRANT_EXPIRED: "This grant has expired.",
  CURRENCY_MISMATCH: "The currency does not match the mandate.",
  CATEGORY_NOT_ALLOWED: "This grant does not allow that category.",
  RECIPIENT_NOT_ALLOWED: "This grant does not allow paying that recipient.",
  PER_TX_LIMIT_EXCEEDED: "The amount is over this grant's limit for a single payment.",
  VELOCITY_LIMIT_EXCEEDED: "Too much has been spent in the current time window.",
  INSUFFICIENT_FUNDS: "This grant does not have enough money available.",
  TOO_MANY_PENDING_REVIEWS: "Too many requests are already waiting for the owner's approval.",
  DENIED_BY_REVIEWER: "The owner denied this request.",
  REVIEW_EXPIRED: "Nobody approved this request in time, so it lapsed.",
  RESERVATION_EXPIRED: "The reserved money was released because the payment was not completed in time.",
  // Why a request was held for the owner
  ABOVE_THRESHOLD: "The amount is above what this grant may spend without the owner's approval.",
  CALLER_FLAGGED: "The request was unclear or risky, so it needs the owner's approval.",
  // Why an action was not allowed
  NOT_OWNER: "Only the mandate owner can do this.",
  NOT_GRANT_HOLDER: "Only the holder of this grant can spend from it.",
  NOT_PERMITTED: "You are not allowed to do this.",
  NOT_SUSPENDED: "This grant is not suspended.",
  HUMAN_ONLY: "Only a person can do this, not an agent.",
  OWNER_MUST_BE_HUMAN: "A mandate owner must be a person.",
  NOT_A_SERVICE: "Only a service account can do this.",
  NOT_SETTLER: "Only the settlement service can do this.",
  PROOF_REQUIRED: "Proof is required before this can go through.",
  SELF_DELEGATION: "A grant cannot be passed to its own holder.",
  PARENT_CANNOT_DELEGATE: "The grant above this one does not allow passing money on.",
  MAX_DEPTH_EXCEEDED: "Grants cannot be nested any deeper.",
  SCOPE_WIDER_THAN_PARENT: "A grant cannot allow more than the grant it comes from.",
  EXPIRY_EXCEEDS_PARENT: "A grant cannot last longer than the grant it comes from.",
  EXPIRY_IN_PAST: "The expiry date is already in the past.",
  IDEMPOTENCY_CONFLICT: "This request id was already used for a different request.",
  INJECTION_SUSPECTED: "The request text looks like an attempt to manipulate the system, so it was not processed.",
  MANDATE_NOT_FOUND: "That mandate was not found.",
  GRANT_NOT_FOUND: "That grant was not found.",
  TX_NOT_FOUND: "That transaction was not found.",
  PRINCIPAL_NOT_FOUND: "That account was not found.",
  HOLDER_NOT_FOUND: "The person or agent to receive the grant was not found.",
  UNKNOWN_SCENARIO: "That attack scenario does not exist.",
  KEY_EXPIRED: "Your API key has expired. Get a new key from the administrator, then sign in again.",
  PRINCIPAL_DISABLED: "This account has been disabled. Contact the administrator.",
  KEY_ALREADY_ROTATED: "This key was already rotated. Sign in with the new key.",
  KERNEL_BUSY: "The kernel is busy. Try again in a moment.",
  RATE_LIMITED: "Too many requests. Wait a moment, then try again.",
  UNAUTHENTICATED: "That API key was not recognised. Check it and try again.",
  ADMIN_ONLY: "Only an administrator can do this.",
  SETTLEMENT_REFUSED: "The payment could not be sent, so it was not settled.",
  NOT_TESTNET_MODE: "Real test-network payments are switched off on this server.",
  ANCHOR_NEEDS_TESTNET: "Anchoring on the test network is switched off on this server.",
  ANCHOR_REFUSED: "The history could not be anchored on the test network.",
};
export const reasonText = (r: string) => REASON_TEXT[r] ?? r;
// For a `title` tooltip: the machine code behind the plain sentence.
export const reasonTitle = (r: string) => r;

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
  label?: string;
};
export type BudgetSnapshot = { month: string; buckets: Bucket[] };

export type AuditEvent = {
  id: number;
  kind: string;
  actor_principal_id: string | null;
  actor_name?: string | null;
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
