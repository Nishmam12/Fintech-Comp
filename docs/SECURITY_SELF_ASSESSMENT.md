# Security Self-Assessment: Budget Kernel (Agent Wallet, Topic F)

**Version:** 2026-10-20 (draft 3; independent review passes on 2026-10-14, 15, 17 and 20, see section 9)
**Scope:** `backend/` (kernel, API, interpretation, cost ledger, simulation, settlement adapter, hash-chained history and anchor, circuit breaker, rate limiting and key lifecycle, background worker) and the dashboard in `frontend/`
**Not covered:** the dashboard (rebuilt as UI revision 3 on 2026-10-19) was reviewed for the controls in section 6 (plain-text rendering, key held in memory only, no HTML sinks, https-only explorer links, demo keys absent from production builds: checked on 2026-10-20) and layout-tested at 390 to 2560 px, but not audited line by line. Nothing here has had an external audit.

---

## 1. Summary

The Budget Kernel lets AI agents spend from a human's budget without the AI ever being able to authorize a payment. It is built on four rules:

1. **Language models only propose.** Natural-language requests become a strictly typed, untrusted *proposal*. The schema has no authorization fields and rejects unknown keys.
2. **One deterministic kernel decides.** Every money decision is recomputed from database state, inside one Postgres transaction, under a per-mandate row lock. The kernel never imports model, routing or provider code, and a boundary test enforces this.
3. **Authority can be transferred but never created.** Delegation moves funds from a parent grant to a child grant. Scope can only narrow, expiry can only shorten, and revocation reaches every descendant.
4. **Every unclear outcome fails closed.** Ambiguity, suspected injection, an invalid model output, a provider failure, an exhausted inference budget or a busy database all lead to "held for human review", "unresolved" or "retry". None of them ever leads to an approval.

**Measured evidence** (details in section 5):
- **Kernel script evaluation:** 134 of 134 steps correct, 0 unauthorized approvals, 0 invariant violations.
- **Interpretation, rules-only configuration A:** 0 unauthorized approvals and 0 wrong-value approvals across 131 text cases.
- **Interpretation, live model:** configuration B (Qwen, Run 5) 106/131 on dataset v1 and 107/131 on a fresh dataset v2; configuration C (Qwen with escalation to DeepSeek V4.1 Flash, Run 6) 113/131 on both. 0 unauthorized and 0 wrong-value approvals in every final run (synthetic data, one run per setting).
- **Test suite:** 366 tests passed plus the slow property-based state machine, which checks the accounting invariants after every step (Run 7, 2026-10-19).
- **On-chain evidence:** two kernel-approved payments and one anchor of the audit history on Base Sepolia, each checked over the public RPC (`evidence/`).
- **Attack scenarios against an intentionally unsafe baseline:** six scenarios; five broke the baseline (the revocation race is timing-dependent and did not reproduce), and the kernel held in all of them, re-confirmed from a clean start on the frozen build (Run 7).

**Known limits:**
- Per-transaction limits can be split into several smaller purchases. Velocity limits exist but are opt-in per grant (R1).
- The settlement service is a powerful principal: it is now bound per mandate by the owner (R2), but within a bound mandate it can confirm any transfer, and there is one operator hot wallet (R5).
- A database superuser can rewrite an un-anchored history (R20); the hash chain makes edits detectable, not impossible.
- Throughput is serialized per mandate: about one authorization every 2.3 s on the hosted database used here (about 115 ms per round trip; R6).

Section 7 lists all known risks.

---

## 2. Trust boundaries

```
 untrusted                         | deterministic, authoritative               | external
 ----------------------------------+--------------------------------------------+-------------------
 user text, documents              |                                            |
 LLM output (Qwen / DeepSeek)  --> | proposal schema (extra=forbid)             |
 router / fast path            --> |   + semantic checks (grounding, injection) |
                                   |        |  plain values only                |
 API caller (bearer API key)   --> | KERNEL: lock mandate -> sweep -> check     |
                                   |   path, scope, limits, balance             |
                                   |   -> conditional UPDATE -> audit           |
                                   |        |  'submitted' + signed raw tx       |
                                   | settlement service (on_submit hook)    --> | Base Sepolia (testnet USDC)
```

