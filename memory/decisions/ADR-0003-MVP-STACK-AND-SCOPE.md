# ADR-0003: Proposed MVP Stack and Scope

- **Status:** ACCEPTED (2026-10-15). Amended: database is Supabase Postgres; the "no blockchain" exclusion is lifted for the testnet settlement adapter only, see ADR-0007.
- **Date:** 2026-10-15
- **Owner:** Project owner / implementation agent

## Context
The prototype needs reliable transactional accounting, an API layer, model adapters and a clear web demonstration on a short competition timeline.

## Options considered
- Python/FastAPI + PostgreSQL + Next.js: strong Python backend and transaction semantics, clear separation and user familiarity.
- All-in-one or distributed microservices: either faster initial UI but weaker control over domain invariants, or more deployment overhead than the MVP needs.

## Proposed decision
Start with a modular monolith: Python + FastAPI + Pydantic, PostgreSQL as authoritative store, Next.js App Router + TypeScript + Tailwind for the UI, pytest for tests. Use SQLite only if deployment constraints require it and concurrency behavior is explicitly serialized and tested. Simulated transactions only. No Redis, Kafka, Kubernetes, live bank integration, blockchain, or model training in MVP unless later evidence warrants scope change.

## Consequences
Fewer moving parts, easier testing and clearer correctness claims. Requires careful database transaction design and a clean domain/API boundary.

## Evidence and validation
Confirm the existing repository/runtime before locking the implementation stack. This ADR is proposed and may be adjusted to preserve existing working code.

## Revisit when
Repository inspection shows a strong existing stack, target deployment imposes constraints, or a measurable need for another component appears.
