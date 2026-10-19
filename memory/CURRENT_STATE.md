# Current State — Budget Kernel

**Last verified:** 2026-10-19 20:45 UTC, lead session (Opus), against `main` after the UI freeze and the Run 7 dry run.
**Overall status:** `BUILD AND UI FROZEN. DRY RUN PASSED (RUN 7). SECURITY SELF-ASSESSMENT DRAFT 3 DONE. REMAINING: VIDEO, EVIDENCE EXPORT, SCREENSHOTS, FINAL DECK AND DOC, SUBMISSION (DEADLINE 2026-10-20 15:59 UTC).`

## Since the 2026-10-18 sync
- **UI revision 3** (BK-R3-1 to 3): full-bleed, viewport-filling, rem-scaled design; shared `frontend/components/ui/`; all seven screens rebuilt (lead: shell, Sign-in, Mandate, Ask; Afnan: Activity, Attack lab; Daniel: Review, Settings). `npm run check:layout` passes at 1366, 1920, 2560, 1024 and 390 px. Design source: `docs/design/mockup.html`, `docs/design/UI_SPEC.md`.
- **Config C** (Run 6): escalation through OpenRouter, 113/131 on both datasets, 0 unauthorized. Route is opt-in (`BK_ESCALATION_PROVIDER=openrouter`).
- **Run 7 dry run**: 366 tests + slow state machine; `demo.py --attacks` 34/34; authorize 2,327 ms median at 114.5 ms RTT.
- **Test robustness**: tests default to simulated settlement; race tests raise `statement_timeout` for queued racers; worker test has a 900 s timeout.
- **Self-assessment draft 3**: R23 (demo keys), R24 (names on `/budget`), R6 and R18 updated.
- **Clock**: the lead machine is on Dhaka time (UTC+6); hook times labelled BST are Dhaka time.

_The sections below are from the 2026-10-18 sync and are still accurate except where the list above supersedes them._

## One-paragraph project summary
Budget Kernel is a financial-decision pipeline with (1) selective, cost-aware model routing for interpreting natural-language financial requests into typed proposals, and (2) a deterministic authorization kernel that independently enforces mandates, delegated authority, spending limits, reservations, revocation, idempotency and auditability. LLMs never authorize transactions. Settlement runs on Base Sepolia (chain 84532) with test USDC only.

## What is built and merged on main
- **Kernel** (ADR-0004, 0005, 0008): move-based accounting, invariants I1 to I5, velocity windows, approval threshold. Opus-reviewed.
- **Hash-chained history and integrity check** (ADR-0009 A, BK-421): `GET /mandates/{id}/integrity`.
- **On-chain anchor** (ADR-0009 A5, BK-401): one anchor on Base Sepolia, verified by the lead over RPC.
- **Agent circuit breaker** (ADR-0009 B, BK-422): strikes, suspend, owner-only reinstate (amendment K1), `limit_probing` scenario.
- **API hardening** (ADR-0009 C): rate limit with `429 RATE_LIMITED` and `Retry-After` (BK-411); replay before interpret (BK-305); key expiry, disable and rotation (BK-412), with `KEY_ALREADY_ROTATED` on a race.
- **Per-agent inference budget** (BK-304, a monthly bucket), **background worker** (BK-403, `BK_WORKER=1`), **settler unbind** (BK-402).
- **Settlement** (BK-075, BK-303): two payments on Base Sepolia, both verified on-chain.
- **Interpretation**: primary model `qwen3.7-flash-2026-07-15`, escalation off in config B. Rules fast path. Number words and operator aliases (Step 8, BK-423).
- **Dashboard** (Next.js 16): redesigned 2026-10-18. Demo sign-in buttons exist in dev builds only. Tabs follow the user's role. Activity and Attack lab screens are plain-language.
- **Tests**: 364 passed on the non-slow suite in simulated mode (after BK-501). 2 tests fail when `.env` sets `BK_SETTLEMENT_MODE=testnet` (open item below). The slow state-machine test last passed before the UI sprint; re-run at Step 11.

