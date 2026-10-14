# ADR-0007: Testnet Settlement Adapter for Topic F (Agent Wallet)

- **Status:** ACCEPTED (2026-10-15, team lead)
- **Date:** 2026-10-15
- **Owner:** Opus planner (draft) / project lead (approval)
- **Related tasks:** BK-075, BK-090, BK-110
- **Related ADRs:** ADR-0001, ADR-0004, ADR-0005 (states `reserved → submitted → settled|released`, lock order). **Amends ADR-0003's** "no blockchain" scope line for this one adapter only. The kernel still does not depend on a chain.
- **Records:** OQ-008 resolution (Topic F)

## Context
Topic F needs **real on-chain transaction hashes** as execution evidence. A bonus of 0 to 5 points is available. AGENTS.md still requires that no real funds move. On-chain transfers cannot be recalled, and a process can crash at any point between "decide to pay" and "know it was paid". The adapter must never authorize anything and never move value the kernel did not reserve.

## Options considered
1. **Chain**
   - **Base Sepolia (chosen):** chain id 84532, about 2 s blocks, public RPC, Basescan explorer links that judges can open, and Circle test USDC is available.
   - **Ethereum Sepolia:** about 12 s blocks make the demo slower, and faucets are stricter.
   - **Polygon Amoy:** viable, but faucets are less reliable.
   - **Solana devnet:** different signing and nonce model; it would mean a second toolchain.
2. **Asset**
   - **Circle test USDC, an ERC-20 with 6 decimals (chosen):** a clean mapping to a USD mandate.
   - **Native Sepolia ETH:** the fallback. Simpler, but needs an arbitrary scale.
   - **Deploying our own ERC-20:** needs Solidity tooling. Rejected for time.
3. **Custody**
   - **Single operator hot wallet, kernel-controlled (chosen):** agents hold *grants*, not keys.
   - **ERC-4337 smart account with on-chain session keys and spend limits:** stronger, but not buildable in 4 days. Listed as future work and as a known risk.
4. **Exactly-once mechanism**
   - **Pre-assign the nonce, sign locally and persist the raw tx before broadcast (chosen):** the chain's nonce rule makes a double send impossible.
   - **Idempotency on our side only:** cannot stop a re-sign after a crash.

## Decision

### Adapter boundary
- The adapter has **no HTTP route and no authorization logic**. The only code path that signs is `kernel.settle_start(tx_id)`.
- `settle_start` builds the transfer **from the DB transaction row only**: amount, recipient, and the mandate's chain and token. It never uses caller input.
- **Recipient:** must be in the grant's `scope.recipients` allowlist, which is checked at authorize (ADR-0004). An LLM cannot introduce a new address.
- **Chain and contract guard:** the adapter refuses any `chain_id` other than 84532 and any token contract other than the configured one. That is a hard-coded mainnet guard, so chain ids 1 and 8453 are refused.
- **Gas:** paid by the hot wallet in test ETH. It is an operator cost, **not** charged to the mandate (ADR-0004).

### Schema
```
settlement_accounts(chain_id INT, address TEXT, next_nonce BIGINT NOT NULL, PRIMARY KEY(chain_id, address))

chain_settlements(
  transaction_id UUID PK REFERENCES transactions,   -- at most one transfer per kernel tx
  chain_id INT, from_address TEXT, nonce BIGINT, to_address TEXT, token_address TEXT,
  token_amount NUMERIC(78,0), raw_tx BYTEA NOT NULL, tx_hash TEXT NOT NULL UNIQUE,
  status TEXT CHECK (status IN ('signed','broadcast','confirmed','failed','stuck')),
  broadcast_attempts INT DEFAULT 0, last_error TEXT,   -- sanitized; never contains key material
  block_number BIGINT, created_at, updated_at,
  UNIQUE (chain_id, from_address, nonce))
```
The signed raw transaction is public data once broadcast and is safe to store. The private key is never stored.

