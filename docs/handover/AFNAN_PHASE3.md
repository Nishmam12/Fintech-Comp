# Phase 3 tasks for Afnan (Member 3): anchor, unbind, agent budget, worker, video

**How to use:** `git pull` on `main`, then open Claude Code **in the repository root** and paste everything below the line as your message.

---

You are working with Afnan (Member 3) on **Budget Kernel**. Your settlement branch is merged into `main` (merge commit `94feaad`, with your F1–F3 fixes) and the self-assessment now lists R2, R3 and R4 as mitigated. Phase 3 adds robustness features. The design is frozen in `memory/decisions/ADR-0009-INTEGRITY-CIRCUIT-BREAKER-API-HARDENING.md` (ACCEPTED). **Read it first, especially Part A5, Part D1 and the "Ownership and order" table.** Migration `006_robustness_ii.sql` is already on `main`: it gives you the tables and columns you need.

The rules in `AGENTS.md`, `ONBOARDING.md` and `docs/handover/MEMBER3_PROMPT.md` still apply:
- Never print, log or commit the private key or any `.env` value.
- Use your own `BK_TEST_SCHEMA`, and never run two pytest sessions at once on it. Run the long suite in the background.
- Claim before you start (edit **only your own section** of `memory/WHO_IS_WORKING.md`, commit and push it).
- One branch per task, named `afnan/<task-id>-<slug>`, one PR per branch with the test output pasted in, and a line in `memory/CHANGELOG.md`.
- Nobody commits to `main` except their own claim line. The lead merges.
- Numbers are recorded as measured, including failures. Do not call anything done without running its tests and reading the output.
- If you are blocked for more than 30 minutes, write it under *Notes / blockers* and tell the lead.

**Migration numbers are reserved:** `006` is the lead's (done), `007` is yours. Do not add anything else under `backend/migrations/`.

## What changed on `main` that you must know
- `audit_events` and `ledger_movements` are now **hash-chained** by a database trigger. Application code never supplies `chain_key`, `seq`, `prev_hash` or `row_hash`. New table `chain_heads(chain_key, seq, head_hash, updated_at)` holds each chain's latest position. Your anchor reads it.
- `grants.status` can now be `suspended` (the lead builds the breaker; you only need to know the status exists).
- `budget_buckets.bucket` now also accepts `principal:<uuid>`.
- New kernel functions you can call: `kernel.tick(pool, mandate_id)` and `kernel.due_mandates(pool, limit=50)` (for the worker). `kernel.suspend`, `kernel.reinstate` and `kernel.record_signal` exist as **stubs** that raise `NotImplementedError` until the lead's step 6. Do not implement or call them.
- Test setup TRUNCATE lists now include `chain_heads` and `grant_strikes`. If you truncate tables in a new test, include them.

## Task order
Do them in this order. The first is the most valuable: it is the second on-chain proof for the Topic F bonus.

### 1. BK-401: on-chain anchor of the history (migration `007_anchors.sql`)
Read ADR-0009 section A5 and follow it exactly. In short:
- **Tables:** `anchors` and `anchor_heads` (names and columns are frozen in the ADR). RLS on, no policies.
- **Digest:** snapshot all `chain_heads` rows with `seq > 0`, sort by `chain_key` (bytewise), build `chain_key|seq|head_hash\n` for each row, `digest = sha256(concatenation)`. Take the snapshot in one `REPEATABLE READ` transaction.
- **Transaction:** a 0-value Base Sepolia transfer from the operator address **to itself**, `data = b"BKANCHOR1" + bytes.fromhex(digest)` (41 bytes). Apply the same gas-ceiling rule as payments (BK-312).
- **Nonce (the part to get right):** the nonce comes from the **same `settlement_accounts` allocator** that payments use, inside the same DB transaction that stores the signed raw transaction. Persist first, broadcast after commit, resend the same bytes on reconcile. An anchor and a payment must never share a nonce. Add a test that interleaves payments and anchors and checks `UNIQUE(chain_id, from_address, nonce)` holds across both tables.
- **Files:** `settlement/anchor.py` (reuse the signer, `advance` and the persist-then-broadcast logic from `adapter.py`; do not copy-paste, extract what you need). Endpoint `POST /admin/anchor` (admin token; returns `{anchor_id, digest, tx_hash, status, explorer_url, chains}`). `POST /settlement/reconcile` also advances anchors. In simulated mode return 409 `ANCHOR_NEEDS_TESTNET`.
- **Fake-chain tests:** the crash windows (after sign before broadcast; after broadcast before confirm), reconcile resends the same bytes, the nonce sharing test above, the digest is stable for the same heads and changes when any head changes, and an RPC error never marks an anchor `failed`.
- **Real run:** anchor the lead's live mandate once on Base Sepolia. Put the transaction hash and explorer link in `evidence/` (hashes and links only) and in `memory/research/SETTLEMENT.md`. The lead verifies it over the public RPC: the calldata must equal `BKANCHOR1` + the digest.
- An anchor is evidence only. It never authorizes anything, and the kernel never reads chain state.

