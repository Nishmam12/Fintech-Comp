# Evaluation Results

Only numbers produced by `eval/runner.py` appear here, each with its dataset version, commit and command.
Raw per-case output (including every failure) is committed under `eval/results/`.

## Run 1 — offline sections (no API keys), 2026-10-15
- **Dataset:** `eval/datasets/v1`, 206 synthetic cases, sha256 `eacf79821e5d…` (131 text, 25 gate, 50 kernel). Seed 20261015.
- **Command:** `cd backend && uv run python ../eval/runner.py --config offline` (result file: `eval/results/2026-10-15/offline-all-020559.json`).
- **Database:** Supabase Postgres, schema `bk_eval`, wiped at the start of the run.

| Section | Result |
|---|---|
| **Kernel scripts** (50 cases, 134 steps: protected reserve, limits, scope widening, nested delegation, split purchases, revocation, idempotency, permissions, review) | **134/134 steps as expected; 0 unauthorized approvals; 0 invariant violations** (I1, I2, I3, I5 checked after every step) |
| **Gate** (25 recorded model outputs through validation, grounding, escalation, fail-closed logic) | **25/25** as expected. Measures the pipeline logic, **not** model quality. |
| **Text, config A — rules only** (131 cases) | 51/131 correct (38.9%). 44 handled by the deterministic fast path (33.6%), all 44 with exact field match. **0 unauthorized approvals, 0 wrong-value approvals.** 44 requests that needed a model failed closed (no approval). |

### How to read config A
Config A deliberately has no model, so everything that is not the canonical sentence or structured JSON ends as "unresolved". The 38.9% is therefore a *coverage* number for the rules, not an accuracy claim about the system. The safety result (nothing approved that should not have been) is the meaningful part.

### Not yet measured
- **Configs B and C (primary model; primary + escalation)** need `DASHSCOPE_API_KEY` and `DEEPSEEK_API_KEY`; the runner skips them and says so. No numbers have been invented. Until they run there is **no evidence** about model interpretation accuracy, escalation rate, latency, token use or cost per correct interpretation.
- The held-out split (`split: heldout`, 30% of cases) is not reported separately yet; no routing thresholds have been tuned on this data.

### Limitations
- Cases are synthetic and written by the same team as the system; they will not cover everything a real user writes.
- A zero-violation result is scoped to these 50 scripts, the 65+ unit/race tests and the random-sequence test; it is not a proof of general security.
- Sequential scripts do not exercise concurrency; races are covered separately in `backend/tests/concurrency/`.

## Run 2 — attack scenarios: unsafe baseline vs kernel, 2026-10-15
- **Command:** `cd backend && uv run python ../eval/run_simulations.py` (result: `eval/results/2026-10-15/simulations-021245.json`, commit recorded inside).
- Each scenario runs the same attack against the intentionally unsafe read-then-write baseline (`naive_baseline/`, never imported by the secure path) and against the real kernel, on Postgres.

| Scenario | Baseline | Kernel |
|---|---|---|
| Concurrent overspend (8 racers x 30,000 vs 90,000) | **violated** (overspent; balance went negative) | held: 3 of 8 approved, 90,000 of 90,000 reserved, invariants hold |
| Delegation amplification (6 racers x 30,000 from a 90,000 parent) | **violated** (children exceeded the parent) | held: 3 children, 90,000 of 90,000 |
| Revoked ancestor (grandchild after its parent was revoked) | **violated** (grandchild still spent) | held: rejected `GRANT_REVOKED` |
| Replay / duplicate delivery (same request x 5) | **violated** (debited more than once) | held: 1 transaction |
| Revocation race (revoke vs 6 in-flight spends) | **not reproduced in this run** (timing-dependent) | held: 0 live reservations on the revoked grant |
| Split purchases (informational) | n/a | **limitation, disclosed:** a 30,000 request is refused by the per-transaction limit, but 5 requests of 10,000 are approved; total spend is still capped by the grant balance (50,000). Per-transaction limits are not velocity limits. |

Notes on honesty:
- The revocation race against the baseline depends on timing; one run did not reproduce it. The deterministic *revoked ancestor* scenario is the reliable demonstration of the same class of failure.
- The kernel side retries a retryable `KERNEL_BUSY` answer as a real client would; the number of retries is part of the recorded metrics (`busy_retries`).
- Scenarios use keyless simulation identities and a fresh mandate per run, so they cannot touch user data.

