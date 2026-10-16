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
- **Status:** ACTIVE
- **Task ID:** Phase 3: BK-305 replay, BK-411 rate limit, BK-412 key lifecycle, BK-413 dashboard (ADR-0009)
- **Branch:** daniel/BK-305-replay (one branch per task)
- **Claimed areas (paths):** frontend/, backend/src/budget_kernel/api/ (ratelimit.py, auth.py, agent/request route; small edits to app.py), backend/src/budget_kernel/routing/, backend/tests/integration/test_replay*.py, test_ratelimit*.py, test_key_lifecycle*.py, docs/submission/
- **Started / last update (UTC):** 2026-10-16
- **Notes / blockers:** PRs #1-#6 (BK-090..327) still stacked. app.py is shared with Afnan: small changes, rebase often.

### Member 3 (RTX 5060) — Afnan Mojumder
- **Status:** ACTIVE
- **Task ID:** Phase 3: BK-401 anchor (007), BK-402 unbind, BK-403 worker, BK-304 per-agent budget (ADR-0009)
- **Branch:** afnan/BK-401-anchor (one branch per task)
- **Claimed areas (paths):** backend/src/budget_kernel/settlement/, backend/migrations/007_anchors.sql, backend/tests/integration/test_anchor*.py, evidence/, scripts/evidence*.py, backend/src/budget_kernel/api/app.py (settlement/anchor/unbind endpoints and the interpret call site only), backend/src/budget_kernel/kernel/ops.py (unbind_settler only), backend/src/budget_kernel/costledger (BK-304 only), backend/src/budget_kernel/worker.py, memory/research/SETTLEMENT.md
- **Started / last update (UTC):** 2026-10-16 09:30
- **Notes / blockers:** settlement branch merged (94feaad). Starting BK-401.

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
