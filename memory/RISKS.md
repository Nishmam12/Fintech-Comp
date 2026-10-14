# Risk Register

| ID | Risk | Likelihood | Impact | Mitigation | Status |
|---|---|---|---|---|---|
| R-001 | Model output is mistakenly treated as authorization | Medium | Critical | Separate proposal and authorization schemas/services; kernel-only authority; malicious-output tests | Open |
| R-002 | Race condition causes over-reservation or grant over-allocation | Medium | Critical | Atomic DB operations, locking/conditional updates, repeated concurrency tests | Open |
| R-003 | Parent/child accounting double-counts the same authority | Medium | Critical | Choose canonical accounting representation before implementation; invariant tests after each transition | Open |
| R-004 | Revocation races with a concurrent authorization or settlement | Medium | High | Define transaction boundary and reservation policy; test race orderings | Open |
| R-005 | Provider pricing/IDs change or region differs from estimate | High | Medium | Re-verify official docs, pin exact routes, store rate-card version, reconcile actual usage | Open |
| R-006 | Concurrent API calls overshoot monthly inference cap | Medium | High | Atomic cost reservation before dispatch, bounded output/retries and cap tests | Open |
| R-007 | Model budget exhaustion leads to unsafe fallback | Medium | Critical | Fail closed for unresolved intent; explicit review state; tests for exhausted budget | Open |
| R-008 | Shared memory goes stale or Claude/GPT overwrite each other | Medium | High | Version-controlled memory protocol, one writer, explicit handoff, diff review, session sync | Open |
| R-009 | Overengineering harms competition delivery | High | Medium | Modular monolith; strict MVP scope; prioritize kernel/test/demo; gate stretch goals | Open |
| R-010 | Real-user financial information is retained or sent to providers unnecessarily | Medium | High | Synthetic data in MVP; data minimization; no training collection until separate review | Open |
| R-011 | Novelty claim is too broad relative to prior art | Medium | Medium | Prior-art review; articulate specific hypothesis; avoid unsupported “first” claims | Open |
| R-012 | UI presents hardcoded or fabricated outcomes | Medium | High | UI reads backend results; all metrics derived from actual scenario/test runs | Open |

Review this register at each milestone gate. Add a mitigation owner and due task where a risk is material.
