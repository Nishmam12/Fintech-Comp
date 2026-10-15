# Review of `afnan/BK-303-mandate-settlers` (Opus review gate, 2026-10-16)

**For Afnan.** `git pull` on `main`, then paste the section below the line into Claude Code (repository root) on your branch.

---

You are working with Afnan (Member 3) on the settlement branch `afnan/BK-303-mandate-settlers`. The lead's Opus review gate has finished. **Verdict: approve after three small fixes.** The design is sound:
- The signature and nonce are persisted atomically under the mandate lock.
- The same bytes are re-broadcast and nothing is ever re-signed.
- Benign "already known" / "nonce too low" errors are handled.
- Confirmation depth is checked from a fresh receipt every time (re-org safe on the success path).
- The nonce-consumed proof needs two observations at least 60 s apart.
- Chain ID is restricted to 84532.
- The key never appears in `repr`.
- The recipient registry and integer-only conversion are correct.
- In testnet mode, the simulated settle path is disabled.

The first real transfer (`0x2c5665e7…9090`, block 48155797) was **independently verified over the public RPC**: status success, 1,000,000 base units of the Circle test-USDC token from the settlement wallet to the registry address.

Fix the three items below on the same branch, each with a test, then push and tell the lead. The lead merges after a green full suite.

## F1 (must fix, safety): wait for confirmation depth before acting on a revert
In `settlement/adapter.py` `advance()`, a receipt with `status == 0` calls `kernel.settle_fail` **immediately**, while a success waits for `cfg.confirmations`.

A re-org can drop the reverted transaction. The *same signed bytes* can then be mined again and succeed, for example if the token balance changed in between. The kernel would already have released the funds while the tokens moved: a double spend. That is the case requirement 6.1 exists to prevent.

**Fix:** apply the same depth rule to both outcomes. Check depth first, then branch on status:
```python
depth = chain.block_number() - receipt["block"] + 1
if depth < cfg.confirmations:
    _update(pool, transaction_id, block_number=receipt["block"])
    return out                      # not final yet, whether it succeeded or reverted
if receipt["status"] == 0:
    ...settle_fail...
```
**Test:** a reverted receipt at depth 1 must leave the kernel transaction `submitted` with funds reserved. It is released only once the revert is `confirmations` deep. Add the re-org variant too: revert at depth 1, re-org, then success → the transaction ends `settled`, never `released`.

## F2 (should fix): the reconciler must not stop at the first refusal
`reconcile()` loops over every pending transfer across all mandates. If the caller is not the bound settler for one transfer's mandate, `kernel.settle_confirm` / `settle_fail` raises `Forbidden`. That aborts the whole pass, so the remaining transfers are never advanced.

**Fix:** catch `kernel.KernelError` per transfer inside `reconcile()` and return it as an error entry for that transfer (`{"transaction_id": …, "error": code}`), then continue. Do not catch broader exceptions.

**Test:** two pending transfers on two mandates, the caller bound to only one → one advances, the other reports `NOT_SETTLER`.

## F3 (should fix): in testnet mode only a bound service may run settlement
In testnet mode the owner can call `POST /transactions/{id}/settle`. That sends a real transfer as the owner. If it reverts, the adapter calls `settle_fail` with the owner as actor. The kernel forbids that (the owner may never declare a failure), so the transfer hangs until a service reconciles.

**Fix:** in the API's testnet branch, refuse unless the caller is a `service` principal: 403 `NOT_SETTLER`. The kernel's binding check then applies as usual. The simulated mode keeps the owner path for the demo.

**Test:** in testnet mode, the owner gets 403 and a bound service succeeds.

## Notes for the record (no code change needed; the lead adds them to the self-assessment)
- **No unbind path.** A bound settler stays bound for the mandate's life. This residual of R2 is documented as such. A future `DELETE /mandates/{id}/settlers/{principal}` would close it.
- **The settlement wallet must be dedicated** to the adapter. Sending from it by hand moves the chain nonce past the DB counter. That is safe (affected transfers fail on proven nonce consumption and the funds are released), but it is slow to recover.
- **A transfer signed with too low a fee can stay `submitted`** until manual action (we never re-sign, by design). The gas ceiling and 2x base-fee headroom make this unlikely on testnet.
- **`api/app.py` switched from CRLF to LF line endings** in your commits, so the diff shows the whole file. That is harmless, but don't flip the endings back.

## After the fixes
1. Run the full non-slow suite on your schema and paste the count.
2. Push, set your WHO_IS_WORKING status to `REVIEW`, and tell the lead.
3. After the merge, the lead applies migration 003 to production `bk`, and runs `scripts/demo.py` in testnet mode once to confirm a second real transfer end to end.
