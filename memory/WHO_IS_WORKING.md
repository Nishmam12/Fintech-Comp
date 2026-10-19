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
- **Status:** WORKING
- **Task ID:** UI revision 3: foundation, Sign-in, Mandate, Ask pushed (a199f5b, 01d4e6a). Teammates build the other four screens from `docs/handover/UI_R3.md`. Freeze 24:00 BST Oct 19.
- **Branch:** main
- **Claimed areas (paths):** frontend/app/*, frontend/components/App.tsx, SignIn, MandateView, AskView, IntegrityBadge, components/ui/*
- **Started / last update (UTC):** 2026-10-19 21:10
- **Notes / blockers:** Production `bk` has migrations 003, 006 and 007. Open items are in `memory/NEXT_ACTIONS.md`.

### Member 2 (RTX 2070 Super) — daniel
- **Status:** REVIEW
- **Task ID:** UI R3 (docs/handover/UI_R3.md): Review (8+4), Settings (6+6), Toast restyle, Suspend/Revoke panel styling
- **Branch:** daniel/BK-R3-review-settings
- **Claimed areas (paths):** frontend/components/{ReviewView,SettingsView,Toast,SuspendControl,RevokeControl}.tsx
- **Started / last update (UTC):** 2026-10-20
- **Notes / blockers:** R3 Review/Settings PR open; earlier PRs #13-#18 awaiting review. BK-120 deck and BK-160 technical document still pending.

### Member 3 (RTX 5060) — Afnan Mojumder
- **Status:** ACTIVE
- **Task ID:** UI R3 (docs/handover/UI_R3.md): Activity (8+4) and Attack lab (ledger) screens
- **Branch:** afnan/BK-R3-activity-attack
- **Claimed areas (paths):** frontend/components/{ActivityView,SimulationView}.tsx, frontend/lib/describe.ts
- **Started / last update (UTC):** 2026-10-19 17:40
- **Notes / blockers:** Earlier BK-501..504 work is merged.

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
