# Budget Kernel — Detailed Master Project Plan

**Version:** 1.0  
**Planning date:** 2026-10-15  
**Status:** planning baseline; coding agent must reconcile against actual repo and competition rules.

## 1. Executive definition

Budget Kernel is a **budget-aware financial-decision pipeline with a deterministic authorization kernel and version-controlled, cross-model project memory**. It interprets natural-language financial instructions into structured proposals using selective inference, while deterministic transactional code remains solely responsible for authorization, delegated financial authority, reservations, settlement, release, revocation and audit.

The project is not a generic financial chatbot, an autonomous trading agent, or just a multi-provider API wrapper. Its technical value is the combination of:
- risk/complexity-sensitive use of inference instead of calling a model indiscriminately;
- typed proposal generation with explicit missing information and ambiguity;
- an authorization kernel that maintains financial invariants under concurrency and adversarial model output;
- a budget meter that reserves and reconciles API cost before/after calls;
- empirical evaluation of decision quality, escalation, cost per correct interpretation and authorization safety;
- a persistent shared repository memory system that lets Claude and GPT work across sessions without treating chat histories as canonical.

The exact novelty claim remains a hypothesis until prior art and competition criteria have been reviewed.

## 2. Requirements and priorities

### P0 — must work
- A model never approves, mutates or bypasses financial authorization.
- Every proposed transaction is checked against canonical mandate/grant/ledger state.
- No authority amplification through nested grants or concurrent calls.
- Correct handling of reservations, settlement, release, idempotency, expiry and revocation.
- Fail closed if intent is unresolved, schema is invalid, policy denies an action, or model budget/provider availability prevents safe interpretation.
- Every spend-affecting transition and authorization outcome has an audit record.
- Cost reservation/reconciliation prevents the application from intentionally dispatching calls above its configured $9.50/month stop.
- Shared memory is kept current across meaningful Claude/GPT sessions.
- Tests and observed results are reproducible.

### P1 — competition demo
- Working interface showing mandate, allocations, available/reserved/settled amounts, route selection, authorization result, budget meter and audit history.
- At least four adversarial demonstrations: concurrency, delegation amplification, revocation, replay/split limits.
- A separate intentionally unsafe baseline to demonstrate the failure of unprotected read-then-write authorization. The baseline must never be used by the secure path.
- Versioned set of at least 200 labeled synthetic cases for route/model evaluation.
- A transparent comparison of rules-only, primary-only and primary-plus-escalation.

### P2 — only after P0/P1
- Better visualization, property-based testing, extra provider comparisons, signed grants, OpenRouter/GLM/Jev experiments.
- Consent-aware decision-trace collection design.
- Model fine-tuning research. Training data collection and training itself are explicitly deferred.

## 3. Non-goals
- Real money movement, bank or card integration, production financial advice, credit decisions or regulatory claims.
- A general multi-agent orchestration platform.
- Full multi-currency accounting in MVP.
- Blockchain/smart contract execution as a dependency.
- Fine-tuning or training model weights during the competition sprint.
- Collecting personal financial information just in case it becomes useful later.
- Claiming universal security or novelty based on a small test suite.

## 4. Design principles
1. **Deterministic authority:** only kernel code may authorize and mutate financial state.
2. **One source of truth:** persistent transactional DB for live account/ledger state; repo Markdown for project knowledge.
3. **Fail closed, not fail open:** uncertainty, budget exhaustion or provider failure never causes auto-approval.
4. **Atomicity:** policy check and state mutation must use appropriate transaction isolation/locking/conditional updates.
5. **Least privilege:** a child receives only transferred authority within the parent's available authority and applicable scopes.
6. **Idempotent APIs:** repeated transport-level requests cannot duplicate allocations or settlements.
7. **Measured routing:** use cost/risk/difficulty criteria validated against labels, not arbitrary confidence or hard quotas.
8. **Budget integrity:** reserve worst-case API cost before dispatch and reconcile after the call.
9. **Privacy by default:** synthetic test inputs; avoid unnecessary personal data; keep secrets outside Git and memory.
10. **Memory as engineering:** every meaningful task changes the code and the corresponding durable project state, not only chat messages.