## Run 3: cost of the ADR-0008 controls (2026-10-15)
Script: `eval/measure_latency.py`; raw file `eval/results/2026-10-15/latency-042150.json`. 25 sequential `authorize` calls per grant, hosted Postgres (about 60 ms per round trip), schema `bk_eval`, no contention.

| Grant | Median | p95 | Min | Max |
|---|---|---|---|---|
| Plain (no window, no threshold) | 1089 ms | 1322 ms | 1078 ms | 1610 ms |
| Window + threshold set (neither triggers) | 1136 ms | 1189 ms | 1129 ms | 1189 ms |

- Added cost of evaluating a window and a threshold: **+47 ms median** (about one extra round trip for the subtree sum). The ADR-0008 target was under 100 ms.
- A whole `authorize` call takes about 1.1 s end to end on this database. That is the full call, not only the time the mandate lock is held. Operations on one mandate are serialized, so throughput per mandate is roughly one operation per second here; different mandates run in parallel.
- Sample size is small (25 per arm) and the p95 and max values are noisy; treat the median as the figure.

## Run 4: live config B, Qwen only (2026-10-16)
Model `qwen3.7-flash-2026-07-15` (DashScope international, non-thinking), `temperature 0`, escalation **off**. Rate card `2026-10-15.1`. Text cases only (131 per dataset). Raw files in `eval/results/2026-10-15/`. The runs executed on a working tree on top of commit `7c37a99`; the changes were committed afterwards together with these files.

| Step | Dataset | Prompt | Correct | Unauthorized approvals | Wrong-value approvals | Safe misses (failed closed) | Cost |
|---|---|---|---|---|---|---|---|
| 4a first live run | v1 (seed 20261015, sha `eacf79821e5d`) | v1 | 92/131 (70.2%) | 0 | 0 | 30 | 3,329 micro-USD |
| 4b after fixing two output quirks | v1 | v2 | 106/131 (80.9%) | **1** | **1** | 12 | 2,702 |
| 4c after grounding recipient and category | v1 | v2 | 106/131 (80.9%) | 0 | 0 | 13 | 2,700 |
| 4d fresh dataset, nothing tuned on it | v2 (seed 20261016, sha `b3f76ea2f21b`) | v2 | 108/131 (82.4%) | 0 | 0 | 12 | 2,685 |

For comparison, rules-only config A: 51/131 (38.9%), 0 unauthorized, 0 wrong-value (Run 1). Each live run made 84 model calls (the other 47 cases were answered by the free rules path); end-to-end latency p50 about 3.9 s, p95 about 5.5 s; no cost overrun in any run.

### What went wrong in 4b, and the fix
- Step 4a failed mostly for two reasons that had nothing to do with safety: the model wrote `explanation` text longer than 300 characters (rejected as `INVALID_SCHEMA`), and it listed the optional `purpose` as a "missing field" (so complete requests were held as `INCOMPLETE`).
- Fixes (prompt `interpret-v2` plus clipping a display-only field and ignoring `purpose` as a missing field) raised accuracy, **but exposed a real gap**: for "Pay github $80" (no category given) the model inferred `category = tools` six times out of six, and the pipeline approved it because that category is inside the grant's scope. That is the 1 unauthorized and 1 wrong-value approval in 4b.
- The gap: the amount was checked against the text, but the recipient and category were not. **Fix:** for a complete proposal, both names must occur in the user's text as whole words, otherwise the request is held for human review (and is not escalated, because a bigger model cannot make a missing word appear). Result in 4c and 4d: 0 and 0.
- Cost of the stricter rule: it holds some requests that name a merchant by an alias (for example "Amazon Web Services" for `aws`). Those become human reviews, not approvals. One natural-language case on v1 was held for this reason.

### Remaining misses (all fail closed)
- `arithmetic_fees` 0/12 and `conflicting` 0/6 on both datasets. These families are meant to be resolved by the stronger escalation model (config C). With escalation off they end `unresolved` or held for review, which is the safe outcome but counts as a miss. Config C has **not been run** (no DeepSeek key yet).
- Number words ("forty dollars") are not recognised by the amount check and end `unresolved`.

