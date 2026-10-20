# Real login and first-run setup (decided 2026-10-20, about 11 h before the deadline)

Status (2026-10-20): **built and tested; independent review pending.** Backend: migrations 008 and 009, `api/login.py`, `api/passwords.py`; 36 login tests and 7 setup tests. Frontend: sign-in, setup, change password. Differences from this plan as written: LOGIN and LOGOUT are not audited (a global-chain write per login would serialise every login on the global chain head; the `sessions` table is the record), and `POST /admin/accounts` was added for operator-created accounts. Authentication is the layer the whole security story rests on, so the result is reviewed again before it is called final.

## What exists today
- Every person and agent is a `principals` row with an API key (256-bit, stored as SHA-256, optional expiry, rotation, admin disable). `current_principal` (api/auth.py) turns `Authorization: Bearer <key>` into a `Principal`; every kernel permission check works on that `Principal`.
- Principals are created only by an admin (`POST /admin/principals`, admin token). There is no password, no sign-up, no session.
- The dashboard holds one string, `session.key`, in React state and sends it as the bearer on every call.

## Design: sessions that resolve to the same Principal
**Principle: change who can obtain a credential, not what a credential can do.** A login produces a session token that `current_principal` resolves to the same `Principal` as an API key. No kernel, ledger, grant or permission code changes. The frontend already sends one bearer string, so a session token drops in unchanged.

### Data (migration 008, forward-only, lead only)
- `principals`: add `username citext/lower text UNIQUE NULL`, `password_hash text NULL`, `password_changed_at timestamptz`, `failed_logins int NOT NULL DEFAULT 0`, `locked_until timestamptz`. `api_key_hash` is already nullable, so a password-only human has no API key.
- New `sessions(token_hash text PRIMARY KEY, principal_id uuid NOT NULL REFERENCES principals(id), created_at, expires_at, revoked_at)`, RLS enabled like every table. Index on `principal_id`.

### Passwords
- Hash with **scrypt** from the standard library (`hashlib.scrypt`, n=2^15, r=8, p=1, 16-byte random salt, 32-byte output), stored as `scrypt$n$r$p$salt$hash` so parameters can change later. No new dependency.
- Policy: 8 to 128 characters (the upper bound stops a hashing-cost attack). Loosened on 2026-10-20 at the owner's request: short worst-password list and a not-contain-the-username rule kept, no composition rules. Usernames may be email addresses (migration 010).
- Verify with `hmac.compare_digest`. For an unknown username, verify against a fixed dummy hash so the response time does not reveal which usernames exist. One generic error for every failure: `INVALID_CREDENTIALS` (401).

### Endpoints
| Endpoint | Rule |
|---|---|
| `POST /auth/signup` | Only when `BK_ALLOW_SIGNUP=1` (default off in production, on in the demo). Creates a **human** principal with username and password; returns a session. Rate-limited per IP. Names and usernames are plain text. |
| `POST /auth/login` | username + password, returns `{session_token, expires_at, principal}` once. Throttled per IP and per username; after 5 consecutive failures the account is locked for 15 minutes (`locked_until`), and a lock returns the same `INVALID_CREDENTIALS` so it cannot be used to probe. Successful login resets the counter. Disabled principals cannot log in. |
| `POST /auth/logout` | Revokes the presented session. Idempotent. |
| `POST /me/password` | Needs the current password; sets a new one, **revokes every other session** of that principal. |
| `POST /agents` (human only, setup flow) | Creates an **agent** principal owned by the caller's setup (name only), returns its API key once. Capped at 10 per human. Agents never get passwords or sessions. |
Existing: `POST /mandates` (humans only, already enforced) and `POST /grants` (delegation) are reused for setup.

