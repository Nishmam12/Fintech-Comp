# ADR-0009: Tamper-Evident History, Agent Circuit Breaker, API Hardening

- **Status:** ACCEPTED (2026-10-16, team lead)
- **Date:** 2026-10-16
- **Owner:** Opus planner (design) / project lead (approval) / Sonnet orchestrator (implementation)
- **Related tasks:**
  - Lead: steps 3, 5, 6, 8 of the Phase 3 plan
  - Afnan: BK-401 anchoring, BK-402 settler unbind, BK-304 per-agent budget, BK-403 worker
  - Daniel: BK-411 rate limiting, BK-412 key lifecycle, BK-413 dashboard
- **Related ADRs:**
  - ADR-0004: tiers and move-based accounting
  - ADR-0005: lock, sweep and lifecycle
  - ADR-0006: cost ledger
  - ADR-0007: settlement adapter and nonce allocator
  - ADR-0008: scope fields and review cap
- **Risks addressed:**
  - **R7 (history edit):** an operator with database access can rewrite history without detection.
  - **R8 (probing agent):** an agent can probe its limits with no consequence.
  - **R9 (unlimited calls):** the API has no rate limits.
  - **R20 (keys never expire):** API keys never expire and cannot be rotated or disabled.

## Purpose of this ADR
This ADR **freezes the contract** for Phase 3. It fixes three things:
- table and column names
- error and reason codes
- endpoint paths and response fields

Teammates build against this file and migration 006. A change to anything in a "frozen" table needs a new amendment section in this ADR, approved by the lead, **before** the code changes.

---

## Part A: Hash-chained history (lead) + on-chain anchor (Afnan, BK-401)

### A1. What is chained
- **Chained tables:** `audit_events` and `ledger_movements`. Both are already append-only: the triggers forbid UPDATE and DELETE.
- **One chain per mandate.** The chain key is `mandate:<uuid>`, and both tables share one sequence for that key.
- **Global chain.** Audit rows with `mandate_id IS NULL` go to the chain `global`.
- **Mutable state tables are not chained:** `grants`, `transactions`, `mandates`. Their money state is checked against the chained movements by the existing invariant checker (I1 to I5). So a silent edit to a balance shows up as an invariant violation, and a silent edit to a movement shows up as a broken chain.
- **Not covered:**
  - `TRUNCATE` of the whole table. The test harness needs it, so the database does not forbid it. The anchor detects it, because the anchored head no longer exists.
  - A full chain rewrite done after the last anchor. Section A6 states this limit.

### A2. Columns (frozen)
**Added to both `audit_events` and `ledger_movements`:**

| Column | Type | Meaning |
|---|---|---|
| `chain_key` | `text NOT NULL` | `mandate:<uuid>` or `global` |
| `seq` | `bigint NOT NULL` | 1, 2, 3 … with no gaps within a chain, shared across both tables. `UNIQUE (chain_key, seq)` holds per table, and the trigger keeps it unique across the two tables |
| `prev_hash` | `text NOT NULL` | 64 lowercase hex characters; for `seq = 1` it is 64 zeros |
| `row_hash` | `text NOT NULL` | 64 lowercase hex characters (section A3) |

**New table `chain_heads`:**

| Column | Type | Meaning |
|---|---|---|
| `chain_key` | `text PRIMARY KEY` | the chain this row describes |
| `seq` | `bigint NOT NULL` | last sequence number used |
| `head_hash` | `text NOT NULL` | hash of the last row |
| `updated_at` | `timestamptz NOT NULL` | last update time |

**Who sets the values.** A `BEFORE INSERT` trigger (`chain_append`) on both chained tables fills in these columns. Application code never supplies them, and any value it does supply is overwritten.
- The trigger serializes per chain with `INSERT … ON CONFLICT (chain_key) DO UPDATE … RETURNING` on `chain_heads`. That row lock is held until commit.
- Writers inside `kernel_tx` already hold the mandate lock. `_audit_outside` writers only take the head-row lock. Lock order is always mandate first, then head, so no deadlock cycle exists.
- If the outer transaction rolls back, the head update rolls back too, so no gaps appear.

