# Demo video script (BK-140) — draft for lead review

Target: 4:45 (limit 5:00). Screen capture + voice-over. Backbone: `scripts/demo.py`; phone beats use Member 2's dashboard. **Draft: not final until the lead approves.** Every number shown must come from a real run on the day.

| # | Time | On screen | Voice-over |
|---|---|---|---|
| 1 | 0:00-0:25 | Title card, then the problem: an AI agent with a wallet | "AI agents are starting to spend money. If a model can authorize a payment, one bad prompt drains the wallet. Budget Kernel puts a deterministic gate between the model and the money." |
| 2 | 0:25-1:00 | Architecture diagram: model proposes, kernel decides, adapter settles | "The model only proposes. Plain code checks mandate, scope, limits and balance, and reserves funds. Nothing a model says is ever trusted as authorization." |
| 3 | 1:00-1:50 | Terminal / dashboard: owner creates a $1000 mandate with $100 protected; delegates $300 to an agent with a narrower scope | "The human owner sets the mandate and delegates a narrower grant. Delegation can only shrink, and an agent cannot create its own authority." Show the refused wider-scope delegation. |
| 4 | 1:50-2:30 | Agent asks "pay 50 USD to aws for cloud"; reserved. Then over-limit and wrong-recipient requests rejected | "A plain-language request becomes a typed proposal. In-scope: reserved. Over the limit or to the wrong recipient: rejected with a reason. Retrying the same request does not double-spend." |
| 5 | 2:30-2:50 | Dashboard on a phone: above-threshold request waits in the approval inbox; owner taps approve | "Large spends wait for the owner." (only if BK-302/321 are merged and working by Oct 19; otherwise cut) |
| 6 | 2:50-3:40 | Settlement service signs and broadcasts; hash appears; open basescan; show confirmed USDC transfer | "Only after the kernel reserves, the settlement service sends a real test-USDC transfer on Base Sepolia. The transaction hash is stored with the kernel record and the audit trail." **Must be a real hash from the same run.** |
| 7 | 3:40-4:05 | Owner taps kill switch / revoke; the agent's next request is rejected | "Revoking cuts the agent off immediately." |
| 8 | 4:05-4:40 | `demo.py --attacks` output: baseline vs kernel per scenario, then invariants ok | "Against six attack scenarios, a naive agent wallet is drained or double-spent. The kernel holds, and the ledger invariants stay true." Read the measured numbers from `memory/evaluation/RESULTS.md`. |
| 9 | 4:40-4:45 | Closing card: repo, team, "testnet only" | "Budget Kernel: agents propose, the kernel decides." |

## Recording checklist
- Fresh run of `scripts/demo.py` with the API in `BK_SETTLEMENT_MODE=testnet`; copy the hash and explorer link from that run.
- Wallet funded (test ETH + test USDC) before recording; mandates about $20 total.
- Hide `.env`, API keys and the admin token from the terminal and screen; never show the settlement private key.
- Say clearly that it is testnet and that model providers were measured, not assumed (disclosed limitations).
- Record Oct 19 before the 20:00 BST freeze; keep a take of each beat so one failure does not need a full redo.

## Open questions for the lead
- Do beats 5 and 7 use the dashboard (Member 2) or the terminal if the UI is not ready?
- Which measured numbers go in beat 8?
