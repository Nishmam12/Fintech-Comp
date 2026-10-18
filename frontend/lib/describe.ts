// One plain sentence per audit event (BK-503). Display only: every value is coerced to a string or number first,
// because details can hold model- or user-derived text. Callers render the result as plain text.
import { money, type AuditEvent } from "@/lib/api";

const REASONS: Record<string, string> = {
  CATEGORY_NOT_ALLOWED: "this category is not allowed",
  RECIPIENT_NOT_ALLOWED: "this recipient is not allowed",
  PER_TX_LIMIT_EXCEEDED: "it is over the per-payment limit",
  VELOCITY_LIMIT_EXCEEDED: "it would break the hourly spending limit",
  INSUFFICIENT_FUNDS: "the grant does not have enough funds",
  GRANT_SUSPENDED: "the grant is suspended",
  GRANT_REVOKED: "the grant was revoked",
  GRANT_EXPIRED: "the grant has expired",
  MANDATE_EXPIRED: "the mandate has expired",
  MANDATE_FROZEN: "the mandate is frozen",
  CURRENCY_MISMATCH: "the currency does not match",
  TOO_MANY_PENDING_REVIEWS: "too many requests are already waiting for approval",
  MAX_PENDING_REVIEWS: "too many requests are already waiting for approval",
  CALLER_FLAGGED: "the caller is flagged",
  NOT_GRANT_HOLDER: "the caller does not hold this grant",
  ABOVE_THRESHOLD: "it is above the approval threshold",
  DENIED_BY_REVIEWER: "the reviewer said no",
  RESERVATION_EXPIRED: "the reservation timed out",
};

const reason = (r: unknown) => (typeof r === "string" ? REASONS[r] ?? r.toLowerCase().replace(/_/g, " ") : "no reason given");
const amt = (v: unknown) => (typeof v === "number" ? money(v) : "an amount");

export function describeEvent(ev: AuditEvent): string {
  const d = (ev.detail ?? {}) as Record<string, unknown>;
  const who = ev.actor_name ?? "The system";
  const amount = amt(d.amount);
  switch (ev.kind) {
    case "MANDATE_CREATED":
      return `${who} created a mandate of ${typeof d.total === "number" ? money(d.total, typeof d.currency === "string" ? d.currency : "USD") : "funds"}, with ${amt(d.protected_reserve)} kept in reserve.`;
    case "GRANT_DELEGATED":
      return `${who} delegated ${amount} to a new grant.`;
    case "TX_REJECTED":
      return `${who} asked to pay ${amount}. Refused: ${reason(d.reason)}.`;
    case "TX_PROPOSED":
      return `${who} asked to pay ${amount}. Held for approval: ${reason(d.review_reason)}.`;
    case "TX_RESERVED":
      return `${who} reserved ${amount}${typeof d.recipient === "string" ? ` for ${d.recipient}` : ""}${typeof d.category === "string" ? ` (${d.category})` : ""}.`;
    case "TX_APPROVED":
      return `${who} approved ${amount}.`;
    case "TX_REVIEW_REJECTED":
      return `${who} declined a held payment: ${reason(d.reason)}.`;
    case "TX_REVIEW_EXPIRED":
      return "A held payment expired before anyone approved it.";
    case "TX_RELEASED":
      return `A reservation was released and the funds returned (${reason(d.reason)}).`;
    case "TX_SUBMITTED":
      return `${who} sent a payment for settlement.`;
    case "TX_SETTLED":
      return `${amount} was paid and settled.`;
    case "TX_SETTLE_FAILED":
      return `${who} reported a payment failed; the funds went back to the grant.`;
    case "GRANT_SUSPENDED":
      return d.reason === "STRIKES"
        ? `Circuit breaker suspended a grant after ${typeof d.strikes === "number" ? d.strikes : "several"} refused requests.`
        : `${who} suspended a grant.`;
    case "GRANT_REINSTATED":
      return `${who} reinstated a suspended grant.`;
    case "GRANT_REVOKED":
      return `${who} revoked a grant. Unspent funds went back up the chain.`;
    case "GRANT_EXPIRED":
      return "A grant expired. Unspent funds went back up the chain.";
    case "SETTLER_BOUND":
      return `${who} allowed a settlement service to pay out of this mandate.`;
    case "SETTLER_UNBOUND":
      return `${who} removed a settlement service from this mandate.`;
    case "KEY_ROTATED":
      return `${who} rotated their API key.`;
    case "PRINCIPAL_DISABLED":
      return "A principal was disabled and can no longer sign in.";
    default:
      return ev.kind;
  }
}