**Backfill.** Migration 006 chains the existing rows, ordered by `(created_at, table, id)` with `audit_events` first on a tie. It then sets `NOT NULL`.

### A3. Hash definition (frozen; the Python verifier must reproduce it exactly)
**Field encoding** is `F(x)`:
- NULL becomes the empty string `""`.
- uuid becomes its lowercase canonical text.
- bigint becomes its decimal text.
- timestamptz becomes integer microseconds since the Unix epoch in UTC, as decimal text.
- jsonb becomes `detail::text`. This is PostgreSQL's own normalized output, and the verifier reads that exact text from the database. It never re-serializes the JSON.
- Each encoded field is then length-prefixed: `char_length(v) || ':' || v`.

**Canonical row string** (fields joined with `|`):
- `audit_events`: `A|` + F(id) | F(chain_key) | F(seq) | F(mandate_id) | F(kind) | F(actor_principal_id) | F(subject_id) | F(created_at) | F(detail)
- `ledger_movements`: `M|` + F(id) | F(chain_key) | F(seq) | F(mandate_id) | F(kind) | F(amount) | F(from_grant_id) | F(from_bucket) | F(to_grant_id) | F(to_bucket) | F(transaction_id) | F(actor_principal_id) | F(created_at)

**Row hash:** `row_hash = lower(hex(sha256(utf8('BK1|' || prev_hash || '|' || canonical))))`

The SQL function `bk_canon(tbl text, r record)` builds the canonical string and the trigger uses it. The Python verifier builds the canonical string **independently** from raw column values. A test checks that the two agree on random rows, including JSON with `|` and non-ASCII text.

### A4. Verification: `kernel.integrity.verify(pool, mandate_id) -> dict` (lead)
**How it runs.** It is read-only and takes no mandate lock. It runs one `REPEATABLE READ READ ONLY` transaction, so the head and the rows come from the same snapshot.

**Checks, in order.** The first failure wins:
- `SEQ_GAP`: the sequence numbers are not exactly 1..n.
- `PREV_MISMATCH`: a row's `prev_hash` is not the previous row's `row_hash`.
- `HASH_MISMATCH`: the recomputed hash is not the stored `row_hash`.
- `HEAD_MISMATCH`: `chain_heads` does not equal (n, last `row_hash`).
- `ANCHOR_MISMATCH`: for the newest **confirmed** anchor that covers this chain, the row at the anchored `seq` must have the anchored `head_hash`. This is the prefix check.

**API: `GET /mandates/{id}/integrity`.**
- Callers: the mandate owner (T0), or the admin token.
- Any other caller gets 403 `NOT_OWNER`. An unknown mandate gets 404.

**Response (frozen):**
```json
{
  "mandate_id": "…",
  "chain_key": "mandate:…",
  "ok": true,
  "length": 42,
  "head_seq": 42,
  "head_hash": "64 hex",
  "broken_at": null,
  "reason": null,
  "verified_at": "ISO-8601",
  "last_anchor": null
}
```
- When the check fails: `ok = false`, `broken_at` is the first bad `seq` (an integer, or `null` for `HEAD_MISMATCH`), and `reason` is one of the codes listed above.
- `last_anchor` is `null` until BK-401 merges. After that it is:
  `{"anchor_id","seq","head_hash","tx_hash","status","explorer_url","matches": bool}`

### A5. On-chain anchor (Afnan, BK-401; migration `007_anchors.sql`)
**Tables (frozen names):**

`anchors`:

| Column | Type / meaning |
|---|---|
| `id` | `bigserial PK` |
| `chain_id` | `int` |
| `from_address` | operator wallet address |
| `nonce` | transaction nonce |
| `digest` | 64 hex characters |
| `raw_tx` | `bytea` |
| `tx_hash` | `text UNIQUE` |
| `status` | `signed`, `broadcast`, `confirmed`, `failed` or `stuck` (same meanings as `chain_settlements`) |
| `broadcast_attempts`, `last_error`, `block_number` | as in `chain_settlements` |
| `created_at`, `updated_at` | timestamps |

