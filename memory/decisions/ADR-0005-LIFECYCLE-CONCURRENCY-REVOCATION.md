# ADR-0005: Transaction Lifecycle, Concurrency Control, Idempotency, Expiry and Revocation

- **Status:** ACCEPTED (2026-10-15, team lead)
- **Date:** 2026-10-15
- **Owner:** Opus planner (draft) / project lead (approval)
- **Related tasks:** BK-010, BK-020, BK-030, BK-075
- **Related ADRs:** ADR-0001, ADR-0004 (balances and invariants), ADR-0007 (settlement adapter)
- **Resolves:** OQ-004 (revocation vs reservations) and OQ-006 (database: Supabase Postgres, session pooler, READ COMMITTED)

## Context
Concurrent authorizations, delegations, settlements and revocations on one mandate must not overspend, double-settle or leave authority alive after revocation. Agents and the settlement adapter can crash and retry at any point. On-chain transfers cannot be recalled. The stack is Python 3.12, psycopg 3 raw SQL and Supabase Postgres via the **session pooler (5432)** at the default **READ COMMITTED** isolation level.

## Options considered
1. **SERIALIZABLE isolation with retry loops.** Correct, but needs retry handling on every path and gives confusing serialization failures under demo load. Rejected for the 4-day timeline.
2. **Per-grant row locks.** Higher concurrency, but delegation, revocation and release touch several grants (ancestors and subtree). The team would have to prove a lock order across a tree. Too risky.
3. **One pessimistic lock per mandate, plus conditional UPDATEs and CHECK constraints (chosen).** Every kernel operation on a mandate is fully serialized, which makes the reasoning simple and the tests clear. Throughput per mandate is limited (stated below).

## Decision

### 1. Kernel transaction shape
Every state-changing kernel operation is exactly one DB transaction:
```
BEGIN;
SET LOCAL lock_timeout = '3s'; SET LOCAL statement_timeout = '5s';
SELECT ... FROM mandates WHERE id = $m FOR UPDATE;   -- serialization point
<lazy sweep for this mandate>                        -- section 5
<operation: reads + conditional UPDATEs + INSERT ledger_movements + audit_events>
COMMIT;
```
- **Covered operations:** authorize, approve-proposed, delegate (child-grant creation), settle-start, settle-confirm, release, revoke and sweep. **Delegation must take the lock**, because it moves `parent.available` and races with authorize and revoke.
- **Operations addressed by transaction or grant ID:** first read the immutable `mandate_id` without a lock, then lock the mandate, then re-read the row `FOR UPDATE`.
- **Why READ COMMITTED is correct here:** under RC each statement after the lock sees all commits made before the lock was granted, so post-lock reads are current. Do **not** raise isolation to REPEATABLE READ. That would turn waits into serialization errors.
- **Conditional UPDATEs are the second layer of defence.** Example: `UPDATE grants SET available = available - $a, reserved = reserved + $a WHERE id = $g AND status = 'active' AND available >= $a`. The kernel asserts `rowcount == 1` and otherwise rolls back and rejects. CHECK constraints are the third layer.
- **Lock timeout:** a timed-out lock returns a retryable 503 and **never** an approval (fail closed).
- **Network calls:** never made while holding the mandate lock. No LLM calls and no chain RPC. Local signing (ADR-0007) is allowed.
- **Global lock order:** `mandates` row, then `settlement_accounts` row (ADR-0007). No operation locks two mandates. The cost ledger (ADR-0006) runs in separate transactions and is never nested inside a kernel transaction. There are no cycles, so no deadlocks.
- **Single writer path:** all writes go through one `kernel_tx(mandate_id)` context manager. A test greps the code to check that no other module issues `UPDATE grants` or `UPDATE transactions`.

