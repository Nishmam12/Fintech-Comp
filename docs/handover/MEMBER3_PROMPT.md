# Handover prompt: Member 3 (chain, evidence, video)

**How to use:** clone the repo and finish setup (ONBOARDING.md section 1). Then open Claude Code **in the repository root** and paste everything below the line as your first message. Before pasting, replace `<NAME>` with your name in lowercase, for example `sam`.

---

You are working with me, Member 3 of a 3-person team, on **Budget Kernel**, our entry for the 2026 Shenzhen FinTechathon (Topic F, Agent Wallet). The hard deadline is **2026-10-20 17:00 BST**, and the build freezes on **Oct 19 at 20:00 BST**. The team lead built the backend. My job is the **on-chain part**:

- **Settlement adapter:** the kernel authorizes and reserves a spend, then my adapter sends a real **Base Sepolia test-USDC** transfer and records its transaction hash.
- **Execution evidence:** the transaction hash is the competition's execution evidence (deliverable 6) and earns the 0–5 on-chain bonus. It is the team's top priority.
- **Demo video.** I also produce the demo video.

## Read first, in this order
1. `AGENTS.md` and `CLAUDE.md`: rules for us both.
2. `ONBOARDING.md`: setup, the claim protocol, and my BK-075 brief in section 4, including **5 security requirements**.
3. `memory/decisions/ADR-0007-TESTNET-SETTLEMENT-ADAPTER.md`: the design I implement.
4. `docs/plans/PHASE2_PLAN.md`: my tasks, the timeline and the cut order.
5. `docs/SECURITY_SELF_ASSESSMENT.md` sections 3, 6 and 7: the settlement service tier and risks R2–R5, which my work closes.
6. `backend/src/budget_kernel/kernel/ops.py`: `settle_start` (with its `on_submit` hook), `settle_confirm`, `settle_fail`, `_require_settler`.
7. `memory/WHO_IS_WORKING.md`: check nobody else claims my paths.

## Rules that are not negotiable
- **Claim first.** Before coding, fill in my section of `memory/WHO_IS_WORKING.md` only. Commit only that file as `claim: <NAME> <task-id>` and push to `main`. Keep it updated.
- **Branches and PRs.** One branch per task, named `<NAME>/<task-id>-<slug>`. Never commit to `main` except the claim file. Open a PR with test output; the lead merges.
- **My paths.** I own `backend/src/budget_kernel/settlement/`, `backend/migrations/003_settlement.sql` (migration number 003 is reserved for me), `backend/tests/integration/test_settlement*.py`, `evidence/` and `scripts/evidence*.py`.
- **Kernel exceptions.** I may touch the kernel and cost ledger for **BK-303** and **BK-304 only**, each on its own branch. Those PRs need the lead's review **and** an Opus review before merge. Never edit an existing migration.
- **Testnet only.** Use a **new wallet created only for this**. Its private key lives only in `.env` as `SETTLEMENT_PRIVATE_KEY`. Never print it, log it, store it in the DB, put it in an exception message or commit it. Only the wallet **address** goes into docs.
- **Untrusted values.** Never take a destination address, amount or chain parameter from a request, a proposal or model output. Addresses come from a static, operator-controlled registry only.
- **Shared test schema rules.** Use my own `BK_TEST_SCHEMA=bk_test_<NAME>`, and never run two pytest sessions at once.
- **Honest evidence.** Record only transactions that really happened, with real hashes. Report failures as failures.
- **Ask, don't guess.** If a design question isn't answered by ADR-0007, stop and ask me so I can ask the lead.

## My tasks, in order
1. **BK-075 step 1: report back before coding.**
   - Verify the Circle test-USDC contract address on Base Sepolia, the chain ID, and the faucet limits **from official Circle and Base docs**.
   - Create the testnet wallet and fund it with test ETH (gas) and test USDC.
   - Write the contract address, chain ID, wallet address and sources into `memory/research/SETTLEMENT.md`.
   - Show me before continuing. Faucets can be slow, so do this today.
2. **BK-075 step 2: the adapter** (ADR-0007).
   - Sign locally inside `on_submit` (no network I/O there, because it runs under the mandate lock).
   - Pre-assign the nonce and persist the signed raw transaction in migration 003, then broadcast **after** the commit.
   - Confirm via `kernel.settle_confirm` using a **service-kind principal**.
   - Build a reconciler that re-broadcasts the **same bytes** and never re-signs with a new nonce.
   - Add `web3` to `backend/pyproject.toml`.
   - Add `BK_SETTLEMENT_MODE` (`simulated` by default, or `testnet`). In testnet mode the simulated `POST /transactions/{id}/settle` returns 409.
   - Write tests with a **fake chain client** for every crash window in ADR-0007 and for each of the 5 security requirements.
3. **First real transfer.** Run one real kernel-authorized transfer on Base Sepolia. Record the hash and the explorer link. **Target: Oct 17.**
4. **BK-311..315 hardening** (details in PHASE2_PLAN):
   - confirmations (default 2) and re-org tolerance
   - a gas-price ceiling (wait, never re-sign)
   - `settle_fail` only on proof: a mined receipt with `status = 0`, or the nonce consumed by another transaction (a timeout is not proof)
   - the static recipient → address registry
   - explorer links stored and returned by the API, which Member 2's dashboard shows
5. **BK-303 mandate-bound settlers** (kernel exception).
   - Add a `mandate_settlers(mandate_id, principal_id)` table (in migration 003) and an owner-only `POST /mandates/{id}/settlers`.
   - Change `_require_settler` so a service can settle only mandates it is bound to.
   - Write tests for both the allowed and the refused cases.
   - Lead and Opus review before merge.
6. **BK-130 evidence pack** (deliverable 6).
   - Write `scripts/evidence.py`. It exports every testnet settlement (kernel transaction ID, amount, recipient, transaction hash, explorer link, block number, confirmation time, audit trail) to `evidence/` as Markdown and JSON.
   - Run it against the real data.
7. **BK-140 demo video** (deliverable 3, at most 5 minutes; record and edit on Oct 19).
   - Write the script first and show it to me.
   - Suggested beats:
     - an agent asks in plain language
     - the kernel reserves the money
     - an above-threshold request waits for the owner's approval on a phone
     - the testnet transfer happens and the explorer opens
     - the owner taps the kill switch and the agent is cut off
     - attack scenarios run: baseline vs kernel
     - the invariants hold
   - Use `scripts/demo.py` as the backbone.
8. **BK-304 per-principal inference budget** (stretch, only if everything above is done; costledger exception, same review rule).

## Timeline (mine)
- **Oct 15:** step 1 (wallet funded, report back).
- **Oct 16:** adapter with the fake chain; BK-303.
- **Oct 17:** **first real transaction hash**; hardening BK-311..314.
- **Oct 18:** BK-315; evidence script; video script.
- **Oct 19:** record and edit the video (freeze at 20:00).
- **Oct 20:** final evidence export.

If I am behind, cut BK-304 first, then BK-312. **Never cut the real transaction hash.**

## How to work with me
- Start by summarising what you read and proposing step 1. Build in small, tested increments.
- Before calling anything done, run it and show me the output.
- Stop and tell me immediately if a faucet, an RPC endpoint or the contract address doesn't match the docs. That is a blocker the lead must know about the same day.
- At each stopping point, update my WHO_IS_WORKING section, and add a line to `memory/CHANGELOG.md` in the PR.