- **What the kernel accepts:** only primitives (amount as an integer in minor units, currency, recipient, category, idempotency key). The model's proposal is stored only for display.
- **What the kernel rejects:** an actor who is not the grant holder, an expired or revoked grant anywhere on the path, an out-of-scope recipient or category, an amount over the per-transaction limit, and insufficient available funds. A payload that reuses an idempotency key with different content is also rejected.
- **What the database enforces independently of the code:**
  - CHECK constraints (no negative balances; transaction states are limited to the defined set)
  - uniqueness of (grant, idempotency key)
  - append-only triggers on the ledger movement and audit tables
  - a trigger that makes grant structure immutable
- **Database exposure:** Supabase's public `anon` and `authenticated` roles have no schema usage and no table grants on the kernel schemas. This was checked on 2026-10-15 for `bk_test` and `bk_eval`, and must be re-checked once the production schema `bk` is migrated. The API connects as a server-side role, and no database credential reaches the browser.

---

## 3. Permission tiers

| Tier | Who | Can | Cannot | Enforced in |
|---|---|---|---|---|
| **Admin (bootstrap)** | Holder of `BK_ADMIN_TOKEN` (operator) | Create principals and issue their API keys (returned once, stored as SHA-256) | Make any money decision. Admin is not a principal and has no grant. | `api/auth.py` `require_admin` (constant-time compare) |
| **T0: human owner** | `kind = human` principal that created the mandate | Create mandates; hold the root grant; delegate; revoke any grant in the mandate; approve or deny held proposals; run the *simulated* settlement path; run attack simulations | Approve a proposal the current state would refuse (approval re-runs every check); declare a settlement failed | `kernel.create_mandate` (`OWNER_MUST_BE_HUMAN`), `review` (`NOT_OWNER`), `_require_manager`, `_require_settler(owner_allowed=…)` |
| **T1: delegating holder** | Any principal holding a grant with `can_delegate = true` | Delegate a sub-grant with ≤ its available funds, ⊆ its scope, ≤ its expiry, depth ≤ 4; revoke grants *below* it; spend within its own scope | Widen scope, extend expiry or create funds; revoke its own grant or an ancestor's | `kernel.delegate` (`_delegation_problem`), `revoke` (`allow_self=False`) |
| **T2: leaf holder** | Agent holding a grant with `can_delegate = false` | Request spends within scope and per-transaction limit; release its own reservations | Delegate; spend from any grant it does not hold; spend after any ancestor is revoked or expired | `kernel.authorize` (`NOT_GRANT_HOLDER`, `_path_problem`, `_authorize_problem`) |
| **S: settlement service** | `kind = service` principal (the testnet adapter) | Move `reserved → submitted → settled`; declare `submitted → released` only with a failure proof | Create, approve or resize spends; delegate; revoke | `kernel._require_settler` |
| **No tier** | LLMs, router, fast path, provider adapter, cost ledger, simulation baseline | Produce a proposal or a cost record | Call any kernel write; carry authority fields (schema forbids them) | `proposals/schema.py` (`extra="forbid"`), boundary tests (import graph, single writer) |

**Policy note.** The interpretation layer marks a request `needs_review` when it is ambiguous, ungrounded or looks injected. In that case the kernel records a `proposed` transaction that holds **no funds** until the owner approves it. This protects an honest agent against bad interpretation. It is **not** a control against a malicious grant holder, who can call `POST /transactions/authorize` with structured values directly. Against a malicious holder, the guarantee is the grant's scope, per-transaction limit, balance and (when set) velocity window and approval threshold (`review_above`, ADR-0008). The threshold is enforced inside the kernel on the lowest value along the delegation path, so it holds even when the holder calls the authorize endpoint directly; the mandate owner is exempt because the owner is the approver.

