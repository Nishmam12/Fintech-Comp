# Budget Kernel: a safe wallet for AI agents

AI agents can propose payments, but **only a deterministic kernel can authorize them**. A human owner funds a mandate, delegates narrower grants to agents, and every spend is checked against live database state: scope, per-transaction limit, balance, expiry and the whole revocation chain. Language models never decide anything. Their output is parsed into an untrusted, strictly typed proposal, and anything unclear is held for a human.

*2026 Shenzhen FinTechathon, International Track, Topic F: Agent Wallet with testnet settlement.*

## What it does
- **Mandate → grants.** Delegation moves funds from parent to child. Scope can only narrow, expiry can only shorten, and depth is capped. Authority is transferred, never created.
- **Concurrency-safe.** One Postgres transaction per operation, serialized by a per-mandate row lock, with conditional updates as a second line of defense. Ledger invariants (conservation, reservation backing, settlement backing, movement-log reconciliation) are checked in tests after every step and exposed in the API.
- **Safe retries.** Idempotency keys are bound to the payload. A replay returns the stored decision.
- **Natural-language requests.** Deterministic fast path first (free), then a cheap model, then a stronger one only for defined failure classes. Every paid call reserves its worst-case cost in a monthly budget ledger first. Exhausted budget means "unresolved", never "approved".
- **Attack demo.** The same attacks run against an intentionally unsafe baseline and the real kernel, with measured results.
- **Testnet settlement (Topic F).** The kernel reserves, then a settlement service sends a Base Sepolia USDC transfer and records the transaction hash (in progress, see ADR-0007).

## Documents
| | |
|---|---|
| Security self-assessment (tiers, controls, known risks) | [`docs/SECURITY_SELF_ASSESSMENT.md`](docs/SECURITY_SELF_ASSESSMENT.md) |
| Measured results (kernel scripts, evaluation, attacks) | [`memory/evaluation/RESULTS.md`](memory/evaluation/RESULTS.md) |
| Architecture decisions | [`memory/decisions/`](memory/decisions) (ADR-0004 accounting, 0005 concurrency, 0006 cost ledger, 0007 settlement) |
| Competition requirements and checklist | [`memory/research/COMPETITION.md`](memory/research/COMPETITION.md) |

