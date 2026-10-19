# Deck draft 3 (BK-120): 10 slides plus the lead's numbers slide, about 10 minutes

For the lead to review. Replaces the outline in `DECK_OUTLINE.md`. Every number has its source in brackets; nothing is from memory. The final numbers slide (11) is the lead's, written after the freeze. Screenshots named below (`01`, `02`...) are the old 390 px shots in `docs/submission/screenshots/bk413/` and are placeholders: after the UI freeze (Oct 19, 14:00 BST) every one is re-shot from the frozen UI with the demo sign-in buttons, at 1280x800 for slides plus one 390x844 phone shot (BK-120/BK-160).

Rule for the speaker: if a number is not on this page with a source, do not say it.

---

### 1. The problem (40 s)
**On the slide:** "An AI agent that can spend money is one prompt injection away from an overspend."
**Say:** Models read messy text and can be talked into things. Anything that moves money must not depend on what a model wrote.

### 2. The idea: models propose, the kernel decides (50 s)
**On the slide:** one diagram: text → *proposal* (untrusted, typed, no authorization fields) → **kernel** (deterministic, one Postgres transaction, per-mandate lock) → approve / reject / hold.
**Say:** The proposal schema has no way to say "approved" and rejects unknown keys. The kernel never imports model code; a boundary test enforces that. Every unclear outcome fails closed. [ADR-0001; `SECURITY_SELF_ASSESSMENT.md` section 1]

### 3. Authority is moved, never created (60 s)
**On the slide:** the grant tree from screenshot `01` (mandate, protected reserve, delegated grants), plus the invariants in one line each:
- I1 conservation: total = reserve + all grants (available + reserved + settled)
- I2 / I3: reserved and settled balances equal the sum of their transactions
- I4: no negative balances (database CHECK constraints)
- I5: replaying the recorded movements reproduces every balance
**Say:** Delegation moves money from a parent grant to a child; scope can only narrow, expiry only shorten, revocation reaches every descendant. The server re-checks I1, I2, I3 and I5 on every state read (the green "Ledger invariants hold" bar); I4 is a database constraint. [ADR-0004, ADR-0005; `kernel/invariants.py`]

### 4. Guard rails on spending (50 s)
**On the slide:** velocity window ("at most 150.00 USD per hour across the grant's subtree") and approval threshold ("above 60.00 USD the owner must approve"); screenshots `02`, `03`.
**Say:** A per-transaction limit alone can be split into many small spends (we show that limit honestly, below). A window closes it, and it is checked under the same lock. Cost measured: about +47 ms median per authorization, against a target of under 100 ms. [ADR-0008; `RESULTS.md` Run 3. Caveat: Run 3 was before the hash chain and breaker; the lead re-measures at the freeze.]

### 5. Does it hold? Attacks against an unsafe baseline (80 s)
**On the slide:** the table from `RESULTS.md` Run 2.
| Attack | Unsafe baseline | Kernel |
|---|---|---|
| Concurrent overspend (8 racers x 30,000 vs 90,000) | violated | held: 3 of 8 approved |
| Delegation amplification (6 x 30,000 from a 90,000 parent) | violated | held: 3 children, 90,000 of 90,000 |
| Revoked ancestor | violated | held: `GRANT_REVOKED` |
| Replay, same request x 5 | violated | held: 1 transaction |
| Revocation race | **did not reproduce in the recorded run** | held |
**Say:** Four of the five broke the baseline; the fifth is timing-dependent and we say so. Also: kernel scripts 50 of 50 cases, 134 of 134 steps, 0 unauthorized approvals, 0 invariant violations (Run 5 offline re-run). Suite: 327 tests passed plus the slow property-based state machine [CHANGELOG 2026-10-17]. These numbers cover these scenarios, not general security.

### 6. The language interface and what the live model showed (80 s)
**On the slide:** rules path first (free), model only for messy text. Config B, live Qwen, Run 5:
| Dataset | Correct | Unauthorized | Wrong-value | Safe misses |
|---|---|---|---|---|
| v1 | 106/131 (80.9%) | 0 | 0 | 13 |
| v2 | 107/131 (81.7%) | 0 | 0 | 12 |
Rules only: 51/131 (38.9%), 0 unauthorized (Run 1). Cost of a whole 131-case run: about 2,700 micro-USD (84 model calls). p50 about 4.2 s end to end.
**Say the story:** the first live run found a real gap. For "Pay github $80" (no category) the model invented `tools` and the pipeline approved it. We grounded recipient and category in the user's words; the gap closed (Run 4: 1 unauthorized before, 0 after).
**Caveats on the slide (small print, not optional):** synthetic data; v2 uses the same generator as v1 with another seed; one run per setting; config C (escalation model) **not run**; the digit-based datasets cannot show the number-word and alias fix. [`RESULTS.md` Runs 4 and 5]