### Session handling
- Token: `bks_` + 32 random bytes, stored only as SHA-256. Absolute lifetime 12 hours (`BK_SESSION_HOURS`), no sliding renewal. Revoked on logout, on password change, and when the principal is disabled (checked on every request, same as keys).
- `current_principal`: try the API-key lookup; if no row, look up the session (`revoked_at IS NULL AND expires_at > clock_timestamp()`) joined to the principal; apply the same disabled and expired checks and error codes. The rate limiter's `key_for` resolves sessions the same way so limits stay per principal.
- `/me/rotate-key` stays API-key-only (a session has no key to rotate). The dashboard hides key rotation for session users and shows "Change password".
- Audit: `LOGIN`, `LOGOUT`, `PASSWORD_CHANGED`, `ACCOUNT_CREATED`, `AGENT_CREATED` as audit rows. **Failed logins are counted on the account but not written to the hash-chained audit** (a flood of failures must not flood the audit chain; see R14).
- Nothing about passwords, hashes or tokens appears in logs, audit detail or responses beyond the one-time token.

### Dashboard
- Sign-in screen: two tabs, **Sign in** (username, password) and **Create account** (name, username, password, repeat; only if the server allows it). "Use an API key instead" is a small disclosure for agents and admins. The demo one-tap buttons stay, development builds only.
- Setup (when a signed-in human has no mandate): step 1 mandate (amount, protected reserve, expiry), step 2 add an agent (name; shows its key once with a copy button and the warning), step 3 delegate a grant to it (amount, per-payment limit, approval line, expiry). Then the normal Mandate screen. Mandate screen gets a "Delegate to an agent" action for later.
- Settings: password users see Change password and Sign out; key users see key rotation as today.

## Build order (each step independently shippable; cut at the first one that slips)
1. **Backend auth core** (tests first): migration 008, hashing, `/auth/login`, `/auth/logout`, session resolution in `current_principal` and `key_for`, lockout and throttle, tests. *Target 2.5 h.*
2. **Sign-up and password change** (`/auth/signup`, `/me/password`), tests. *1 h.*
3. **Dashboard sign-in screen** (tabs, errors, API-key disclosure), session in `lib/session.tsx`, Settings password change, `check:layout` and `check:flow` updated to the new sign-in. *2 h.*
4. **Setup flow**: `POST /agents`, the three-step setup screen, "Delegate to an agent". *2.5 h.*
5. **Opus review of the whole change**, self-assessment update (new controls, new risks), docs, retake of screenshots. *1.5 h.*
Hard stop for new features: **15:00 UTC-equivalent buffer is kept: everything must be merged and green by 06:00 UTC (12:00 Dhaka) so the video is recorded on the final build and the pack is assembled by 10:00 UTC.** If step 4 is not done by then it is cut and the demo mandate stays seeded by `demo_seed.py` (login still real).

## Tests required before merge (backend, real database)
- Password hash round trip; wrong password, unknown user and locked user return the same code and no timing-oracle shortcut (dummy verify path exercised).
- Lockout after 5 failures, expiry of the lock, reset on success; throttle returns 429.
- Session: valid, expired, revoked, principal disabled, token for another principal; a session token never works as an admin token; an API key still works; a revoked session fails with 401.
- Logout revokes; password change revokes other sessions and keeps the current one.
- Signup off by default; on: creates a human, duplicate username (case-insensitive) is refused with a generic-enough code; agents cannot sign up or log in.
- `POST /agents`: human only, cap, key shown once, agent cannot call it.
- No password, hash or token in any log line, audit row or error body (extend the boundary secret scan).
- Existing suite stays green (366), including the rate-limit and key-lifecycle tests.

## Risks this adds (to the self-assessment)
Credential stuffing and online guessing (throttle, lockout, scrypt); lockout used as a denial of service against a known username (15-minute window, same response, owner can still use an API key); session theft from the browser (token kept in memory only, 12-hour life, revocable); sign-up abuse (off by default, rate-limited, humans only, agents capped); weak passwords (length policy and common-password list, not a strength guarantee). Not added: password reset by email (needs an email service; an admin resets by disabling and re-creating), multi-factor sign-in, single sign-on. These stay in "what we do not claim".