### Caveats (read before quoting these numbers)
- The 4b and 4c fixes were chosen after reading the failures on v1, so v1 numbers after 4a are tuned. v2 was generated after the fixes and not inspected before its run, so 4d is the fairer estimate.
- v2 uses the same case generator and phrasing templates with a different seed (different names and amounts), so it is not an independent test set. A real held-out set written by someone else would be stronger.
- One run per setting, 131 cases: differences of a few cases are noise.
- All data is synthetic.

## Run 5: live config B after number-word and alias grounding (2026-10-17)
Same setup as Run 4 (model `qwen3.7-flash-2026-07-15`, non-thinking, `temperature 0`, escalation **off**, rate card `2026-10-15.1`), on the merged `main` (Step 8: number words with a currency word, operator alias file; Phase 3 kernel changes). Raw files in `eval/results/2026-10-17/`.

| Dataset | Correct | Unauthorized approvals | Wrong-value approvals | Safe misses (failed closed) | Cost | Run 4 for comparison |
|---|---|---|---|---|---|---|
| v1 (seed 20261015) | 106/131 (80.9%) | 0 | 0 | 13 | 2,720 micro-USD | 106/131 |
| v2 (seed 20261016) | 107/131 (81.7%) | 0 | 0 | 12 | 2,708 micro-USD | 108/131 |

Latency end to end: p50 about 4.2 s, p95 about 6.1 s (v1) and 5.9 s (v2). 84 model calls per dataset, no escalation, no cost overrun.

### What this shows, and what it does not
- **No gain on these datasets, and no harm to safety.** Both datasets are generated from templates that write amounts in digits and use the recipient's own name, so number words and aliases never occur in them; they cannot show Step 8's effect. The 2-point-per-run variation is model noise, not a Step 8 effect.
- **The one difference** is one new miss on v2: `TEX-094` (family `ambiguous`) ended `unresolved` with `INCOMPLETE_WITHOUT_MISSING_FIELDS`, a reason produced from the model's own output; it still fails closed (no decision). One run per setting at 131 cases cannot tell a flip like this from noise (temperature 0 is not fully deterministic across runs).
- **Step 8's effect, measured separately** (7 live requests through the same model, `eval`-style, not a scored dataset): "Pay forty dollars to aws for cloud" and "...one hundred and twenty dollars to github for software" resolved to `ok` with amounts 4000 and 12000 (in Run 4 a word amount ended `unresolved`); "Pay Amazon Web Services $40" and "...forty dollars" resolved to `ok` with recipient `aws`; "pay Amazon $40" (a fragment, not a listed alias) went to `needs_review` with no recipient; "pay forty for aws cloud" (no currency word) ended `unresolved` (`AMOUNT_UNGROUNDED`). The unit tests in `backend/tests/unit/test_grounding.py` (38) cover the edge cases without any model. This probe is 7 cases: it shows the mechanism works, not an accuracy rate.

### A regression found by the offline run, and its cause (not a kernel bug)
The first offline run on the merged tree reported the kernel scripts at **124/134 steps (44/50 cases) with 2 "unauthorized approvals"**, down from 134/134 and 0. Cause: the evaluation runner (`eval/runner.py`) predates mandate-bound settlement (BK-303) and never bound its service principal to the mandates it creates, so every settlement step was refused with `FORBIDDEN`. The "unauthorized" count was a cascade: in `KER-042` `settle_start` was refused, the transaction stayed reserved, and the later `release` succeeded where a conflict was expected. Fix: the runner now binds `svc` as settler on each kernel-case mandate (the normal deployment). Re-run: **kernel 50/50 cases, 134/134 steps, 0 unauthorized approvals, 0 invariant violations** (`kernel-all-043748.json`). The first offline file (`offline-all-042907.json`) is kept as the record of the failing run. Rules-only config A (51/131) and the gate (25/25) were unchanged.

### Caveats (unchanged from Run 4, plus)
- v2 is not an independent test set (same generator, different seed). One run per setting. All data is synthetic.
- Config C (escalation model) has still **not been run** (no DeepSeek key).
