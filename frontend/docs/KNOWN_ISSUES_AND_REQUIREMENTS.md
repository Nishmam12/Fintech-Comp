# Dashboard: known issues, requirements and things to know

Owner: Member 2 (daniel). Written 2026-10-15 while building BK-090 / BK-321..326.
Everything below was observed or read from the code. Nothing here is a guess unless it says "unknown".

## 1. Status

| Item | State | Evidence |
|---|---|---|
| Screen 1 sign-in | built | tested against a live API (owner key and agent key) |
| Screen 2 mandate view + invariant banner | built | seeded mandate showed "Ledger invariants hold", totals matched the seed |
| Screen 3 request box (interpretation beside kernel decision) | built | reserved, held (`ABOVE_THRESHOLD`) and unresolved paths all exercised |
| Screen 4 review queue (BK-322, 3 s polling) | built | approve and deny each changed the held count (3 → 2 → 1) and showed the API result |
| Kill switch (BK-323) | built | two-step confirm; result showed 300.00 reclaimed, 3 reservations released, 0 in flight. Server then showed child `revoked`, root 600.00 → 900.00, invariants ok, next agent request refused `GRANT_REVOKED` |
| Screen 5 budget meter + audit feed | built | screen showed 13 events and 5 budget buckets, identical to the API; a request made while the tab was open appeared as event #14 within one poll |
| Screen 6 attack panel | not started | |
| BK-321 PWA, BK-324 velocity meter, BK-325 explorer links, BK-326 Playwright smoke | not started | |

Checks run on every change: `npx tsc --noEmit`, `npm run lint`, `npm run build`, plus a headless Chromium run at 390 px width (no horizontal scroll).

## 2. Local setup facts (so the next person does not lose time)

- The team `.env` must be named exactly `.env`. A copy saved as `d41d8cd9.env` was **not** covered by `.gitignore` (`.env.*` does not match that name) and could have been committed. It was renamed.
- `BK_TEST_SCHEMA` must be your own (`bk_test_daniel`). The shared value `bk_test` is wiped by every test run.
- The dev API runs on a private schema: `BK_SCHEMA=bk_dev_daniel`, migrated with `python -m budget_kernel.db.migrate`. This keeps the lead's `bk` data untouched.
- Start: `cd backend && BK_SCHEMA=bk_dev_daniel uv run uvicorn budget_kernel.api.app:app --port 8000`, then `cd frontend && npm run dev` (port 3000).
- API base URL comes from `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).
- The three model API keys (`DASHSCOPE_API_KEY`, `DEEPSEEK_API_KEY`, `OPENROUTER_API_KEY`) are **empty** in the current `.env`. That is why any request the rules-only fast path cannot parse ends `unresolved` with `PROVIDER_FAILED`. It fails closed and nothing is reserved. Free-text beyond "pay N USD to X for Y" needs keys from the lead.

## 3. Backend contract gaps (need a decision from the lead; not fixed here because the files are not mine)

1. **No stored proposal in the state read model.** `GET /mandates/{id}/state` selects transactions without the `proposal` column. The approval inbox therefore cannot show the model trail the plan asks for (BK-322). Fix is one column in `api/app.py`. That file is claimed by Member 3 (settlement endpoints) and the lead. *Needs: lead to approve who makes the change.*
2. **No `GET /me` and no "list my mandates".** Sign-in must ask for a mandate ID next to the key and verifies the pair by reading `/mandates/{id}/state`. A phone user has to be given the ID.
3. **CORS** allows only `http://localhost:3000` and the methods GET and POST (`BK_CORS_ORIGINS` to extend). Opening the dashboard on a phone over the LAN, or from a deployed URL, needs that variable set on the API. Required before any phone demo.
4. **Reservations expire.** A reserved transaction is released after a TTL (observed 15 minutes, audit event `ttl_release`) and the funds return to the grant. A demo that idles will lose its reservations. Seed data right before showing it.
5. **Held requests have no expiry in the data we read.** `reserve_expires_at` is null for `proposed` transactions. The kernel caps pending reviews per grant at 20 (ADR-0008); a long demo can hit that cap.

## 4. Known issues (observed)

| # | Issue | Impact | Mitigation / owner |
|---|---|---|---|
| K1 | The hosted database drops idle pooled connections. The first API call after a pause returns a 500 (`server closed the connection unexpectedly`), then recovers. Seen at least five times in one session, so treat it as routine, not rare. | A live demo can open with an error. | The client retries a **GET** once on 5xx (`lib/api.ts`). Writes are not retried. The real fix is a connection health check in `db/`, which is the lead's. Tell the lead before the demo. |
| K2 | Next dev overlay shows a hydration warning ("1 Issue") while Playwright fills inputs. | None. Playwright injects a `caret-color` style. Not our code. | Ignore, or run the smoke test against `next build` + `next start`. |
| K3 | First request after `next dev` starts can exceed 30 s (compilation). | Flaky automated tests. | Use long timeouts in dev, or test against a production build. |
| K4 | `window_used` and the velocity fields exist now (ADR-0008 is merged) but the UI does not show them yet. | BK-324 pending. | Planned. |

