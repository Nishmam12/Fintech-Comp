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
| BK-080 | Build labeled evaluation set and naive isolated baseline | REVIEW | 206-case dataset + runner done; offline sections measured (see memory/evaluation/RESULTS.md). Baseline + 6 attack scenarios built and measured (RESULTS.md Run 2). Configs B/C pending API keys. Versioned scenarios, expected labels, reproducible runner and baseline report. |
| BK-090 | Build dashboard wired to backend | READY | **Member 2.** Brief in ONBOARDING.md section 4. UI displays actual server results and runs repeatable simulations. |
| BK-100 | Complete security review, README, demo and event submission | IN PROGRESS | README + deployment steps + scripts/demo.py done (2026-10-15). Remaining: demo video, final clean-start run recording, submission checklist. Clean-start demo, passing tests, disclosed limitations and submission requirements met. |
| BK-075 | Testnet settlement adapter (Topic F): kernel-authorized spends settle as real testnet txs; tx hash stored on the transaction | READY | **Member 3.** Brief in ONBOARDING.md section 4. Adapter is called only after kernel `reserved`; testnet only, key from .env; hashes visible in audit + UI; ADR-0007 accepted. |
| BK-110 | Submission pack: tech doc, deck (10 min or less), demo video (5 min or less), security self-assessment (permission tiers + known risks), execution evidence (tx hashes + logs) | IN PROGRESS | All 6 checklist items in [[research/COMPETITION]] present and emailed by 2026-10-20 17:00 BST. Security self-assessment drafted: docs/SECURITY_SELF_ASSESSMENT.md (2026-10-15). |
| BK-301 | Velocity limits (window_limit/window_seconds, subtree sum, attenuation) | REVIEW | **Lead.** Plan: docs/plans/PHASE2_PLAN.md. Closes R1; tests + Opus review. |
| BK-302 | Approval threshold (review_above -> proposed, stricter only) | REVIEW | **Lead.** Schema pushed first (API contract freeze, target Oct 16). |
| BK-303 | Mandate-bound settlement services | READY | **Member 3** (kernel exception: lead + Opus review before merge). Closes R2. |
| BK-304 | Per-principal daily inference budget | BACKLOG | **Member 3, stretch** (costledger exception: lead + Opus review). Closes R7. Cut 4th if late. |
| BK-305 | /agent/request replays by idempotency key before interpreting | READY | **Member 2** (api/ + routing/). Closes R9. |
| BK-306 | Signed grant receipts (Ed25519) | BACKLOG | **Lead, stretch.** Cut 1st if late. |
| BK-311..315 | Settlement hardening: confirmations, gas ceiling, verified settle_fail, recipient registry, explorer links | READY | **Member 3**, after BK-075 core. |
| BK-321..326 | Dashboard: mobile-first PWA, approval inbox, kill switch, velocity meter, explorer links, Playwright smoke | READY | **Member 2**, with BK-090. |
| BK-120 | Deck (deliverable 2, 10 min or less) | READY | **Member 2.** Lead supplies outline + measured numbers. |
| BK-150 | Live evaluation configs B/C/D, results recorded as measured | BLOCKED | **Member 2.** Blocked on API keys (lead shares privately). |
| BK-160 | Technical document draft (deliverable 1) | READY | **Member 2**, written alongside the deck; lead reviews. |
| BK-130 | Execution evidence pack script -> evidence/ (hash, explorer link, kernel tx, audit) | READY | **Member 3.** Deliverable 6. |
| BK-140 | Demo video (deliverable 3, 5 min or less) | READY | **Member 3.** Lead supplies script + shot list. Oct 19. |
| BK-OWN-1 | **Owner:** email registration form + passport pages to wangyr@pbcsf.tsinghua.edu.cn | READY | Must be sent by 2026-10-20 17:00 BST; send early to confirm the slot. |
| BK-OWN-2 | **Owner:** provide GitHub repo URL so the orchestrator can add the remote and push | DONE | origin = github.com/Nishmam12/Fintech-Comp, main pushed 2026-10-15 (84f8c6a). |
| BK-200 | Investigate consent-aware decision trace collection for future model improvement | DEFERRED | Separate design/privacy review; no real-user training collection until approved. |
| BK-210 | Evaluate fine-tuning an existing model | DEFERRED | Only after enough reviewed data and a measurable baseline; not an MVP task. |

## Rules
- Do not mark `DONE` without evidence (test output, diff, URL/source, or explicit review result).
- A task may be split into smaller tasks when implementation reveals meaningful subproblems. Update IDs and links rather than losing context.
- When a task is completed, update `CURRENT_STATE.md`, `NEXT_ACTIONS.md` and `CHANGELOG.md`.
