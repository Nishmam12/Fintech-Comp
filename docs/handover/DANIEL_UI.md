# Daniel (Member 2): UI usability sprint. Demo sign-in, role-aware tabs, core screens, then the deck

**How to use:** `git pull` on `main`, then open Claude Code **in the repository root** and paste everything below the line as your message.

---

You are working with Daniel (Member 2) on **Budget Kernel**. The lead found the dashboard hard to use. A visual redesign is already merged on `main`, so **start from `main`** and keep its system:
- **Tokens** in `app/globals.css`: `ok` jade, `warn` amber, `bad` brick, `accent` cobalt, `ink` rail.
- **Classes:** `panel`, `fig` (Bricolage Grotesque for headings and amounts), `btn-primary`, `btn-ghost`.
- **Colour** marks state only.
- **Avoid:** ALL-CAPS labels and decorative shadows.

This sprint fixes usability. Afnan works in parallel on the API names (BK-501), the demo seed (BK-502), the Activity screen and the Attack lab. **Do not edit `ActivityView.tsx`, `SimulationView.tsx` or `lib/describe.ts`.** Afnan only adds three optional type fields to `lib/api.ts`; the rest of that file is yours.

The rules in `AGENTS.md`, `ONBOARDING.md` and `frontend/AGENTS.md` still apply:
- **Keys:** never print or commit a key.
- **Plain text:** model text is untrusted and rendered as plain text only.
- **Server rules:** what the UI hides must match the server's rules. The server stays the enforcer.
- **Claim and branch:** claim in `memory/WHO_IS_WORKING.md` (your own section) before each task, use one branch per task (`daniel/BK-5xx-<slug>`), and paste `tsc`, lint and build in each PR with a line in `memory/CHANGELOG.md`.
- **Off limits:** do not edit `kernel/`, `costledger/`, `db/` or `migrations/`.

**Hard deadline: UI freeze Oct 19 14:00 BST.** After that, only bug fixes, and you re-shoot the deck screenshots from the frozen UI.

## Task 1: BK-514 plain-language reasons (`frontend/lib/api.ts`)
- **The problem:** transactions show `CATEGORY_NOT_ALLOWED`, and the current glosses repeat the code.
- **Coverage:** rewrite `REASON_TEXT` to cover **every** refusal code the kernel can emit. Find them with `grep -rhoE "code=\"[A-Z_]+\"|\"[A-Z_]{6,}\"" backend/src/budget_kernel/kernel backend/src/budget_kernel/api | sort -u`, and keep only the refusal and error codes.
- **Wording:** plain sentences, for example `CATEGORY_NOT_ALLOWED` → "This grant does not allow that category." and `GRANT_SUSPENDED` → "This grant is suspended."
- **Code shown:** in a `title` tooltip only.
- **Check:** add a small check (a script or test) that lists any kernel code missing from the map.

## Task 2: BK-512 role-aware navigation (`components/App.tsx`)
- **Tabs by role:**
  - **Owner:** Mandate, Review (with a count badge of held requests), Activity, Attack, Settings.
  - **Agent or manager** (not the owner): Mandate, Ask, Activity, Settings.
- **Server rules followed:** approve and deny are owner-only, and simulations are human-only.
- **The rail:** replace "Signed in as human" with the name and role from `/me` (for example "Nabil, owner").
- **Bottom bar:** phones get ≤ 5 items for every role.

## Task 3: BK-511 demo sign-in buttons (`components/SignIn.tsx`, `lib/session.tsx`)
`scripts/demo_seed.py` (Afnan) writes `frontend/.env.local` with `NEXT_PUBLIC_DEMO_KEYS={"Nabil (owner)":"…","Ops bot (manager)":"…","Research bot (agent)":"…"}`. Until it lands, make your own `.env.local` with keys from your schema; it is gitignored.
- **With the env set:**
  - Sign-in shows one button per label ("Continue as Nabil (owner)").
  - The buttons go through the **same** `/me` and `/mandates` path as the paste form.
  - The paste field stays below, under "Or paste an API key".