### 2. Stated throughput limitation
Each operation holds the mandate lock for about 4 to 6 round trips. On Supabase from Europe that is roughly 50 to 300 ms, so one mandate handles about **3 to 20 kernel ops per second**. Different mandates run in parallel up to the pool size. The target of 100,000 decisions a month averages about 0.04 per second, so this is acceptable and will appear on the known-risk list. If it ever matters, move the op body into a single `plpgsql` function, which needs one round trip. That is not planned for the MVP.

### 3. Transaction states
```
                ┌──────────► rejected                      (terminal; no balance change)
 (request) ─────┤
                ├──────────► proposed ──approve──► reserved  (proposed = needs human review; holds NO funds)
                │                └──deny/expire──► rejected
                └──────────► reserved ──settle-start──► submitted ──confirm──► settled   (terminal)
                                  │                          └──fail-proven──► released  (terminal)
                                  └──release / TTL / revoke / grant-expiry──► released   (terminal)
```
| From | To | Trigger | Guard (checked under lock) | Balance effect (ADR-0004) |
|---|---|---|---|---|
| — | reserved | authorize | Whole path active and unexpired; scope, per_tx_limit, recipient and currency match; `available >= amt` | avail→reserved |
| — | rejected | authorize | Any guard fails | none |
| — | proposed | authorize with `needs_review` | Schema valid; no funds held | none |
| proposed | reserved / rejected | owner approve / deny | Full authorize guards re-run at approval time | avail→reserved / none |
| reserved | submitted | settle-start | Path still active and unexpired; `reserve_expires_at > now()` | none (stays reserved) |
| submitted | settled | confirm (receipt success) | — | reserved→settled |
| submitted | released | fail proven (ADR-0007 rules) | — | reserved→target.available |
| reserved | released | release / TTL / revoke / expiry | — | reserved→target.available |

**Idempotent repeats:**
- settle on `submitted` or `settled` returns the current state (200). This means a duplicate settle never signs a second transfer.
- release on `released` returns 200.
- release on `submitted` returns **409**, because funds in flight cannot be released.
- settle on `released` or `rejected` returns 409.
- release on `settled` returns 409.

All of these are decided by `UPDATE transactions SET state = $to WHERE id = $t AND state = $from` with a rowcount check.

### 4. Idempotency
- `transactions` has `UNIQUE (grant_id, idempotency_key)`, and `payload_hash = sha256(canonical JSON of {grant_id, amount, currency, recipient, category})`.
- **Lookup happens inside the mandate lock, before evaluation.** If the hash matches, return the **stored decision**, including a stored rejection. Decisions are replayed, never re-evaluated, so a retry cannot flip a rejection into an approval after funds are freed. A client that wants re-evaluation must send a new key.
- **Same key, different hash:** HTTP 409, `audit_events(kind='IDEMPOTENCY_CONFLICT')` written in its own short transaction, and no state change.
- **Backstop:** a UNIQUE violation causes a rollback and a re-read, which returns the existing result.
- **Delegation:** has its own key, `UNIQUE (parent_id, idempotency_key)`.

### 5. Expiry: lazy checks plus a lazy, lock-scoped sweep (no background infrastructure required)
- **Time source:** always the DB's `now()`, never the app clock.
- **Authorize and settle-start:** reject if any grant on `path` has `status <> 'active'` or `expires_at <= now()`, or the mandate is frozen or expired. One query: `SELECT ... FROM grants WHERE id = ANY($path)`.
- **Reservation TTL:** `transactions.reserve_expires_at = now() + 15 min`, configurable. A reservation that was never submitted cannot pin funds forever.
- **Sweep(mandate):** runs inside the lock at the start of every kernel op on that mandate. It also runs from `POST /admin/sweep`, a CLI loop that iterates mandates with due work, one lock each. Sweep does three things:
  1. Releases `reserved` transactions that are past `reserve_expires_at` or whose path has expired.
  2. Marks grants with `expires_at <= now()` as `expired` and reclaims their subtree using the same routine as revoke.
  3. Never touches `submitted` transactions. Only the ADR-0007 reconciler resolves those.