| K5 | Owner cannot revoke the root grant (`revoke` uses `allow_self=False`), so the kill switch is offered on non-root grants only. | Killing everything under a mandate means revoking each direct child. | By design in the kernel. |
| K6 | The Ask screen lists active grants only, so after a kill the form shows "No active grant" and cannot send. The kernel's own `GRANT_REVOKED` refusal was verified directly over the API. | None. | By design. |

| K7 | Long unbroken strings (JSON audit details, recipients) widened the page to 643 px on a 390 px phone. `break-words` is not enough inside flex/grid; use `wrap-anywhere` on every untrusted string. Fixed in Activity, Ask and Review. | Horizontal scroll on phones. | New screens must reuse `wrap-anywhere` and be re-checked at 390 px. |
| K8 | `/budget` has five buckets (`global`, `primary`, `escalation`, `retries`, `eval`), all at 0 spent while no model key is set. | The meter looks idle until keys arrive. | Expected. |

## 5. Required later (by task)

- **BK-323 kill switch (built; notes kept for review):** `POST /grants/{id}/revoke` as the owner. Response fields to display exactly as returned: `status`, `reclaimed` (minor units), `released_reservations`, `in_flight_count`, `in_flight_amount`, `stranded_on_root`, `already`. `submitted` transfers cannot be recalled, so `in_flight_*` must be shown prominently and not described as reclaimed. Needs a confirmation step.
- **BK-325 explorer links:** blocked on Member 3 (BK-315). The API does not return a link yet. Do not hard-code a URL pattern; use the field the API returns.
- **BK-150 live evaluation:** blocked on model keys from the lead. Read `eval/README.md` first. Record model IDs, prompt version (`PROMPT_VERSION` in `routing/interpret.py`) and dataset hash in `memory/evaluation/RESULTS.md`.
- **BK-305 replay before interpret:** in `backend/src/budget_kernel/api/` and `routing/` only; needs its own claim in `WHO_IS_WORKING.md` first. `/agent/request` must look up (grant_id, idempotency_key) before the interpreter, and the holder check must still run. Today a retry still pays for a model call. Note the dashboard sends a fresh `crypto.randomUUID()` key per click, so a retry from the UI is a new request by design.
- **PWA (BK-321):** a service worker and install prompt need HTTPS (localhost is exempt). A phone demo therefore needs a tunnel or a deployed origin, which then also needs the CORS change in 3.3.
- **Deliverables:** deck (BK-120) and technical document (BK-160) go in `docs/submission/`. Add a `memory/CHANGELOG.md` line in each PR.
- **Timeline:** build freeze Oct 19 20:00 BST; deadline Oct 20 17:00 BST. Cut order if late: Playwright smoke, PWA polish, config D.

## 6. Security rules the UI must keep (from `docs/SECURITY_SELF_ASSESSMENT.md` section 6)

- Proposal fields, evidence quotes, reasons, audit details and error messages are untrusted. React text nodes only. No `dangerouslySetInnerHTML`, no Markdown-to-HTML. Verified with a `<script>` payload in a request (rendered as text).
- Every number is shown from an API response. `money()` only formats an integer the API returned; no floats, no browser arithmetic on money.
- The API key is kept in React state only. Never `localStorage`, never a cookie. A reload signs the user out by design.
- Do not claim more than the self-assessment says. In particular the simulated settle path can mark a transaction settled with no chain transfer (risk R3) and the settlement service is cross-mandate (R2). The UI must not say funds "moved on-chain" unless an explorer link from the API backs it.
- The dashboard never calls Supabase. No database credential reaches the browser.
- Never print or commit `.env`. Check `git status` for stray env files before every commit.

## 7. Things a reviewer should know

- Branches: `daniel/BK-090-dashboard` (screens 1-2) and `daniel/BK-322-screens-3-4` (screens 3-4). Claimed path is `frontend/` only. Nothing outside it has been edited except my own section of `memory/WHO_IS_WORKING.md`.
- `frontend/AGENTS.md` and `frontend/README.md` were generated by `create-next-app`. The AGENTS note says this Next.js version has breaking changes; consult `node_modules/next/dist/docs/` before using unfamiliar APIs.
- `@playwright/test` is a devDependency for BK-326. The Chromium download lives outside the repo.
