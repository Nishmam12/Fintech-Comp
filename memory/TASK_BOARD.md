# Task Board

Keep this board concise. Each task needs an ID, owner/agent, status, acceptance criteria and evidence. Status values: `BACKLOG`, `READY`, `IN_PROGRESS`, `BLOCKED`, `REVIEW`, `DONE`, `DEFERRED`.

## Active
| ID | Task | Status | Owner | Acceptance criteria / evidence |
|---|---|---|---|---|
| BK-000 | Inspect target repository, current branch, runtime, dependencies and competition requirements | DONE | Implementation agent | Summarize actual repo structure, useful existing code, working tree, available commands and verified event requirements. Do not overwrite work. |

## Backlog / gated by prior work
| ID | Task | Status | Gate / acceptance criteria |
|---|---|---|---|
| BK-010 | Specify trust boundaries, threat model and transaction state machine | DONE | ADR-0004..0007 ACCEPTED 2026-10-15 (commit 9fbb1df + acceptance commit). Accepted ADRs; every transition/invariant explicitly defined. |
| BK-020 | Implement mandate/grant/ledger domain layer | DONE | `001_core.sql` + kernel ops; 65/65 backend tests pass (2026-10-15, `uv run pytest`). Unit tests pass for accounting, reservation, settlement, release and delegation. |
| BK-030 | Enforce concurrency safety, idempotency and revocation | DONE | Opus review done, findings fixed; races + hardening tests pass (90/90 non-slow, 2026-10-15). |
| BK-040 | Implement proposal schema and server-side semantic validation | DONE | test_interpret.py (mocked providers, real DB) 2026-10-15. | Model outputs cannot include/override trusted authorization state; invalid schemas fail closed. |
| BK-050 | Implement model provider adapters | DONE | Mocked tests pass; live smoke test pending API keys (OQ-005). | Explicit model IDs, timeout behavior, bounded retries and usage metrics; mocked tests pass. |
| BK-060 | Implement internal spend ledger and global cap | DONE | 13 tests pass incl. 50-way concurrent cap test and 60-call mixed-route no-deadlock test (2026-10-15). |
| BK-070 | Implement route policy and primary/escalation path | DONE | routing/interpret.py; escalation only on defined classes; tests 2026-10-15. | Routes driven by documented deterministic criteria; no arbitrary quota enforcement. |
| BK-080 | Build labeled evaluation set and naive isolated baseline | DONE | 206-case dataset (v1, v2), runner, offline sections, baseline and 6 attack scenarios (Run 2), config B on v1 and v2 (Run 5). Config C not run, see BK-150. Evidence: `memory/evaluation/RESULTS.md`. |
| BK-090 | Build dashboard wired to backend | DONE | **Member 2.** Merged to `main` (BK-413 stack, 2026-10-17). Click-through at 390 px against the live API: `docs/submission/CLICKTHROUGH_BK413.md`. Visual redesign (6cf63dd) and UI usability sprint (dbbd732, e42a002) merged 2026-10-18. |
| BK-100 | Complete security review, README, demo and event submission | IN PROGRESS | README, deployment steps and `scripts/demo.py` done. Remaining: demo video (BK-140), clean-start run (Step 11), self-assessment re-read at the freeze (Step 12). |
| BK-075 | Testnet settlement adapter (Topic F): kernel-authorized spends settle as real testnet txs; tx hash stored on the transaction | DONE | **Member 3.** Merged 2026-10-16 (suite 213 passed; F1-F3 fixed). First real transfer verified over RPC: tx `0x2c5665e7...49090`, block 48155797. Second payment `0x7570ccbe...abf1`, block 48219666 (`evidence/settlements.json`). |
| BK-110 | Submission pack: tech doc, deck (10 min or less), demo video (5 min or less), security self-assessment (permission tiers + known risks), execution evidence (tx hashes + logs) | IN PROGRESS | Tech doc and deck drafts merged (c51da9a, 578f91a). Self-assessment version 2026-10-17 (needs the freeze re-read, see NEXT_ACTIONS). Video pending. Email due 2026-10-20 17:00 BST. |
| BK-301 | Velocity limits (window_limit/window_seconds, subtree sum, attenuation) | DONE | Opus-reviewed 2026-10-15; **Lead.** Plan: docs/plans/PHASE2_PLAN.md. Closes R1; tests + Opus review. |
| BK-302 | Approval threshold (review_above -> proposed, stricter only) | DONE | Opus-reviewed 2026-10-15; **Lead.** Schema pushed first (API contract freeze, target Oct 16). |
| BK-303 | Mandate-bound settlement services | DONE | **Member 3** (kernel exception, Opus reviewed). Merged; migration 003 applied to production `bk`. Closes R2. |
| BK-304 | Per-principal daily inference budget | DONE | **Member 3** (costledger exception, approved). Built as a **monthly** bucket `principal:<uuid>` (default 500000 micro-USD); the title says daily, so correct the title. Merged. |
| BK-305 | /agent/request replays by idempotency key before interpreting | DONE | **Member 2.** Merged 2026-10-16. A retry makes zero model calls; the holder check still applies. Closes R9. |
| BK-306 | Signed grant receipts (Ed25519) | DEFERRED | Lead, stretch. Not built. Cut first, as planned. |
| BK-401 | Anchor chain heads on Base Sepolia (migration 007, `settlement/anchor.py`, `POST /admin/anchor`) | DONE | **Member 3.** ADR-0009 A5. Shares the payment nonce allocator. Needs one real anchor tx hash in evidence/. Never cut. |
| BK-402 | Settler unbind (`kernel.unbind_settler`, DELETE /mandates/{id}/settlers/{principal_id}) | DONE | **Member 3** (kernel exception: lead + Opus review). Finishes R2. |
| BK-403 | Background worker (`worker.py`, `BK_WORKER=1`): reconcile, `sweep_stale`, `kernel.tick` | DONE | **Member 3.** Cut 3rd if late (demo uses manual reconcile). |
| BK-411 | HTTP rate limiting (`api/ratelimit.py`, 429 `RATE_LIMITED`) | DONE | **Member 2.** ADR-0009 C1. Closes half of R8. Never cut. |
| BK-412 | API key lifecycle: expiry, disable, `POST /me/rotate-key` | DONE | **Member 2.** ADR-0009 C2. Closes the rest of R8. Cut rotation first if late. |
| BK-413 | Dashboard: integrity badge, suspended grants + reinstate, new error codes, rotate key | DONE | **Member 2.** Builds on the frozen shapes in ADR-0009; 390 px check; live click-through. |
| BK-421 | Hash-chained audit and ledger + `GET /mandates/{id}/integrity` | DONE | **Lead.** Migration 006, verifier and endpoint merged; Opus review pending (step 7). Anchor side is BK-401 (Afnan). |
| BK-422 | Agent circuit breaker: strikes, suspend, reinstate, `limit_probing` scenario | DONE | **Lead.** ADR-0009 part B. Built and tested (274 passed + slow state machine); Opus review (step 7) pending. Never cut. |
| BK-423 | Grounding coverage: number words, operator alias file; config B re-run (Run 5) | DONE | **Lead.** ADR-0009 D2. Run 5 recorded (v1 106/131, v2 107/131, 0 unauthorized, 0 wrong-value). Commit 40a02f7. |
| BK-501 | Names in the API: `holder_name`, `owner_name`, audit `actor_name`, budget `label` (API layer only) | DONE | **Member 3.** Merged (e39aca8). Suite 364 passed in simulated mode; 2 tests fail when `.env` sets `BK_SETTLEMENT_MODE=testnet`, open item for the freeze. |
| BK-502 | `scripts/demo_seed.py`: named demo mandate, keys to gitignored `frontend/.env.local` | DONE | **Member 3.** Merged. Creates a fresh mandate, prints labels only, `.env.local` ignored by git. Verified live on 2026-10-18. |
| BK-503 | Activity screen: plain-language event lines, names, one loading state | DONE | **Member 3.** Merged. Verified by screenshot at 1280 px (2026-10-18). |
| BK-504 | Attack lab: descriptions before run, Run all, clearer verdict | DONE | **Member 3.** Merged. Run all verified live (Concurrent Overspend: baseline violated, kernel held). |
| BK-511 | Demo sign-in buttons (dev only, from `NEXT_PUBLIC_DEMO_KEYS`) and name/role in the rail | DONE | **Member 2.** Merged (dbbd732, e42a002). Opus review fix B1: keys inlined only outside production; production build has 0 key occurrences. |
| BK-512 | Role-aware navigation and Review count badge | DONE | **Member 2.** Merged. Owner, manager and agent tabs follow the server's rules. |
| BK-513 | Mandate screen: holder names, Manage disclosure, status colours, tx time, last updated | DONE | **Member 2.** Merged. Suspend, reinstate and revoke still use the same server calls. |
| BK-514 | Plain-language reason text for every kernel code | DONE | **Member 2.** Merged. `npm run check:reasons`: 51 backend codes checked, 52 have plain text. |
| BK-515 | Ask screen: decision first, example chips, collapsible model trail | DONE | **Member 2.** Merged. Fix B2 (lead): the wrong-recipient chip is labelled honestly. |
| BK-516 | Review, Settings and Integrity skeleton and explanation, toasts | DONE | **Member 2.** Merged. Toasts cut first if late; they were not cut. |
| BK-R3-1 | UI revision 3 foundation: full-bleed shell, shared `components/ui/`, Sign-in, Mandate, Ask, `npm run check:layout` | DONE | **Lead.** a199f5b. check:layout ALL CHECKS PASS at 1366/1920/2560/1024/390; tsc, eslint, build clean. |
| BK-R3-2 | Activity (8+4) and Attack lab (ledger) as native sections | DONE | **Member 3.** Reviewed and merged 140bb79 (Opus-style review by lead, Sonnet session): frontend-only diff, no api/lib/request-path change; check:layout ALL CHECKS PASS; looked at 1366 screenshots. Nit: attack names lower-case. |
| BK-R3-3 | Review (8+4) and Settings (6+6, Sign out), Toast, Suspend/Revoke styling | DONE | **Member 2.** Reviewed and merged (lead): frontend-only diff, no request-path change; tsc, eslint, check:reasons, check:layout all pass; looked at Review, Settings and Manage at 1366. |
| BK-UIF | **UI freeze** (moved from Oct 19 14:00 to after the R3 rebuild) | DONE | **Lead.** Frozen on `main` 2026-10-19 about 18:40 UTC after BK-R3-1 to 3; Run 7 dry run on the frozen build. Bug fixes only from here. |
| BK-311..315 | Settlement hardening: confirmations, gas ceiling, verified settle_fail, recipient registry, explorer links | READY | **Member 3**, after BK-075 core. |
| BK-321..326 | Dashboard: mobile-first PWA, approval inbox, kill switch, velocity meter, explorer links, Playwright smoke | READY | **Member 2**, with BK-090. |
| BK-120 | Deck (deliverable 2, 10 min or less) | IN PROGRESS | **Member 2.** Draft 3 merged (trim to 10 slides, 600 s, plus the lead's numbers slide). Lead corrected config C, the 366-test suite and latency (Run 7). Remaining: screenshots from the frozen UI, final by Oct 20 08:00 UTC. |
| BK-150 | Live evaluation configs B/C, results recorded as measured | DONE | Config B Run 5 (106/131 v1, 107/131 v2); config C Run 6 through OpenRouter (113/131 on both); 0 unauthorized and 0 wrong-value in every final run. Config D was never defined: owner to confirm it is dropped. |
| BK-160 | Technical document draft (deliverable 1) | IN PROGRESS | **Member 2**, lead reviews. Dashboard section updated for the new UI; config C row, 366-test suite and Run 7 latency added by the lead. Remaining: screenshots and the lead's final numbers section. |
| BK-130 | Execution evidence pack script -> evidence/ (hash, explorer link, kernel tx, audit) | REVIEW | **Member 3.** Deliverable 6. `scripts/evidence.py` and `evidence/` hold 2 payments (`settlements.json`, `earlier_transfers.json`) and 1 anchor (`anchors.json`, block 48219690). Final export Oct 20 before noon. |
| BK-140 | Demo video (deliverable 3, 5 min or less) | IN PROGRESS | **Member 3.** Script updated for the new UI (df4f344). Rehearsal Oct 18 evening; final take Oct 19 15:00-18:00, after the UI freeze at 14:00. |
| BK-OWN-1 | **Owner:** email registration form + passport pages to wangyr@pbcsf.tsinghua.edu.cn | READY | Must be sent before 2026-10-20 15:59 UTC (23:59 Beijing); send early to confirm the slot. Owner said "sending" on Oct 19; not confirmed sent. |
| BK-OWN-2 | **Owner:** provide GitHub repo URL so the orchestrator can add the remote and push | DONE | origin = github.com/Nishmam12/Fintech-Comp, main pushed 2026-10-15 (84f8c6a). |
| BK-200 | Investigate consent-aware decision trace collection for future model improvement | DEFERRED | Separate design/privacy review; no real-user training collection until approved. |
| BK-210 | Evaluate fine-tuning an existing model | DEFERRED | Only after enough reviewed data and a measurable baseline; not an MVP task. |

## Rules
- Do not mark `DONE` without evidence (test output, diff, URL/source, or explicit review result).
- A task may be split into smaller tasks when implementation reveals meaningful subproblems. Update IDs and links rather than losing context.
- When a task is completed, update `CURRENT_STATE.md`, `NEXT_ACTIONS.md` and `CHANGELOG.md`.
