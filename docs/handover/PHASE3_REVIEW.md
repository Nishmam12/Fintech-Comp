# Phase 3 review (Opus, 2026-10-17): lead steps 3, 5, 6 and the eight teammate branches

**Reviewer:** Opus (lead's session). **Scope:** migration 006, `kernel/integrity.py`, `kernel/breaker.py` and its edits to `ops.py`, `funds.py` and `sweep.py` (lead, step 7); Afnan's stack `BK-401 → 402 → 403 → 304`; Daniel's stack `BK-305 → 411 → 412 → 413` (step 9).

**Checks run:**
- A secret scan of both stacks' diffs (private keys, `bk_` API keys, provider keys, DB URLs). **Nothing found.**
- Screenshot `15-rotate-key.png` checked by eye: the new key is blurred.
- A trial merge of both stack tips onto `main`. Afnan's merges cleanly. Daniel's then conflicts in `README.md`, `memory/CHANGELOG.md` and `api/app.py` (the CORS line), and each conflict is a "keep both" case.

## Verdict
| Branch | Verdict |
|---|---|
| afnan/BK-401-anchor | **Approve** |
| afnan/BK-402-unbind-settler | **Approve** (kernel exception reviewed) |
| afnan/BK-403-worker | **Approve** with fix A1 |
| afnan/BK-304-agent-budget | **Approve** (costledger exception reviewed) |
| daniel/BK-305-replay | **Approve** |
| daniel/BK-411-ratelimit | **Approve** |
| daniel/BK-412-keys | **Approve** with fix D3 |
| daniel/BK-413-dashboard | **Approve** with UI follow-up after K1 |
| Lead steps 3, 5, 6 | **Approve** with fix K1 (must land before the freeze) |

## Findings

### K1 (Medium, lead kernel; must fix): an agent can reinstate its own suspended grant
**The path:**
1. Agent A holds grant P with `can_delegate`.
2. A delegates a child C **to itself**. `_delegation_problem` has no `holder != actor` check.
3. A probes on C. C is suspended, as designed.
4. A calls `reinstate(C)`. `_require_manager` accepts the holder of a strict ancestor, and A holds P, so the call succeeds.
5. The loop repeats indefinitely, so the breaker never contains A.

The same rule lets two colluding agents reinstate each other along a delegation chain.

**Fix (ADR-0009 amendment K1):**
- `reinstate` is **mandate-owner only**. `suspend` keeps the owner-or-ancestor rule, because it can only make things stricter.
- `delegate` refuses `holder_principal_id == actor` with `SELF_DELEGATION`. A self-child adds no authority, and it was the only way to multiply probe targets.

**Tests first:**
- An agent can self-delegate → refused `SELF_DELEGATION`.
- An ancestor holder can suspend a descendant but gets 403 `NOT_OWNER` on reinstate.
- The owner can still reinstate.
- Update `test_an_ancestor_holder_may_reinstate_a_descendant` (now the opposite).
- The state machine's `delegate` rule must accept `DelegationRejected`, which it already does.

### K2 (Low, accept and document): delegation refusals are not strikes
A holder can probe through `POST /grants` (`SCOPE_WIDER_THAN_PARENT`, `INSUFFICIENT_FUNDS`, …) without strikes. These attempts only describe the holder's own grant, which the holder already knows, and they are rate-limited. Add this to R22 as a stated limit.

### K3 (Low, accept): approving a held request on a suspended grant rejects it permanently
Fail-closed. After reinstating, the agent resubmits. It is already covered by `test_the_owner_cannot_approve_a_held_request_on_a_suspended_grant`.

### K4 (Info): lock order verified
- Kernel writes: mandate row → chain head.
- `_audit_outside`, `KEY_ROTATED`, `PRINCIPAL_DISABLED`: chain head only.
- Cost ledger: bucket rows (sorted) → global chain head (`COST_OVERRUN`).
- Anchors: `settlement_accounts` row only. Payments: mandate → `settlement_accounts`.

No path takes these in the opposite order, so no deadlock cycle exists.

### A1 (Low, Afnan, BK-403): one failing tick skips the rest of the pass
`step("ticks", lambda: len([kernel.tick(pool, m) for m in kernel.due_mandates(pool)]))` stops at the first mandate whose tick raises (for example `KernelBusy`). Every mandate after it waits a full interval. Fix: wrap each `tick` separately and count the failures.

### A2 (Info, Afnan, BK-304)
- `_buckets_of` recovers the agent bucket from the `purpose` text. It is internal-only (no caller passes user text as `purpose`), so it is acceptable.
- The stale sweep and overrun charging both use it, so the agent buckets cannot leak reservations.
- Lock order is sorted, so `principal:` sorts after `primary`.

### A3 (Info, Afnan, BK-401)
**Correct:**
- The nonce comes from the shared `settlement_accounts` row lock.
- `nonce_disjoint` (an advisory lock plus a cross-table check) also guards writers that bypass the allocator.
- The digest matches ADR A5.
- The signer is offline, and `drive()` is shared rather than copied.

**Still owed:** the real anchor transaction. It needs migration 007 on production `bk` first (the lead runs `uv run python -m budget_kernel.db.migrate` after the merge).

### D1 (Low, Daniel, BK-305): a retry on a suspended grant gets 409, not the stored decision
`_grant_context` refuses a suspended path before the replay lookup. This fails closed and is acceptable. Document it.

### D2 (Low, Daniel, BK-411): one extra DB round trip per request
Resolving the key costs about 60 ms on the hosted DB. Accept it for the demo, and mention it in the README next to "per process".

### D3 (Low, Daniel, BK-412): two concurrent rotations with the same old key both "succeed"
Both requests authenticate before either `UPDATE`, so the last write wins. One caller then holds a key that never worked.

**Fix:** `UPDATE principals SET api_key_hash = %s, key_rotated_at = clock_timestamp() WHERE id = %s AND api_key_hash = %s`, using the hash of the presented key. If 0 rows change, return 409 `KEY_ALREADY_ROTATED`. Add a test.

### BK-413 follow-up (after K1)
Show **Reinstate** to the mandate owner only. **Suspend** stays visible to the owner and ancestor holders.

## Merge plan (Sonnet, step 9)
1. On a branch from `main`, merge `origin/afnan/BK-304-agent-budget` (clean), then `origin/daniel/BK-413-dashboard`.
2. Resolve the conflicts:
   - **`api/app.py` CORS:** `allow_methods=["GET", "POST", "DELETE"]` **and** `expose_headers=["Retry-After"]`.
   - **`README.md` and `memory/CHANGELOG.md`:** keep both sides.
3. Make the fixes, each test first: K1, D3, A1. Add K2, D1 and D2 to the self-assessment.
4. Run the full non-slow suite and the slow state machine on the lead schema, then push.
5. **The lead runs the production migration (007).**
6. Afnan runs the real anchor (`POST /admin/anchor` in testnet mode). The lead verifies the calldata over the public RPC.
7. Daniel hides Reinstate for non-owners.
