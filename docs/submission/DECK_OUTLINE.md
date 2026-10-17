# Deck outline, draft 1 (BK-120). For the lead to review.

Target: 10 minutes or less, about 9 slides. Numbers come only from `memory/evaluation/RESULTS.md` (latest run of each kind); copy the caveats with them. Screenshots are from the live click-through in `CLICKTHROUGH_BK413.md`.

1. **Problem (45 s).** An AI agent that can spend money is one prompt injection away from an overspend. Models propose; nothing trusted should depend on model text.
2. **Idea (45 s).** Budget Kernel: the model only produces a *proposal*. A deterministic kernel decides, under a lock, from authoritative state. Show the one-line boundary: model output never becomes an authorization.
3. **Delegation model (60 s).** Mandate, protected reserve, delegable grants, per-transaction limit, velocity window, review threshold, kill switch. Screenshot 01.
4. **Why it holds (90 s).** Attack scenarios, unsafe baseline vs kernel (Run 2): overspend race, delegation amplification, revoked ancestor, replay all violated on the baseline and held on the kernel. State the disclosed limitation (split purchases) and the one scenario that did not reproduce.
5. **Language interface (75 s).** Rules path first, model only for messy text. Config B on a fresh dataset (Run 4d): 108/131 correct, 0 unauthorized, 0 wrong-value, 12 safe misses; rules only 51/131 with 0 unauthorized. Include the story: the first live run found a real gap (model-inferred category) and the grounding fix closed it. Caveats on the slide: synthetic data, same generator as v1, one run, config C not run.
6. **Robustness added this week (75 s).** Replay by idempotency key (zero model calls on retry), circuit breaker (5 refusals suspend a grant), tamper-evident hash chain with an integrity check, rate limits and key lifecycle. Screenshots 05, 06, 01, 14, 15.
7. **Live dashboard (60 s).** Held request and approval, suspension and reinstate, kill switch. Screenshots 02, 05, 08, 12.
8. **Settlement evidence (45 s).** The real Base Sepolia transfer through the kernel (tx hash from `evidence/`, verified over RPC; see Afnan's evidence export). Anchor slide only if BK-401 lands.
9. **Honest limits and next steps (60 s).** From `SECURITY_SELF_ASSESSMENT.md`: per-process rate limit, database superuser can rewrite an un-anchored chain, synthetic evaluation set, about 1.1 s per authorize on the hosted database (Run 3).

Open for the lead: confirm the slide order, whether config C results will exist by Oct 19, and which tx hash to show.
