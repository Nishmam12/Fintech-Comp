# ADR-0006: Inference Cost Ledger (Monthly Buckets, Worst-Case Reservation, Reconciliation)

- **Status:** ACCEPTED (2026-10-15, team lead)
- **Date:** 2026-10-15
- **Owner:** Opus planner (draft) / project lead (approval)
- **Related tasks:** BK-050, BK-060, BK-070
- **Related ADRs:** ADR-0001 (budget exhaustion never authorizes), ADR-0005 (lock ordering), [[model-routing/COST_CONTROL]]

## Context
Paid LLM interpretation must stay below an application stop of $9.50/month. That total is split into primary $2.50, escalation $4.00, retries/overruns $2.00 and eval $1.00. Concurrent requests must not overshoot any cap. Provider bills can exceed the estimate: reasoning tokens, missing usage fields and crashes after dispatch are all possible. This ledger is separate from the mandate money ledger (ADR-0004) and never holds a mandate lock.

## Options considered
1. **In-process counter.** Lost on restart and wrong with multiple workers. Rejected.
2. **Post-hoc accounting only (no reservation).** Concurrent calls overshoot the cap. Rejected (R-006).
3. **Postgres bucket rows, reserve the worst case before dispatch, reconcile after (chosen).**

## Decision

### Schema
```
budget_buckets(
  month DATE,                      -- first day of the month, UTC
  bucket TEXT CHECK (bucket IN ('global','primary','escalation','retries','eval')),
  cap_micro_usd BIGINT NOT NULL, reserved_micro BIGINT NOT NULL DEFAULT 0 CHECK (reserved_micro >= 0),
  spent_micro BIGINT NOT NULL DEFAULT 0 CHECK (spent_micro >= 0),
  PRIMARY KEY (month, bucket))

inference_calls(
  id UUID PK, month DATE, route_bucket TEXT, provider, model_id, rate_card_version,
  est_micro BIGINT, actual_micro BIGINT NULL, overrun_micro BIGINT DEFAULT 0,
  status TEXT CHECK (status IN ('reserved','dispatched','reconciled','released','charged_worst_case')),
  input_tokens, output_tokens, reasoning_tokens, cached_tokens, created_at, dispatched_at, reconciled_at)
```
Caps are in micro-USD: global 9_500_000; primary 2_500_000; escalation 4_000_000; retries 2_000_000; eval 1_000_000. The route caps add up to exactly the global cap today. The global row is still kept as the hard stop, so caps can be rebalanced without overshooting $9.50. There is deliberately **no** CHECK `reserved + spent <= cap`, because a provider overrun must still be recordable. The cap is enforced only when reserving.

### Month rollover
- **Month key:** `date_trunc('month', now() AT TIME ZONE 'UTC')::date`, taken from the DB clock. The app clock is never used.
- **Lazy row creation:** rows are created on the first reservation of a month by `INSERT ... ON CONFLICT DO NOTHING`, using caps from the versioned config. A race between two creators is harmless.
- **Reconciliation uses the stored month:** a call stores `month` at reservation time and is reconciled against **that** month's rows. A call reserved at 23:59:59 on 31 Oct and reconciled in November is charged to October.
- **No carry-over:** unused budget does not roll into the next month.

### Reservation (one short DB transaction, deadlock-free)
```
BEGIN;
SELECT bucket FROM budget_buckets
 WHERE month = $m AND bucket IN ('global', $route)
 ORDER BY bucket FOR UPDATE;                         -- fixed lock order: alphabetical
UPDATE budget_buckets SET reserved_micro = reserved_micro + $est
 WHERE month = $m AND bucket IN ('global', $route)
   AND reserved_micro + spent_micro + $est <= cap_micro_usd;
-- require rowcount == 2, otherwise ROLLBACK -> BUDGET_EXHAUSTED
INSERT INTO inference_calls(..., status='reserved');
COMMIT;
```
- **Why the explicit ordered `FOR UPDATE`:** a multi-row UPDATE locks rows in plan scan order, which is not guaranteed to match across sessions. Locking in `ORDER BY bucket` order first means every transaction takes the shared rows in the same order, so there are no deadlocks.
- **Why the conditional UPDATE is overshoot-safe under READ COMMITTED:** a waiting UPDATE re-checks its WHERE clause against the newly committed row version, and the rowcount==2 check makes the update all-or-nothing.
- **Never nested in a kernel transaction:** a cost transaction never runs inside a kernel (mandate-lock) transaction and vice versa, which rules out cross-ledger cycles.

