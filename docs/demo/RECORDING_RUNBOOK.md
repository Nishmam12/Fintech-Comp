# Recording runbook: one person, one screen, about 4:45

Replaces the beat table in `VIDEO_SCRIPT.md` for the actual recording. That table has beats the app cannot show (delegation refusal screen, a live testnet transfer, a tamper shot on a scratch database, a velocity bar). This one only uses what the frozen build really does, checked end to end by `npm run check:flow`.

## Before you press record (10 minutes)
1. API running on port 8000 in simulated mode, dashboard on port 3000. If not: start the API (`$env:BK_SETTLEMENT_MODE="simulated"; uv run --project backend uvicorn budget_kernel.api.app:app --app-dir backend/src --port 8000`), then run `powershell -ExecutionPolicy Bypass -File scripts\reset-demo.ps1`.
2. **For every retake** run `scripts\reset-demo.ps1` again. It makes a fresh mandate (a suspended agent or a spent budget from the last take would spoil the next one) and restarts the dashboard.
3. Open Chrome at 100% zoom, window about 1280 x 800 (or full screen at 1366 x 768). Close other tabs, hide the bookmarks bar, turn off notifications.
4. Open **three browser tabs** on `http://localhost:3000`. Tabs do not share sign-ins (the key lives in each tab's memory), so you can switch roles without signing out:
   - Tab A: sign in as **Nabil (owner)**.
   - Tab B: sign in as **Research bot (agent)**, open **Ask**.
   - Tab C: open `https://sepolia-explorer.base.org/tx/0x2c5665e7908ebb775e03185e5aef9fd9e566b79c21652d7f3c789db1add49090` (a kernel-approved settlement) and, in a fourth tab, `https://sepolia-explorer.base.org/tx/0xcb1ba8f8c64413779274509bb7333e9693123cdc8d5e9229ba927b74f5578e2e` (the history anchor).
5. Wait until Tab A's Mandate screen is full (about 5 s: the database is far away). Every screen takes about 5 s the first time; talk over it or trim it later.
6. Nothing with a key on screen: no terminal, no `.env`, no editor. Windows: Win+G (Game Bar) records the browser window; OBS also works. Do a 10-second test with sound.

## The takes (record each beat as its own clip, then join them; one clip can be redone alone)
| Clip | Target | What you do | What you say |
|---|---|---|---|
| 1 | 0:25 | Sign-in screen (before you sign in). Say once: "People and agents sign in with an API key; these three buttons are demo accounts." | "AI agents are starting to spend money. If a model can authorize a payment, one bad prompt drains the wallet. Budget Kernel puts a deterministic gate between the model and the money: models propose, the kernel decides." |
| 2 | 0:30 | Slide 2 of the deck (the diagram), or hold on the sign-in cheque | "The model only proposes. Plain code checks the mandate, the scope, the limits and the balance inside one database transaction, and reserves the money. Nothing a model says is ever trusted as authorization." |
| 3 | 0:45 | Tab A, **Mandate**. Point at the cheque (1,000.00 USD, 100.00 protected), the allocation bar, then **Who may spend**: Nabil, Ops bot, Research bot | "A human owner funds a mandate and delegates narrower grants. Delegation moves money down, never creates it, and scope can only narrow. 100 USD is protected and can never be spent. The seal says the history is intact: every record is hash-chained." |
| 4 | 0:50 | Tab B, **Ask**. Click the first example (20 USD), **Send to the kernel**: *Approved*. Click the 150 USD example, send: *Refused, over the limit, nothing was reserved* | "A plain-language request becomes a typed proposal, on the left, untrusted. The kernel's verdict is on the right. Twenty dollars is inside the grant: approved and reserved. One hundred fifty is over the limit: refused, with a reason, and nothing is reserved." |
| 5 | 0:40 | Tab B: 80 USD example, send: *Held*. Switch to Tab A, **Review**: the request is waiting. Click **Approve** (toast "Request approved", inbox empties) | "Eighty dollars is above this agent's approval line, so the kernel holds it and reserves nothing. The owner sees it in the inbox. Only the owner can approve, and approving re-runs every check." |
| 6 | 0:50 | Tab B: send the 150 USD request four more times (five refusals in all). The fifth says the grant was suspended. Tab A, **Mandate**: Research bot is *suspended*; click **⋯**, **Reinstate this grant**, **Confirm reinstate** | "An agent that keeps probing its limits is suspended automatically after five refusals. Only the owner can reinstate it, never the agent and never the manager above it." |
| 7 | 0:35 | Tab A, **Attack lab**. Click **Run** on *Concurrent overspend* only and wait for the result (about 30 s; keep talking, or cut the wait). Show the row: *Broken* without the kernel, *Held* with it | "Here the same attack runs against an intentionally unsafe baseline and against the real kernel, on a real database. Eight payments arrive at once for a budget that covers three. The baseline spends 2,400 of 900; the kernel approves exactly three and reserves exactly 900." |
| 8 | 0:40 | Back on Tab A **Mandate**, point at the seal; then the settlement tab (Tab C) and the anchor tab | "Two kernel-approved payments settled on Base Sepolia, a public testnet, and the head of the audit history is anchored there too, so editing history later is detectable. These came from earlier runs; this is a testnet prototype, not audited, and it must not hold real funds." |
| 9 | 0:10 | Sign-in screen or the repo page | "Budget Kernel: agents propose, the kernel decides." |

Total about 5:25 raw; the waits cut about 40 s, so it lands near 4:45. **The limit is 5:00. Check the final length before you upload.**

## Optional: the full Attack lab
**Run all attacks** takes about 3.7 minutes (7 scenarios, about 30 s each, on a database far away). Record it as a separate clip, speed it up 8x in the editor and use it only if you have time to spare. It must not replace clip 7.

## What not to claim
- Do not say a payment on screen settled on chain in this take: the demo runs in simulated settlement. The two explorer pages are earlier real transfers.
- Do not say "secure". Say what was measured: 0 unauthorized approvals in every run; the kernel held in all 7 attack scenarios; synthetic data; testnet only.
- Nothing about the velocity limit as a screen: it is in the grant (250.00 an hour) and shown only as a line in the Mandate footer.

## If something goes wrong
- A screen stays empty more than 15 s: reload the tab (you keep the story, the mandate is on the server) and sign in again with the button.
- Sign-in buttons missing: the dashboard was started before the last reset. Run `scripts\reset-demo.ps1`.
- The agent cannot ask ("you do not hold an active grant"): it is suspended or revoked from a previous take. Reset.
- `Request failed` with a wait time: the rate limiter (30 model requests a minute). Wait 30 s.