## 5. Domain model and invariant

### Core entities
- `Mandate`: total authority, currency, protected reserve, validity, allowed purposes/categories, root status.
- `Grant`: agent identity, parent grant, current available authority, constraints, expiry, status and revocation ancestry.
- `TransactionProposal`: untrusted structured interpretation of requested action; never contains trusted authorization state.
- `Reservation`: amount held for a transaction until settlement/release/expiry policy applies.
- `Transaction`: lifecycle state and references to grant, idempotency key/payload hash and reservation.
- `AuditEvent`: append-only record of proposals, policy outcomes and successful state transitions.
- `InferenceUsage`: route/provider/model, request ID, usage/tokens, cost estimate/reconciliation, retries and result category (data-minimized).
- `BudgetReservation`: pre-call cost reservation against monthly/provider/model allocation.

### Required accounting logic
For a single-currency mandate, ensure each unit of authorized funds is represented exactly once as settled spend, outstanding reservation, or available authority. Delegation transfers authority; it does not create it. Parent unallocated balance and descendant balances must not both count the same authority in aggregate. Protected reserve is not spendable by ordinary agents.

Before implementation, choose and document one canonical accounting representation in an ADR. Do not implement multiple competing representations of remaining budget.

### Transaction lifecycle
Proposed initial lifecycle: `proposed -> reserved -> settled` or `proposed -> rejected`, with `reserved -> released` when a transaction validly fails/cancels. Define idempotent behavior for repeated settle/release calls and what happens when grants are revoked after reservation but before simulated settlement. Settled funds are not magically restored because authorization is later revoked.

### Concurrency and revocation
A grant, ancestor status, effective scope and available balance must be checked from authoritative state within the serialization boundary for the action. Revocation must invalidate descendants for new authorization. Policy choice is needed for unexecuted reservations: cancel/release them or mark them blocked pending review. Decide before implementing.

## 6. System architecture

### 6.1 Intake and normalization
- Accept typed proposals and natural-language instructions.
- Set input limits, validate types and reject malformed envelopes.
- Minimize external-provider context; avoid sending identifiers and unnecessary financial text.

### 6.2 Deterministic fast path
- Apply only where the input is structured or completely resolvable by explicit tested rules.
- Do not force an 80% no-inference quota.
- Record why inference was bypassed when useful for evaluation.

### 6.3 Model router
- Rules-based, reproducible and provider-independent.
- Uses task class, missing fields, conflict signals, schema/semantic validation errors, known hard-case patterns, budget state and bounded retry state.
- Self-reported model confidence is only a logged feature until empirically calibrated.

### 6.4 Primary and escalation provider adapters
- Candidate starting point: Qwen Flash via direct Alibaba API for primary; DeepSeek Flash via direct API for escalation.
- Optional controlled comparison: GLM/OpenRouter and potentially Jev if available and justified.
- Re-check exact model IDs, regions, token tiers, structured-output support, billing semantics and live price rates at implementation time.
- Pin model/provider versions where possible and log the exact route used.
- Enforce bounded timeout/retry/output tokens and server-side credentials.

### 6.5 Typed proposal contract
The schema should include request type, candidate action, integer amount/minor units, currency, category/recipient/purpose when relevant, constraints, evidence references/spans, missing fields, ambiguities, conflicts, human-review requirement, prompt/schema version and explanation for the UI. It must not expose a trusted field like `authorized=true`.

### 6.6 Deterministic authorization kernel
Validate the proposal against mandate/grant state, global and sub-allocation caps, protected reserve, category/merchant/purpose scope, expiry, ancestor revocation, cumulative limits, idempotency, reservations and current balance. Rejections are final for that proposal; a model may generate a revised proposal but the new proposal needs a new authorization check.