### 7. The circuit breaker, and the bug review found in it (75 s)
**On the slide:** screenshots `05` (suspended) and `18` (only the owner can reinstate).
**Say:** Five probing refusals inside ten minutes suspend a grant and everything below it (a suspected injection counts 3). Then an independent review found a bypass: an agent could delegate a child to itself, probe it into suspension, and reinstate it as holder of the parent, forever. **Fix, with tests first:** reinstate is owner-only and self-delegation is refused. The dashboard shows an ancestor "Only the mandate owner can reinstate this grant" and the server returns 403 `NOT_OWNER` either way. Finding it before the freeze is the point of the review. [ADR-0009 B and amendment K1; `PHASE3_REVIEW.md`]

### 8. Tamper-evident history and real settlement, both on a public chain (75 s)
**On the slide:** the badge ("History intact · N records", head hash, "View anchor on Base Sepolia" button), then three explorer links: the history anchor and the two settlements (testnet, 1.0 test USDC each).
**Say:** Every audit and movement row is hash-chained by a database trigger; a read-only verifier recomputes it and names the break (`SEQ_GAP`, `PREV_MISMATCH`, `HASH_MISMATCH`, `HEAD_MISMATCH`, `ANCHOR_MISMATCH`). The newest head is written to Base Sepolia as a zero-value transaction whose calldata is `BKANCHOR1` + the 32-byte digest. Settlement is real too: the recipient comes from an operator allow-list, never from a model, and each transfer has its audit trail (reserved, submitted, settled).
- Anchor 1: tx `0xcb1ba8f8c64413779274509bb7333e9693123cdc8d5e9229ba927b74f5578e2e`, block 48219690, checked by the lead over the public RPC (status 1).
- Settlement: `0x2c5665e7908ebb775e03185e5aef9fd9e566b79c21652d7f3c789db1add49090` (block 48155797)
- Settlement: `0x7570ccbe8c9ca0aa52c057d2c52e567fece698c28909718e29e3b505f061abf1` (block 48219666)
[`evidence/SETTLEMENTS.md`; CHANGELOG 2026-10-17]
**State the limit on the slide:** a database superuser can rewrite a whole chain and recompute every hash unless the head was anchored. The anchor makes that detectable after the fact; it does not prevent it. [ADR-0009 A; R20]

### 9. The dashboard, in 30 s
**On the slide:** three frozen-UI shots: the Ask decision ("Held for the owner's approval"), the owner-only reinstate text, the Review card.
**Say:** Real API, real keys, no mocks; sign-in in one tap, tabs match the role, refusals in plain words, model text rendered as plain text. [`CLICKTHROUGH_BK413.md`]

### 10. What we do not claim (60 s)
**On the slide:** four short lines.
- Testnet prototype, no external audit, must not hold real funds.
- A database superuser can rewrite an un-anchored chain (R20); the hot wallet is one key (R5).
- The rate limiter is per process (R8); the router's "needs review" does not bind a malicious holder (R10); revoking the root freezes the mandate (R11); in-flight transfers cannot be recalled (R12); service principals can read every mandate (R13); injection detection is pattern-based (R19).
- Evaluation is synthetic, one run per setting, config C not run; authorize takes about 1.1 s on the hosted database (Run 3, one operation per second per mandate).

### 11. Final numbers (lead, after the freeze)

---

## Timing
40 + 50 + 60 + 50 + 80 + 80 + 75 + 75 + 30 + 60 = **600 s (10 min)**, before the lead's numbers slide. Slide 9 is shrunk to 30 s and the old slide 10 (settlement) is merged into slide 8.

## For the lead to decide
1. `SECURITY_SELF_ASSESSMENT.md` sections 1 and 8 still read as if live-model accuracy was not measured and as if the summary evidence were rules-only (Runs 4 and 5 now exist), and section 1 still lists "no velocity limit" as a known limit although R1 is mitigated (opt-in). I did not copy those lines. Update at the freeze.
2. Run 3 latency is from before the hash-chain trigger and the breaker. Re-measure before quoting 1.1 s as final.
3. Config C: if it will not exist by Oct 19, slide 6 keeps the "not run" line.
4. The two small UI findings, and a third (the agent saw Revoke buttons it could not use), are fixed in the stacked follow-up PR; slide 7 can now say the agent is told who can reinstate. Screenshots `07` and `19` changed accordingly.
