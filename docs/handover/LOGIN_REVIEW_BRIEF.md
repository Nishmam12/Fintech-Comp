# Review brief: username and password login (for the Opus pass)

Plan: `docs/plans/LOGIN_PLAN.md`. Built 2026-10-20 in one day, so this is the change most worth a hostile read. Commits: 9275593 (backend core), 45a889f (agents), 81985e6 (frontend and setup), a06537f (docs), plus the cache-control follow-up.

## Files
- `backend/migrations/008_login.sql`, `009_agents.sql`
- `backend/src/budget_kernel/api/passwords.py` (hashing, policy), `login.py` (all new routes), `auth.py` (session resolution), `ratelimit.py` (auth bucket, session key), `schemas.py`, `app.py` (wiring, `/me`, rotate-key guard)
- Tests: `backend/tests/integration/test_login.py` (37), `test_agents_setup.py` (7)
- Frontend: `lib/api.ts`, `lib/session.tsx`, `lib/mandate.tsx`, `components/SignIn.tsx`, `SetupView.tsx`, `SettingsView.tsx`, `App.tsx`
- Checks: `npm run check:login` (16 steps), `check:flow` (14), `check:layout`

## Claims to try to break
1. **A session token is exactly as powerful as the person's API key was, and no more.** `current_principal` is the only place a credential becomes a `Principal`; no kernel code changed. Look for any route that reads the `Authorization` header another way (`rotate_key`, `logout`, `/me/password`, the rate limiter's `key_for`, the integrity route's admin-token path).
2. **No account enumeration, no timing oracle** on `POST /auth/login`: one `INVALID_CREDENTIALS` for wrong password, unknown user, locked, disabled, agent without a password; the dummy hash is verified for missing users. Is the response time of a locked or disabled account distinguishable (they skip the UPDATE but still verify)? Is the 401 body identical?
3. **Lockout is correct and not a free denial of service.** Five consecutive failures lock for 15 minutes using the database clock; a failure while locked does not extend the lock; success resets it; the counter and the failure are committed even though the request ends in a 401 (the raise happens after the transaction block). Race: two concurrent logins on one account (the row is locked `FOR UPDATE`).
4. **Revocation is real.** Logout, password change (every other session), disabled person, expiry: all refused on the next request with the right code. A revoked or expired session must never fall through to "unknown key" and be retried as an API key (it is looked up by prefix `bks_` only after the key lookup fails).
5. **Nothing secret is stored, logged or audited.** Passwords hashed with scrypt and a random salt; tokens stored as SHA-256; failed logins not audited; audit rows carry no secret; `Cache-Control: no-store` on every credential-bearing response. Check logs and error bodies.
6. **Humans only get passwords** (CHECK constraint), **agents cannot create agents or log in**, creation is capped and serialised (`FOR UPDATE` on the creator's row), `created_by` grants no authority.
7. **Sign-up is off by default** and still rate-limited when on; `/admin/accounts` needs the admin token.
8. **Frontend:** the token lives in React memory only; sign-out ends the server session; a late 401 from an old credential cannot sign out a newer session (`failedKey` check in `session.tsx`); no password in any URL, log or title; the one-time agent key is cleared on "I have stored it"; `NEXT_PUBLIC_DEMO_KEYS` still absent from a production build (re-scan).

## Known and accepted (do not re-raise unless you disagree with the reasoning)
No password reset by email, no MFA, no SSO, no identity verification; no device or IP binding for sessions; the auth rate limit is per process and per client IP; the 15-minute lock can be used against a known username; sign-up writes one global-chain audit row per account (serialises on the global chain head; sign-up is off by default); LOGIN and LOGOUT are not audited on purpose (the `sessions` table records them).

## How to run it
API with `BK_SCHEMA=bk_dev BK_ALLOW_SIGNUP=1 BK_SETTLEMENT_MODE=simulated`; `uv run pytest tests/integration/test_login.py tests/integration/test_agents_setup.py`; then `npm run check:login` from `frontend/`.
