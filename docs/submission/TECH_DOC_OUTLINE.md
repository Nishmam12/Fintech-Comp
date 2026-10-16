# Technical document outline, draft 1 (BK-160). For the lead to review.

1. Problem and threat model (agent, prompt injection, concurrency, a compromised key).
2. Architecture: the authorization boundary (proposal vs decision), components, data flow. Source: `AGENTS.md`, ADR-0001.
3. The kernel: mandate and grant tree, move-based accounting, invariants I1 to I5, lock and sweep (ADR-0004, 0005).
4. Language interface: rules path, model route, validation and grounding, cost ledger (ADR-0006, 0008; Run 4 with caveats).
5. Settlement: adapter, nonce allocator, crash safety (ADR-0007).
6. Phase 3 robustness: hash chain and integrity check, circuit breaker, replay, rate limit, key lifecycle (ADR-0009).
7. Evaluation: kernel scripts, attack scenarios, live model runs, latency. Numbers from `RESULTS.md`, latest run only, with their caveats.
8. Security self-assessment: permission tiers and known risks R1 to R22 (`SECURITY_SELF_ASSESSMENT.md`).
9. Limits and future work.
