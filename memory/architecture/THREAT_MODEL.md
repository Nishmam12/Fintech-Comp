# Threat Model — Initial Draft

**Status:** initial threat inventory. Superseded for the submission by `docs/SECURITY_SELF_ASSESSMENT.md` (2026-10-15), which maps every threat below to a control and its evidence, and keeps the known-risk list (R1–R20). Update that document, not this one.

## Assets to protect
- User mandate and restrictions.
- Available authority, reserved funds and settled-spending state.
- Grant hierarchy, status, expiry and revocation state.
- Idempotency keys and transaction records.
- Provider credentials and budget caps.
- Audit events and evaluation datasets.
- User privacy and any future consent-aware learning data.

## Threat actors / failure sources
- Misleading or malformed user instructions.
- Malicious or compromised child agent.
- Prompt injection in supplied text/documents.
- Hallucinated, schema-invalid or contradictory model output.
- Concurrent requests that race against the same balance.
- Retries, duplicate delivery, stale grants or revoked ancestors.
- Provider outage, timeout, rate-limit or unexpected price/model change.
- Accidental secret leakage or overcollection of financial information.
- A coding agent that updates code without synchronizing design/tests/memory.

## Required controls
- Model output is untrusted; strict typed schema and semantic validation.
- Only deterministic kernel may authorize and mutate ledger.
- Atomic allocation/reservation plus isolation/locking that matches concurrency guarantees.
- Idempotency-key uniqueness and payload-hash binding.
- Effective-revocation check across grant ancestry at authorization time.
- Bounded retries and circuit breakers; fail closed for unresolved interpretation.
- Worst-case cost reservation before paid inference; reconciliation after response.
- Data minimization, consent-aware future dataset workflow, synthetic test data by default.
- Auditable decision reason codes and reproducible attack tests.
- Persistent project state in version-controlled docs and a single-writer collaboration protocol.

## Required adversarial tests
1. Concurrent requests exceeding shared allocation.
2. Child grant exceeding parent available authority.
3. Multiple child grants exceeding parent total.
4. Revoked ancestor with still-active descendant record.
5. Duplicate request and idempotency key reused with different payload.
6. Reservation followed by settlement, release, and repeated transitions.
7. Prompt telling the model to ignore the user's restrictions or system rules.
8. Invalid/oversized output, provider timeout and provider budget exhaustion.
9. Escalation request when global spend cap cannot reserve worst-case cost.
10. Memory conflict or overlapping-agent changes detected before merge.

## Explicit limitations
The initial threat model does not prove security, authenticate real banks, detect all semantically equivalent split purchases, or guarantee that a legitimate external payment settles as simulated. State which threats were tested and which remain out of scope.
