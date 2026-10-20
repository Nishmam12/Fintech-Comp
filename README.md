# Budget Kernel: a safe wallet for AI agents

AI agents can propose payments, but **only a deterministic kernel can authorize them**. A human owner funds a mandate, delegates narrower grants to agents, and every spend is checked against live database state: scope, per-transaction limit, balance, expiry and the whole revocation chain. Language models never decide anything. Their output is parsed into an untrusted, strictly typed proposal, and anything unclear is held for a human.

*2026 Shenzhen FinTechathon, International Track, Topic F: Agent Wallet with testnet settlement.*

## What it does
- **Mandate → grants.** Delegation moves funds from parent to child. Scope can only narrow, expiry can only shorten, and depth is capped. Authority is transferred, never created.
- **Concurrency-safe.** One Postgres transaction per operation, serialized by a per-mandate row lock, with conditional updates as a second line of defense. Ledger invariants (conservation, reservation backing, settlement backing, movement-log reconciliation) are checked in tests after every step and exposed in the API.
- **Safe retries.** Idempotency keys are bound to the payload. A replay returns the stored decision.
- **Natural-language requests.** Deterministic fast path first (free), then a cheap model, then a stronger one only for defined failure classes. Every paid call reserves its worst-case cost in a monthly budget ledger first. Exhausted budget means "unresolved", never "approved".
- **Attack demo.** The same attacks run against an intentionally unsafe baseline and the real kernel, with measured results.
- **Testnet settlement (Topic F).** The kernel reserves, then a settlement service sends a Base Sepolia USDC transfer to an operator-allow-listed address and records the transaction hash. Two kernel-approved payments and one anchor of the audit history are on chain (`evidence/SETTLEMENTS.md`). Every audit and movement row is hash-chained; `GET /mandates/{id}/integrity` recomputes the chain.
- **Dashboard.** A Next.js app (`frontend/`) over the real API: mandate cheque with history seal, who may spend, decisions as proposal beside verdict, Ask, Review, Activity, Attack lab, Settings. Full-bleed, scales with the screen, phone layout included.

## Documents
| | |
|---|---|
| Submission pack index (the six deliverables and where each lives) | [`docs/submission/PACK.md`](docs/submission/PACK.md) |
| Technical document | [`docs/submission/TECH_DOC_DRAFT.md`](docs/submission/TECH_DOC_DRAFT.md) |
| Deck | [`docs/submission/DECK_DRAFT.md`](docs/submission/DECK_DRAFT.md) |
| Execution evidence (settlements, anchor, hashes) | [`evidence/SETTLEMENTS.md`](evidence/SETTLEMENTS.md) |
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

### Dashboard
People sign in with a username and password (agents and operators with an API key). Public sign-up is off by default; set `BK_ALLOW_SIGNUP=1` on the API to show "Create account", or create people with `POST /admin/accounts` (admin token). A new account has no money: the dashboard walks them through funding a mandate, adding agents and giving them budgets.