---

## 4. Controls mapped to threats

| Threat | Control | Evidence |
|---|---|---|
| Concurrent requests overspend a shared balance | Per-mandate `SELECT … FOR UPDATE`; conditional `UPDATE … WHERE available >= amount`; CHECK `available >= 0` | `tests/concurrency/test_races.py`; scenario `concurrency_overspend` |
| A child grant exceeds its parent; siblings together exceed the parent | Delegation debits the parent under the lock; the debit is conditional | `test_kernel.py`, `test_races.py`; scenario `delegation_amplification` |
| A revoked or expired ancestor leaves a descendant live | Full-path status and expiry check under the lock; revocation reclaims the whole subtree and releases its reservations | `test_kernel_hardening.py`; scenarios `revoked_ancestor`, `revocation_race` |
| Retry or duplicate delivery debits twice | `UNIQUE(grant_id, idempotency_key)` + payload hash; replay returns the stored decision; a different payload under the same key gets 409 + audit | `test_kernel.py`; scenario `replay_duplicate` |
| Illegal state transitions (double settle, release after settle) | Each transition is guarded by a conditional `UPDATE … WHERE state = …`; terminal states replay | `test_state_machine.py` (Hypothesis state machine, invariants checked every step) |
| Split purchases; large spends without the owner | Velocity window over the grant subtree, checked on every grant on the path under the lock; approval threshold = lowest `review_above` on the path (owner exempt); held requests hold no funds; at most 20 pending reviews per grant (ADR-0008) | `test_velocity_threshold.py` (incl. 8 racing spends vs a window); scenario `split_purchases` (plain vs windowed grant); state-machine test with the new fields |
| Expiry seen late because of lock wait | Clock read *after* the lock (`clock_timestamp()` → `ctx.now`), never SQL `now()` | `test_kernel_hardening.py` |
| Prompt injection / "ignore your rules" | Request text sent as delimited data; regex injection flag → human review (never escalated); model has no authority fields | `test_interpret.py`; gate cases (25/25) |
| Model-inferred recipient or category (found by the live evaluation) | A complete proposal must name its recipient and category in the user's own text (whole words), else it is held for human review and not escalated | `test_interpret.py` (inferred category, inferred recipient, word-boundary cases); config B runs 4c and 4d |
| Hallucinated or altered amounts | Deterministic grounding: the amount must appear in the text, or be a sum of 2–3 amounts or a stated percentage of them; otherwise escalate, then review | `proposals/validate.py`; `test_interpret.py`; config A results |
| Invalid, truncated or oversized model output | Strict JSON schema; `finish_reason=length` treated as invalid; input capped at 2,000 chars | `test_interpret.py` |
| Runaway inference spend | Worst-case reservation on global + route buckets before dispatch (one conditional UPDATE); reconcile from usage; stale calls charged at worst case; overruns audited | `test_cost_ledger.py` (concurrent cap test) |
| Inference budget exhausted mid-request | Ends in `unresolved`; never reaches the kernel | `test_interpret.py`, `test_agent_flow.py` |
| Agent mints its own authority | Only `human` principals can create mandates | `test_api.py` (`OWNER_MUST_BE_HUMAN`) |
| Crash between kernel commit and on-chain broadcast | Nonce pre-assigned and raw signed tx persisted inside the same DB transaction as `submitted` (`on_submit` hook); broadcast after commit; reconciler re-broadcasts | ADR-0007; `settle_start` docstring. Adapter tests are pending in BK-075 |
| Database outage or lock contention | Lock timeout 3 s, statement timeout 5 s → `KernelBusy` (retryable with the same key) | `kernel/tx.py`; `busy_retries` and `gave_up` reported by every concurrent scenario |
| Secret leakage | `.env` gitignored; API keys stored hashed; boundary test scans for secrets | `tests/boundary/test_boundaries.py` |

---

## 5. Measured evidence

All numbers come from runs against the hosted Postgres database and are recorded in `memory/evaluation/RESULTS.md` and `eval/results/2026-10-15/`.

