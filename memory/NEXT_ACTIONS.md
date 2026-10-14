# Next Actions

1. **Planner review (Opus, fresh context)** of `backend/src/budget_kernel/kernel/` against ADR-0004/0005 before more code builds on it.
2. **Hypothesis state-machine test** over random delegate/authorize/settle/release/revoke sequences with I1–I3 after each step.
3. **FastAPI layer** (`api/`): principals + API-key auth (hashed), endpoints from the master plan section 7, error mapping from `KernelError.http_status/code`.
4. **ADR-0006 cost ledger** (`costledger/`) with concurrent-reservation cap test, then proposal schema, provider adapter, router.
5. **ADR-0007 settlement adapter** (parallel, separate worktree): verify Circle test-USDC address/faucet on Base Sepolia, fund a testnet wallet (key in `.env` only), add `web3.py`, migration `002_settlement.sql`.
6. **Owner actions:** registration email (BK-OWN-1); reset DB password before final submission.