### Flow and crash windows
1. **settle-start** is one kernel transaction (ADR-0005), holding the mandate lock and then the `settlement_accounts` lock:
   - Guard: state = `reserved`, the path is active and unexpired, and the TTL has not passed.
   - `n = next_nonce; next_nonce += 1`.
   - Build an ERC-20 `transfer(to, token_amount)` with fixed gas and EIP-1559 fees. Fees are read *before* the transaction from a cached value refreshed outside the lock, multiplied by 2 as headroom.
   - **Sign locally** (no network).
   - Insert `chain_settlements(status='signed', raw_tx, tx_hash)`, which gives a deterministic hash. Move the kernel tx from `reserved` to `submitted`. COMMIT.
2. **Broadcast** happens after commit and outside all locks: `eth_sendRawTransaction(raw_tx)`. "Already known" and "nonce too low" count as success-or-mined. Set status to `broadcast`.
3. **Confirm:** poll for the receipt for up to 30 s inline, otherwise leave it to the reconciler.
   - Receipt with `status == 1` (one confirmation is enough on testnet): kernel `submitted → settled`.
   - Receipt with `status == 0` (reverted, so no token moved): kernel `submitted → released`.
   - Both run inside a kernel transaction, guarded by `WHERE state = 'submitted'`, so they are idempotent.

**What happens on a crash at each point:**
- **Before settle-start commits:** rollback. The tx stays `reserved` and the nonce is not consumed. The client retries settle, or the TTL releases it.
- **After commit, before broadcast:** the reconciler finds `signed` and re-broadcasts the **same raw bytes**.
- **After broadcast, before confirm:** the reconciler finds `broadcast` and checks the receipt by `tx_hash`.

**No double send, guaranteed by three layers:**
1. The kernel state guard: settle on `submitted` or `settled` is a no-op and never signs again.
2. `UNIQUE(transaction_id)` and `UNIQUE(chain_id, from_address, nonce)`.
3. **The chain itself:** only one transaction per (address, nonce) can ever be mined, and we only ever re-send identical bytes.

### Reconciler
Run as `python -m budget_kernel.settlement.reconcile [--once]`, a loop every 10 s, also triggered by `POST /admin/reconcile`. For each `chain_settlements` row in `signed` or `broadcast`:
- **Receipt exists:** confirm or release as above.
- **No receipt:** re-broadcast the raw tx (idempotent).
- **Released only on proof.** The kernel tx moves to `released` only when the receipt is a revert, **or** when the account's on-chain `latest` nonce is greater than our nonce and our hash still has no receipt on two checks at least 60 s apart (the nonce was consumed by something else).
- **Stuck after 30 min with no receipt:** mark `stuck`. Funds **stay reserved**, which is fail-safe because it over-reserves and never under-reserves. A runbook covers the operator response: send a 0-value self-transfer at the same nonce with a higher fee, then let the proof rule above release the tx. Building the cancel tool is optional.
- **Nonce sync:** `next_nonce` is initialized from `eth_getTransactionCount(pending)` only when no rows are in `signed` or `broadcast`. The hot wallet is **exclusively** used by the adapter. A team member sending manually from it desynchronizes the nonce, so that is forbidden by the runbook.

### Amount mapping (integer only)
- A mandate in `USD` minor units (cents) maps to USDC base units (6 decimals) as `token_amount = amount_minor * 10_000`. This is exact, with no floats, and computed in Python `int`, stored as `NUMERIC(78,0)`.
- **Fallback (native ETH):** `wei = amount_minor * WEI_PER_MINOR`, using a documented constant (for example `10**10`, so 1 cent = 1e-8 ETH). The UI and the evidence pack must label it "scaled demo units".
- The mapping lives in a config table keyed by `(currency, chain_id, token)`. The adapter refuses any currency without a mapping.
- Demo mandates stay small (for example $20.00 total) so faucet funding covers them at a 1:1 mapping.