With the API running (`BK_SETTLEMENT_MODE=simulated BK_ALLOW_SIGNUP=1` for a local demo; add `BK_SCHEMA=bk_dev` to keep it off your main schema):
```bash
uv run --project backend python scripts/demo_seed.py   # seeds a mandate for Nabil (username nabil, password kernel-demo-2026), Ops bot, Research bot; writes frontend/.env.local
cd frontend && npm install && npm run dev               # http://localhost:3000, one-tap sign-in per demo account
npm run check:layout                                    # layout check at 1366, 1920, 2560, 1024 and 390 px (needs the above running)
npm run check:flow                                      # the demo story through the UI (agent asks, owner approves, breaker, reinstate, revoke)
npm run check:login                                     # sign-up, setup, sign-in, wrong password, password change (API needs BK_ALLOW_SIGNUP=1)
```
The demo sign-in buttons exist only in development builds; a production build contains no key. The demo owner's password is a demo value for a testnet prototype (override with `BK_DEMO_PASSWORD`).

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
uv run --project ../backend python runner.py --config B         # live models: needs DASHSCOPE_API_KEY (C also needs DEEPSEEK_API_KEY, or OPENROUTER_API_KEY with BK_ESCALATION_PROVIDER=openrouter)
```
Results are written to `eval/results/<date>/`. See [`eval/README.md`](eval/README.md).

## Deployment
1. **Database.** Create a Supabase project (or any Postgres 15+). Put the **session pooler** URL (port 5432) in `DATABASE_URL`. Do not use the transaction pooler (port 6543). The kernel relies on `SET LOCAL` and row locks inside one transaction.
2. **Schema.** Run `uv run python -m budget_kernel.db.migrate`. It is forward-only and idempotent. Do not expose the schema through Supabase's REST API. The `anon` and `authenticated` roles must have no access, and the tables have row-level security enabled with no policies.
3. **Secrets.** Set these on the server only, never in the browser or the repository: `DATABASE_URL`, `BK_ADMIN_TOKEN`, optional model keys (`DASHSCOPE_API_KEY`, `DEEPSEEK_API_KEY`, `OPENROUTER_API_KEY`) and, for settlement, `SETTLEMENT_PRIVATE_KEY` (a testnet-only wallet).
4. **Worker (optional).** `BK_WORKER=1` starts a housekeeping thread inside the API process every `BK_WORKER_INTERVAL` seconds (default 30): settlement and anchor reconcile (testnet mode), cost-ledger stale sweep, and the kernel sweep for due mandates. It authorizes nothing. For payment reconcile set `BK_WORKER_PRINCIPAL` to a service principal that owners have bound as settler; without it only anchors, the sweeps and ticks run.
5. **Run.** `uv run uvicorn budget_kernel.api.app:app --host 0.0.0.0 --port 8000`, behind a TLS proxy. Set `BK_CORS_ORIGINS` to the dashboard's origin.
6. **Rate limiting.** The API limits requests itself (`api/ratelimit.py`): 120 per minute per principal (per client IP when not authenticated), plus a separate 30 per minute bucket for `POST /agent/request` and `POST /interpret`, which cost real money. `/health` is exempt. A limited call gets HTTP 429, code `RATE_LIMITED` and a `Retry-After` header. Tune with `BK_RATE_DEFAULT_PER_MIN` and `BK_RATE_MODEL_PER_MIN` (0 turns a bucket off). **The limiter is per process:** with several replicas the effective limit is multiplied by the replica count (a shared store is future work). `X-Forwarded-For` is ignored unless `BK_TRUST_PROXY=1`; set that only behind a proxy that appends the real client address, because the last entry is then used as the client IP.
7. **Bootstrap.** Create principals with `POST /admin/principals` and the `X-Admin-Token` header. Each API key is shown once and stored only as a SHA-256 hash.

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
scripts/demo.py       clean-start replay; demo_seed.py seeds the dashboard demo accounts
frontend/             Next.js dashboard (components/ui = shared layout parts, scripts/ = layout checks)
evidence/             on-chain evidence: settlements, anchor, hashes
memory/, docs/        decisions, plans, results, submission documents
```
The kernel never imports model, routing or provider code, and only `simulation/` may import the unsafe baseline. Both rules are enforced by tests in `backend/tests/boundary/`.

## Working on this repo
**Team members: read [`ONBOARDING.md`](ONBOARDING.md) first**, then [`AGENTS.md`](AGENTS.md) (Claude Code also reads [`CLAUDE.md`](CLAUDE.md)). Claim your task on [`memory/WHO_IS_WORKING.md`](memory/WHO_IS_WORKING.md) before you start, and update [`memory/TASK_BOARD.md`](memory/TASK_BOARD.md) when you finish. Keep API keys, credentials and real financial data out of the repository.

## Status and limits
This is a hackathon prototype on testnet. It has not been externally audited and must not hold real funds. The known limitations (for example, per-transaction limits can be split into smaller purchases) are listed in the security self-assessment.
