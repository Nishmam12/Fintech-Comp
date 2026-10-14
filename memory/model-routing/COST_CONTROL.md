# Inference Cost Control

## Targets from handoff
- Workload target: 100,000 decisions/month.
- Monthly model API target: under $10.
- Application-controlled stop: $9.50; keep $0.50 unallocated buffer.
- Candidate allocation: primary $2.50; escalation $4.00; retries/overruns $2.00; evaluation $1.00. Revisit when actual traces arrive.

## Required design
- Per-provider/model and global monthly ledgers.
- Rate card versioned with source URL, access date, region, input-size tier and billing semantics.
- Max input and output token budgets per route.
- Estimate worst-case cost before dispatch and reserve that amount atomically.
- Reconcile against actual provider usage after the call; release unused reservation.
- Bounded retry/repair policy.
- Daily and monthly thresholds plus hard application stop.
- Tests for concurrent spend reservations so multiple requests cannot overshoot the application cap.
- A provider account-level limit if supported, but never assume it replaces the application ledger.

## Expected cost formula
`estimated_cost = input_tokens * input_price_per_token + billable_output_tokens * output_price_per_token + fixed_provider_fees_if_any`

Use exact provider token-usage fields and pricing semantics. If hidden reasoning tokens are separately billed or included in output tokens, model that explicitly. Cache pricing, batch discounts, promotions and peak/off-peak rates must be represented, not ignored.

## Failure behavior
If the system cannot reserve the worst-case cost within the remaining budget, do not dispatch the call. Use a valid deterministic path when possible; otherwise return pending/review. Do not auto-approve.

## Not a guarantee
100,000 calls under $10 is a testable economic target. It depends on prompt length, output length, escalation rate, retries, current provider rates and usage semantics. Report p50/p95 and observed cost, not just an average token-price calculation.
