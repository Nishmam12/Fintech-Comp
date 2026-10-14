# Evaluation Plan

**Status:** proposed. Do not report results until the runner executes against a versioned dataset.

## Evaluation questions
1. Can deterministic rules safely handle the truly unambiguous subset?
2. Does the primary model extract user intent and constraints correctly?
3. Does conditional escalation improve accuracy enough to justify its cost and latency?
4. Does the kernel preserve its financial-authority invariants under every defined adversarial test?
5. Can the system respect the monthly inference budget under concurrent API requests and provider failures?

## Initial dataset
Create 200+ curated scenarios initially, then expand. Use synthetic data for MVP. Each case should have a stable ID, scenario family, input, expected interpretation, known constraints, expected route/review label, kernel state fixture, expected authorization result, severity and notes. Separate training-like examples from the held-out evaluation set. No model-training work in current MVP.

## Families
- Structured valid proposal.
- Simple unambiguous natural language.
- Arithmetic, totals, fees, rounding and currency validation.
- Purchase comparisons and multiple constraints.
- Ambiguous instructions that require clarification.
- Contradictory constraints or missing required fields.
- Prohibited category, insufficient balance, protected reserve.
- Nested delegation and aggregate limits.
- Concurrency races, idempotency, duplicate retries and revocation.
- Prompt-injection attempts and model-generated authorization claims.
- Invalid JSON/schema, malformed types, huge input and out-of-distribution inputs.
- Provider timeout, rate limit and exhausted inference budget.

## Configurations to compare
A. Deterministic rules only.  
B. Primary model for eligible requests.  
C. Rules + primary + conditional escalation.  
D. Optional alternative provider or Jev only if a fair reproducible comparison is possible.

## Metrics
- Field-level and exact-match interpretation accuracy.
- Constraint adherence and arithmetic correctness (recomputed by code).
- Schema-valid output rate.
- Correct clarification/review rate.
- False-rejection rate and correct interpretation acceptance rate.
- Escalation rate and route reason distribution.
- p50/p95 latency.
- Tokens, retries, actual billed cost and cost per correct interpretation.
- Number of unauthorized approvals and invariant violations in kernel tests.
- Number of budget-cap violations in cost-ledger concurrency tests.

## Release gates
- No known invariant violation in the defined kernel test suite.
- Required authorization decision never comes from the model.
- All costs and evaluation metrics derived from actual logs, not hard-coded values.
- Held-out results remain separate from routing-threshold tuning.
- Document failures, confidence limitations and untested threat areas.
