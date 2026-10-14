# Budget Kernel — Shared Agent Instructions

## Mission
Build Budget Kernel as a cost-aware financial-decision pipeline with a deterministic authorization boundary. The model can interpret and propose; only deterministic application code using authoritative state can authorize, reserve, settle or reject a transaction.

## Before work
- Read `memory/INDEX.md`, `memory/CURRENT_STATE.md`, and `memory/TASK_BOARD.md`.
- Read only the domain documents relevant to the task. Do not load the entire memory vault for a small change.
- Inspect the working tree and existing code before editing. Preserve useful work.
- For significant tasks, create/update an execution plan with scope, acceptance criteria, tests, risks and rollback notes.

## Hard constraints
- Never allow an LLM, router, confidence score, provider outage or budget exhaustion to override a deterministic authorization rejection.
- Treat all model outputs as untrusted proposals. Validate schema and semantics server-side.
- Keep authorization, balances, reservations, grants, revocation and accounting in deterministic code and a transactional source of truth.
- Use integer minor currency units; no floating-point money.
- Make reservation/allocation mutations atomic; test concurrent calls, retries, idempotency and revocation races.
- All payments are simulated. No live bank integration or movement of real funds in the MVP.
- Do not add infrastructure or dependencies without a demonstrated requirement.
- Do not store secrets or raw sensitive financial data in project memory, logs, training sets, test fixtures or Git.
- Do not make model training a current milestone. Preserve a clean future path for reviewed, consent-aware datasets, but defer training work.

## Shared memory is part of the deliverable
- Before finishing a meaningful task, update the relevant task status, `memory/CURRENT_STATE.md`, `memory/CHANGELOG.md`, and `memory/NEXT_ACTIONS.md`.
- Update or create an ADR when an architectural decision is made or changed; distinguish proposed, accepted, superseded and rejected decisions.
- Update tests/evaluation notes with observed results only. Never claim a test passed unless it was run and its output was checked.
- Record concise durable conclusions and evidence, not hidden chain-of-thought or raw model transcripts.
- If a memory update cannot be completed, report that explicitly and leave a TODO.

## Definition of done
A task is not done because code was generated. It is done when its acceptance criteria are met, applicable tests were run, failures are reported, and the persistent project state accurately reflects the result.

## Collaboration
Only one agent should edit shared source files and canonical memory files at a time. Another agent may perform a read-only review and provide precise findings. Never overwrite another agent's uncommitted work. Check `git status` and inspect diffs before editing and before committing.

## Project map
- `memory/INDEX.md`: navigation map.
- `memory/CURRENT_STATE.md`: concise source-of-truth status snapshot.
- `memory/TASK_BOARD.md`: tasks and acceptance criteria.
- `memory/DECISION_REGISTER.md` and `memory/decisions/`: architecture decisions.
- `memory/architecture/`: design and trust boundaries.
- `memory/model-routing/`: provider/routing/budget decisions.
- `memory/evaluation/`: test scenarios, datasets and evaluation results.
- `memory/research/`: sourced prior art and competition research.
- `memory/logs/`: append-only session/change summaries.
- `docs/`: longer implementation plans and threat model.
