# ADR-0008: Velocity Limits and Approval Threshold

- **Status:** ACCEPTED (2026-10-15, team lead)
- **Date:** 2026-10-15
- **Owner:** Opus planner (design) / project lead (approval) / Sonnet orchestrator (implementation)
- **Related tasks:** BK-301, BK-302, and BK-090/BK-324 (dashboard)
- **Related ADRs:**
  - ADR-0004: scope and attenuation
  - ADR-0005: lock, sweep, states, review
  - Security self-assessment risk R1 (split purchases)

## Context
A grant's scope currently limits each payment (`per_tx_limit`) and the total (the grant's balance). It does not limit **rate**. The `split_purchases` scenario proves this: a 30,000 request is refused, but five requests of 10,000 are approved.

There is also no way for an owner to say "anything above X needs my approval". Today review only happens when the interpretation layer flags a request, and a malicious holder can skip that layer (self-assessment section 3, policy note).

Both new controls must be enforced by the kernel, under the mandate lock, from database state. They must also hold against a holder who calls `/transactions/authorize` directly.

## Decision

### 1. New optional scope fields (API contract, frozen by this ADR)
| Field | Type | Meaning | Default |
|---|---|---|---|
| `window_limit` | integer, minor units, > 0 | Maximum committed spend in any rolling window, across this grant's **whole subtree** | absent = no velocity limit |
| `window_seconds` | integer, 60 ≤ x ≤ 2,592,000 (30 days) | Length of that rolling window | required if `window_limit` is set, forbidden otherwise |
| `review_above` | integer, minor units, ≥ 0 | Requests with `amount > review_above` are held for owner approval instead of reserved | absent = no threshold |

- **Existing scopes stay valid.** The four existing keys remain required; the three new ones are optional.
- **Normal form.** `validate_scope` stores only the keys that are present.
- **API.** The `Scope` request model gains three optional `StrictInt` fields, and the handler passes `model_dump(exclude_none=True)`.

### 2. Velocity limit: what counts and when
- **Counted:** transactions in state `reserved`, `submitted` or `settled` whose `reserved_at` falls inside `(ctx.now − window_seconds, ctx.now]` and whose grant lies in the subtree of the limiting grant (`grants.path @> ARRAY[limiting_grant]`).
- **Not counted:**
  - `released` transactions (the money was returned)
  - `proposed` transactions (no funds held)
  - `rejected` transactions
- **New column `transactions.reserved_at`:** set to `ctx.now` whenever a transaction enters `reserved`, whether through `authorize` or through owner `review`.
  - We use it instead of `created_at`. Otherwise a proposal approved hours later would be dated in the past and could slip out of the window.
  - Existing reserved, submitted and settled rows are backfilled with `created_at`.
- **Check, inside `_authorize_problem`, under the lock:** for **every grant on the request's path** (self and all ancestors) that has a `window_limit`, require
  `window_spend(grant) + amount ≤ window_limit`.
  - Otherwise refuse with `VELOCITY_LIMIT_EXCEEDED`, stored as an ordinary `rejected` transaction.
  - The check runs after `PER_TX_LIMIT_EXCEEDED` and before `INSUFFICIENT_FUNDS`.
- **Why ancestors too:**
  - A parent's limit binds its whole subtree, so a holder cannot escape it by delegating to sub-agents.
  - This is the same reason the revocation check walks the full path.
  - It also makes attenuation of the window safe without extra rules (section 4).
- **Owner approval re-checks the window.** `review(approve=True)` re-runs `_authorize_problem`, so a held proposal is approved only if the window still allows it at approval time.
- **Cost.** At most `MAX_DEPTH + 1 = 5` aggregate queries per authorization, each using the existing GIN index on `grants.path` plus a new index on `transactions (mandate_id, reserved_at)`. They run under the lock that already serializes the mandate, so the sums cannot race.

### 3. Approval threshold
- **Effective threshold:** the **minimum** `review_above` over the request's path (self and ancestors). An ancestor's threshold therefore binds every descendant.
- **Order of decisions in `authorize`:**
  1. **Refuse.** Any `_authorize_problem` (including velocity) → `rejected`.
  2. **Hold.** Otherwise, if `needs_review` (caller flag) **or** `amount > effective threshold` → `proposed`, holding no funds. A new column `review_reason` takes `CALLER_FLAGGED` or `ABOVE_THRESHOLD`; the threshold wins when both apply. The `TX_PROPOSED` audit event carries the reason.
  3. **Reserve.** Otherwise → `reserved`.
- **Exemption for the mandate owner.** The threshold does not apply when the actor is the mandate owner (tier T0): the owner is the approver, so holding the owner's own request for the owner's approval adds nothing. The caller's `needs_review` flag still applies to the owner.
- **Idempotency is unchanged.** The threshold is derived from stored scope, not from the request. A replay returns the stored decision, and the payload hash does not change.
- **Proposal expiry is unchanged.** Unreviewed proposals are auto-rejected after 24 hours (ADR-0005 section 3).

