# Live click-through, 2026-10-16 (BK-413 / step 5)

**Setup.** Real backend (`uvicorn`, branch stack BK-305 + BK-411 + BK-412 + BK-413) on a scratch schema `bk_daniel_demo` (migrations 001 to 006), real built dashboard (`next start`), headless Chromium at **390 x 844**, real API keys created through `/admin/principals`. No model was called (canonical request texts take the rules path). Nothing is mocked. Keys were never printed; the rotated key is blurred in the saved image.

**Flow and result** (screenshots in `screenshots/bk413/`):

| # | Step | Result |
|---|---|---|
| 01 | Owner signs in, mandate view with integrity badge | History intact, hash head shown, "Not anchored on-chain yet" |
| 02-03 | Held request (above threshold) in Review, then approved | Held with `ABOVE_THRESHOLD`; approval reserves funds |
| 04 | Agent asks in the Ask tab | Decision card shows the kernel decision |
| 05 | Five refused requests (`RECIPIENT_NOT_ALLOWED`) | 5th decision says `suspended`; grant shows SUSPENDED, reason, time, Reinstate button |
| 06 | Spend attempt on the suspended grant | Stored as rejected `GRANT_SUSPENDED`, shown with a plain-language gloss |
| 07 | Agent's own view | Suspended grant visible, no Ask target |
| 08-10 | Reinstate with confirmation; manual Suspend with confirmation; reinstate | All three work; reinstate resets the strike count |
| 11 | Attack panel | Loads, scenarios listed |
| 12 | Kill switch (revoke) | Unchanged: result card with reclaimed amount |
| 13 | Integrity after all of the above | Still intact (22 records) |
| 14 | 429 under a burst | "Too many requests. Wait N s, then try again." |
| 15 | Settings, rotate key | New key shown once (blurred in the image), copy button, old key then 401, session continues on the new key |
| 16 | Expired key at sign-in | "Your API key has expired..." |
| 17 | Principal disabled while signed in | Dropped to sign-in with "This account has been disabled" |

Also checked: no horizontal scroll at 390 px on the mandate and settings screens; a retry with the same idempotency key replays the stored decision (BK-305).

**Defects found by this run, and their status**
1. `Retry-After` was not readable by the browser (CORS did not expose it), so the 429 message could not say how long to wait. **Fixed** in BK-411 (`expose_headers`), with a test.
2. After an expired key at sign-in the same message was shown twice (sign-in error plus the "session dropped" notice). **Fixed**: the notice is only set when a signed-in session is dropped.
3. Not a defect, but worth knowing: the limiter refills 2 tokens per second at the default limit, so a test has to fire its burst and the next request together to see a 429.

**Not covered yet.** Integrity badge with an on-chain anchor (BK-401 is Afnan's and not merged). Re-run this click-through against `main` once the PRs are merged, and against the production schema after migration 006 is applied there.