`anchor_heads`:

| Column | Type |
|---|---|
| `anchor_id` | `bigint REFERENCES anchors` |
| `chain_key` | `text` |
| `seq` | `bigint` |
| `head_hash` | `text` |

The primary key is `(anchor_id, chain_key)`. Both tables have RLS on and no policies.

**Digest:**
- Snapshot every `chain_heads` row with `seq > 0`.
- Sort the rows by `chain_key` (bytewise).
- Build the line `chain_key|seq|head_hash\n` for each row.
- `digest = sha256(concatenation)`.

**Transaction:**
- A 0-value Base Sepolia transfer from the operator address **to itself**.
- `data = b"BKANCHOR1" + bytes.fromhex(digest)`, which is exactly 41 bytes.
- The gas limit is fixed and validated like payments. The gas ceiling from BK-312 applies.

**Nonce and crash safety:**
- The nonce **must** come from the same `settlement_accounts` allocator that payments use, inside the same database transaction that persists the signed raw transaction. Persist first, broadcast after commit, as in ADR-0007.
- An anchor and a payment can never share a nonce. The `UNIQUE(chain_id, from_address, nonce)` property must hold across `chain_settlements ∪ anchors`. A trigger or the allocator's row lock enforces it, and a test proves it.

**Endpoints:**
- `POST /admin/anchor` (admin token). It creates, signs and persists an anchor for the current heads, broadcasts it, and returns `{anchor_id, digest, tx_hash, status, explorer_url, chains: n}`.
- `POST /settlement/reconcile` also advances anchors.
- In simulated mode the endpoint returns 409 `ANCHOR_NEEDS_TESTNET`.

**What anchoring does not mean.** An anchor is evidence only. It never authorizes anything, and the kernel never reads chain state to make a decision.

### A6. Honest limits (to be written into the self-assessment)
- Someone with database superuser rights can disable the trigger and rewrite a whole chain consistently. Only rows covered by a confirmed anchor are protected against that. Anything after the last anchor is only tamper-*evident* against partial edits.
- The verifier runs inside the same system it checks. An external auditor can re-run it from the exported rows, because the hash definition (section A3) is public and deterministic.

---

## Part B: Agent circuit breaker (lead)

### B1. Status and columns (frozen)
**`grants.status`** gains `suspended`. The full set is now: `active`, `suspended`, `revoked`, `expired`.

**New `grants` columns:**

| Column | Type | Meaning |
|---|---|---|
| `suspended_at` | `timestamptz` | when the grant was suspended |
| `suspend_reason` | `text` | `CHECK IN ('STRIKES', 'MANUAL')` |
| `reinstated_at` | `timestamptz` | when it was last reinstated |

`suspended_at` and `suspend_reason` are both null or both set. Their state is tied to the status: `status = 'suspended'` exactly when `suspended_at IS NOT NULL`. A `CHECK` constraint enforces this.

**New table `grant_strikes`:**

| Column | Type |
|---|---|
| `id` | `bigserial PK` |
| `mandate_id` | uuid |
| `grant_id` | uuid |
| `actor_principal_id` | uuid |
| `kind` | `text CHECK IN ('REFUSAL','INJECTION')` |
| `reason` | `text` |
| `weight` | `smallint` |
| `created_at` | timestamptz |

It is append-only (`forbid_mutation`) and has RLS on.

**Transitions:**
- `active → suspended`: by the breaker or a manual suspend.
- `suspended → active`: by reinstate.
- `suspended → revoked`: by revoke.
- `suspended → expired`: by the sweep.

Sweep, `reclaim_subtree`, `revoke` and the funds liveness check must treat `suspended` like `active` wherever they currently filter on `status = 'active'` for expiry and revocation. A suspended grant still expires, can still be revoked, and its subtree is still reclaimed.

