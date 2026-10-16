# Phase 3 tasks for Daniel (Member 2): replay, rate limits, key lifecycle, dashboard surfaces, deck

**How to use:** `git pull` on `main`, then open Claude Code **in the repository root** and paste everything below the line as your message.

---

You are working with Daniel (Member 2) on **Budget Kernel**. Your dashboard is merged into `main` (commit `6f91f6d`). Phase 3 adds robustness features. The design is frozen in `memory/decisions/ADR-0009-INTEGRITY-CIRCUIT-BREAKER-API-HARDENING.md` (ACCEPTED). **Read it first, especially Part B (the circuit breaker), Part C (API hardening) and A4 (the integrity response).** Migration `006_robustness_ii.sql` is already on `main`: the `principals` columns you need exist.

The rules in `AGENTS.md`, `ONBOARDING.md`, `frontend/AGENTS.md` and `docs/handover/MEMBER2_PROMPT.md` still apply:
- Never print, log or commit a key or any `.env` value. API keys live in memory or `sessionStorage` only, as before.
- Model text is **untrusted**: render it as plain text, never as HTML.
- Use your own `BK_TEST_SCHEMA`, and never run two pytest sessions at once on it. Run the long suite in the background.
- Claim before you start (edit **only your own section** of `memory/WHO_IS_WORKING.md`, commit and push it). Claim `backend/src/budget_kernel/api/` and `routing/` before you touch them.
- One branch per task, named `daniel/<task-id>-<slug>`, one PR per branch with the test output (or `tsc`, lint and build output) pasted in, and a line in `memory/CHANGELOG.md`.
- Nobody commits to `main` except their own claim line. The lead merges.
- Numbers and screenshots must come from the real running system.
- If you are blocked for more than 30 minutes, write it under *Notes / blockers* and tell the lead.

**Do not edit** `kernel/`, `costledger/`, `db/` or `migrations/`. If you need a change there, ask the lead. Afnan is also editing `api/app.py` for settlement and anchor routes: keep your changes small, rebase often, and keep both sides when you resolve a conflict.

## Task order

### 1. BK-305: replay by idempotency key before interpreting (closes R9)
- In `POST /agent/request`, before any model call, look for an existing transaction for `(grant_id, idempotency_key)`. If one exists, return its stored decision. A retry must make **zero** model calls.
- The holder check still applies first (a non-holder gets 403, and learns nothing about the stored decision).
- If the key exists but the **text differs**, return the same `IDEMPOTENCY_CONFLICT` the kernel returns for a changed request. Never re-interpret.
- Tests in `backend/tests/integration/`: a retry makes zero model calls (count them with the test transport), the replay returns the identical decision, the non-holder case, and a changed text under the same key.
- Update R9 in `docs/SECURITY_SELF_ASSESSMENT.md` from Open to Mitigated in your PR.

### 2. BK-411: rate limiting (`backend/src/budget_kernel/api/ratelimit.py`)
Follow ADR-0009 section C1 exactly.
- An in-process token bucket per key: the principal id when authenticated, the client IP otherwise. **Do not trust `X-Forwarded-For`** unless `BK_TRUST_PROXY=1`, because a client could spoof it to dodge the limit.
- Defaults: 120 requests per minute for everything, and a separate 30 per minute bucket for `POST /agent/request` and `POST /interpret` (these cost real money). `/health` is exempt. Configurable via `BK_RATE_DEFAULT_PER_MIN` and `BK_RATE_MODEL_PER_MIN`.
- When limited: HTTP 429, body `{"detail": {"code": "RATE_LIMITED", "message": "..."}}`, header `Retry-After` in whole seconds.
- Memory must stay bounded: expire idle buckets so an attacker rotating keys or IPs cannot grow the table without limit.
- Tests: a burst gets 429 with `Retry-After`; the bucket recovers after the wait (use an injectable clock, not real sleeps); two keys do not share a bucket; the model-call bucket is separate; `/health` is never limited.
- Write down in the README that the limiter is per process (several replicas multiply the limit).

