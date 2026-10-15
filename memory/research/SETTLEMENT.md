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