### B2. Effect of suspension
- **Path check.** `_path_problem` returns `GRANT_SUSPENDED` if any grant on the path is suspended. It is checked after `GRANT_REVOKED` and before `GRANT_EXPIRED`. The effect:
  - `authorize` → `rejected` with reason `GRANT_SUSPENDED`
  - `delegate` → refused
  - `settle_start` → refused (409 `GRANT_SUSPENDED`)
  - owner `review` approval → refused
  - A suspended ancestor therefore freezes its whole subtree.
- **Money already in flight.**
  - `submitted` transactions keep going: `settle_confirm` and `settle_fail` do not check the path.
  - `reserved` transactions are not released early. They cannot be started, and the normal TTL sweep releases them.
  - `release` is still allowed.
- **No strikes.** Requests refused with `GRANT_SUSPENDED` do not add strikes.

### B3. What counts as a strike
A strike is recorded under the mandate lock, in the same transaction as the decision. It is recorded **only when the actor is the grant's holder and is not the mandate owner.** Strikes from anyone else would let an outsider suspend a victim's grant. (Today a non-holder fails `NOT_GRANT_HOLDER` before any check, so this holds by construction. The rule makes it explicit.)

| Event | Kind | Weight |
|---|---|---|
| `authorize` rejected with `CATEGORY_NOT_ALLOWED`, `RECIPIENT_NOT_ALLOWED`, `PER_TX_LIMIT_EXCEEDED`, `VELOCITY_LIMIT_EXCEEDED`, `INSUFFICIENT_FUNDS`, `CURRENCY_MISMATCH`, or `TOO_MANY_PENDING_REVIEWS` | `REFUSAL` | 1 |
| `/agent/request` text where `injection_suspected(text)` is true (the API calls `kernel.record_signal`) | `INJECTION` | 3 |

**Not counted:**
- idempotent replays, because they return before any check
- path refusals (`GRANT_REVOKED`, `GRANT_EXPIRED`, `MANDATE_FROZEN`, …), because they are not probing
- held-for-review outcomes
- failures in the interpretation layer

### B4. Trip rule (frozen constants; env override for tests only)
- `STRIKE_LIMIT = 5` (env `BK_STRIKE_LIMIT`)
- `STRIKE_WINDOW_SECONDS = 600` (env `BK_STRIKE_WINDOW_SECONDS`)

After inserting a strike, the kernel sums `weight` over the grant's strikes where:
- `created_at > ctx.now − window`, and
- `created_at > coalesce(reinstated_at, '-infinity')`

If the sum is **≥ STRIKE_LIMIT**, the grant becomes `suspended` with reason `STRIKES` in the same transaction. The kernel also writes the audit event `GRANT_SUSPENDED` with detail `{reason, strikes, window_seconds}`.
- The rejected decision that tripped the breaker is still returned as a normal rejection, and the response gains `"suspended": true`.
- Reinstating resets the count, because only strikes after `reinstated_at` count.

### B5. Kernel API (signatures frozen; stubs in step 3, bodies in step 6)
- `kernel.record_signal(pool, *, grant_id, actor, kind: str, reason: str) -> dict`
  - Returns `{"grant_id", "strikes", "suspended": bool}`.
  - `kind` must be `INJECTION`. Anything else is 422 `BAD_SIGNAL`.
  - The actor must be the holder; anyone else gets 403 `NOT_GRANT_HOLDER`.
  - Signals on an already suspended or dead grant are recorded but do not change the status.
- `kernel.suspend(pool, *, grant_id, actor) -> dict`
  - A manual suspend, reason `MANUAL`.
  - Same permission rule as `revoke`: the owner, or a holder of a strict ancestor.
  - Idempotent: an already suspended grant returns `{"already": true}`.
- `kernel.reinstate(pool, *, grant_id, actor) -> dict`
  - `suspended → active`. Sets `reinstated_at = ctx.now` and clears `suspended_at` and `suspend_reason`.
  - Same permission rule as `revoke`.
  - Audit event `GRANT_REINSTATED`.
  - A grant that is not suspended gets 409 `NOT_SUSPENDED`.
  - A grant whose expiry has passed is swept to `expired` first, and the call then gets 409 `NOT_SUSPENDED`.
