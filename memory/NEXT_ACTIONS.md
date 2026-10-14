# Next Actions

1. **BK-020: migration `001_core.sql`** from ADR-0004/0005 (mandates, grants with path, transactions incl. `submitted`, audit_events, idempotency key + payload_hash), run with `python -m budget_kernel.db.migrate --test`.
2. **Kernel operations** (`kernel/`): create_mandate, delegate, authorize, settle, release, revoke, each taking the mandate `FOR UPDATE` lock first; invariant checks I1–I3 after every transition.
3. **Tests**: unit per transition, hypothesis state machine, concurrency races (shared allocation, siblings over parent, revoke vs authorize, duplicate idempotency key).
4. **ADR-0007 pre-work (parallel, separate worktree):** verify Circle test-USDC address and faucet on Base Sepolia, create a funded testnet wallet (key in `.env` only), add `web3.py`.
5. **Owner actions:** send registration email (BK-OWN-1); reset the DB password before final submission.
