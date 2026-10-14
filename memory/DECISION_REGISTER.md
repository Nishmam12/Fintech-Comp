# Decision Register

Status values: `PROPOSED`, `ACCEPTED`, `REJECTED`, `SUPERSEDED`. Accepted means the project owner has approved the direction; it does not mean implemented.

| ID | Decision | Status | Rationale | Detail |
|---|---|---|---|---|
| ADR-0001 | LLM proposes; deterministic kernel authorizes | ACCEPTED | Essential security boundary | [[decisions/ADR-0001-DATA-AND-AUTHORITY-BOUNDARY]] |
| ADR-0002 | Repository Markdown is canonical shared memory; Obsidian is optional view/editor | ACCEPTED | Keeps Claude and GPT aligned in one IDE | [[decisions/ADR-0002-SHARED-MEMORY-AND-OBSIDIAN]] |
| ADR-0003 | Python/FastAPI + transactional database + Next.js candidate stack; start modular monolith | PROPOSED | Familiar, rapid MVP, testable invariants | [[decisions/ADR-0003-MVP-STACK-AND-SCOPE]] |
| POL-01 | Model training deferred; preserve future path only (formerly listed as "ADR-0004", no ADR file) | ACCEPTED | First establish labeled evaluation, privacy controls and baseline | To be created if this changes |
| POL-02 | Under-$10 monthly API budget and 100K monthly decisions as targets (formerly listed as "ADR-0005", no ADR file) | ACCEPTED | User-defined constraint from handoff; workload split remains hypothesis | See [[docs/MASTER_PLAN]] |
| ADR-0004 | Move-based accounting: grants hold available/reserved/settled; delegation moves units; conservation invariant I1–I3; scope attenuation; permission tiers | PROPOSED | No derived "remaining"; one unit in one column of one grant, so double counting is testable (resolves OQ-003) | [[decisions/ADR-0004-ACCOUNTING-REPRESENTATION]] |
| ADR-0005 | Per-mandate FOR UPDATE serialization at READ COMMITTED; states reserved→submitted→settled/released; replay-style idempotency; lazy expiry sweep; revocation cannot cancel in-flight (submitted) transfers | PROPOSED | Simple provable concurrency for a 4-day build; throughput limit stated (resolves OQ-004, OQ-006) | [[decisions/ADR-0005-LIFECYCLE-CONCURRENCY-REVOCATION]] |
| ADR-0006 | Inference cost ledger: monthly micro-USD buckets, ordered-lock two-row worst-case reservation, reconcile from usage, worst-case charge on crash | PROPOSED | Hard $9.50 stop under concurrency; deadlock-free | [[decisions/ADR-0006-INFERENCE-COST-LEDGER]] |
| ADR-0007 | Base Sepolia test-USDC settlement adapter; pre-assigned nonce + persisted signed raw tx before broadcast; reconciler; key only in .env | PROPOSED | Real tx hashes for Topic F with chain-enforced no-double-send; amends ADR-0003 "no blockchain" | [[decisions/ADR-0007-TESTNET-SETTLEMENT-ADAPTER]] |

Note (2026-10-15, BK-010): the two register-only rows formerly labelled ADR-0004/ADR-0005 were re-IDed POL-01/POL-02 to avoid colliding with the new ADR files. Their content and status are unchanged.