- **With the env unset:** no buttons. Check that `next build` without the env contains no demo strings: `grep -r "Continue as" .next` should give no matches.
- **Keys** must never appear in DOM text, `console` output or screenshots.

## Task 4: BK-513 mandate screen (`MandateView.tsx`, `SuspendControl.tsx`, `RevokeControl.tsx`)
- **Grant card titles:** use the holder's name (`holder_name` from BK-501, falling back to the short id until it lands). Mark the root as "Owner's root grant". The short id moves to small muted text.
- **Manage section:** put **Suspend** and **Revoke** inside a quiet "Manage" section, collapsed by default (`<details>` or a toggle button). Keep both confirm steps and all server calls exactly as they are, and keep the visibility rules (owner-only reinstate, `canManage`).
- **Status colours:** `proposed` and `reserved` amber (pending), `settled` jade, `rejected` brick. Use the same mapping in the transactions list and on the Ask decision.
- **Transactions:** each row shows the time and the grant's holder name.
- **Last updated:** show the time of the last refresh next to Refresh.

## Task 5: BK-515 Ask screen (`components/AskView.tsx`)
- **Decision first:**
  - Show the kernel decision big at the top, in plain words: "Approved and reserved", "Held for the owner's approval", or "Refused: <plain reason>".
  - Put `aria-live="polite"` on it.
- **Example chips:** add 3–4 one-tap example requests that fill the text box:
  - "pay 20 USD to aws for cloud" (allowed)
  - "pay 80 USD to aws for cloud" (held)
  - "pay 150 USD to aws for cloud" (over the limit)
  - "pay 10 USD to evil for cloud" (wrong recipient)
  - Check each one gives that outcome on the seeded mandate.
- **Grant picker:** show the holder name and available amount.
- **Model trail:** the interpretation and route trail move into a collapsed "How the model read this request" section, still labelled untrusted.

## Task 6: BK-516 Review, Settings, Integrity and toasts
- **Review (`ReviewView.tsx`):** each card shows the holder name, the plain reason it was held, the amount large, and Approve and Deny (owner only, as now).
- **Settings (`SettingsView.tsx`):** your name, role, the mandate (total and short id) and the key expiry, above Rotate key.
- **Integrity (`IntegrityBadge.tsx`):**
  - A skeleton while loading (the check takes about 1.7 s).
  - One plain line: "Every record is linked to the one before it, so editing any record breaks the chain."
  - The anchor as a clear "View anchor on Base Sepolia" link button (only the API's `https://` URL, as now).
- **Toasts (`components/Toast.tsx`, new):**
  - A small shared toast with `role="status"`, auto-dismissed after 4 s.
  - Use it for approve, deny, suspend, reinstate, revoke and rotate key, with the same verb as the button ("Grant suspended").
- **Cut order if late:** toasts first.

## Task 7: BK-120 deck and BK-160 technical document
- **Trim the deck** to ≤ 10 minutes: shrink slide 9 to about 30 s and merge slide 10 into 8.
- **Screenshots:** after the 14:00 freeze on Oct 19, re-shoot every one at 1280×800 (deck) and 390×844 (one phone shot), using the demo buttons. Blur nothing except keys, which should not be visible anyway.
- **Technical document:** gets the same screenshots.
- **Final numbers:** the lead writes that section after the 20:00 freeze.

## Order
**Oct 18:**
1. Task 1 and Task 2 in the morning.
2. Task 4 and Task 3 in the afternoon.
3. Task 5 and Task 6 in the evening.

**Oct 19:**
- Fixes from the lead's click-through by 12:00.
- 14:00 freeze.
- Task 7.

## How to report
Update your section in `memory/WHO_IS_WORKING.md` when your status changes. Tell the lead when each PR is ready; BK-511 gets an Opus review because of the demo keys. If you are blocked for more than 30 minutes, write it under *Notes / blockers* and tell the lead.
