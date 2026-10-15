# Team Onboarding — Budget Kernel

Repo: https://github.com/Nishmam12/Fintech-Comp · Deadline: **2026-10-20 17:00 BST** (see `memory/research/COMPETITION.md`).
Read `AGENTS.md` (rules for people **and** AI assistants) and `memory/WHO_IS_WORKING.md` before touching anything.

## 1. Set up (about 15 minutes)

You need: **Git** (with Git Bash on Windows), **uv** (https://docs.astral.sh/uv/), **Node 20+**.

```bash
git clone https://github.com/Nishmam12/Fintech-Comp.git
cd Fintech-Comp
git config user.name "<your GitHub name>"     # the presence board and commits use this
cp .env.example .env                           # then fill it in, see below
cd backend && uv sync
```

**`.env` (never commit it — it is gitignored):**
- `DATABASE_URL` — ask the lead for the password **privately** (not in the repo, not in group chat history you can't delete). Percent-encode special characters (`@` → `%40`). Remove any `[` `]` around it.
- `BK_TEST_SCHEMA=bk_test_<yourname>` — **use your own** (lowercase letters, digits, underscore). Every test run wipes its schema; two people sharing one will break each other's runs.
- `BK_ADMIN_TOKEN` — any long random string (your own, local).
- Model API keys are only needed if your task says so. Tests mock the providers.

**Check it works:** `uv run pytest tests/boundary tests/integration/test_db_connection.py -q` (should pass in under a minute).
The full suite takes about 7 minutes because the database is overseas (~60 ms per round trip): `uv run pytest -q -m "not slow"`. Run only the tests for the area you changed while developing.

**Using Claude Code or another AI assistant:** open the **repository root** (the folder containing `AGENTS.md`), never its parent folder, or the project's settings, agents and hooks will not load. On start you should see the team-presence printout.

## 2. How we work together

1. `git pull`, then read `memory/WHO_IS_WORKING.md`.
2. **Claim your task:** fill in *your own section only* (status ACTIVE, task ID, branch, paths), commit just that file as `claim: <name> <task-id>`, push to `main`. If the push is rejected, pull and re-check for overlap.
3. Work on a branch named `<name>/<task-id>-<slug>`. Never commit directly to `main` (the claim file is the only exception).
4. Open a pull request when your acceptance criteria are met **with test output**. The lead reviews and merges.
5. When you stop: set your status to IDLE/PAUSED/REVIEW and push.

**Hands off without lead review:** `backend/src/budget_kernel/kernel/`, `costledger/`, `db/`, and existing migrations. These are the security core; the tests there are the evidence for the judges. Ask first, and never edit an existing migration (add a new numbered one).

**Migration numbers are reserved to avoid clashes:** `003_*` = settlement (Member 3), `004_*` = lead. Ask before taking another number.

**Secrets:** never commit keys, passwords, private keys or real personal data. A test fails if a 64-hex string sits next to `PRIVATE_KEY`/`SECRET_KEY`.

**Definition of done:** acceptance criteria met, tests you added are passing (paste the output in the PR), and you updated nothing outside your claimed paths.

## 3. What is already built (all pushed)

| Area | Where | Notes |
|---|---|---|
| Deterministic kernel (mandates, delegation, authorize, release, settle, revoke) | `backend/src/budget_kernel/kernel/` | Only code allowed to change balances. 100+ tests. |
| HTTP API (FastAPI) | `backend/src/budget_kernel/api/` | Run: `cd backend && uv run uvicorn budget_kernel.api.app:app --reload`. Docs at http://localhost:8000/docs |
| Natural language to proposal | `backend/src/budget_kernel/{proposals,routing,providers}/` | The model output is untrusted. |
| Inference cost ledger | `backend/src/budget_kernel/costledger/` | $9.50/month stop. |
| Design decisions | `memory/decisions/ADR-0004 … 0007` | Read the ones for your task. |

**Trying the API locally:** create a human and an agent with `POST /admin/principals` (header `X-Admin-Token`), then follow `backend/tests/integration/test_agent_flow.py` — it is a working example of the whole flow.

## 4. Starting tasks

### Member 3 — BK-075: Testnet settlement adapter (Topic F, the on-chain evidence)
Read **`memory/decisions/ADR-0007-TESTNET-SETTLEMENT-ADAPTER.md`** first; it specifies the design.
- **Paths you own:** `backend/src/budget_kernel/settlement/`, `backend/migrations/003_settlement.sql`, `backend/tests/integration/test_settlement*.py`.
- **Step 1 (do first, report back before coding):** verify the Circle test-USDC contract address on Base Sepolia and the faucet limits from Circle's official docs; create a **new testnet-only** wallet; fund it with test ETH (gas) and test USDC. Put the private key in `.env` as `SETTLEMENT_PRIVATE_KEY` only. Record the contract address, chain ID and the wallet **address** (never the key) in `memory/research/SETTLEMENT.md`.
- **Step 2:** add `web3` to `backend/pyproject.toml`; implement the flow in ADR-0007: sign locally inside the `on_submit` hook of `kernel.settle_start` (it already exists), persist the raw transaction, broadcast **after** the commit, confirm, and a reconciler that re-sends the same bytes. Use `kernel.settle_confirm` / `kernel.settle_fail` with a **service-kind principal** (the kernel enforces this).
- **Security requirements (from the security review, `docs/SECURITY_SELF_ASSESSMENT.md` section 6, all required before merge):**
  1. Call `settle_fail` **only** with on-chain proof the transfer cannot land: a mined receipt with `status = 0`, or the nonce consumed by a different transaction. A timeout or mempool drop is not proof. Keep those `submitted` and re-broadcast. Calling `settle_fail` on a transfer that landed double-spends.
  2. Recipient → address mapping comes from a static, operator-controlled allowlist (config or migration), never from a request, proposal or model output. Refuse unknown recipients before signing.
  3. Integer conversion only (1 cent = 10,000 base units), USD only.
  4. Add `BK_SETTLEMENT_MODE` (`simulated` default | `testnet`). In `testnet` mode the simulated `POST /transactions/{id}/settle` returns 409, and `settle_start` is always called with your `on_submit` hook.
  5. `on_submit` signs and persists only. No network I/O, because it runs under the mandate lock.
- **Acceptance:** tests with a fake chain client for every crash window in ADR-0007 and for each requirement above; one real transfer on Base Sepolia with its **transaction hash** recorded (this is the competition's execution evidence); no key material in logs, DB or exceptions.

### Member 2 — BK-090: Dashboard (Next.js + TypeScript + Tailwind)
- **Paths you own:** `frontend/` only.
- **Backend you call:** the FastAPI app above (CORS is already allowed for http://localhost:3000). Read `backend/tests/integration/test_agent_flow.py` and `test_api.py` for exact requests.
- **Screens:**
  1. Sign in by pasting an API key (keep it in memory/session only).
  2. Mandate view: grant tree with available / reserved / settled per grant, status, expiry. `GET /mandates/{id}/state` (includes the invariant check result — show it prominently).
  3. Agent request box: free text to `POST /agent/request`; show the interpretation (route used, reasons, trail) **and** the kernel decision side by side.
  4. Review queue for the owner: held (`proposed`) transactions with approve/deny (`POST /transactions/{id}/review`).
  5. Budget meter from `GET /budget` (micro-USD → dollars) and a live audit feed from `GET /mandates/{id}/audit`.
  6. Attack-scenario panel: list from `GET /simulation/scenarios`, run with `POST /simulation/run` (human key only; 409 `SIMULATION_RUNNING` if one is already running). Show baseline vs kernel side by side, including `gave_up` and the invariant result.
- **Security requirement:** proposal fields, evidence quotes, reasons and audit details are untrusted text. Render them as plain text only: no `dangerouslySetInnerHTML`, no Markdown-to-HTML.
- **Acceptance:** every number on screen comes from the API (nothing hard-coded); works at phone width; screenshots in the PR. Do not add features beyond this list.

### Lead
Evaluation dataset and runner (BK-080), the intentionally unsafe baseline and attack scenarios (BK-070), the simulation endpoint, security self-assessment.

## 5. Who to ask
Anything touching the kernel, money rules, or merging: the lead. If blocked more than 30 minutes, write it in your section of `WHO_IS_WORKING.md` under *Notes / blockers* and ping the lead.
