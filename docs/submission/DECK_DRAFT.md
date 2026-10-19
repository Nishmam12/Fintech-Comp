# Deck draft 4 (BK-120): 11 slides, about 10 minutes

For the lead to review. Replaces the outline in `DECK_OUTLINE.md`. Every number has its source in brackets; nothing is from memory. Slide 11 (final numbers) is written. Screenshots named below are from the frozen UI, in `docs/submission/screenshots/r3/` (1280x800; `13` and `14` are 390x844): `01-signin`, `02-mandate`, `03-ask-approved`, `04-ask-held`, `05-ask-refused`, `06-ask-suspended`, `07-review`, `08-activity`, `09-owner-reinstate`, `10-attack-lab`, `11-settings`, `12-manager-owner-only`, `13-phone-mandate`, `14-phone-review`. Older numbers in the text below refer to the superseded set in `screenshots/bk413/` and are replaced by this list.

Rule for the speaker: if a number is not on this page with a source, do not say it.

---

### 1. The problem (40 s)
**On the slide:** "An AI agent that can spend money is one prompt injection away from an overspend."
**Say:** Models read messy text and can be talked into things. Anything that moves money must not depend on what a model wrote.

### 2. The idea: models propose, the kernel decides (50 s)
**On the slide:** one diagram: text → *proposal* (untrusted, typed, no authorization fields) → **kernel** (deterministic, one Postgres transaction, per-mandate lock) → approve / reject / hold.
**Say:** The proposal schema has no way to say "approved" and rejects unknown keys. The kernel never imports model code; a boundary test enforces that. Every unclear outcome fails closed. [ADR-0001; `SECURITY_SELF_ASSESSMENT.md` section 1]

### 3. Authority is moved, never created (60 s)
**On the slide:** the grant tree from `r3/02-mandate` (mandate cheque, protected reserve, delegated grants), plus the invariants in one line each:
- I1 conservation: total = reserve + all grants (available + reserved + settled)
- I2 / I3: reserved and settled balances equal the sum of their transactions
- I4: no negative balances (database CHECK constraints)
- I5: replaying the recorded movements reproduces every balance
**Say:** Delegation moves money from a parent grant to a child; scope can only narrow, expiry only shorten, revocation reaches every descendant. The server re-checks I1, I2, I3 and I5 on every state read (the green "Ledger invariants hold" bar); I4 is a database constraint. [ADR-0004, ADR-0005; `kernel/invariants.py`]

### 4. Guard rails on spending (50 s)
**On the slide:** velocity window ("at most 250.00 USD per hour", seeded demo grant) and approval threshold ("above 60.00 USD the owner must approve"); `r3/04-ask-held` and `r3/07-review`.
**Say:** A per-transaction limit alone can be split into many small spends (we show that limit honestly, below). A window closes it, and it is checked under the same lock. Cost measured: about +64 ms median per authorization, against a target of under 100 ms. [ADR-0008; `RESULTS.md` Run 7, re-measured on the frozen build]

### 5. Does it hold? Attacks against an unsafe baseline (80 s)
**On the slide:** the table from `RESULTS.md` Run 2.
| Attack | Unsafe baseline | Kernel |
|---|---|---|
| Concurrent overspend (8 racers x 30,000 vs 90,000) | violated | held: 3 of 8 approved |
| Delegation amplification (6 x 30,000 from a 90,000 parent) | violated | held: 3 children, 90,000 of 90,000 |
| Revoked ancestor | violated | held: `GRANT_REVOKED` |
| Replay, same request x 5 | violated | held: 1 transaction |
| Revocation race | **did not reproduce in the recorded run** | held |
**Say:** Four of the five broke the baseline; the fifth is timing-dependent and we say so. Also: kernel scripts 50 of 50 cases, 134 of 134 steps, 0 unauthorized approvals, 0 invariant violations (Run 5 offline re-run). Suite: 366 tests passed plus the slow property-based state machine [suite run 2026-10-19, `RESULTS.md` Run 6 notes]. These numbers cover these scenarios, not general security.

### 6. The language interface and what the live model showed (80 s)
**On the slide:** rules path first (free), model only for messy text. Config B, live Qwen, Run 5:
| Dataset | Correct | Unauthorized | Wrong-value | Safe misses |
|---|---|---|---|---|
| v1 | 106/131 (80.9%) | 0 | 0 | 13 |
| v2 | 107/131 (81.7%) | 0 | 0 | 12 |
Rules only: 51/131 (38.9%), 0 unauthorized (Run 1). Cost of a whole 131-case run: about 2,700 micro-USD (84 model calls). p50 about 4.2 s end to end.
**Say the story:** the first live run found a real gap. For "Pay github $80" (no category) the model invented `tools` and the pipeline approved it. We grounded recipient and category in the user's words; the gap closed (Run 4: 1 unauthorized before, 0 after).
**Caveats on the slide (small print, not optional):** synthetic data; v2 uses the same generator as v1 with another seed; one run per setting; config C (escalation model, Run 6) scored 113/131 (86.3%) on both datasets with 0 unauthorized, at about 2.3 to 2.7 times the cost of config B; the digit-based datasets cannot show the number-word and alias fix. [`RESULTS.md` Runs 4, 5 and 6]