| Evaluation | Result |
|---|---|
| Kernel scripts (50 cases, 134 steps) | 134/134 correct; 0 unauthorized approvals; 0 invariant violations |
| Gate cases (recorded model outputs, 25) | 25/25 |
| Config A, rules only (131 text cases) | 51/131 resolved correctly (coverage); **0 unauthorized approvals, 0 wrong-value approvals** |
| Config B, Qwen only (131 text cases, live model) | **Current figures (Run 5, 2026-10-17, after number-word and alias grounding and the Phase 3 changes): 106/131 (80.9%) on v1 and 107/131 (81.7%) on v2; 0 unauthorized, 0 wrong-value approvals**; kernel scripts 134/134 steps, 0 unauthorized, 0 invariant violations. History (Run 4): an intermediate run had 1 unauthorized and 1 wrong-value approval (a model-inferred category was approved), fixed by requiring recipient and category to appear in the user's text; the run after that fix scored 106/131 on v1 and 108/131 on v2. Details and caveats: `memory/evaluation/RESULTS.md` Runs 4 and 5 |
| Config C, Qwen with escalation (131 text cases, live models) | **Run 6 (2026-10-19): 113/131 (86.3%) on v1 and on v2; 0 unauthorized, 0 wrong-value approvals**; 13 and 12 safe misses. Escalation to DeepSeek V4.1 Flash through OpenRouter, thinking off, on about 19 to 20% of model cases; cost about 2.3 to 2.7 times config B. Escalation fixed most `conflicting` and `ambiguous` cases; fee arithmetic stays 0/12 (held or unresolved, never approved with a wrong value) |

**Attack scenarios.** Each scenario runs the same attack against an intentionally unsafe read-then-write baseline and against the kernel:

| Scenario | Unsafe baseline | Kernel |
|---|---|---|
| Concurrent overspend (8 × 30,000 vs 90,000) | Overspent, balance negative | 3 approved, 90,000 reserved, invariants hold |
| Delegation amplification (6 × 30,000 vs 90,000) | Children held more than the parent | 3 children, 3 refused, invariants hold |
| Revoked ancestor | Grandchild still spent | Refused `GRANT_REVOKED`; descendant revoked |
| Revocation race | **No violation this run.** Timing-dependent, reported as measured | 0 live reservations on the revoked grant |
| Duplicate delivery (same key × 5) | Debited 5 times | 1 transaction |
| Limit probing (12 refused probes) | No consequence; the next request is served | Suspended after probe 5; served again only after the owner reinstates |
| Split purchases (informational) | n/a | 30,000 refused (per-tx limit); plain grant: 5 × 10,000 approved, bounded by the 50,000 balance; windowed grant (20,000/hour): 2 approved, then `VELOCITY_LIMIT_EXCEEDED` |

**Re-run on the frozen build (Run 7, 2026-10-19).** `scripts/demo.py --attacks` from a clean start: 34 checks, 0 failed; every scenario above gave the same outcome (the revocation race again did not reproduce on the baseline).

**Honesty rules for the harness.**
- Baseline violations are measured, not asserted. A scenario that does not reproduce reports `violated: false`.
- Concurrent scenarios now also report `gave_up`, meaning requests that stayed busy after every retry. A kernel that refused everyone would look "safe", so liveness is shown next to safety, and tests assert `gave_up == 0`.

---

## 6. Requirements on settlement and the dashboard (built; kept as the acceptance checklist)

**Status 2026-10-20:** BK-075 and BK-090 are built; the dashboard was rebuilt as UI revision 3 on 2026-10-19 and re-checked against this list on 2026-10-20. The settlement items below are covered by tests (`test_settlement.py`, `test_anchor.py`, the F1 to F3 review fixes). The dashboard items were verified in the code review (no `dangerouslySetInnerHTML` or other HTML sink anywhere in `frontend/`; the API key lives in React state only, never in `localStorage` or a cookie).