## Quick start
Requirements: Python 3.12, [uv](https://docs.astral.sh/uv/), a Postgres database (we use Supabase, session pooler on port 5432).

```bash
cp .env.example .env                  # then fill in DATABASE_URL and BK_ADMIN_TOKEN (model keys are optional)
cd backend
uv sync
uv run python -m budget_kernel.db.migrate            # creates the "bk" schema (BK_SCHEMA)
uv run uvicorn budget_kernel.api.app:app --port 8000
```

Interactive API docs are at `http://localhost:8000/docs`.

### Replay the demo (no model keys needed)
With the API running:
```bash
uv run --project backend python scripts/demo.py             # people, mandate, delegation, requests, revocation, invariants
uv run --project backend python scripts/demo.py --attacks   # plus the baseline-vs-kernel attack scenarios
```
It creates fresh principals and a fresh mandate on every run, so it can be replayed any number of times. It exits 0 only if every expectation held.

### Tests
```bash
cd backend
BK_TEST_SCHEMA=bk_test_<yourname> uv run python -m budget_kernel.db.migrate --test
BK_TEST_SCHEMA=bk_test_<yourname> uv run pytest -q -m "not slow"
```
- Tests run against a real Postgres schema that is **truncated at the start of each run**. Use your own `BK_TEST_SCHEMA` and never run two pytest sessions on the same schema.
- `-m slow` adds the long property-based state-machine test.
- Some tests take about a minute because every kernel operation makes several round trips to the hosted database.

### Evaluation
```bash
cd eval
uv run --project ../backend python make_dataset.py              # deterministic dataset (seed 20261015)
uv run --project ../backend python runner.py --config offline   # kernel scripts + recorded-output gate + rules-only config A
uv run --project ../backend python runner.py --config B         # live models: needs DASHSCOPE_API_KEY (C also needs DEEPSEEK_API_KEY)
```
Results are written to `eval/results/<date>/`. See [`eval/README.md`](eval/README.md).

## Deployment
1. **Database.** Create a Supabase project (or any Postgres 15+). Put the **session pooler** URL (port 5432) in `DATABASE_URL`. Do not use the transaction pooler (port 6543). The kernel relies on `SET LOCAL` and row locks inside one transaction.
2. **Schema.** Run `uv run python -m budget_kernel.db.migrate`. It is forward-only and idempotent. Do not expose the schema through Supabase's REST API. The `anon` and `authenticated` roles must have no access, and the tables have row-level security enabled with no policies.
3. **Secrets.** Set these on the server only, never in the browser or the repository: `DATABASE_URL`, `BK_ADMIN_TOKEN`, optional model keys (`DASHSCOPE_API_KEY`, `DEEPSEEK_API_KEY`, `OPENROUTER_API_KEY`) and, for settlement, `SETTLEMENT_PRIVATE_KEY` (a testnet-only wallet).
4. **Run.** `uv run uvicorn budget_kernel.api.app:app --host 0.0.0.0 --port 8000`, behind a TLS proxy. Set `BK_CORS_ORIGINS` to the dashboard's origin.
5. **Rate limiting.** The API limits requests itself (`api/ratelimit.py`): 120 per minute per principal (per client IP when not authenticated), plus a separate 30 per minute bucket for `POST /agent/request` and `POST /interpret`, which cost real money. `/health` is exempt. A limited call gets HTTP 429, code `RATE_LIMITED` and a `Retry-After` header. Tune with `BK_RATE_DEFAULT_PER_MIN` and `BK_RATE_MODEL_PER_MIN` (0 turns a bucket off). **The limiter is per process:** with several replicas the effective limit is multiplied by the replica count (a shared store is future work). `X-Forwarded-For` is ignored unless `BK_TRUST_PROXY=1`; set that only behind a proxy that appends the real client address, because the last entry is then used as the client IP.
6. **Bootstrap.** Create principals with `POST /admin/principals` and the `X-Admin-Token` header. Each API key is shown once and stored only as a SHA-256 hash.

## Repository layout
```
backend/src/budget_kernel/
  kernel/       the only code that changes balances (ops, funds, sweep, invariants)
  api/          FastAPI layer: authentication, strict request schemas, error mapping
  proposals/    untrusted proposal schema and deterministic semantic checks
  routing/      fast path, model routing, interpret-then-decide
  providers/    OpenAI-compatible adapter for Qwen / DeepSeek / OpenRouter
  costledger/   monthly inference-budget reservation and reconciliation
  simulation/   attack scenarios; naive_baseline/ is the deliberately unsafe comparison
backend/migrations/   plain SQL, applied in name order
backend/tests/        integration, concurrency, boundary (import-graph and secret scans)
eval/                 labelled dataset, runner, dated results
scripts/demo.py       clean-start replay
memory/, docs/        decisions, plans, results, submission documents
```
The kernel never imports model, routing or provider code, and only `simulation/` may import the unsafe baseline. Both rules are enforced by tests in `backend/tests/boundary/`.

## Working on this repo
**Team members: read [`ONBOARDING.md`](ONBOARDING.md) first**, then [`AGENTS.md`](AGENTS.md) (Claude Code also reads [`CLAUDE.md`](CLAUDE.md)). Claim your task on [`memory/WHO_IS_WORKING.md`](memory/WHO_IS_WORKING.md) before you start, and update [`memory/TASK_BOARD.md`](memory/TASK_BOARD.md) when you finish. Keep API keys, credentials and real financial data out of the repository.

## Status and limits
This is a hackathon prototype on testnet. It has not been externally audited and must not hold real funds. The known limitations (for example, per-transaction limits can be split into smaller purchases) are listed in the security self-assessment.