### 7. The circuit breaker, and the bug review found in it (75 s)
**On the slide:** `r3/06-ask-suspended`, `r3/09-owner-reinstate` and `r3/12-manager-owner-only` (only the owner can reinstate).
**Say:** Five probing refusals inside ten minutes suspend a grant and everything below it (a suspected injection counts 3). Then an independent review found a bypass: an agent could delegate a child to itself, probe it into suspension, and reinstate it as holder of the parent, forever. **Fix, with tests first:** reinstate is owner-only and self-delegation is refused. The dashboard shows an ancestor "Only the mandate owner can reinstate this grant" and the server returns 403 `NOT_OWNER` either way. Finding it before the freeze is the point of the review. [ADR-0009 B and amendment K1; `PHASE3_REVIEW.md`]

### 8. Tamper-evident history and real settlement, both on a public chain (75 s)
**On the slide:** the seal on the cheque (`r3/02-mandate`: "History intact, N records", anchor line), then three explorer links: the history anchor and the two settlements (testnet, 1.0 test USDC each).
**Say:** Every audit and movement row is hash-chained by a database trigger; a read-only verifier recomputes it and names the break (`SEQ_GAP`, `PREV_MISMATCH`, `HASH_MISMATCH`, `HEAD_MISMATCH`, `ANCHOR_MISMATCH`). The newest head is written to Base Sepolia as a zero-value transaction whose calldata is `BKANCHOR1` + the 32-byte digest. Settlement is real too: the recipient comes from an operator allow-list, never from a model, and each transfer has its audit trail (reserved, submitted, settled).
- Anchor 1: tx `0xcb1ba8f8c64413779274509bb7333e9693123cdc8d5e9229ba927b74f5578e2e`, block 48219690, checked by the lead over the public RPC (status 1).
- Settlement: `0x2c5665e7908ebb775e03185e5aef9fd9e566b79c21652d7f3c789db1add49090` (block 48155797)
- Settlement: `0x7570ccbe8c9ca0aa52c057d2c52e567fece698c28909718e29e3b505f061abf1` (block 48219666)
[`evidence/SETTLEMENTS.md`; CHANGELOG 2026-10-17]
**State the limit on the slide:** a database superuser can rewrite a whole chain and recompute every hash unless the head was anchored. The anchor makes that detectable after the fact; it does not prevent it. [ADR-0009 A; R20]

### 9. The dashboard, in 30 s
**On the slide:** `r3/04-ask-held` (proposal beside verdict), `r3/12-manager-owner-only`, `r3/10-attack-lab`; the 390 px `r3/13-phone-mandate` in the corner.
**Say:** Real API, real keys, no mocks; sign-in in one tap, tabs match the role, refusals in plain words, model text rendered as plain text. [`CLICKTHROUGH_BK413.md`]

### 10. What we do not claim (60 s)
**On the slide:** four short lines.
- Testnet prototype, no external audit, must not hold real funds.
- A database superuser can rewrite an un-anchored chain (R20); the hot wallet is one key (R5).
- The rate limiter is per process (R8); the router's "needs review" does not bind a malicious holder (R10); revoking the root freezes the mandate (R11); in-flight transfers cannot be recalled (R12); service principals can read every mandate (R13); injection detection is pattern-based (R19).
- Evaluation is synthetic, one run per setting; authorize takes about 2.3 s on our hosted database, which is about 115 ms away (about 20 round trips; one operation every 2.3 s per mandate; Run 7).

### 11. Final numbers (45 s, optional; cut first if over 10 minutes)
**On the slide:** six lines, each with its source.
- 0 unauthorized approvals, 0 invariant violations: kernel scripts 134/134 steps; 366 tests plus the property-based state machine. [Runs 5, 7]
- Attacks: kernel held in 7 of 7; baseline broke in 5 (revocation race timing-dependent; split purchases informational). [Run 7]
- Language interface: rules only 51/131; config B 106/131 and 107/131; config C 113/131 on both; 0 unauthorized and 0 wrong-value in every final run. [Runs 1, 5, 6]
- Latency: 2.3 s per authorization on a database 115 ms away (about 20 round trips); controls add 64 ms. [Run 7]
- On-chain: 2 kernel-approved settlements and 1 history anchor on Base Sepolia. [`evidence/SETTLEMENTS.md`]
- 5 independent reviews, 20 findings and fixes, all with tests (a sixth pass over the UI rebuild found nothing new).
**Say:** synthetic data, one run per setting; these numbers cover these scenarios, not general security.

---

## Timing
40 + 50 + 60 + 50 + 80 + 80 + 75 + 75 + 30 + 60 = **600 s (10 min)** for slides 1 to 10; slide 11 adds 45 s and is cut first. Slide 9 is shrunk to 30 s and the old slide 10 (settlement) is merged into slide 8.

## Resolved
1. Self-assessment draft 3 (2026-10-20) replaces the stale lines; quote it.
2. Latency re-measured on the frozen build (Run 7): 2,327 ms median at a 114.5 ms round trip; controls add 64 ms.
3. Config C: done (Run 6, 113/131 on both datasets); slide 6 states it in the caveats.
4. The UI findings from the earlier click-through are fixed and the whole UI was rebuilt (revision 3); the screenshots above replace the old set.