**BK-075, testnet settlement adapter (must hold before its merge):**
1. **Failure proof.** `settle_fail` releases funds back to the grant. The adapter may call it only with on-chain proof that the transfer cannot land: a mined receipt with `status = 0`, or the pre-assigned nonce consumed by a different transaction. A timeout or a dropped-from-mempool signal is **not** proof; those cases stay `submitted` and are re-broadcast. Calling `settle_fail` on a transfer that actually landed would double-spend.
2. **Recipient → address mapping.** It must be a static allowlist controlled by the operator (configuration file or migration). It must never come from a proposal, a request body or model output. An unknown recipient is refused before signing.
3. **Amount conversion.** Integer only (1 cent = 10,000 base units for 6-decimal USDC), and USD only. Any other currency is refused.
4. **Disable simulated settlement in testnet mode.** When testnet mode is on, `POST /transactions/{id}/settle` (simulated) must be disabled, for example with `BK_SETTLEMENT_MODE=testnet` → 409. `settle_start` must always be called with the `on_submit` hook. Otherwise the ledger could say `settled` with no on-chain transfer behind it.
5. **`on_submit` work stays local.** Signing and persistence only, with no network I/O, because it runs under the mandate lock.
6. **Testnet key handling.** `SETTLEMENT_PRIVATE_KEY` lives in `.env` only and is never logged. It is a testnet key with only test funds.

**BK-090, dashboard:**
- Proposal fields, evidence quotes, audit details and reasons are model-derived or user-supplied text. Render them as text only: no `dangerouslySetInnerHTML` and no Markdown-to-HTML.
- Show values only from the API, never computed in the browser.
- Store the API key in memory for the demo, never in `localStorage`.

---

## 7. Known-risk list

Severity is rated for a production deployment. Status is one of: **Mitigated** (control in place and tested), **Accepted** (disclosed design limit), **Open** (work remaining).

