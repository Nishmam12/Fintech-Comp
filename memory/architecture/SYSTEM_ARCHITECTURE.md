# System Architecture

**Status:** proposed; must be reconciled with actual code before implementation.

## Responsibilities
1. **Request intake/normalization:** accepts structured proposals or user instructions; validates size, format and permissible fields.
2. **Deterministic fast path:** handles inputs that can be processed using explicit, tested rules. It does not infer missing intent.
3. **Router:** decides whether an interpretation model is needed and whether escalation criteria are met. The router never authorizes transactions.
4. **Provider adapters:** call pinned model IDs with bounded timeouts/tokens/retries and record usage. Provider-specific details remain outside domain logic.
5. **Proposal schema/validator:** treats model output as untrusted; checks schema, types, currency, arithmetic invariants and required evidence fields.
6. **Human review state:** represents ambiguity or policy-required review as pending; review does not bypass kernel checks.
7. **Authorization kernel:** checks root mandate, grant tree, available authority, reserve, category/scope, expiry, revocation and limits.
8. **Transactional ledger:** applies grant transfers and reservation/settlement/release state changes atomically.
9. **Cost ledger:** reserves worst-case estimated inference cost, reconciles actual usage, enforces model/provider and monthly caps.
10. **Audit/evaluation:** preserves decision metadata, authorization reasons, route selection, token usage, test results and scenario identifiers, subject to data-minimization policy.
11. **UI/simulation:** allows judges to reproduce benign and adversarial scenarios; all state and results come from the backend.

## Trust boundary
Models, prompt contents, retrieved examples and user-provided instructions are untrusted inputs. A model result can only enter through the proposal-validation interface. It cannot call internal ledger mutations or set trusted `authorized=true` state. Only the kernel can issue an authorization decision and execute a state transition.

## Core invariant
For one single-currency mandate, each unit of authority must be counted exactly once:

`original authorized budget = settled spending + outstanding reservations + all currently available unspent authority`

Protected reserve is part of the original budget but is not included in ordinary agent-available authority. The chosen representation must prevent parent grants and descendants from being double-counted.

## Initial stack proposal
- Backend: Python, FastAPI, Pydantic.
- Database: PostgreSQL; transactional writes/row locks/conditional updates. SQLite may be used for a serialized local demo only if its behavior is proven and the limitation documented.
- Frontend: Next.js App Router, TypeScript, Tailwind CSS.
- Testing: pytest, integration tests against real transaction semantics, and property-based tests if time permits.
- Payments: simulated only.

## Proposed API surface
- `POST /mandates`
- `POST /grants`
- `POST /transactions/authorize`
- `POST /transactions/{id}/settle`
- `POST /transactions/{id}/release`
- `POST /grants/{id}/revoke`
- `GET /ledger/state`
- `GET /audit`
- `POST /simulation/run`

Adapt this list to existing repository structure, but maintain the same responsibilities and security boundary.
