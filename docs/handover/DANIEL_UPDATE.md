# Update for Daniel (Member 2): answers to your known-issues report

**How to use:** `git pull` on `main`, then read this. If you use Claude Code, paste it in with the instruction "read this and act on it".

---

The lead read `frontend/docs/KNOWN_ISSUES_AND_REQUIREMENTS.md` on your branch. It was thorough, and most of it is now answered. The dashboard branches (screens 1–5 and the kill switch) look good and follow the security rules. No key material was found in your diff.

## What changed on `main` (commit `dee775c`)
| Your item | Answer |
|---|---|
| 3.1 No proposal in the state read model | **Fixed.** `GET /mandates/{id}/state` now returns `proposal` for each transaction. It is **untrusted model output**: render it as plain text only. Your approval inbox can show the model trail. |
| 3.2 No `GET /me`, no mandate list | **Added.** `GET /me` returns `{principal_id, name, kind}`. `GET /mandates` returns the mandates the caller owns or holds a grant in, each with a `role` of `owner` or `holder`. Sign-in can now be a key alone: call `/me`, then `/mandates`, and let the user pick one. |
| 3.3 CORS | Not a code change. Set `BK_CORS_ORIGINS` on the API to include the dashboard's origin (comma-separated). Do this before any phone demo. |
| 3.4 Reservations expire after 15 min | Expected. Seed data right before showing the demo. |
| 3.5 Held requests and the cap | Held requests are auto-rejected after 24 h and at most 20 can wait per grant (`TOO_MANY_PENDING_REVIEWS`). The `proposed` rows simply have no `reserve_expires_at`. Show the pending count and handle that refusal code. |
| K1 first request after a pause returns a 500 | **Fixed in the backend.** The connection pool now tests each connection before use. Keep your GET retry; it is harmless. |
| Env file name `d41d8cd9.env` not ignored | **Fixed.** `.gitignore` now also ignores `*.env`. |

## Other things to know
- **`.env.example` was deleted from `main`** by a commit from your account (`ff836a4`, "Delete .env.example"). It is restored now. If that was deliberate, tell the lead. If it was a slip through the GitHub web page, nothing more is needed. The setup guide depends on that file.
- **Explorer links (BK-325):** the API returns an `explorer_url` field on each transaction in the state (null until a real transfer exists). Use that field and never build a URL yourself. Afnan's real transaction is the first one to show it.
- **Velocity and threshold (BK-324):** each grant's scope can now carry `window_limit`, `window_seconds` and `review_above`. The state response includes `window_used` for windowed grants. Display those values as returned.

## Your next tasks, in order
1. Merge-ready state: open a PR for each branch (`daniel/BK-090-dashboard`, `daniel/BK-322-screens-3-4`), with the `tsc`, lint and build results pasted in.
2. Sign-in with a key alone (`/me` + `/mandates`); the proposal in the approval inbox.
3. Screen 6: the attack panel (`GET /simulation/scenarios`, `POST /simulation/run`; human key only; handle 409 `SIMULATION_RUNNING`).
4. BK-324 velocity meter, BK-325 explorer links, BK-321 PWA.
5. BK-305, the replay-before-interpret fix (claim it first). Then BK-150, the live evaluation, when the lead shares the keys.
6. The deck (BK-120) and the technical document draft (BK-160). Start the outline by Oct 17, because both need real screenshots and numbers.

Build freeze: Oct 19 at 20:00 BST. Cut order if late: Playwright smoke test, PWA polish, config D.
