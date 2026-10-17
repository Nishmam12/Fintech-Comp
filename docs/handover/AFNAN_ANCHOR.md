# Afnan (Member 3): your stack is merged. Next: the real anchor, then the video

**How to use:** `git pull` on `main`, then open Claude Code **in the repository root** and paste everything below the line as your message.

---

You are working with Afnan (Member 3) on **Budget Kernel**. The lead reviewed all four of your Phase 3 branches (`docs/handover/PHASE3_REVIEW.md`) and **approved them**. They are merged into `main` together with Daniel's stack. Your A1 fix (one failing tick no longer skips the other mandates) is already applied by the lead. The kernel's K1 amendment changed one rule you should know: **reinstating a grant is now owner-only**, and a holder can no longer delegate to itself (`SELF_DELEGATION`).

The rules in `AGENTS.md`, `ONBOARDING.md` and `docs/handover/AFNAN_PHASE3.md` still apply. Never print, log or commit the private key or any `.env` value. Use your own `BK_TEST_SCHEMA`, and never run two pytest sessions at once on it.

## Before you start
1. `git pull` on `main`. Confirm `backend/migrations/007_anchors.sql` is there.
2. **Wait for the lead's message that production `bk` has migration 007.** The anchor writes to the `anchors` tables on the production schema, so it cannot run before that. (The lead applies it with `uv run python -m budget_kernel.db.migrate`.) If you are unsure, check from your machine: `uv run python -m budget_kernel.db.migrate` prints `applied=[]` once everything is applied. Do not run it yourself unless the lead asks.
3. Claim in `memory/WHO_IS_WORKING.md` (your own section only): task `BK-401 real anchor + BK-140`, branch `afnan/BK-401-real-anchor`.

## Task 1: the real anchor transaction (the second on-chain proof; the most valuable item left)
Your `.env` must have `BK_SETTLEMENT_MODE=testnet`, `BK_SETTLEMENT_RECIPIENTS` pointing at your recipient file, `SETTLEMENT_PRIVATE_KEY`, and `BK_ADMIN_TOKEN`. Check the wallet still has test ETH for gas.

1. Start the API against the production schema: `uv run --project backend uvicorn budget_kernel.api.app:app --port 8000`.
2. **Create something worth anchoring with the live demo,** so the anchored heads include a real payment, a suspension and a reinstate: `DEMO_PAY_USD=1 uv run --project backend python scripts/demo.py` (tiny amount; the wallet holds about 20 test USDC). All steps must show `[ok]`. Note the mandate id it prints or find it in the dashboard.
3. Anchor: `POST /admin/anchor` with the `X-Admin-Token` header. The response has `anchor_id`, `digest`, `tx_hash`, `status`, `explorer_url` and `chains`.
4. Reconcile until the anchor is `confirmed` (`POST /settlement/reconcile`, which also advances anchors, with the service and admin headers as in `scripts/demo.py`).
5. **Check it yourself on the explorer:** open the `explorer_url`. The transaction is a 0-value transfer from your operator address to itself, with input data starting `0x424b414e43484f5231` (that is `BKANCHOR1`) followed by the 32-byte digest. It must equal `digest` from step 3.
6. **Check the integrity endpoint sees it:** `GET /mandates/{id}/integrity` with the owner key (the demo's owner), or with the admin token. It must return `ok: true` and `last_anchor` with `status: confirmed` and `matches: true`.
7. Record in `memory/research/SETTLEMENT.md` and under `evidence/` (hashes and links only, no secrets): the anchor id, the `tx_hash`, the block number, the explorer link, the digest and the time. Update `scripts/evidence.py` output if it lists transactions, so the anchor appears next to the payment.
8. Send the lead the `tx_hash`. The lead verifies the calldata over the public RPC.

If anything fails, **stop and tell the lead** with the exact error (no key material). Typical causes: gas price above the ceiling (the anchor waits; retry), wallet out of ETH, or the migration not applied yet.

## Task 2: the video (BK-140, final recording Oct 19)
Update `docs/demo/VIDEO_SCRIPT.md` with the beats that are now real on `main`:
- **A probing agent is suspended:** five out-of-scope requests, the grant is suspended, even a valid request is refused, the **owner** reinstates it (the agent cannot).
- **Tamper evidence:** the dashboard's integrity badge is green with the anchor link; then show the check failing. For the failing shot use a **scratch schema or a copy**, never the production data (lift the append-only trigger as the table owner, edit one audit row, reload the badge: red with `broken_at`). Restore or discard the scratch data afterwards.
- **Rate limit and key rotation** are optional quick beats.
- It must stay **5 minutes or less**, use the real testnet run, and show the explorer pages for the payment and the anchor.
Record when the lead says the build is frozen (Oct 19, 20:00 BST), or record a rehearsal earlier and re-record only if something changed.

## Timeline
- **Today (Oct 17):** Task 1 as soon as the lead confirms the migration.
- **Oct 18:** script update and a rehearsal recording.
- **Oct 19:** final recording and the evidence export (`scripts/evidence.py`); freeze at 20:00 BST.
- **Oct 20, before noon:** final evidence.

**Never cut the real anchor transaction hash.**

## How to report
Update your section in `memory/WHO_IS_WORKING.md` when your status changes, add a line to `memory/CHANGELOG.md` in each PR, and tell the lead when a branch or the anchor is ready for review. If you are blocked for more than 30 minutes, write it under *Notes / blockers* and tell the lead.
