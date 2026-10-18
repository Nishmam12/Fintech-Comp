# Who Is Working — live team presence

**Read this before you start. Update it when you start and when you stop.** It is the team's lock board. Git is the sync, so a claim only counts once it is **pushed**.

## Team roster
| Member | GitHub | Role | Machine | GPU | Good for |
|---|---|---|---|---|---|
| Nishmam (lead) | Nishmam12 | Team lead; final merge + submission owner | Windows 11 | RTX 4070 Ti Super (16 GB) | Kernel/core, reviews, any local-model or video-render work |
| Member 2 *(name TBD)* | *(TBD)* | *(TBD)* | *(TBD)* | RTX 2070 Super (8 GB) | Frontend, docs, eval dataset, tests |
| Member 3 *(name TBD)* | *(TBD)* | *(TBD)* | *(TBD)* | RTX 5060 (8 GB) | Frontend, testnet adapter, demo/video, tests |

GPU only matters for local inference or video rendering. All model calls in the product go to hosted APIs, so every machine can run the full stack.

## Active now
One section per member. **Edit only your own section** to avoid merge conflicts. Times are UTC.

### Nishmam (RTX 4070 Ti Super)
- **Status:** ACTIVE
- **Task ID:** Phase 3 lead: BK-421 hash chain + integrity, BK-422 circuit breaker, BK-423 grounding coverage (ADR-0009)
- **Branch:** main
- **Claimed areas (paths):** backend/src/budget_kernel/{kernel,db,simulation}, backend/migrations, backend/tests, docs/SECURITY_SELF_ASSESSMENT.md, memory/
- **Started / last update (UTC):** 2026-10-15 17:50
- **Notes / blockers:** Production `bk` still needs migrations 003 and 006 (lead runs `uv run python -m budget_kernel.db.migrate`).

### Member 2 (RTX 2070 Super) — daniel
- **Status:** REVIEW
- **Task ID:** BK-514, BK-512, BK-511, BK-513, BK-515, BK-516 done; PRs #13-#18 (stacked, merge in that order). BK-120 deck and BK-160 technical document wait for the Oct 19 14:00 BST freeze
- **Branch:** daniel/BK-514-reasons > BK-512-nav > BK-511-demo-signin > BK-513-mandate > BK-515-ask > BK-516-screens
- **Claimed areas (paths):** frontend/ (except ActivityView.tsx, SimulationView.tsx, lib/describe.ts), docs/submission/
- **Started / last update (UTC):** 2026-10-18
- **Notes / blockers:** BK-511 (#15) needs the Opus review (demo keys). `/me` has no key expiry (Settings shows it only after a rotate); lead to decide on an API field. The wrong-recipient chip needs a live model; no provider keys on this machine, so not verified.

### Member 3 (RTX 5060) — Afnan Mojumder
- **Status:** REVIEW
- **Task ID:** UI sprint: BK-501 names in API, BK-502 demo seed, BK-503 Activity, BK-504 Attack lab, BK-140 video script
- **Branch:** afnan/BK-501-names, afnan/BK-502-demo-seed, afnan/BK-503-activity, afnan/BK-504-attack-lab, afnan/BK-140-video-script
- **Claimed areas (paths):** backend/src/budget_kernel/api/app.py (read models /state, /audit, /budget only), backend/tests/integration/test_api_read_models.py, scripts/demo_seed.py, frontend/components/{ActivityView,SimulationView}.tsx, frontend/lib/describe.ts, frontend/lib/api.ts (3 type lines only), docs/demo/VIDEO_SCRIPT.md
- **Started / last update (UTC):** 2026-10-18 05:45
- **Notes / blockers:** All five branches pushed, PRs pending. BK-501 first (Daniel depends on it); 501 and 502 need the Opus review. Full suite: 364 passed; 2 tests fail only when .env has BK_SETTLEMENT_MODE=testnet (pass in simulated). Next: video rehearsal on merged main, final take after UI freeze.

Status values: `ACTIVE`, `PAUSED` (claim kept), `IDLE` (no claim), `REVIEW` (waiting on review/merge).

## Protocol
1. **Start:**
   - `git pull`, then read this file.
   - If someone else's claimed area overlaps yours, pick another task or agree on it in team chat first.
2. **Claim:**
   - Fill in your section (status `ACTIVE`, task ID from [[TASK_BOARD]], branch, paths).
   - Commit only this file as `claim: <member> <task-id>` and push to `main` immediately.
   - If the push is rejected, pull, re-check for conflicts, and try again.
3. **Work:**
   - Do the work on your own branch `<member>/<task-id>-<slug>`, never directly on `main`.
   - Update "last update" when you change areas, or at least every few hours.
4. **Stop:**
   - Set status `IDLE` (or `PAUSED`/`REVIEW`) and clear or keep your claim.
   - Push a `release: <member> <task-id>` commit, and open a PR for your branch.
5. **Stale claims:** if a claim has no update for 12 h and the owner can't be reached, the lead may release it and must note that here.

## Ownership rules
- **Kernel / ledger / cost-ledger / migrations** (`backend/src/budget_kernel/{kernel,costledger,db}`, `backend/migrations`): one claimant at a time, and a PR review is required before merging.
- **Canonical memory** (CURRENT_STATE, TASK_BOARD, ADRs, DECISION_REGISTER): change it through your PR. The lead resolves conflicts at merge.
- **This file:** you may push your own section directly to `main` (the only exception to "no direct commits to main").
- Each member's Claude/GPT session follows [[AGENT_HANDOFF]] and AGENTS.md. A session works only inside its member's claimed areas.
