# Current State — Budget Kernel

**Last verified:** 2026-10-15 (starter-kit creation; repository implementation not yet inspected by a coding agent)  
**Overall status:** `KERNEL BUILT / API + PROPOSAL LAYER NEXT`  
**Implementation status:** deterministic kernel (mandate, delegate, authorize, release, settle start/confirm/fail, revoke, lazy expiry sweep, invariants I1–I3) implemented on Supabase Postgres. No API, cost ledger, providers, router, settlement adapter or UI yet.

## One-paragraph project summary
Budget Kernel is a financial-decision pipeline with (1) selective, cost-aware model routing for interpreting natural-language financial requests into typed proposals, and (2) a deterministic authorization kernel that independently enforces mandates, delegated authority, spending limits, reservations, revocation, idempotency and auditability. LLMs never authorize transactions. All MVP transactions are simulated.

## Requirements currently treated as accepted
- Deterministic code is the only authority for approval/rejection and ledger mutation.
- Delegated authority must not be amplified through nested grants or concurrent requests.
- Maintain a target workload of 100,000 decisions/month and an API budget below $10/month, with an application stop at $9.50 and $0.50 unallocated buffer. These are targets to validate, not proof of actual economics.
- Start with a rules-based fast path, a low-cost primary interpretation model, and conditional escalation; the 80% no-inference / 18% primary / 2% escalation split is a hypothesis only.
- Provider/model IDs and prices must be re-verified against official sources before implementation/deployment.
- Model-training is a future phase. Do not build training pipelines in the MVP.
- Claude and GPT/Codex are used in the same IDE; version-controlled repo files are the shared cross-model memory.
- Obsidian is optional and should point to the project repository as a vault, not create a disconnected duplicate.

## Proposed starting stack (not yet implemented or locked)
- Backend: Python, FastAPI, Pydantic.
- Authoritative data store: PostgreSQL with transactions/conditional updates/locking; SQLite only for a locally constrained prototype with demonstrated serialized write behavior.
- Frontend: Next.js App Router, TypeScript, Tailwind CSS.
- Tests: pytest; add property-based concurrency/state-machine testing where useful.
- Candidate model routes: Alibaba Qwen Flash primary; DeepSeek Flash escalation; optional GLM/OpenRouter comparison. Verify exact model IDs, endpoints and prices first.

## Active agent handoff
See [[AGENT_HANDOFF]]. No implementation writer/reviewer has been assigned in the target IDE workspace yet.

## Current milestone status
| Milestone | Status | Evidence / note |
|---|---|---|
| M0 — Repository and event requirements inspection | DONE | Repo = Nishmam12/Fintech-Comp; rules in [[research/COMPETITION]]; Supabase DB reachable. |
| M1 — Threat model, state machine and invariants | DONE (design) | ADR-0004..0007 ACCEPTED. Threat model still to be refreshed against them. |
| M2 — Deterministic ledger and authorization tests | DONE (pending planner review) | 65 tests pass: 46 behaviour, 12 concurrency races, 5 static boundary, 2 DB connectivity. |
| M3 — Typed proposal schema and provider adapters | PLANNED | No implementation verified. |
| M4 — Budget-aware router and provider cost ledger | PLANNED | No implementation verified. |
| M5 — Adversarial evaluation and baseline comparison | PLANNED | No results yet. |
| M6 — Dashboard, repeatable demo and documentation | PLANNED | No working UI verified. |
| M7 — Post-MVP data collection/fine-tuning research | DEFERRED | Not part of current build. |

## Active blockers / unknowns
- Actual repository tree, existing implementation and package manager have not been inspected in the target IDE workspace.
- Competition dates, submission requirements and judging criteria must be verified before prioritizing deliverables.
- Provider account availability, region, exact model IDs, pricing and billing semantics must be verified from official sources.
- Need to confirm what database is available in deployment environment.
- Need to decide exact grant/revocation/reservation semantics in an ADR before implementing them.

## Last verified tests
`cd backend && uv run pytest -q` → **65 passed in 277 s** (2026-10-15, bk_test schema on Supabase session pooler). Scope of that claim: the listed scenarios only, not a proof of general security. Not yet covered: property-based state machine, API layer, cost ledger, settlement.
Measured: DB round trip ~60 ms from the dev machine, so a kernel op holds the mandate lock ~0.6 s (~1.5 ops/s per mandate). Deployed next to the DB it should be much faster. See ADR-0005 section 2.

## Next action
Run the Phase 0 repository reconnaissance in [[docs/MASTER_PLAN]] and update this file with actual repository evidence. Do not assume the status above still applies after the first implementation pass.