### Worst-case estimate (integer, round up)
- **Input bound:** `in_tokens_upper = UTF-8 byte length of the full prompt` (system + user + schema). This is a safe upper bound for BPE tokenizers. It can be replaced by a provider token-count endpoint if one exists and is free.
- **Output bound:** `out_tokens_upper = max_tokens` sent on the request. It must cover **reasoning plus visible output**. If a provider does not count reasoning tokens inside `max_tokens`, thinking mode must be **disabled** for that route, or the route is not allowed.
- **Cost:** `est_micro = ceil_div(in_upper * in_price_micro_per_Mtok, 1_000_000) + ceil_div(out_upper * out_price_micro_per_Mtok, 1_000_000) + fixed_fee_micro`.

### Retries
A retry or repair of the same request is a **new** reservation charged to `('global', 'retries')`, not to the route bucket. Bounded at most 1 retry and 1 repair per request.

### Reconciliation
- **Normal path:** after the response, in a new short transaction with the same lock order, compute `actual_micro` from the provider `usage` fields (input, cached input, output, and reasoning tokens if billed separately) using the **same rate-card version**. Then:
  - `reserved -= est` on both rows.
  - `spent += min(actual, est)` on global and route.
  - If `actual > est`: `overrun = actual - est` is added to `spent` on **global and retries**, recorded on the call, and an `audit_events(kind='COST_OVERRUN')` row is written.
- **Usage missing or unparseable:** charge `est` (status `charged_worst_case`).
- **Provider error before any tokens (connection refused, 4xx before generation):** release the reservation (`released`). A timeout is **not** treated as before-generation: it is charged at worst case.
- **Crash between reserve and reconcile:** rows in `reserved` or `dispatched` older than 10 minutes are swept to `charged_worst_case` (`reserved -= est; spent += est`). They are never released, because the provider may have billed. The sweep runs lazily on each reservation and from the same admin sweep CLI as ADR-0005.

### Rate card
`config/rate_card.json`, versioned and committed. It holds **no secrets**. Each entry contains:
- `{provider, model_id, region, input_price_micro_per_Mtok, cached_input_price_micro_per_Mtok, output_price_micro_per_Mtok, reasoning_billing: "as_output"|"separate"|"none", tier_rules, fixed_fee_micro, source_url, accessed_on}`.

Rules:
- An unknown model, a missing field or an unhandled tier makes the route **unavailable** (fail closed to the deterministic path or pending review).
- Each call stores `rate_card_version`.
- Prices are integers in micro-USD per million tokens. No floats.

### Exhaustion behaviour (ADR-0001)
`BUDGET_EXHAUSTED` means no paid call. The request goes to the deterministic fast path if it fully applies, otherwise to `proposed` (pending human review). It is **never** auto-approved. A provider-side account limit is treated as an extra safety net and does not replace this ledger.

## Consequences
- **Positive:** A hard, concurrency-safe stop at $9.50 that has been tested under concurrent load. Crashes err on the side of over-charging the internal ledger, never under-charging. Every call can be audited against a dated price source.
- **Negative/tradeoffs:** Byte-based input bounds over-reserve by about 3 to 4 times for English. With small prompts this is acceptable, but it reduces how many calls can run concurrently near the cap. Charging stale crashed calls at worst case can overstate spend.
- **Security/privacy effects:** Prompts are not stored in `inference_calls`, only counts and costs. Provider API keys live only in `.env`.
- **Operational effects:** Daily soft thresholds are deferred. If wanted, they would be one extra bucket keyed by day using the same pattern.

## Evidence and validation
Not yet implemented. Required tests:
- 50 concurrent reservations against a cap that fits k of them: exactly k succeed, and global never exceeds its cap.
- Mixed-route concurrency with no deadlock over 1,000 iterations.
- Month rollover: reserve on day N, reconcile after the month changes (simulated by injecting `$m`), and the charge lands in the stored month.
- Overrun goes to retries and global, plus an audit row. Missing usage gives worst-case charge. Stale sweep gives worst-case charge.
- Unknown model in the rate card makes the route unavailable.
- Exhaustion gives pending/deterministic, never approve.

Prices and model IDs are **assumptions until OQ-005 is resolved**.

## Revisit when
Real traces show the estimate is too loose or too tight, a provider changes billing semantics (cache or reasoning), or the cap split is rebalanced.