| ID | Risk | Severity | Status | Notes / mitigation |
|---|---|---|---|---|
| R1 | **Split purchases.** The per-transaction limit is not a velocity limit; many small spends are allowed | Medium | Mitigated (opt-in) | A grant can set `window_limit` / `window_seconds` (ADR-0008): committed spend across its whole subtree in a rolling window is capped, checked under the mandate lock on every grant on the path. Demonstrated in the `split_purchases` scenario (plain grant approves 5 splits; windowed grant approves 2). Grants without a window are still bounded only by their balance |
| R2 | **The settlement service is cross-mandate.** Any `service` principal can submit, confirm or fail any transaction, and `settle_fail` relies on the service's proof | High | Mitigated | Service principals are bound per mandate (`kernel.bind_settler`, owner only; `_require_settler` on submit/confirm/fail). `settle_fail` only on proof at confirmation depth (F1). Owner can unbind (`kernel.unbind_settler`, BK-402, idempotent, audit `SETTLER_UNBOUND`); an in-flight `submitted` transfer stays recoverable by the owner or after a re-bind |
| R3 | **Simulated settlement path.** The owner can mark a transaction settled with no chain transfer | Medium | Mitigated | In testnet mode (`BK_SETTLEMENT_MODE`) simulated settle goes through the adapter and the testnet settle path is service-only (F3) |
| R4 | **Recipient → address mapping is a trust point** | High | Mitigated | Recipient addresses come from an operator allow-list (`BK_SETTLEMENT_RECIPIENTS`), not from model or agent input. Still a trust point: the operator controls that list |
| R5 | **Operator hot wallet.** One key signs every transfer | Medium (testnet: Low) | Accepted | Testnet only. Future work: smart-account wallets with on-chain spending limits (ADR-0007) |
| R6 | **Per-mandate serialization limits throughput.** Measured on 2026-10-19: median 2,327 ms per authorization end to end on the hosted database (25 calls) with a 114.5 ms round trip, so roughly one operation every 2.3 s per mandate. Run 3 measured 1,089 ms at about 60 ms per round trip: both are about 20 round trips, so the cost is the network, not the kernel | Low | Accepted | Fails closed as `KernelBusy` (retryable, never an approval). Different mandates run in parallel. The 5 s `statement_timeout` also counts time spent waiting for the mandate lock, so under a burst on one mandate the later callers get `KernelBusy` instead of queueing; a deployment close to its database (a few ms per round trip) would serialize in tens of milliseconds. The ADR-0008 controls add 64 ms (`memory/evaluation/RESULTS.md`, Runs 3 and 7) |
| R7 | **Shared inference budget, no per-principal rate limit.** One holder can drain the monthly model budget | Medium | Mitigated (BK-304) | Each agent has its own monthly bucket `principal:<uuid>` (default 500,000 micro-USD, `BK_AGENT_MONTHLY_CAP_MICRO_USD`) reserved together with the global and route buckets in one atomic reservation. Exhaustion ends `unresolved` with `AGENT_BUDGET_EXHAUSTED` and the model is never called; it can never become an approval. Global and route caps still bound the total. Limit: a party that can create many principals gets many buckets (principal creation is admin-only) |
| R8 | **No HTTP rate limiting; API keys do not expire or rotate** | Medium | Mitigated (BK-411, BK-412) | Rate limiting is built in (`api/ratelimit.py`): 120/min per principal or IP, 30/min for model-backed endpoints, 429 `RATE_LIMITED` with `Retry-After`, bounded memory, `X-Forwarded-For` ignored unless `BK_TRUST_PROXY=1`. It is per process, so several replicas multiply the limit. Keys are 256-bit random, stored as SHA-256, with optional expiry (`expires_in_days`, 401 `KEY_EXPIRED`), self-service rotation (`POST /me/rotate-key`, the old key dies in the same UPDATE, audit `KEY_ROTATED` without key material) and admin disable (401 `PRINCIPAL_DISABLED`; grants are not revoked, the owner does that). Keys still have no expiry unless one is requested at creation. Each request resolves the key with one extra database round trip (about 60 ms on the hosted database); two rotations racing on one old key cannot both win (`KEY_ALREADY_ROTATED`, found in review as D3). |
| R9 | **`/agent/request` re-runs interpretation on retry.** Costs inference; a non-deterministic model may produce a 409 instead of a replay | Low | Mitigated (BK-305) | After the holder check and before any model call, the API looks up `(grant, idempotency key)` and returns the stored decision (`replayed: true`, zero model calls). The text hash is stored with the proposal; a key reused with different text is `IDEMPOTENCY_CONFLICT`, and a key with no provable text (e.g. made via `/transactions/authorize`) is also a conflict. Requests that never reached the kernel (unresolved interpretation) leave no transaction, so a retry of those is re-interpreted |
| R10 | **The router's `needs_review` does not bind a malicious holder** | Low | Accepted | By design; see the section 3 policy note. Scope, limits and balance are the binding controls |
| R11 | **Revoking the root grant freezes the mandate.** Funds are stranded on the root | Low | Accepted | Intentional "kill switch". Funds remain counted (invariant I1); the owner creates a new mandate |
| R12 | **In-flight (`submitted`) transfers cannot be recalled by revocation** | Low | Accepted | Reported in the revocation result (`in_flight_count`, `in_flight_amount`) |
| R13 | **Service principals can read every mandate; `/budget` is visible to every principal** | Low | Accepted | Read-only. Future work: scope reads per mandate. See R24 for the names `/budget` now carries |
| R14 | **Refused requests write audit rows.** Anyone who knows a grant ID can add audit noise | Low | Accepted | IDs are random UUIDs. Mitigated further by R8's rate limiting |
| R15 | **Model text is shown in the UI** (XSS if rendered as HTML) | Medium | Mitigated | The dashboard renders proposal fields, evidence quotes, audit details and reasons as plain text; `frontend/` contains no `dangerouslySetInnerHTML`, `innerHTML` or `insertAdjacentHTML` (searched 2026-10-17); explorer links are used only as the API returns them and only when they start with `https://`. Limit: checked by search and review, not by an automated test |
| R16 | **Simulations run in the live schema** (keyless identities, separate `naive_*` tables) | Low | Mitigated | Human-only endpoint; one run at a time (`SIMULATION_RUNNING` 409); the baseline module is isolated by boundary tests |
| R17 | **A development DB credential was exposed in a session log** | Medium | Mitigated | Password rotated 2026-10-15. The replacement appeared in a chat transcript, so rotate once more just before submission |
| R18 | **Provider drift.** Model IDs, prices and the "thinking disabled" parameters | Low | Partly mitigated | Qwen verified live on 2026-10-16 (call accepted, 0 reasoning tokens billed, cost within the reservation). The escalation route used for Run 6 is DeepSeek V4.1 Flash through OpenRouter, opt-in by the operator (`BK_ESCALATION_PROVIDER=openrouter`); a live probe showed 0 reasoning tokens with `reasoning.enabled=false` and 30 without (OpenRouter ignores DeepSeek's own `thinking` switch, so the parameter is route-specific and tested). The OpenRouter rate-card entry is priced at or above DeepSeek's own peak prices (a test enforces it). DeepSeek's direct `thinking: disabled` is still unverified (no direct key). Prices are frozen per call from a versioned rate card; overruns are charged and audited |
| R19 | **Injection detection is pattern-based** and misses paraphrased attacks | Low | Accepted | A missed injection still cannot authorize. The amount must be grounded in the text, and recipient and category must be in scope. Worst case: an in-scope, grounded payment the user's text actually contains |
| R20 | **Direct database access bypasses the kernel** (anyone holding the DB password) | High | Partly mitigated | No DB credential leaves the server. Append-only triggers protect the audit and movement tables. Invariant checks (`GET /mandates/{id}/state`) detect tampering with balances. **New (ADR-0009):** audit and movement rows are hash-chained by a database trigger and `GET /mandates/{id}/integrity` recomputes the chain independently (tested: edited detail, edited amount, deleted row, deleted newest row and forged head are each detected at the right row). **Limit, tested:** someone who can disable the trigger can rewrite a whole chain consistently; only a confirmed on-chain anchor (BK-401) closes that for history before the last anchor |
| R21 | **Approval-inbox flooding.** A holder can send many above-threshold requests that wait for the owner | Low | Mitigated | Held requests reserve nothing; at most 20 pending reviews per grant (`TOO_MANY_PENDING_REVIEWS`); unreviewed requests expire after 24 h |
| R22 | **A probing agent suffers no consequence for repeated refusals** (it can map the grant's limits at leisure) | Medium | Mitigated | Circuit breaker (ADR-0009 part B): each probing refusal is a strike, a suspected injection weighs 3, five within ten minutes suspend the grant and its whole subtree. Only the holder's own refusals count; the owner is exempt; a suspended grant costs no inference. Only the mandate owner can reinstate (an ancestor holder can suspend but not reinstate, and self-delegation is refused: found in review as K1, fixed with tests). Measured by `limit_probing` (baseline: unlimited probing, then business as usual). Limits: delegation refusals (`POST /grants`) are not strikes (they only describe the holder's own grant and are rate-limited); the strike threshold is a policy choice, and a patient agent that stays under it is not stopped (it is still bound by every other limit) |
| R23 | **One-click demo sign-in keys in the dashboard.** Dev builds read `NEXT_PUBLIC_DEMO_KEYS` (written by `scripts/demo_seed.py` to the gitignored `frontend/.env.local`) and show a button per demo account | Medium (if shipped) | Mitigated | `next.config.ts` inlines the value only when `NODE_ENV` is not `production`; a production build was scanned on 2026-10-20: 0 occurrences of the 3 demo keys in 150 build files. The keys stay in a closure, never rendered, logged or put in a field. The seeded accounts are testnet demo principals. Limit: a dev server reachable from a network would serve the keys; run the demo locally only |
| R24 | **Display names in shared read models.** Since BK-501 the API adds `holder_name`, `owner_name`, audit `actor_name` and, on `/budget`, a `label` with the principal's name for each per-agent bucket | Low | Accepted | Mandate read models are already restricted to viewers of that mandate. `/budget` is not (R13): any principal can see every agent's name next to its monthly inference spend, across mandates. Names are operator-chosen labels, not credentials. Future work: scope `/budget` to the caller's own buckets and mandates |

---

## 8. What we do not claim

- This is a hackathon prototype on testnet. It has not been externally audited and must not hold real funds.
- Velocity limits are opt-in per grant (R1); a grant without a window can still be split up to its balance. We do not authenticate real banks or merchants.
- Live-model accuracy is measured on synthetic data, one run per setting, and the second dataset shares the first's generator: configuration B 106/131 and 107/131 (Run 5), configuration C 113/131 on both (Run 6). We make no claim about real users' wording, and fee arithmetic is not solved by either configuration.
- Latency figures are for one hosted database about 115 ms away; they are not a throughput benchmark.
- The revocation-race baseline failure depends on timing and did not reproduce in the recorded run. The revoked-ancestor scenario is the deterministic demonstration of that failure class.

---

## 9. Review log

| Date | Reviewer | Scope | Outcome |
|---|---|---|---|
| 2026-10-14 | Independent review (Opus, fresh context) | Kernel, API, state machine | 9 findings, all fixed with tests. Included: unauthenticated settle operations, asserts used as guards, clock read before the lock, lowercased idempotency keys, a crash window before broadcast (→ `on_submit` hook), a refusal rolling back the sweep (→ savepoint), and agents able to create mandates (→ `OWNER_MUST_BE_HUMAN`) |
| 2026-10-15 | Independent review (Opus) | Simulation harness, baseline, interpretation, cost ledger, settlement hand-off | 3 harness fixes: report `gave_up` separately from refusals; split-purchase note uses measured counts; one simulation at a time. 6 hand-off requirements for BK-075/BK-090 (section 6). Known-risk list R1–R20 |
| 2026-10-15 | Independent review (Opus) | ADR-0008 velocity windows and approval threshold | No bypass found: delegation, revocation, release, replay and races all covered. 2 fixes: path scopes now cached from the path check (removes 2 round trips under the lock from every authorization); per-grant cap on pending reviews (R21) |
| 2026-10-16 | Independent review (Opus) | Settlement branch (BK-303) | Approved after 3 fixes, all tested: F1 act on a reverted receipt only at confirmation depth (re-org double-spend); F2 reconcile survives refusals; F3 testnet settle is service-only. Merged 94feaad; full non-slow suite 213 passed |
| 2026-10-17 | Independent review (Opus) | Phase 3: migration 006, hash-chain verifier, circuit breaker, and the eight teammate branches (anchor, unbind, worker, agent budget, replay, rate limit, key lifecycle, dashboard) | All approved. 1 medium kernel finding fixed with tests: K1 (an agent could self-delegate a child, probe it into suspension, then reinstate it as holder of an ancestor; now reinstate is owner-only and self-delegation is refused). 2 low fixes with tests: D3 (concurrent key rotations), A1 (one failing tick skipped the other mandates). Lock order verified acyclic. Details: `docs/handover/PHASE3_REVIEW.md` |
| 2026-10-20 | Independent review (Opus) | Changes since 2026-10-17: UI revision 3 (all screens), demo sign-in keys, display names in read models (BK-501), the OpenRouter escalation route and its rate-card entry, the test-isolation fixes; dry run on the frozen build | No new kernel finding. Checked: no HTML sinks or browser storage of keys in `frontend/`, explorer links https-only, production build free of demo keys, no secrets in tracked files, `.env` and `.env.local` ignored, frontend diffs touch no request path or permission check. Added R23 (demo keys) and R24 (names on `/budget`); updated R6 (latency, re-measured with the round trip) and R18 (escalation route). Figures refreshed from Runs 5 to 7 |