### 6.7 Cost meter
- Global monthly stop: $9.50; $0.50 buffer below the $10 target.
- Initial suggested allocation: $2.50 primary, $4.00 escalation, $2.00 retries, $1.00 evaluation. Adjust based on evidence.
- Reserve worst-case cost atomically before dispatch.
- Reconcile estimated and actual billed usage, including thinking/reasoning tokens according to the provider's billing model.
- Test concurrent cost reservations and cap enforcement.
- On budget exhaustion, preserve deterministic processing for already valid structured requests; otherwise return review/unresolved. Never auto-approve.

### 6.8 Audit, UI and simulation
- UI displays backend results only.
- Store route, version, decision reason, latency, token usage and cost, but minimize raw request retention.
- All payments are simulated.
- Demo runner must reset fixtures and replay scenarios deterministically.

## 7. API proposal

- `POST /mandates`: create root mandate.
- `POST /grants`: transfer/delegate available authority.
- `POST /transactions/authorize`: validate proposal and reserve atomically.
- `POST /transactions/{id}/settle`: settle reserved simulated transaction.
- `POST /transactions/{id}/release`: release reservation according to state policy.
- `POST /grants/{id}/revoke`: revoke and invalidate descendant authority according to documented semantics.
- `GET /ledger/state`: authoritative balances and invariant check.
- `GET /audit`: chronological events.
- `POST /simulation/run`: run named attack scenario and return measured outcome.
- Optional `POST /interpret`: call route/model and return an untrusted proposal only; this endpoint never authorizes.

Existing repo conventions may alter endpoint naming, but not the trust boundary.

## 8. Evaluation

### Minimum scenario dataset
At least 200 versioned synthetic cases initially. Include simple structured requests, ordinary natural-language interpretation, totals/fees/arithmetic, missing data, conflicting constraints, clarification cases, protected reserve, insufficient funds, nested delegation, race conditions, idempotency, revoked ancestors, injection, invalid JSON, timeouts, provider budget exhaustion and out-of-distribution cases.

### Configurations
A. Deterministic rules only.  
B. Primary model only for eligible cases.  
C. Rules + primary + conditional escalation.  
D. Optional alternative/aggregator/Jev only if fair and reproducible.

### Metrics
- Field/exact-match correctness for interpretation.
- Constraint extraction and arithmetic correctness (arithmetic recomputed deterministically).
- JSON/schema validity and correction retry frequency.
- Proper clarification/review rate; false rejection/acceptance of interpretations.
- Escalation share and reasons.
- p50/p95 latency, exact model/provider, input/output/reasoning token usage and billed cost.
- Cost per correct interpretation.
- Kernel unauthorized approvals and invariant violations.
- Cost-budget invariant violations.

Never invent performance or cost data. Report dataset version, scenario IDs, prompt/schema/model versions, dates and test command. A zero-violation test result is scoped to the tested suite, not a proof of universal security.

## 9. Persistent project memory and shared IDE

### Canonical system
The repo's version-controlled Markdown is the shared project memory for both Claude and GPT/Codex. Agent-specific conversation memory is not authoritative. Obsidian is optional and should open this same repository root as a vault; do not maintain a separate copy.

### Files
- `AGENTS.md`: concise common agent operating contract.
- `CLAUDE.md`: Claude-specific entry file referencing common rules.
- `memory/INDEX.md`: note map and wikilinks.
- `memory/CURRENT_STATE.md`: verified snapshot, status, blockers and last tests.
- `memory/TASK_BOARD.md`: active/backlog/blocked/done tasks with acceptance criteria.
- `memory/NEXT_ACTIONS.md`: next 1–5 executable actions.
- `memory/DECISION_REGISTER.md` + `memory/decisions/ADR-*.md`: lasting decisions and their status.
- `memory/architecture/`: system model and threat model.
- `memory/model-routing/`: provider choices, policy and cost controls.
- `memory/evaluation/`: evaluation plan/results.
- `memory/research/PRIOR_ART.md`: sourced claims and novelty research.
- `memory/logs/CHANGELOG.md` and `SESSION_LOG.md`: concise factual history.

