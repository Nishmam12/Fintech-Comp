# ADR-0004: Canonical Accounting Representation for Mandates and Grants

- **Status:** PROPOSED
- **Date:** 2026-10-15
- **Owner:** Opus planner (draft) / project lead (approval)
- **Related tasks:** BK-010, BK-020, BK-030, BK-110
- **Related ADRs:** ADR-0001 (authority boundary), ADR-0005 (lifecycle/concurrency/revocation), ADR-0007 (testnet settlement)
- **Resolves:** OQ-003

## Context
A mandate gives an agent tree a bounded amount of spending authority in one currency. Parents delegate part of their authority to children. The representation must make it impossible to count one unit of authority twice (parent and child both believing they can spend it) and must let a test prove that by checking an invariant after every operation. Money is integer minor units (`BIGINT`). Postgres (Supabase) is the only source of truth.

## Options considered
1. **Allocation tree with a derived "remaining" (cap minus SUM of descendants' spend).** Natural to read, but every authorization must aggregate the whole subtree. That costs extra queries and leaves room for a missed descendant, which means double counting. Rejected.
2. **Move-based balances (chosen).** Each grant holds only the units it currently controls, in three columns: `available`, `reserved` and `settled`. Delegation moves units from `parent.available` to `child.available`. A unit always sits in exactly one column of one grant, so the invariant is a plain SUM.
3. **Double-entry journal only (balances derived from entries).** This is the strongest audit story, but every check needs a SUM over the journal. Too slow and too much work for 4 days. We keep an append-only movement log for audit (below), but the balance columns stay authoritative.

## Decision

### Schema (raw SQL, psycopg 3, no ORM)
```
mandates(
  id UUID PK, owner_principal_id, currency CHAR(3),
  total BIGINT CHECK (total > 0),
  protected_reserve BIGINT CHECK (protected_reserve >= 0 AND protected_reserve <= total),
  status TEXT CHECK (status IN ('active','frozen')),
  expires_at TIMESTAMPTZ, created_at TIMESTAMPTZ DEFAULT now())

grants(
  id UUID PK, mandate_id UUID FK NOT NULL, parent_id UUID FK NULL,
  path UUID[] NOT NULL,            -- ancestors root..self, includes self
  depth SMALLINT CHECK (depth BETWEEN 0 AND 4),
  holder_principal_id UUID NOT NULL,
  available BIGINT NOT NULL CHECK (available >= 0),
  reserved  BIGINT NOT NULL CHECK (reserved  >= 0),
  settled   BIGINT NOT NULL CHECK (settled   >= 0),
  status TEXT CHECK (status IN ('active','revoked','expired')),
  expires_at TIMESTAMPTZ NOT NULL,
  scope JSONB NOT NULL,            -- immutable after insert
  idempotency_key TEXT, created_at, revoked_at)
UNIQUE (mandate_id) WHERE parent_id IS NULL        -- exactly one root
UNIQUE (parent_id, idempotency_key)                 -- idempotent delegation

ledger_movements(                                    -- append-only audit
  id BIGSERIAL, mandate_id, kind, amount BIGINT CHECK (amount > 0),
  from_grant_id, from_bucket, to_grant_id, to_bucket, transaction_id NULL,
  actor_principal_id, created_at)
```
There is no `remaining`, `allocated` or `limit` column. Nothing is derived and stored.

### Creation
Creating a mandate inserts the mandate plus one root grant with `available = total - protected_reserve`, `expires_at = mandate.expires_at`, and the mandate's full scope. `protected_reserve` is never assigned to any grant, so no agent can reach it. `total` and `protected_reserve` are immutable in the MVP (no top-ups).

### Invariants (checked in tests after every operation, and exposed at `GET /ledger/check`)
- **I1 (conservation):** `mandate.total = protected_reserve + SUM over the mandate's grants (available + reserved + settled)`.
- **I2 (reservation backing):** for each grant, `reserved = SUM(amount)` over its transactions in state `reserved` or `submitted` (see ADR-0005).
- **I3 (settlement backing):** for each grant, `settled = SUM(amount)` over its transactions in state `settled`.
- **I4 (no negatives):** enforced by CHECK constraints, so a logic bug fails the transaction instead of corrupting state.

I2 and I3 close a hole that I1 alone misses. Code could keep I1 true while moving a reservation onto the wrong grant. Tying the columns to transaction rows catches that.

### Movements (all happen inside one kernel transaction under the mandate lock; ADR-0005)
| Operation | Column effect | Notes |
|---|---|---|
| delegate(parent, amt) | parent.available -= amt; child.available += amt (new row) | Requires parent active, unexpired, `scope.can_delegate`, depth < 4 |
| authorize (approve) | g.available -= amt; g.reserved += amt | Rejection changes no column |
| settle (confirm) | g.reserved -= amt; g.settled += amt | Always on the grant that reserved, even if it is now revoked |
| release | g.reserved -= amt; target.available += amt | `target` = nearest **active, unexpired** grant on `g.path` (self if g is active). If none (root revoked or expired), target = root, which is frozen and stranded by design |
| revoke / expire-reclaim | subtree available zeroed; sum added to target.available | See ADR-0005; `settled` never moves |

Every movement writes one `ledger_movements` row in the same transaction.

### Authority-attenuation rules (no amplification through delegation)
Checked at delegation time. Scope is immutable after that, so checking it once is sound.
- `child.amount <= parent.available` (conditional UPDATE; CHECK as backstop).
- `child.expires_at <= parent.expires_at`.
- `child.scope ⊆ parent.scope`: categories are a subset, the recipient allowlist is a subset, `per_tx_limit <= parent.per_tx_limit`, and `can_delegate` can only be true when the parent's is true.
- Same currency and same mandate as the parent. The depth cap (4) bounds `path` length and ancestor checks.

### Permission tiers (supports the security self-assessment deliverable)
| Tier | Principal | Can do |
|---|---|---|
| T0 | Mandate owner (human) | Create mandate, revoke any grant, freeze mandate, view all |
| T1 | Holder of a grant with `can_delegate` | Authorize within own grant; delegate to children; revoke any descendant |
| T2 | Holder of a leaf grant | Authorize within own grant only |
| — | LLM / router / settlement adapter | **No tier.** Proposes (LLM) or executes an already-reserved transfer (adapter); never authorizes (ADR-0001) |

Principals authenticate with per-principal API keys. Only a SHA-256 hash of each key is stored in a `principals` table. Raw keys are never stored or logged.

### Explicitly out of scope (MVP)
These are stated so that nobody adds them half-way:
- Partial settlement, over-capture, refunds and chargebacks. Settle amount must equal the reserved amount exactly.
- Multi-currency mandates and FX.
- Top-ups or changes to `total` and `protected_reserve`.
- Velocity limits (per-day spend). Only `per_tx_limit` is enforced.
- Gas or network fees charged to the mandate. Fees are an operator cost (ADR-0007).

## Consequences
- **Positive:** Authorization reads and writes one grant row plus its ancestors' status. The invariant is a single GROUP BY. Double counting needs a broken CHECK or a broken conservation test, and both are tested.
- **Negative/tradeoffs:** A parent cannot see "how much my subtree has spent" without an aggregate query. That is fine because it is only needed for display. Units released from a revoked subtree go to the nearest active ancestor, which may surprise users who expect them to return to the grant that originally delegated them. That behaviour is intended and documented.
- **Security/privacy effects:** Attenuation rules stop children from widening scope, time or amount. CHECK constraints make negative balances impossible even if a lock is missed. The audit log records every movement.
- **Operational effects:** A root revoked or expired with nowhere to return funds leaves them stranded in root.available on a frozen mandate. They are still counted by I1, so conservation holds.

## Evidence and validation
Not yet implemented. Required tests:
- I1, I2 and I3 asserted after every step of every scenario (pytest fixture).
- A property-based random sequence of delegate, authorize, settle, release and revoke ops, checking invariants after each step.
- Threat-model tests 2 and 3 (child over parent, children summing past parent).
- Scope widening rejected (category, recipient, per_tx_limit, expires_at, can_delegate).

## Revisit when
Partial capture, refunds or multi-currency are required; top-ups are needed; or audit requirements call for a full double-entry journal as the source of truth.
