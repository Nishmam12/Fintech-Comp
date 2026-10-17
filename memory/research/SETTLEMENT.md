# Settlement research — Base Sepolia (BK-075 step 1)

Verified 2026-10-15 by Member 3 (Afnan).

| Item | Value | Source / check |
|---|---|---|
| Chain | Base Sepolia, chain ID **84532** (0x14a34) | Base docs network-information; confirmed live via `eth_chainId` on the RPC |
| Public RPC | https://sepolia.base.org (rate limited; not for production) | Base docs; Alchemy/Infura key is the fallback |
| Test USDC (Circle) | `0x036CbD53842c5426634e7929541eC2318f3dCF7e` | Circle docs, USDC contract addresses; on-chain `decimals()` = 6, `symbol()` = "USDC" |
| Explorer | https://sepolia.basescan.org/tx/<hash> (ADR-0007); Base docs list https://sepolia-explorer.base.org | Check which one resolves before the demo; store both link forms if needed |
| Settlement wallet (address only) | `0x228F0C5Dcdd12b2A9E21d289969FF286ff71a97D` | Fresh key generated 2026-10-15, stored only in the gitignored `.env` |

## Faucets
- **Circle public faucet** (faucet.circle.com): test USDC, Base Sepolia supported. Circle docs say 10 USDC per request, one request per 24 h per token per testnet. Their pages disagree slightly; check the live page.
- **Circle developer-console faucet**: 20 USDC per request, needs a Circle developer account and a Circle-created wallet, so not usable for our own key.
- **Coinbase CDP faucet**: 1 USDC per request, 10 USDC per rolling 24 h; also gives Base Sepolia ETH (docs.cdp.coinbase.com faucets).
- Gas ETH: Coinbase CDP / Alchemy / other Base Sepolia faucets (docs.base.org/tools/network-faucets).

## Status
- [x] Contract, chain ID, decimals verified from docs and on-chain.
- [x] Wallet created (key in `.env` only).
- [ ] Wallet funded with test ETH (gas) — manual, browser faucet.
- [ ] Wallet funded with test USDC — manual, browser faucet.

Demo mandates must stay small (about $20 total, ADR-0007) so the 10 USDC faucet drip covers them 1:1.

## Explorer check (2026-10-15)
- `https://sepolia-explorer.base.org` (Blockscout) answers 200 from curl. `https://sepolia.basescan.org` answers 403 to curl (likely bot check; unverified in a browser). No real tx page exists yet; open the real link before the demo and pick the one that renders.
- `BK_EXPLORER_URL` (tx-page prefix ending in `/tx/`) switches the link the API returns, for both `GET /mandates/{id}/state` (`explorer_url`) and the settle response. Default stays basescan.
- Wallet 0x228F...a71D balance checked via public RPC: 0 ETH (still blocked on gas).

## Hardening status (Step 4)
- BK-311: confirmations default 2; `test_reorg_before_depth_does_not_confirm_or_fail`.
- BK-312: `max_fee_ceiling` (50 gwei); above it nothing is signed and no nonce is used; `test_gas_ceiling_waits_without_consuming_a_nonce`. A signed tx is only ever re-broadcast, never re-signed.
- BK-313/314: proof rules and recipient registry covered by the review-gate tests in `test_settlement.py`.

## Gas ETH routes re-checked (2026-10-15, from the faucets' own pages)
- **QuickNode Base Sepolia** (faucet.quicknode.com/base/sepolia): page states no account, no mainnet balance, no X post needed (post only boosts the amount); verification step; once per 12 h per wallet. Base amount shown only after entering the address. Earlier note said it gated on mainnet balance: the page now says otherwise, and a 2026 third-party guide still says it does, so treat as "try it".
- **ZalalenA** (faucet.zalalena.com/base): page states no login/balance, captcha, 60 min cooldown, 10 claims/day. Small third-party operator; paste only the public address.
- Alchemy and GetBlock still need mainnet balance / signup (third-party roundup, unverified). Base docs list page did not render its faucet table when fetched.
- Paste only the PUBLIC address 0x228F0C5Dcdd12b2A9E21d289969FF286ff71a97D. Needed: about 0.001 ETH (a transfer costs well under that).

