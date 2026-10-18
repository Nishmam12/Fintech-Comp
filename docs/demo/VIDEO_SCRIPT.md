# Demo video script (BK-140) — draft 2, for the redesigned dashboard (BK-501..504)

Target: 4:58 (limit 5:00; trim beat 3 or 4 if it runs long). Screen capture + voice-over. Everything runs in the dashboard, signed in with the one-click demo buttons (seeded by `scripts/demo_seed.py`): **Nabil (owner)**, **Ops bot (manager)**, **Research bot (agent)**. Names, not ids, appear on every screen. **Draft: not final until the lead approves.** Every number shown must come from a real run on the day.

| # | Time | On screen | Voice-over |
|---|---|---|---|
| 1 | 0:00-0:25 | Title card, then the problem: an AI agent with a wallet | "AI agents are starting to spend money. If a model can authorize a payment, one bad prompt drains the wallet. Budget Kernel puts a deterministic gate between the model and the money." |
| 2 | 0:25-1:00 | Architecture diagram: model proposes, kernel decides, adapter settles | "The model only proposes. Plain code checks mandate, scope, limits and balance, and reserves funds. Nothing a model says is ever trusted as authorization." |
| 3 | 1:00-1:50 | Dashboard as **Nabil (owner)**: the 1,000 USD mandate with 100 protected; grant tree Nabil -> Ops bot (500) -> Research bot (300, narrower scope). Sign in as **Ops bot** to show it cannot delegate more than it holds | "The human owner sets the mandate and delegates a narrower grant. Delegation can only shrink, and an agent cannot create its own authority." Show the refused wider-scope delegation. |
| 4 | 1:50-2:30 | Sign in as **Research bot**: ask "pay 50 USD to aws for cloud", reserved. Then an over-limit and a wrong-recipient request, rejected. **Activity** tab shows each as a sentence ("Research bot asked to pay ... Refused: ...") | "A plain-language request becomes a typed proposal. In-scope: reserved. Over the limit or to the wrong recipient: rejected with a reason. Retrying the same request does not double-spend." |
| 5 | 2:30-3:10 | Dashboard: Research bot asks for 70 USD to aws (above its 60 USD approval line); the request waits in the owner's inbox as "needs approval"; owner taps approve; it becomes reserved | "Large spends wait for the owner. The threshold lives in the grant, and the kernel, not the model, holds the request until the human approves." Needs BK-302/321 working by Oct 19; otherwise show it with `demo.py` section 7b. |
| 6 | 3:10-4:00 | Settlement service signs and broadcasts the approved transfer; hash appears; open the explorer page from the `explorer_url` field; show the confirmed USDC transfer | "Only after the kernel approves and reserves, the settlement service sends a real test-USDC transfer on Base Sepolia. The hash is stored with the kernel record and the audit trail." **Must be a real hash from the same run.** |
| 7 | 4:00-4:15 | Velocity limit: Research bot's small requests add up; the next is refused once the 250 USD/hour total is reached (usage bar on the grant) | "Splitting a big spend into small ones does not get around the limit." |
| 8 | 4:15-4:35 | A probing agent: five out-of-scope requests, the grant becomes **suspended** (Activity: "Circuit breaker suspended Research bot's grant..."), even a valid request is refused. The **owner** reinstates it from the dashboard. | "An agent that probes outside its scope is suspended automatically. Only the owner can bring it back, never the agent." |
| 9 | 4:35-4:52 | Dashboard integrity badge green with the anchor link; open the anchor tx on the explorer (0-value self-transfer, data `BKANCHOR1` + digest). Then a scratch-schema copy where one audit row was edited: badge red with `broken_at`. | "The audit trail is hash-chained and its head is anchored on-chain. Edit one row and the check fails at exactly that row." **Real anchor tx hash; tamper shot on a scratch copy only.** |
| 10 | 4:52-4:58 | Closing card: repo, team, "testnet only"; (optional quick cut before it: rate-limit 429 and key rotation) | "Budget Kernel: agents propose, the kernel decides." |

## Recording checklist
- Run `scripts/demo_seed.py` against the live API just before recording (new mandate, new keys in `frontend/.env.local`), then restart `next dev` so the sign-in buttons pick the keys up. Keys are never printed; do not open `.env.local` on camera.
- Fresh run of `scripts/demo.py` with the API in `BK_SETTLEMENT_MODE=testnet`; copy the hash and explorer link from that run.
- Wallet funded (test ETH + test USDC) before recording; mandates about $20 total.
- Hide `.env`, API keys and the admin token from the terminal and screen; never show the settlement private key.
- Say clearly that it is testnet and that model providers were measured, not assumed (disclosed limitations).
- Tamper shot: scratch schema or copy only (lift the append-only trigger as table owner, edit one audit row, reload badge). Never touch production `bk`; discard the scratch data afterwards.
- Record Oct 19 before the 20:00 BST freeze; keep a take of each beat so one failure does not need a full redo.

## Open questions for the lead
- Do beats 5, 7 and 8 use the dashboard (Member 2) or the terminal if the UI is not ready?
- The Attack lab (**Run all attacks**, two columns "Without the kernel" / "With Budget Kernel") has no beat of its own (time); show it as a 5-second overlay in beat 4 or drop it. Which measured numbers from `memory/evaluation/RESULTS.md` go there?
