# Decision Register

Status values: `PROPOSED`, `ACCEPTED`, `REJECTED`, `SUPERSEDED`. Accepted means the project owner has approved the direction; it does not mean implemented.

| ID | Decision | Status | Rationale | Detail |
|---|---|---|---|---|
| ADR-0001 | LLM proposes; deterministic kernel authorizes | ACCEPTED | Essential security boundary | [[decisions/ADR-0001-DATA-AND-AUTHORITY-BOUNDARY]] |
| ADR-0002 | Repository Markdown is canonical shared memory; Obsidian is optional view/editor | ACCEPTED | Keeps Claude and GPT aligned in one IDE | [[decisions/ADR-0002-SHARED-MEMORY-AND-OBSIDIAN]] |
| ADR-0003 | Python/FastAPI + transactional database + Next.js candidate stack; start modular monolith | PROPOSED | Familiar, rapid MVP, testable invariants | [[decisions/ADR-0003-MVP-STACK-AND-SCOPE]] |
| ADR-0004 | Model training deferred; preserve future path only | ACCEPTED | First establish labeled evaluation, privacy controls and baseline | To be created if this changes |
| ADR-0005 | Under-$10 monthly API budget and 100K monthly decisions as targets | ACCEPTED | User-defined constraint from handoff; workload split remains hypothesis | See [[docs/MASTER_PLAN]] |