## Milestones
| Milestone | Status | Evidence / note |
|---|---|---|
| M0 Repository and event requirements | DONE | Repo Nishmam12/Fintech-Comp; rules in `memory/research/COMPETITION.md`. |
| M1 Threat model, state machine, invariants | DONE | ADR-0004 to 0007 ACCEPTED. |
| M2 Deterministic ledger and authorization tests | DONE | Phase 1 suites, then the Phase 3 suite. |
| M3 Typed proposal schema and provider adapters | DONE | BK-040, BK-050. |
| M4 Budget-aware router and cost ledger | DONE | BK-060, BK-070; Run 3 measured the cost of the controls. |
| M5 Adversarial evaluation and baseline | DONE | BK-080 (Run 2, Run 5). Config C not run. |
| M6 Dashboard, demo, documentation | DONE | BK-090, BK-413, UI sprint BK-501 to 516 merged. |
| M7 Post-MVP fine-tuning research | DEFERRED | Not part of the build. |
| Phase 3 A: hash chain and anchor | DONE | BK-421, BK-401. |
| Phase 3 B: circuit breaker | DONE | BK-422. |
| Phase 3 C: API hardening | DONE | BK-411, BK-412, BK-305. Signed receipts (BK-306) cut. |
| Phase 3 D: coverage, budgets, worker | DONE | BK-423, BK-304, BK-403. |
| Submission deliverables | IN PROGRESS | Tech doc and deck drafts merged (BK-160, BK-120). Video script updated (BK-140). Self-assessment version 2026-10-17. Evidence export (BK-130) due Oct 20. |

## Evidence on Base Sepolia (chain 84532)
| Item | Transaction | Block | Check |
|---|---|---|---|
| Payment 1 (first real transfer) | `0x2c5665e7908ebb775e03185e5aef9fd9e566b79c21652d7f3c789db1add49090` | 48155797 | Receipt status 1; verified over RPC by the lead. |
| Payment 2 | `0x7570ccbe8c9ca0aa52c057d2c52e567fece698c28909718e29e3b505f061abf1` | 48219666 | Receipt status 1; in `evidence/settlements.json`. |
| Anchor 1 (chain-head digest) | `0xcb1ba8f8c64413779274509bb7333e9693123cdc8d5e9229ba927b74f5578e2e` | 48219690 | 0-value self-transfer; calldata `BKANCHOR1` plus digest; lead verified; integrity endpoint reports `matches: true`. |

## Evaluation (latest run: Run 5, live config B)
- **v1:** 106/131 correct (80.9%). **v2:** 107/131 correct (81.7%). 0 unauthorized approvals, 0 wrong-value approvals.
- Cost about 2,700 micro-USD per run. End-to-end latency p50 about 4.2 s, p95 about 6.1 s.
- **Offline kernel scripts:** 134/134 steps, 0 unauthorized approvals, 0 invariant violations.
- **Config C (escalation model) has not been run.** No DeepSeek key.
- **Authorization latency:** the 1.1 s figure predates the hash chain and the breaker. It must be re-measured before anything quotes it.

## Open items (checked against the repository on 2026-10-18)
1. **Self-assessment figure is stale.** `docs/SECURITY_SELF_ASSESSMENT.md` quotes config B on v2 as 108/131 (82.4%), which is Run 4. Run 5 measured 107/131 (81.7%). Fix at the Step 12 pass.
2. **Two tests fail in testnet mode.** They pass only when `.env` does not set `BK_SETTLEMENT_MODE=testnet` (Afnan's note on BK-501). This must be explained or fixed before the freeze.
3. **BK-150 title.** Config C not run, and config D is not defined anywhere in `RESULTS.md`.
4. **Board rows not verified.** BK-311 to 315 and BK-321 to 326 are still READY. Some may already be covered by BK-303 and BK-401. Decide: finish or cut.
5. **Presence sections are stale.** Daniel's and Afnan's sections still show REVIEW and "PRs pending". Each member should update their own section.
6. **Deck length.** About 11 min 10 s against a 10-minute limit.
7. **Latency not yet re-measured.**
8. **Owner actions not done:** BK-OWN-1 registration email (not confirmed sent); Alibaba key rotation; DB password rotation before submission.
9. **Demo keys.** Dev-only after the Opus fix B1. Record as a new risk (R23) at the freeze.
10. **Budget labels.** `/budget` names the principals in a bucket to any signed-in caller (low risk, finding L1). Record at the freeze.

## Next action
See [[NEXT_ACTIONS]].