### Key custody
- A **fresh, testnet-only** key is generated for this project and never used on mainnet. It is funded only with test ETH for gas and test USDC.
- The key is supplied as `SETTLEMENT_PRIVATE_KEY` in `.env` only. `.env` is gitignored, and `.env.example` holds a placeholder.
- The key is loaded once into an `eth_account` `LocalAccount`, inside a wrapper whose `__repr__` and `__str__` are redacted.
- The key is never written to the DB, logs, audit events, memory notes, exceptions or test fixtures. Tests use a deterministic throwaway key generated in-process.
- Only the derived **address** is stored and displayed.
- A CI and pre-commit grep fails on a 64-hex-character string next to `PRIVATE_KEY`.
- RPC URL and any provider key also live only in `.env`.

### Library
`web3.py` (which brings `eth-account`) is a **justified new dependency**: signing and RPC are a demonstrated requirement. Run it synchronously in a threadpool, or use its async provider. No other chain dependencies.

### Competition deliverables this ADR directly supports
- **Execution evidence:** `python -m budget_kernel.settlement.export_evidence` writes a CSV and Markdown table with kernel tx id, grant path, amount, tx_hash, Basescan URL, block and kernel decision. Rejected attempts are listed with **no** hash, which is evidence that the kernel blocked them before anything reached the chain.
- **UI and audit:** every settled transaction shows its hash and explorer link (`https://sepolia.basescan.org/tx/<hash>`).
- **Known-risk list entries:**
  - Custodial single hot wallet (key compromise means everything the testnet wallet holds can be drained). Limited by small balances.
  - In-flight transfers are not revocable (ADR-0005).
  - Stuck or nonce-gap transactions need an operator.
  - Gas is not charged to the mandate.
  - Public RPC rate limits.
  - Testnet only; no mainnet legal or compliance review.
- **Permission tiers:** the adapter is an explicit non-authorizing tier (ADR-0004 table).

## Consequences
- **Positive:** Real hashes for the bonus. Exactly-once settlement rests on chain semantics, not just our own code. The kernel stays chain-agnostic, and a `SimulatedAdapter` with the same interface (`sign → raw bytes/hash`, `broadcast`, `get_receipt`) runs tests and an offline demo.
- **Negative/tradeoffs:** Settlement throughput is serialized through one account nonce. That is fine for the demo. A stuck nonce blocks later transfers until an operator acts. The design is custodial, not self-custody per agent.
- **Security/privacy effects:** No authority in the adapter. Recipient allowlist. Mainnet guard. Key only in `.env`. No real value moves (testnet), which is consistent with AGENTS.md "no real funds".
- **Operational effects:** The faucet ETH and test-USDC balance must be pre-funded before demo day. Public RPC may rate-limit, so an Alchemy or Infura testnet key in `.env` is the fallback.

## Evidence and validation
Not yet implemented. **To verify before coding (assumptions):**
- The Circle Base Sepolia USDC contract address and faucet limits, from Circle's official docs.
- The public Base Sepolia RPC URL and the Basescan Sepolia URL.

Required tests:
- **SimulatedAdapter crash injection:** crash after commit and before broadcast, then reconcile, gives exactly one broadcast hash and `settled`. Crash after broadcast gives one hash and `settled`.
- Concurrent settle ×10 on one tx gives one `chain_settlements` row.
- Revert receipt gives `released`, with funds returned to the nearest active ancestor.
- Revoke during `submitted` leaves the tx in flight, and the revoke response reports the exposure.
- A recipient outside the allowlist is rejected at authorize, before any signing.
- A wrong chain id is refused.
- A log scan shows no key material.

Plus one live smoke test on Base Sepolia whose hash is recorded in the evidence pack.

## Revisit when
The on-chain bonus calls for on-chain enforcement (move to an ERC-4337 or Safe module with spend limits that mirror grants), more than one settlement wallet is needed, or the competition requires mainnet.