- `kernel.tick(pool, mandate_id) -> dict`
  - Runs `kernel_tx` with no operation, so only the sweep runs.
  - Returns `{"mandate_id", "expired_grants", "released", "review_expired"}`.
  - For the worker (BK-403).
- `kernel.due_mandates(pool, *, limit: int = 50) -> list[uuid]`
  - Mandates with an active or suspended grant past its expiry, a reserved transaction past its TTL, or a proposal past its TTL.
  - Read-only, with no lock.

**HTTP:**
- `POST /grants/{id}/suspend` → `{grant_id, status, already}`
- `POST /grants/{id}/reinstate` → `{grant_id, status}`

Both are owner or ancestor-holder only. The `/mandates/{id}/state` grant objects gain `suspended_at`, `suspend_reason` and `strikes_in_window`.

### B6. Required tests (Opus gate)
- **Probing trips the breaker:** 5 refusals on one grant suspend it. The 6th request is `GRANT_SUSPENDED`, and no strike is added for it.
- **Injection weight:** 2 injection signals (weight 6) suspend the grant.
- **Outsider:** a non-holder's refused calls add no strike.
- **Owner exemption:** the owner probing their own root grant is never suspended.
- **Descendants:** a suspended parent blocks its children's authorize and delegate.
- **Reinstate:** reinstating resets the count, and 4 more strikes do not trip it.
- **Money in flight:** a submitted transaction on a suspended grant still confirms. A reserved one cannot `settle_start`.
- **Revoke and expiry:**
  - Revoke works on a suspended grant and reclaims its subtree.
  - Expiry sweeps a suspended grant.
- **Invariants:** I1 to I5 hold after every step.
- **Race:** two concurrent refusals at strike 4 give exactly one `GRANT_SUSPENDED` audit event.
- **Simulation:** a new `limit_probing` scenario runs against both the naive baseline and the kernel.
- **State machine:** the slow state-machine test gains suspend and reinstate rules.

---

## Part C: API hardening (Daniel)

### C1. Rate limiting (BK-411, `api/ratelimit.py`)
**Design:**
- An in-process token bucket per key: the principal id when authenticated, the client IP otherwise.
- **Limits:**
  - 120 requests per minute by default.
  - 30 per minute on `POST /agent/request` and `POST /interpret`, as a separate bucket.
  - `/health` is exempt.
- Configurable via `BK_RATE_DEFAULT_PER_MIN` and `BK_RATE_MODEL_PER_MIN`.

**Response when limited (frozen):**
- HTTP 429.
- Body `{"detail": {"code": "RATE_LIMITED", "message": "…"}}`.
- Header `Retry-After: <whole seconds>`.

**Limits of this design:**
- It is per process. That is stated in the self-assessment. With several replicas the effective limit is multiplied, and the shared-store variant is future work.
- A refusal is not a kernel strike, because rate limiting happens before authentication-dependent logic.

### C2. Key lifecycle (BK-412, `api/auth.py`; columns from migration 006)
**New `principals` columns:**

| Column | Type |
|---|---|
| `key_expires_at` | `timestamptz` (null = no expiry) |
| `disabled_at` | `timestamptz` |
| `key_rotated_at` | `timestamptz` |

**Authentication results (frozen codes, all HTTP 401):**

| Condition | Code |
|---|---|
| Unknown key | `UNAUTHENTICATED` |
| `key_expires_at <= now()` | `KEY_EXPIRED` |
| `disabled_at IS NOT NULL` | `PRINCIPAL_DISABLED` |

**Endpoints:**
- `POST /me/rotate-key` (authenticated)
  - Generates a new key and stores only its hash. The old hash is replaced in the same `UPDATE`, so the old key stops working immediately.
  - Returns the raw key once: `{"api_key", "key_expires_at"}`.
  - Writes the audit event `KEY_ROTATED` (global chain, no key material).
- `POST /admin/principals/{id}/disable` (admin token)
  - Sets `disabled_at`. Idempotent.
  - Audit event `PRINCIPAL_DISABLED`.
  - Does **not** revoke the principal's grants. The owner revokes them separately, which keeps money operations in the kernel.
