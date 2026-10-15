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
