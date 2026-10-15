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
- **Task ID:** BK-110 (security self-assessment) + BK-080 (eval configs B/C when keys arrive)
- **Branch:** main
- **Claimed areas (paths):** backend/src/budget_kernel/{kernel,db,simulation}, backend/migrations, backend/tests, docs/SECURITY_SELF_ASSESSMENT.md, memory/
- **Started / last update (UTC):** 2026-10-15 07:25
- **Notes / blockers:** Supabase DB reachable via DATABASE_URL (psycopg). Project-scoped Supabase MCP not loaded in this session.

### Member 2 (RTX 2070 Super) — daniel
- **Status:** ACTIVE
- **Task ID:** BK-090 (dashboard) then BK-321..326
- **Branch:** daniel/BK-090-dashboard
- **Claimed areas (paths):** frontend/
- **Started / last update (UTC):** 2026-10-15
- **Notes / blockers:** BK-305 (api/, routing/) and docs/submission/ will be claimed when I start them.

### Member 3 (RTX 5060) — Afnan Mojumder
- **Status:** ACTIVE
- **Task ID:** BK-075/303/315/130 (settlement; first real tx waiting on test ETH)
- **Branch:** afnan/BK-303-mandate-settlers (carries BK-075 + BK-303 + BK-315 + BK-130 script)
- **Claimed areas (paths):** backend/src/budget_kernel/settlement/, backend/migrations/003_settlement.sql, backend/tests/integration/test_settlement*.py, evidence/, scripts/evidence*.py, backend/src/budget_kernel/api/app.py (settlement endpoints only), memory/research/SETTLEMENT.md
- **Started / last update (UTC):** 2026-10-15 06:45
- **Notes / blockers:** Wallet has 20 test USDC, 0 ETH: Alchemy/QuickNode/Superchain faucets all need mainnet balance or World ID, Coinbase CDP down. Need 0.001 Base Sepolia ETH (teammate send?). PR pending for lead + Opus review (kernel change BK-303).

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
