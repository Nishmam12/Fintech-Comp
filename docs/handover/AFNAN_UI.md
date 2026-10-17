# Afnan (Member 3): UI usability sprint. Names in the API, demo seed, Activity and Attack screens, then the video

**How to use:** `git pull` on `main`, then open Claude Code **in the repository root** and paste everything below the line as your message.

---

You are working with Afnan (Member 3) on **Budget Kernel**. The lead found the dashboard hard to use. A visual redesign is already merged on `main` (ink side rail, budget bar, two-column mandate view, new fonts), so **start from `main`**. This sprint fixes usability. Daniel works on the shell and the core screens in parallel, and you own the files listed below, so you will not conflict.

The rules in `AGENTS.md`, `ONBOARDING.md` and `frontend/AGENTS.md` still apply:
- Never print, log or commit a key or any `.env` value.
- Use your own `BK_TEST_SCHEMA`, and run one pytest session at a time.
- **Do not edit `kernel/`, `costledger/`, `db/` or `migrations/`.**
- Model and user text is rendered as plain text only.
- Claim in `memory/WHO_IS_WORKING.md` (your own section only) before each task.
- One branch per task (`afnan/BK-5xx-<slug>`).
- Each PR pastes the test or `tsc`/lint/build output and adds a line to `memory/CHANGELOG.md`.

**Hard deadline: UI freeze Oct 19 14:00 BST.** After that, only bug fixes. Your final video take is 15:00 to 18:00 the same day.

## Task 1: BK-501 names in the API (first, by Oct 18 13:00; Daniel depends on it)
Every screen shows `Grant 1c413ee2` because the API only returns principal UUIDs. Add names **in the API layer only** (`backend/src/budget_kernel/api/app.py`):
1. **`GET /mandates/{id}/state`:** add `holder_name` to each grant. The grants query (around line 367) becomes a `LEFT JOIN principals p ON p.id = g.holder_principal_id` and selects `p.name AS holder_name`. Also add `owner_name` to the mandate object.
2. **`GET /mandates/{id}/audit`:** add `actor_name` with the same join on `actor_principal_id`. It can be null for system events.
3. **`GET /budget`:** `cost_ledger.snapshot()` is costledger code, so **do not edit it**. In the API handler, post-process its result. For each bucket named `principal:<uuid>`, look up the name and add `label` (for example "Research bot"). Other buckets get `label` equal to the bucket name.
4. **Tests** (`backend/tests/`, next to the existing API tests): the names come back, a missing principal gives null rather than an error, and no field is removed.
5. Run the full non-slow suite on your own schema and paste the count in the PR. There must be no diff under `kernel/` or `costledger/`.
6. Add the new optional fields to the TypeScript types in `frontend/lib/api.ts`: `holder_name?: string | null` on `Grant`, `actor_name?: string | null` on `AuditEvent`, and `label?: string` on `Bucket`. **Change only those type lines.** Daniel owns the rest of that file.

## Task 2: BK-502 demo seed script (Oct 18 afternoon)
Viewers must be able to sign in with one click. Write `scripts/demo_seed.py`:
- **Create a fresh demo mandate** through the same API/admin calls `scripts/demo.py` already uses (reuse its helpers; do not talk to the database directly). It contains:
  - **Owner "Nabil"** (human), mandate 1,000 USD, protected reserve 100 USD.
  - **Manager "Ops bot"** (agent) with a delegable grant of 500 USD.
  - **Agent "Research bot"**, holding a grant below Ops bot:
    - 300 USD
    - per-transaction limit 100 USD
    - velocity 250 USD per hour
    - approval needed above 60 USD
    - recipients `aws`, `github`, `openai`; category `cloud`
- **Write `frontend/.env.local`** with one line: `NEXT_PUBLIC_DEMO_KEYS={"Nabil (owner)":"<key>","Ops bot (manager)":"<key>","Research bot (agent)":"<key>"}`. Overwrite the line if it already exists, and keep any other lines in the file.
- **Print only** the labels and the mandate id. **Never print a key.**
- **Verify:**
  - `.env*` is ignored by `frontend/.gitignore` (it is today; confirm with `git check-ignore frontend/.env.local`).
  - Running the script twice gives two independent mandates.
- **Bind the settlement service** if `BK_SETTLEMENT_MODE=testnet`, the way `demo.py` does, so the live payment works from the dashboard.

## Task 3: BK-503 Activity screen (`frontend/components/ActivityView.tsx`, new `frontend/lib/describe.ts`)
Today the screen shows raw JSON and UUIDs.
- **`lib/describe.ts`:** export `describeEvent(ev: AuditEvent): string`. It returns one plain sentence per audit `kind`; list all kinds with `grep -rn "audit(" backend/src/budget_kernel`. Use `actor_name` and amounts through `money()`. Examples:
  - "Research bot asked to pay 10.00 USD to aws. Refused: this category is not allowed."
  - "Nabil approved 70.00 USD to aws."
  - "Circuit breaker suspended Research bot's grant after 5 refused requests."
  - An unknown kind falls back to the kind name.
- **Feed rows:** the sentence, the time, and a `<details>` "Details" element that holds the raw detail as plain text.
- **Budget meter:** use `label` instead of the bucket id. Show **one** loading state (not "Loading…" and "No events yet" together).
- Match the new design: `panel`, `fig` for amounts, colour only for state (`text-ok`, `text-warn`, `text-bad`).
- Screenshots at 1280×800 and 390×844.

## Task 4: BK-504 Attack lab (`frontend/components/SimulationView.tsx`)
- **Before running:** show a one-line description under each attack title. Use a static map in the component, written from the `what_it_proves` text in `backend/src/budget_kernel/simulation/scenarios.py`.
- **Run all:** add a button that runs the attacks one after another, never in parallel (the API refuses a second run with `SIMULATION_RUNNING`), with progress ("3 of 7").
- **Verdict:**
  - Use two clear columns: "Without the kernel" (brick when violated) and "With Budget Kernel" (jade when it held).
  - Lead with the summary sentence.
  - Keep the measured numbers; never compute results in the browser.
- **Cut first if late:** Run all.

## Task 5: BK-140 the video
- **Script:** update `docs/demo/VIDEO_SCRIPT.md` for the new UI. Sign in with the demo buttons, which is faster on camera.
- **Rehearsal:** Oct 18 evening, on merged `main`.
- **Final take:** Oct 19 15:00 to 18:00, only after the lead announces the UI freeze.
- **Content:** ≤ 5 minutes, the real testnet run, and the explorer pages for the payment and the anchor.

## How to report
Update your section in `memory/WHO_IS_WORKING.md` when your status changes. Tell the lead when each PR is ready: BK-501 and BK-502 get an Opus review (API change and demo keys). If you are blocked for more than 30 minutes, write it under *Notes / blockers* and tell the lead.