### Synchronization contract
Before task: check Git status; read memory index/current state/task board/next actions; read relevant detail notes. After meaningful task: run tests; inspect diff; update task status, current state, next actions, change log, session log and affected design notes; record ADRs when decisions change. If interrupted, write a `MEMORY UPDATE INCOMPLETE` item. Do not store private chain-of-thought, secrets or raw financial data.

### Claude and GPT roles
Use one writer at a time for shared code and canonical notes. Recommended pattern: Claude implements a well-scoped task; GPT reviews read-only and develops adversarial test cases; the writer resolves findings and updates memory. Swap roles when useful. If parallel editing is necessary, use separate Git worktrees/branches and merge carefully. Shared files are the memory protocol, not a license for concurrent writes.

### Obsidian
Use internal wikilinks among decisions, tasks, architecture, risks and evaluation notes; Graph View helps navigation and reveals orphan notes. It does not automatically improve model reasoning or inject all notes into every prompt. Agents must read the needed files explicitly.

## 10. Privacy and future learning data

Model training is deferred. The MVP can log minimal operational metadata needed for security, debugging, evaluation and cost control. Use synthetic scenario fixtures in tests. Do not collect real financial statements merely to prepare for future training.

Before any later user-data collection, create a separate privacy/data-governance design with informed consent, data minimization, retention/deletion, redaction, access control, separation of operational/audit data from eligible training examples, provenance/labels, and provider-transfer analysis. A successful transaction is not automatically a correct label. Fine-tune only after a high-quality reviewed dataset and held-out baseline exist.

## 11. Milestones and gates

### M0 — Reconnaissance and competition verification
Inspect current repo/branch/diff, dependencies, runtime and official event requirements. **Gate:** repo facts and submission timeline recorded; useful code preserved.

### M1 — Security design
Define threat model, canonical budget representation, grant/descendant semantics, transaction state machine, reservation/revocation policy and API schemas. **Gate:** ADRs accepted, no contradictory accounting rules.

### M2 — Deterministic kernel
Implement mandate/grant/ledger functions, authorization, idempotency, atomic reservation/settlement/release/revocation and audit events. **Gate:** unit/integration/concurrency tests pass; accounting invariant checked after state transitions.

### M3 — Cost ledger and proposal schema
Implement typed proposal validation and internal API-cost ledger with reservation/reconciliation. **Gate:** invalid model output cannot reach authorization; concurrent model-cost reserves cannot overrun the app cap in tests.

### M4 — Provider adapters and routing
Integrate primary + escalation through provider-independent interfaces, pinned model IDs and safe failure handling. **Gate:** mocked and live smoke tests; exact usage captured; no secret leaks; route reasons logged.

### M5 — Evaluation runner
Create 200+ labeled synthetic scenarios, naive isolated baseline, reproducible configuration comparison and cost/error reporting. **Gate:** dataset/version and actual results saved; no hardcoded metrics.

### M6 — Dashboard and demo
Show state, routes, proposals, policy decisions, audit, cost meter, and named adversarial scenarios. **Gate:** clean-start demo uses real backend state.

### M7 — Submission hardening
Security review, setup instructions, known limitations, demo recording/script, verify category/deadline requirements. **Gate:** all critical tests and clean-start run recorded.

### Deferred — learning/fine-tuning
Design consent-aware data capture and training/evaluation workflow later; only proceed when data quality and privacy review justify it.

## 12. Suggested short-sprint priority
If time is extremely limited, deliver M0, M1, M2, the minimum of M3/M4 needed for one end-to-end example, then M5 and a minimal M6 demo. Cut dashboard decoration, extra providers and model training before weakening atomicity, invariants or reproducibility.

## 13. Completion reporting
Every meaningful work session ends with: task ID/status, summary of changes, changed files, commands/tests and actual results, known defects/untested paths, decision links, memory files synchronized, and next 1–5 actions. A task is not complete merely because code was generated.