### 3. BK-412: key lifecycle (`api/auth.py`)
Follow ADR-0009 section C2 exactly. The columns `key_expires_at`, `disabled_at` and `key_rotated_at` exist on `principals`.
- `current_principal` returns 401 `KEY_EXPIRED` when `key_expires_at <= now()`, and 401 `PRINCIPAL_DISABLED` when `disabled_at` is set. An unknown key is still `UNAUTHENTICATED`.
- `POST /me/rotate-key` (authenticated): store the new key's hash in **one `UPDATE`** that also sets `key_rotated_at`, so the old key stops working immediately. Return the raw key once. Audit event `KEY_ROTATED` (no key material in the audit row).
- `POST /admin/principals/{id}/disable` (admin token). Idempotent. Audit event `PRINCIPAL_DISABLED`. It does **not** revoke grants.
- `POST /admin/principals` gains an optional `expires_in_days` (integer 1 to 365).
- Tests: expired key; disabled principal; rotation (old key 401, new key works); rotating twice in a row leaves exactly one valid key; the raw key never appears in the audit rows.

### 4. BK-413: dashboard surfaces
Wire these to the real API. Where the backend endpoint is not merged yet, build against the **frozen response shapes in the ADR** and show a clear "not available" state when the call fails; never invent data.
- **Integrity badge** (`GET /mandates/{id}/integrity`, ADR section A4): green with the chain length, a short head hash, and the last anchor link when `last_anchor` is not null (use the returned `explorer_url`, never build a URL). Red with `broken_at` and `reason` when `ok` is false. Owner only.
- **Suspended grants:** the state response's grant objects gain `suspended_at`, `suspend_reason` and `strikes_in_window`. Show a clear "suspended" state, and for the owner (and ancestor holders) a **Reinstate** button (`POST /grants/{id}/reinstate`) and a **Suspend** button (`POST /grants/{id}/suspend`), each with a confirmation. The kill switch stays exactly as it is.
- **New codes:** show friendly messages for 429 `RATE_LIMITED` (wait `Retry-After` seconds, then retry), 401 `KEY_EXPIRED` / `PRINCIPAL_DISABLED` (return to sign-in), and `GRANT_SUSPENDED` as a transaction reject reason.
- **Rotate key:** a button in settings that calls `POST /me/rotate-key` and shows the new key once, with a copy button.
- Check every new screen at **390 px** width. Deliver click-through screenshots made against the live API.
- The lead lands the backend for the integrity and suspend endpoints in steps 5 and 6 (about Oct 17). You will be told when they are live.

### 5. A live click-through
Once your PRs are merged, run the whole dashboard against the live API with a real key: sign in, a held request, approve, an above-threshold request, the kill switch, the attack panel, and the new surfaces. Record every defect with the screenshot. This is the evidence for the deck.

### 6. BK-120: the deck (Oct 19) and BK-160: the technical document
Start the outline now; it needs real screenshots and the numbers in `memory/evaluation/RESULTS.md` (use the latest run only, and copy the caveats). The deck is **10 minutes or less**. The lead supplies the outline and reviews both documents.

## Timeline
| Day | Target |
|---|---|
| Oct 16 | BK-305, then BK-411 |
| Oct 17 | BK-412, then start BK-413 against the frozen shapes |
| Oct 18 | BK-413 polish, the live click-through, a Playwright smoke test if time allows |
| Oct 19 | Deck draft with real screenshots. Freeze at 20:00 BST |
| Oct 20, before noon | Deck and technical document final |

**Cut order if you are late:** the Playwright smoke test, then PWA polish, then key rotation in the UI (keep expiry and disable).

## How to report
Update your section in `memory/WHO_IS_WORKING.md` when your status changes (`ACTIVE`, `REVIEW`, `BLOCKED`, `DONE`), add a line to `memory/CHANGELOG.md` in each PR, and tell the lead when a branch is ready for review.