### 6. Revocation
`revoke(G)` is allowed for the mandate owner or the holder of any strict ancestor of G. Revoking an already-revoked grant is a no-op returning 200. Under the mandate lock:
1. Set `status = 'revoked'` and `revoked_at = now()` for every grant where `G = ANY(path)` and `status = 'active'`.
2. Release every subtree transaction in state `reserved`: move it to `released`, `reserved -= amt` on its grant.
3. `S = SUM(available) over the subtree + SUM(released amounts from step 2)`. Set the subtree's `available = 0`. Add S to `target.available`, where target is the nearest active, unexpired strict ancestor of G. If G is the root, the mandate is set to `frozen` and S stays on the root (stranded, still counted).
4. `settled` is never touched.
5. **In-flight rule (explicit):** subtree transactions already in `submitted` **are not and cannot be cancelled**. They stay reserved on their (now revoked) grant until the reconciler resolves them. Success moves them to `settled`. Proven failure moves them to `released`, with funds going to the nearest active ancestor at that time.
6. The revoke response and audit event report `in_flight_count` and `in_flight_amount`. The maximum post-revocation exposure is exactly this amount, and it is bounded because nothing new can enter `submitted` after the revocation commits. The settle-start guard re-checks the path under the same lock.

**Race outcomes, all serialized by the lock:**
- authorize then revoke: the reservation is released by the revoke.
- revoke then authorize: rejected, `GRANT_REVOKED`.
- settle-start then revoke: the transfer is in flight and reported as exposure.
- revoke then settle-start: rejected, and the reservation is already released.

### 7. Double-counting checks addressed here
- **Revocation moves each unit once:** the subtree's `available` is zeroed in the same statement that computes S, and released reservations are counted once because the state change and the `reserved` decrement happen together.
- **Released funds of revoked grants go up the tree,** never back to the revoked grant, so nothing is stranded where it could be spent.
- **Rejected and proposed transactions hold no funds.**
- **Partial settlement is out of scope** (ADR-0004).

## Consequences
- **Positive:** One clear serialization point; races reduce to orderings that can be enumerated and tested. Crash at any point leaves either nothing changed (rollback) or a consistent committed state. No Redis, queue or cron infrastructure is needed.
- **Negative/tradeoffs:**
  - Per-mandate throughput is limited (section 2).
  - Revocation cannot stop in-flight on-chain transfers. That limit is disclosed, and its size is reported.
  - A lazy sweep means an untouched mandate may keep expired reservations until the next op or the CLI sweep runs. Those reservations are still unspendable because authorize and settle-start check expiry.
- **Security/privacy effects:** Fail closed on lock timeout. Idempotent replay prevents retry-based flips. Conflicts are audited.
- **Operational effects:** Use the Supabase session pooler with a small `psycopg_pool` (for example `max_size=5`) to respect pooler connection limits. Do not use the transaction pooler (6543) for kernel connections, because prepared statements and session settings behave differently there.

## Evidence and validation
Not yet implemented. Required tests, run against real Postgres and not mocks:
- **Overspend race:** N=20 concurrent authorizes on one grant whose `available` covers only k of them. Exactly k succeed, and I1, I2 and I3 hold.
- **Delegation race:** concurrent delegate plus authorize on the same parent. No overspend.
- **Revoke races:** revoke vs authorize, and revoke vs settle-start, in both orderings (forced with an `asyncio`/thread barrier). Results match section 6.
- **Idempotency:** same key and payload ×10 concurrently gives one transaction. Same key with a different payload gives 409 plus an audit row.
- **Repeated transitions:** settle/settle, release/release, release-after-settle and release-on-submitted give the codes in section 3.
- **Expiry:** an expired child blocks authorization. TTL releases a stale reservation. Expired-grant funds are reclaimed to the parent.
- **Lock timeout:** gives 503, never an approval.

## Revisit when
A single mandate needs more than about 10 ops per second, multi-mandate operations appear, or settlement moves to a contract that enforces limits on-chain.
