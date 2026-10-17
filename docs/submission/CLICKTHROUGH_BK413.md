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

---

# Re-run on merged `main`, 2026-10-17 (branch `daniel/BK-413-final-check`)

**Setup.** `main` at `e5c69ed` (all Phase 3 branches merged), own local API (`uvicorn`) on my own scratch schema `bk_daniel_final` (migrations 001 to 007), built dashboard (`next start`), headless Chromium at **390 x 844**, real keys from `/admin/principals`, driven by Playwright. Nothing is mocked. No key was printed; the rotated key is blurred in `15`. Three principals took part: the **owner**, a **manager** (holds a delegable grant, so is an ancestor holder) and an **agent** (holds the grant below the manager's). `tsc`, lint and build are clean (see the PR).

| # | Step | Result |
|---|---|---|
| 01-04 | Owner signs in (integrity badge green), agent asks 70.00 USD (held), owner approves | As before. Badge: "History intact" with a record count and head. |
| 05, 05a | Five refused requests (`PER_TX_LIMIT_EXCEEDED`), fifth says "this refusal suspended the grant" | Grant shows SUSPENDED by the circuit breaker. |
| 07 (replaced, updated by the follow-up) | **Agent's own view** of its suspended grant | **No Reinstate button** (0 counted). After the follow-up it also shows "Suspended. Only the mandate owner can reinstate this grant." |
| 18 (new) | **Ancestor holder (manager)** looks at the suspended grant | **No Reinstate button.** Text: "Suspended. Only the mandate owner can reinstate this grant." |
| 08, 09 (replaced) | **Owner** reinstates, with confirmation | Works: grant active again, strike count reset. |
| 19 (new, updated by the follow-up) | Manager opens Review with a held request in its subtree | No Approve or Deny buttons; text "Waiting for the mandate owner. Only the owner can approve or deny." Before the follow-up the buttons showed and a click returned 403 `NOT_OWNER`, displayed as "Only the mandate owner can do this." |
| 20 (new) | Two tabs on one key click "Confirm rotate" at the same moment | The loser shows "This key was already rotated. Sign in with the new key." (server 409 `KEY_ALREADY_ROTATED`). A real race, reproduced on the first attempt, not an intercepted response. |
| 13 | Integrity after everything | Still intact (21 records), "Not anchored on-chain yet" |
| 14, 15, 16, 17 | 429, key rotation, expired key, disabled principal | Unchanged and working: "Wait 1 s", new key shown once and old key then 401, expired message shown once, dropped to sign-in with "disabled" |

No horizontal scroll at 390 px on the owner, agent and manager mandate views or on settings.

**Findings (none blocks submission)**
1. **Spec vs UI for the agent.** The handover says the explanation text must appear when the agent looks at a suspended grant. It does not: `SuspendControl` renders nothing when the viewer cannot manage the grant, and an agent cannot manage its own grant. Only ancestor holders (screenshot 18) see the text. The agent still sees the "Suspended ... It cannot spend until reinstated" banner but not who can reinstate. I did not change it (it is the lead's component). One-line fix if wanted: show the explanation text to any non-owner viewer of a suspended grant.
2. **Review tab shows Approve/Deny to a non-owner.** The manager sees held requests in its subtree with working-looking buttons; the server refuses with `NOT_OWNER` (screenshot 19). Safe, but the buttons could be hidden for non-owners. Not changed.
3. **Not covered: the on-chain anchor link.** The real anchor (tx `0xcb1ba8f8...78e2e`) lives in the production `bk` schema, and my local schema has no anchor, so the badge shows "Not anchored on-chain yet". Re-check against the shared API once the lead gives its URL.
4. **Gotcha for the next person.** The rules path only accepts recipients and categories that the grant's own scope lists, so "pay 10 USD to github for cloud" on a grant that lists only `aws` goes to the model, not the kernel. A model failure (`PROVIDER_FAILED`) records nothing, so no strike. Use a limit breach ("pay 150 USD to aws for cloud" against a 100.00 limit) to trip the breaker through the Ask screen.

**Follow-up (branch `daniel/BK-413-ui-followups`, stacked on this one).** Findings 1 and 2 above are fixed, and a third found while checking them:
1. `SuspendControl`: any non-owner viewer of a suspended grant (the holder itself, not only an ancestor) now sees the "only the mandate owner can reinstate" text. Verified live: agent sees 1 explanation and 0 Reinstate buttons.
2. `ReviewView`: Approve and Deny are shown to the mandate owner only; others see "Waiting for the mandate owner." Verified live: 0 Approve buttons for the manager. `NOT_OWNER` text stays in `describeError` for the case where the UI is stale.
3. New: the agent's view showed **Revoke this grant** on every grant, including grants above its own. The server refuses (revoke needs the owner or a strict ancestor holder), so it was safe but misleading. `MandateView` now shows the kill switch only where `canManage` is true, the server's own rule; owners and ancestor holders see no change.
After the follow-up the screenshot-19 NOT_OWNER click is no longer reachable from the UI, which is why 19 changed. `tsc`, lint and build clean; the same live run shows no horizontal scroll at 390 px and the other stages unchanged.