### 2. BK-402: unbind a settlement service
- `kernel.unbind_settler(pool, *, mandate_id, actor, principal_id)` in `kernel/ops.py` next to `bind_settler`, and `DELETE /mandates/{id}/settlers/{principal_id}`.
- **Kernel exception:** the lead reviews it, and an Opus review happens before merge. Keep the change small.
- Owner only (`NOT_OWNER` otherwise). Idempotent (a missing binding returns `{"already": true}`). Audit event `SETTLER_UNBOUND`.
- Tests: owner only; after unbinding, the service gets `NOT_SETTLER` on submit, confirm and fail; **an in-flight transfer is not lost** (a `submitted` transaction stays recoverable: the owner can still confirm it, and re-binding lets the service finish it); invariants hold.
- Update R2 in the self-assessment from "no unbind yet (BK-402)" to done in your PR.

### 3. BK-403: background worker
- `backend/src/budget_kernel/worker.py`, started when `BK_WORKER=1` (as a thread in the API process, or `python -m budget_kernel.worker`; pick the simpler one and document it in the README).
- Every 30 seconds (`BK_WORKER_INTERVAL`, default 30): in testnet mode run the settlement reconcile (including anchors once BK-401 is in), run the cost-ledger `sweep_stale`, and call `kernel.tick` for each mandate returned by `kernel.due_mandates`.
- A failure in one pass is logged (no secrets, no raw tx) and never stops the loop. Make a shutdown clean.
- Test: one pass advances a mined fake-chain transfer to settled and releases an expired reservation.
- The worker authorizes nothing. It only runs housekeeping that already exists.

### 4. BK-304: per-agent inference budget (cut this if you are late)
- **Costledger exception:** lead review plus an Opus review before merge.
- ADR-0009 section D1: bucket `principal:<uuid>`, monthly, default cap 500,000 micro-USD, created lazily. `interpret(..., principal_id=None)` gains the parameter. When it is set, the call reserves against `global`, the tier bucket **and** the principal bucket in one conditional reservation (all succeed or none does).
- Exhaustion ends `unresolved` with code `AGENT_BUDGET_EXHAUSTED`, and the model is never called. It must never become an approval.
- Test: a concurrency test where many threads reserve at once and the cap is never exceeded.
- The API passes `principal_id=me.id`. Coordinate with Daniel, who owns `api/` for BK-305: touch only the `interpret` call site, and rebase on his work.

### 5. BK-140: the demo video (Oct 19)
Update `docs/demo/VIDEO_SCRIPT.md` with two new beats: **a probing agent is suspended** (the lead is building it) and **the integrity check plus the anchor** (a database edit is detected, and the anchor transaction opens on the explorer). The lead will tell you when those are demonstrable. Record and edit; 5 minutes or less. Use the real testnet run.

## Who holds the testnet key for the demo
The default is that **you** run the live testnet demo and the video on your machine, because `SETTLEMENT_PRIVATE_KEY` exists only in your `.env`. The lead does not need the key. If that changes, the lead will say so.

## Timeline
| Day | Target |
|---|---|
| Oct 16–17 | BK-401 on the fake chain, then live (a real anchor transaction hash), and BK-402 |
| Oct 18 | BK-403, then BK-304 if time allows |
| Oct 19 | Evidence export (`scripts/evidence.py`), the video. Freeze at 20:00 BST |
| Oct 20, before noon | Final evidence |

**Cut order if you are late:** BK-304 first, then BK-403 (the demo will use the manual reconcile). **Never cut the real anchor transaction hash.**

## How to report
Update your section in `memory/WHO_IS_WORKING.md` when your status changes (`ACTIVE`, `REVIEW`, `BLOCKED`, `DONE`), add a line to `memory/CHANGELOG.md` in each PR, and tell the lead when a branch is ready for review.
