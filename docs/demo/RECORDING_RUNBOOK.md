# Recording runbook: one person, one screen, about 4:45

Replaces the beat table in `VIDEO_SCRIPT.md`. This one only uses what the frozen build really does, and the whole story is checked end to end by `npm run check:login` and `npm run check:flow`.

**The story is now a real product from the first click:** a new person creates an account, sets up a mandate, adds an agent and gives it a budget, then the agent asks, the kernel decides, the owner reviews, the breaker trips, and the attack lab shows why.

## Before you press record (10 minutes)
1. Start the API with sign-up on, on its own schema so your main one stays untouched. In PowerShell from the repo root:
   `$env:BK_SCHEMA="bk_dev"; $env:BK_ALLOW_SIGNUP="1"; $env:BK_SETTLEMENT_MODE="simulated"; uv run --project backend python -m budget_kernel.db.migrate; uv run --project backend uvicorn budget_kernel.api.app:app --app-dir backend/src --port 8000`
   (the API and dashboard are already running this way if I left them up; check `http://localhost:8000/health`).
2. Dashboard: `cd frontend; npm run dev` (port 3000). Open `http://localhost:3000`. You should see **Sign in** and **Create account** tabs.
3. Chrome at 100% zoom, window about 1280 x 800. Close other tabs, hide the bookmarks bar, turn off notifications.
4. **Pick a fresh username for each take** (`demo1`, `demo2`, ...): sign-up refuses a name that exists. Password for every take: `a good demo passphrase`. Nothing else needs resetting between takes.
5. Open the explorer pages in extra tabs: the settlement `https://sepolia-explorer.base.org/tx/0x2c5665e7908ebb775e03185e5aef9fd9e566b79c21652d7f3c789db1add49090` and the anchor `https://sepolia-explorer.base.org/tx/0xcb1ba8f8c64413779274509bb7333e9693123cdc8d5e9229ba927b74f5578e2e`.
6. Every screen takes about 5 s to fill the first time (the database is far away). Talk over it or trim it. Nothing sensitive on screen: no terminal, no `.env`. Windows: Win+G (Game Bar) records the browser window; OBS also works. Do a 10-second test with sound.
7. Keys: the agent key you will see on screen is a throwaway demo key on a scratch schema. It is fine to show; say it is a demo key.

## The takes (record each as its own clip, then join; one clip can be redone alone)
| Clip | Target | What you do | What you say |
|---|---|---|---|
| 1 | 0:20 | The sign-in screen | "AI agents are starting to spend money. If a model can authorize a payment, one bad prompt drains the wallet. Budget Kernel puts a deterministic gate between the model and the money: models propose, the kernel decides." |
| 2 | 0:25 | Slide 2 of the deck (the diagram), or hold on the sign-in cheque | "The model only proposes. Plain code checks the mandate, the scope, the limits and the balance inside one database transaction, and reserves the money. Nothing a model says is ever trusted as authorization." |
| 3 | 1:00 | **Create account**: your name, username `demoN`, the passphrase twice. You land on **Setup**. Click **Create the mandate** (defaults: 1,000 USD, 100 reserve). Type `Research bot`, **Add agent**: the key is shown once, click **Copy the key**, then **I have stored it**. **Give this agent a budget** (defaults: 300 USD, 100 per payment, ask above 60). **Open the dashboard** | "A person signs in with a password, which is hashed, locked after five wrong tries, and ends in a session that vanishes on reload. A new account has no money. The owner funds a mandate, 100 dollars of it protected and never spendable, creates an agent, and gives it a narrower budget: the most it can spend on one payment, and the amount above which the owner must approve. The agent's key is shown once." Then point at the cheque and **Who may spend**. |
| 4 | 0:45 | New tab: **Use an API key instead**, paste the key you copied, **Sign in with the key**: **Ask**. Click the 20 USD example, **Send to the kernel**: *Approved*. Click the 150 USD example, send: *Refused* | "The agent signs in with its own key. A plain-language request becomes a typed proposal, on the left, untrusted. The kernel's verdict is on the right. Twenty dollars is inside the grant: approved and reserved. One hundred fifty is over the limit: refused, with a reason, and nothing is reserved." |
| 5 | 0:40 | Agent tab: 80 USD example: *Held*. Owner tab: **Review**, **Approve** (toast, inbox empties) | "Eighty dollars is above this agent's approval line, so the kernel holds it and reserves nothing. Only the owner can approve, and approving re-runs every check." |
| 6 | 0:40 | Agent tab: send the 150 USD request four more times. The fifth says the grant was suspended. Owner tab: **Mandate**, Research bot is *suspended*; **⋯**, **Reinstate this grant**, **Confirm reinstate** | "An agent that keeps probing its limits is suspended automatically after five refusals. Only the owner can reinstate it, never the agent." |
| 7 | 0:35 | Owner tab, **Attack lab**: click **Run** on *Concurrent overspend* only and wait (about 30 s; keep talking, or cut the wait). *Broken* without the kernel, *Held* with it | "The same attack runs against an intentionally unsafe baseline and against the real kernel, on a real database. Eight payments arrive at once for a budget that covers three. The baseline spends 2,400 of 900; the kernel approves exactly three and reserves exactly 900." |
| 8 | 0:40 | Owner tab **Mandate**, point at the seal; then the settlement tab and the anchor tab | "Two kernel-approved payments settled on Base Sepolia, a public testnet, and the head of the audit history is anchored there too, so editing history later is detectable. These came from earlier runs; this is a testnet prototype, not audited, and it must not hold real funds." |
| 9 | 0:10 | The sign-in screen or the repo page | "Budget Kernel: agents propose, the kernel decides." |

Total about 5:15 raw; the waits cut about 40 s, so it lands near 4:35. **The limit is 5:00. Check the final length before you upload.**

## Optional: the full Attack lab
**Run all attacks** takes about 3.7 minutes (7 scenarios, about 30 s each). Record it as a separate clip, speed it up 8x and use it only if you have time to spare. It must not replace clip 7.

## What not to claim
- Do not say a payment on screen settled on chain in this take: the demo runs in simulated settlement. The two explorer pages are earlier real transfers.
- Do not say "secure". Say what was measured: 0 unauthorized approvals in every run; the kernel held in all 7 attack scenarios; synthetic data; testnet only.
- Do not claim identity checks, password reset by email or multi-factor sign-in: none exist (the limits are written down).

## If something goes wrong
- A screen stays empty more than 15 s: reload the tab and sign in again (the mandate is on the server).
- **Create account** is not offered: the API was started without `BK_ALLOW_SIGNUP=1`.
- "That username is taken": use the next `demoN`.
- "Wrong username or password" five times locks the account for 15 minutes: use a new username.
- The agent cannot ask ("you do not hold an active grant"): its grant is suspended or revoked; do clip 6's reinstate, or start a new take with a new username.
- `Too many requests`: wait 30 s (30 model requests a minute; 10 sign-in attempts a minute).
- Backup if sign-up misbehaves live: the demo owner `nabil` / `kernel-demo-2026` (seeded by `scripts\demo_seed.py` or `scripts\reset-demo.ps1`) opens a mandate that already has an agent; its one-tap buttons are on the sign-in screen.
