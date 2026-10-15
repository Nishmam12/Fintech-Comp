# Next steps for Afnan (Member 3): rebase, review gate, first real transaction

**How to use:** `git pull` on `main`, then open Claude Code **in the repository root** and paste everything below the line as your message. The lead wrote this after reading your branch `afnan/BK-303-mandate-settlers`.

---

You are working with Afnan (Member 3) on **Budget Kernel**. The lead reviewed Afnan's branch `afnan/BK-303-mandate-settlers` on 2026-10-15 and found it in good shape. The settlement adapter core, the mandate-bound settlers (BK-303), the testnet mode, the derived explorer link (BK-315), the evidence script (BK-130) and the video script draft are all there. No key material was found in the diff. The deadline is **2026-10-20 17:00 BST**, and the build freezes on **Oct 19 at 20:00 BST**.

The rules in `AGENTS.md`, `ONBOARDING.md` and `docs/handover/MEMBER3_PROMPT.md` still apply. Never print, log or commit the private key. Use your own `BK_TEST_SCHEMA`, and never run two pytest sessions at once.

## Step 0: rebase onto the current `main` (do this first)
`main` has moved since you branched. As of commit `dee775c` it also contains:
- **ADR-0008:** velocity windows and the approval threshold, plus migration `005_robustness.sql`
- **Demo changes:** `scripts/demo.py` has a new guard-rail section (7b)
- **Pool fix:** the connection pool now checks connections before use
- **New API routes:** `GET /me` and `GET /mandates`
- **Template restored:** `.env.example` was accidentally deleted from `main` and is back

A trial merge showed conflicts in `backend/src/budget_kernel/api/app.py` and `scripts/demo.py`. Resolve them like this:
1. Commit or stash your work. Then:
   ```bash
   git fetch origin
   git checkout afnan/BK-303-mandate-settlers
   git rebase origin/main
   ```
2. **`api/app.py`:** keep **both** sides. Main added `GET /me`, `GET /mandates`, the `proposal` column in the state query, `window_used` and `review_reason`. You added the settlement endpoints, testnet mode and `explorer_url`. Neither side should lose anything.
3. **`scripts/demo.py`:** main added the section "7b. Guard rails" (approval threshold, velocity limit). Keep it. Keep your testnet-mode block as well, and make sure the whole script still passes in simulated mode with no extra environment.
4. **`.env.example`:** keep your 8 added lines on top of the restored file.
5. **Migrations:** `003_settlement.sql` must apply on a fresh schema, and on a schema that already has `001`, `002`, `004` and `005`. The production schema is in that second state, because migration `003` was never applied there. Test both. Do not renumber your migration.
6. Run the **full** non-slow suite on your own schema (`uv run pytest -q -m "not slow"`, about 14 minutes) and paste the result in your PR. It must include your settlement tests and the BK-303 tests.
7. Push with `git push --force-with-lease origin afnan/BK-303-mandate-settlers`. Never force-push `main`.

## Step 1: the review gate (the lead's Opus session reviews this)
After the rebase and a green suite, tell the lead the branch is ready (and update your section of `memory/WHO_IS_WORKING.md` to `REVIEW`). The review checks your work against `docs/SECURITY_SELF_ASSESSMENT.md` section 6. Make sure each of these is already true, with a test:
1. `settle_fail` is called **only** with on-chain proof: a mined receipt with `status = 0`, or the nonce consumed by a different transaction. A timeout, a dropped mempool entry or an RPC error never releases funds. Those stay `submitted`/`stuck` and get re-broadcast.
2. Recipients resolve **only** from the static registry file (`BK_SETTLEMENT_RECIPIENTS`). An unknown recipient is refused **before** signing. Nothing from a request, proposal or model output can supply an address.
3. Amounts convert as integers only (1 cent = 10,000 base units), USD only.
4. `BK_SETTLEMENT_MODE=testnet` makes the simulated `POST /transactions/{id}/settle` return 409, and every real settlement goes through `on_submit`.
5. `on_submit` signs and stores only. It makes no network call (it runs under the mandate lock).
6. The private key never appears in logs, exceptions, the DB, API responses or audit rows. Add a test that triggers a failure and checks the error text.
7. **BK-303:** an unbound service principal is refused (`NOT_SETTLER`), only the owner can bind, binding is idempotent, and the existing settlement tests were updated to bind their service principal.
8. Also answer in your PR: what happens if the process crashes after signing but before broadcast, and after broadcast but before the confirm call? Point to the test for each.

The lead may ask for changes. Fix them on the same branch.

## Step 2: the blocker, test ETH
Your wallet has 20 test USDC but no test ETH for gas, so a real transfer is impossible. The lead is asking the team to send about **0.001 Base Sepolia ETH** to your wallet address `0x228F0C5Dcdd12b2A9E21d289969FF286ff71a97D` (public address; never share the key).
- Until it arrives, keep working on the fake chain.
- If you find a faucet or bridge route that works, verify it from official docs before you use it, and note it in `memory/research/SETTLEMENT.md`.
- Tell the lead the moment the ETH arrives. The first real transaction is the top priority, with a target of **Oct 17**.

## Step 3: the first real transaction (once the wallet has gas)
1. Run one kernel-authorized transfer on Base Sepolia in testnet mode. Keep the amount tiny.
2. Record, in `memory/research/SETTLEMENT.md` and in the evidence output: the kernel transaction ID, the transaction hash, the block number, the explorer link, and the time. Open the explorer link and confirm it resolves before the demo. Your notes list two explorers, so state which one the demo uses.
3. Run `scripts/evidence.py` against the real data and commit the output under `evidence/` (hashes and links only; no secrets).
4. Tell **Daniel** (Member 2, dashboard) the exact field name the API returns for the explorer link. Today it is `explorer_url` on each transaction in `GET /mandates/{id}/state`. His UI must use that field and must not build URLs itself.

## Step 4: hardening and the video (in this order, after Step 3)
- **BK-311:** confirmations (default 2) and tolerance for a re-org back to pending.
- **BK-312:** a gas-price ceiling. Above it the transfer waits and is never re-signed with a new nonce.
- **BK-313/314:** verify the proof rules and the recipient registry are covered by the tests above.
- **BK-140 video script:** your draft is `docs/demo/VIDEO_SCRIPT.md`. Update it so the video shows the guard rails now on `main`: an above-threshold request waits for the owner, the owner approves, then the testnet transfer and the explorer page. Then the velocity-limit refusal, the kill switch, and the baseline-versus-kernel attack result.
- Do **not** start BK-304 (per-agent inference budget) until everything above is done.

## Timeline
- **Oct 15–16:** Step 0, and the Step 1 review request.
- **Oct 17:** Steps 2–3, the first real transaction.
- **Oct 18:** Step 4, evidence run, updated video script.
- **Oct 19:** record and edit the video (freeze at 20:00).
- **Oct 20 before noon:** final evidence export.

If you fall behind, cut BK-312 and BK-304. **Never cut the real transaction hash.**

## How to report
Update your section in `memory/WHO_IS_WORKING.md` whenever your status changes. Add a line to `memory/CHANGELOG.md` in each PR. If you are blocked for more than 30 minutes, write it under *Notes / blockers* and tell the lead.