- `POST /admin/principals` gains an optional `expires_in_days` (an integer from 1 to 365).

### C3. Required tests
- **Burst:** the request after the limit gets 429 with `Retry-After`. Requests recover after refill.
- **Independent buckets:** two keys do not share a bucket.
- **Expired key:** gets 401 `KEY_EXPIRED`.
- **Disabled principal:** gets 401 `PRINCIPAL_DISABLED`.
- **Rotation:**
  - The old key gets 401.
  - The new key works.
  - Rotating twice quickly leaves exactly one valid key.

---

## Part D: Coverage and budgets

### D1. Per-agent inference budget (Afnan, BK-304; costledger exception, needs lead and Opus review)
**Bucket and cap:**
- Bucket name `principal:<uuid>`, monthly, default cap 500,000 micro-USD.
- Migration 006 relaxes the `budget_buckets.bucket` CHECK to accept `^principal:[0-9a-f-]{36}$`.
- The bucket row is created lazily at its default cap.

**Reservation:**
- `interpret(…, principal_id=None)` gains the parameter.
- When it is set, the call reserves against `global`, the tier bucket **and** `principal:<id>` in the same conditional reservation. Either all of them succeed or none does.

**Fail-closed:** when the budget is exhausted, the request ends `unresolved` with code `AGENT_BUDGET_EXHAUSTED`, and the model is never called.

### D2. Grounding coverage (lead, step 8)
**Number words in the amount check:**
- Cardinals up to 999,999, plus "and", hyphens, and "dollars/cents".
- Grounding only. A number word never creates an amount the model did not also produce.

**Operator alias file `backend/config/recipient_aliases.json`:**
- Format: `{ "<canonical recipient>": ["alias", …] }`.
- An alias counts as the recipient appearing in the text (whole word, case-insensitive).
- The file is operator-controlled and loaded at start-up. A model can never add to it.

---

## Migration 006 contents (lead, step 3)
`006_robustness_ii.sql`:
- the chain columns, `chain_heads`, `bk_canon`, and the `chain_append` triggers, plus the backfill and `NOT NULL`
- the grants status CHECK with `suspended`, the suspension columns and their CHECK, and the `grant_strikes` table with its trigger and RLS
- the `principals` key-lifecycle columns
- the relaxed `budget_buckets.bucket` CHECK

The migration must be idempotent with respect to the runner, as with the earlier migrations, and safe on the production `bk` schema, which already has rows to backfill.

## Ownership and order
| Item | Owner | Can start |
|---|---|---|
| Migration 006, kernel stubs | Lead | now (step 3) |
| A4 verify + endpoint, Part B bodies, D2 | Lead | after 006 |
| BK-401 anchor (migration 007) | Afnan | after 006 is pushed (needs `chain_heads`) |
| BK-402 unbind, BK-403 worker | Afnan | BK-402 now; BK-403 after the stubs (`tick`, `due_mandates`) |
| BK-304 budget | Afnan | after 006 (relaxed CHECK) |
| BK-305, BK-411 | Daniel | now (no schema dependency) |
| BK-412 | Daniel | after 006 (columns) |
| BK-413 | Daniel | after the endpoints exist; can mock against the frozen response shapes earlier |

## Rejected alternatives
- **Hashing in Python at write time.** Rejected: `_audit_outside` and the kernel would race on the chain head, and any write path that skipped the helper would break the chain. A database trigger covers every writer.
- **One global chain.** Rejected: every mandate's writes would serialize on a single head row. A per-mandate chain matches the existing lock domain.
- **Merkle tree anchoring per row.** Rejected for time: a single digest over the heads gives the same prefix guarantee for the demo.
- **Suspending on any refusal including path refusals.** Rejected: an owner revoking a parent would cascade into strikes against innocent children.
- **Counting strikes on non-holder refusals.** Rejected: an outsider could suspend anyone's grant (denial of service).
- **Rate limiting in the kernel.** Rejected: it is transport policy, not money authority. Kernel strikes are the money-side control.
