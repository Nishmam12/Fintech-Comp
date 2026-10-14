# Open Questions

Keep unresolved questions here. Each entry should identify why it matters, what evidence would resolve it, who owns the decision and the current status. Remove a question only after recording the resolution in the canonical design note or ADR.

## OQ-001 — Target repository state
- **Status:** OPEN
- **Why it matters:** The starter plan must adapt to existing code rather than overwrite useful work.
- **Resolution evidence:** Repository tree, `git status`, package manifests, current run/test commands and implementation notes from the actual IDE workspace.
- **Owner:** Implementation agent

## OQ-002 — Official competition requirements
- **Status:** OPEN
- **Why it matters:** Deadline, eligibility, required format and judging criteria affect sprint prioritization.
- **Resolution evidence:** Current official event page or organizer confirmation, saved in `memory/research/PRIOR_ART.md`.
- **Owner:** Research agent / project owner

## OQ-003 — Canonical accounting representation
- **Status:** OPEN
- **Why it matters:** A parent allocation and descendant allocations must not double-count financial authority.
- **Resolution evidence:** Explicit state model, transition table, examples and tests, recorded in a security ADR.
- **Owner:** Backend implementation agent

## OQ-004 — Revocation semantics for reservations
- **Status:** OPEN
- **Why it matters:** Revocation may race with authorization or affect previously reserved but unsettled amounts.
- **Resolution evidence:** Defined transaction policy and concurrent tests; record in ADR.
- **Owner:** Backend/security agent

## OQ-005 — Provider account, exact model IDs and price tiers
- **Status:** OPEN
- **Why it matters:** Model availability/pricing, billing semantics, supported output formats and region can change.
- **Resolution evidence:** Official provider docs plus live account smoke test; save dated evidence and pricing snapshot.
- **Owner:** Model-routing agent

## OQ-006 — Database deployment choice
- **Status:** OPEN
- **Why it matters:** Concurrency correctness depends on the actual transactional database semantics.
- **Resolution evidence:** Current environment/deployment constraints and tests against the chosen DB.
- **Owner:** Backend agent

## OQ-007 — Cross-border user-data handling
- **Status:** OPEN / NOT AN MVP BLOCKER FOR SYNTHETIC DATA
- **Why it matters:** Future real-user data or provider transmission may be subject to privacy and cross-border requirements.
- **Resolution evidence:** A privacy/legal review before collecting real user financial data. Training remains deferred.
- **Owner:** Project owner