## FIRST REAL TRANSACTION (2026-10-15 15:58 UTC / 21:58 BST+6 local)
- Kernel tx `769b9063-fe9d-4226-bd0f-962e92d17c9b` (mandate in schema `bk_afnan_demo`, run by `scripts/demo.py` with `BK_SETTLEMENT_MODE=testnet`, `DEMO_PAY_USD=1`)
- Tx hash `0x2c5665e7908ebb775e03185e5aef9fd9e566b79c21652d7f3c789db1add49090`, block 48155797, nonce 0, 1.000000 test USDC to `aws` (0x69fF...88A0)
- Independently verified over public RPC: receipt status 1, `to` = Base Sepolia USDC contract, Transfer log amount 1000000.
- Explorer: https://sepolia-explorer.base.org/tx/0x2c5665e7908ebb775e03185e5aef9fd9e566b79c21652d7f3c789db1add49090 -> HTTP 200. **The demo uses Blockscout (sepolia-explorer.base.org)**; basescan returns 403 to curl so it is not the demo explorer. Defaults in API, adapter and evidence.py now point at Blockscout.
- Gas ETH came from the ZalalenA faucet (0.001 ETH). After the transfer the wallet had 0.000999627 ETH, so this transfer cost ~0.00000037 ETH, plenty for the rest.
- Ran in own schema `bk_afnan_demo` (migration 003 applied there). Production schema `bk` still lacks 003: the lead decides when to apply it.
- Evidence: `evidence/SETTLEMENTS.md` + `evidence/settlements.json` (hashes and links only).
- Demo needs an admin token: `BK_ADMIN_TOKEN` in .env is empty, so a session token was passed by environment for both API and demo.

## REAL ANCHOR + production payment (2026-10-17 03:26-03:28 UTC, production schema `bk`)
- Payment (live demo, `DEMO_PAY_USD=1`): kernel tx `0a60f8d4-b5ac-49d9-b8e0-5c282ad9e4a0`, tx `0x7570ccbe8c9ca0aa52c057d2c52e567fece698c28909718e29e3b505f061abf1`, block 48219666, 1 test USDC to `aws`. The same run also exercised delegation, hold/approve, velocity limit, circuit-breaker suspend + owner reinstate, revoke; all steps `[ok]`.
- Anchor id 1: tx `0xcb1ba8f8c64413779274509bb7333e9693123cdc8d5e9229ba927b74f5578e2e`, block 48219690, nonce 2, status `confirmed`, 0-value self-transfer from `0x228F0C5Dcdd12b2A9E21d289969FF286ff71a97D`, 9 chains.
- Digest `3b1cc8888b7940d336f8fb4b9f3fcbf32eb3306fb289244ca30a7f04c386d8f5`. Explorer: https://sepolia-explorer.base.org/tx/0xcb1ba8f8c64413779274509bb7333e9693123cdc8d5e9229ba927b74f5578e2e
- Verified by me over the public RPC (`eth_getTransactionByHash`): from == to, value 0x0, input = `0x424b414e43484f5231` (BKANCHOR1) + the digest above.
- `GET /mandates/2643fc03-f889-4777-9f30-726dacc90226/integrity` (admin token): `ok: true`, `last_anchor` status `confirmed`, `matches: true`, seq 37, head `7ad4ecf0487f...`.
- Notes: `.env` `BK_ADMIN_TOKEN` was blank, so I set a random local one (the API I ran is my own instance). `/settlement/reconcile` needs a service-principal bearer key as well as the admin header.
- `evidence/` was regenerated from `bk`, so `settlements.json` now lists this payment; the first transaction (`0x2c5665e7...`, schema `bk_afnan_demo`) stays documented above and in git history.