### 4. Attenuation (delegation)
`is_subset(child, parent)` gains three rules:
- **Window limit.** If the parent has `window_limit`, the child **may** omit it. The ancestor check in section 2 still binds the child. If the child sets one, it must satisfy `child.window_limit ≤ parent.window_limit` **and** `child.window_seconds ≥ parent.window_seconds` (amended during implementation: the same cap over a *shorter* window allows more spend per hour than the parent declared, so it reads looser; a longer window binds harder).
- **Approval threshold.** If the parent has `review_above`, the child may omit it, and the ancestor minimum still binds. If set, it must satisfy `child.review_above ≤ parent.review_above`.
- **Parent without these fields.** The child may add either control freely; adding one only narrows the child.

The rules exist so that a child's *declared* scope never reads wider than its parent's. Safety itself comes from the path-wide checks. A violation returns `SCOPE_WIDER_THAN_PARENT`, as today.

### 5. Migration `005_robustness.sql` (lead)
- **New columns:** `ALTER TABLE transactions ADD COLUMN reserved_at timestamptz` and `ADD COLUMN review_reason text CHECK (review_reason IN ('CALLER_FLAGGED','ABOVE_THRESHOLD'))`.
- **Backfill:** set `reserved_at = created_at` where state is `reserved`, `submitted` or `settled`.
- **Index:** `CREATE INDEX transactions_mandate_reserved_idx ON transactions (mandate_id, reserved_at)`.
- **Constraint:** `CHECK (state <> 'reserved' OR reserved_at IS NOT NULL)`. `reserved_at` stays set after the transaction leaves `reserved`, so the window keeps counting `submitted` and `settled` spend.

### 6. API and read models
- `GET /mandates/{id}/state` includes, for each grant that has a window, `window_used` (the same subtree sum, computed at read time) next to `window_limit` and `window_seconds`. The dashboard velocity meter (BK-324) reads these values and never computes them itself.
- Transactions in the state response include `review_reason`.

## Consequences
- **Closes R1** for every grant that sets a window. Splitting a large purchase into small ones now hits `VELOCITY_LIMIT_EXCEEDED` once the window total is reached. The `split_purchases` scenario gains a second kernel run with a window and must show the refusal. The self-assessment moves R1 from "Accepted" to "Mitigated (opt-in)".
- **Adds a control that binds a malicious holder:** a large payment can't be made without the owner's approval, whichever endpoint the holder calls.
- **Cost:** more work under the mandate lock. The added time per operation must be measured (target under 100 ms over the pooler) and reported.
- **Limitation:** a rolling window counts reservations, so releasing a reservation frees window capacity immediately. That is intended, because a released reservation is money not spent.

## Tests required before merge (Opus review gate)
1. **Window refusal:** with a window limit of 30,000, four spends of 10,000 give three `reserved` and one `VELOCITY_LIMIT_EXCEEDED`.
2. **Ancestor limit binds the subtree:** a parent window of 20,000 and two children spending 10,000 each; the third spend from either child is refused.
3. **Window expiry:** spends older than the window stop counting. Use a short window and `ctx.now` control, or backdate `reserved_at` in the test DB.
4. **Released reservations free capacity;** submitted and settled spends keep counting.
5. **Approval threshold:** `amount > review_above` → `proposed` with `ABOVE_THRESHOLD`, holding no funds. Approval moves it to `reserved` with `reserved_at` set at approval time. An ancestor threshold binds a child. The owner's own request is not held.
6. **Approval re-checks the window:** a proposal whose approval would break the window is rejected with `VELOCITY_LIMIT_EXCEEDED`.
7. **Attenuation:**
   - a child with a larger `window_limit` or `review_above` than the parent → `SCOPE_WIDER_THAN_PARENT`
   - a child omitting both → accepted
8. **Concurrency:** 8 racing spends against a window of 30,000 give exactly 3 reserved, and the invariants hold.
9. **State machine:** the property-based test generates scopes with and without the new fields, and invariants I1–I5 hold after every step.
10. **Replay:** the same key returns the stored `proposed` or `rejected` decision.
11. **Boundary:** the existing tests still pass, and scopes without the new fields behave exactly as before.

## Rejected alternatives
- **A fixed calendar window (per day or month):** allows twice the limit around the boundary. Rejected in favour of a rolling window.
- **A per-grant counter column updated on each spend:** a second representation of the same money, with drift risk (ADR-0004 forbids derived duplicates). Rejected in favour of an aggregate query under the lock.
- **Enforcing velocity in the router or interpretation layer:** bypassable by direct API calls. Rejected.
- **A threshold that applies only to the declaring grant:** a child could escape the parent's threshold by delegating. Rejected in favour of the path minimum.

## Review amendments (Opus, 2026-10-15)
- **Pending-review cap.** At most `MAX_PENDING_REVIEWS = 20` proposals may wait per grant. A further request that would be held is refused with `TOO_MANY_PENDING_REVIEWS` (stored as `rejected`, nothing reserved). Without the cap, a holder could bury the owner's approval inbox at no cost (self-assessment R21).
- **No extra round trips.** The path check now returns each path grant's scope, cached on the operation context. Scope is immutable by trigger, so the cache can't go stale. The window and threshold checks reuse it, so grants without these controls pay no extra queries under the lock.
