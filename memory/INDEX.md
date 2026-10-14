# Budget Kernel — Memory Map

> This is the index for the project's persistent shared memory. Treat the repository—not any individual chat—as the source of truth.

## Current orientation
- [[CURRENT_STATE]] — verified current status and blockers.
- [[TASK_BOARD]] — work in progress, backlog and acceptance criteria.
- [[NEXT_ACTIONS]] — next 1–5 actions to execute.
- [[MEMORY_PROTOCOL]] — rules for how Claude and GPT maintain the memory.
- [[memory/CHANGELOG]] — concise chronological changes.
- [[DECISION_REGISTER]] — index of accepted/proposed/superseded decisions.
- [[OPEN_QUESTIONS]] — unresolved choices requiring evidence or owner decision.
- [[RISKS]] — current project, security, cost and delivery risks.
- [[AGENT_HANDOFF]] — current writer/reviewer handoff between Claude and GPT.

## Product and engineering
- [[docs/MASTER_PLAN]] — complete staged plan and scope.
- [[memory/architecture/SYSTEM_ARCHITECTURE]] — components, data flows and trust boundary.
- [[memory/architecture/THREAT_MODEL]] — assets, threats, controls and limitations.
- [[memory/model-routing/ROUTING_POLICY]] — model route selection and safe failure behavior.
- [[memory/model-routing/COST_CONTROL]] — API budget, reservations, reconciliation and caps.
- [[memory/evaluation/EVALUATION_PLAN]] — labeled scenarios, comparison plan and metrics.
- [[memory/research/PRIOR_ART]] — sourced related work and novelty claims needing verification.

## Decisions
- [[decisions/ADR-0001-DATA-AND-AUTHORITY-BOUNDARY]] — model output versus deterministic authorization.
- [[decisions/ADR-0002-SHARED-MEMORY-AND-OBSIDIAN]] — repository memory and optional Obsidian vault.
- [[decisions/ADR-0003-MVP-STACK-AND-SCOPE]] — initial stack and out-of-scope items.

## Logs and templates
- [[memory/logs/CHANGELOG]] — changes that materially affect the project.
- [[logs/SESSION_LOG]] — concise session summaries by date.
- [[templates/ADR_TEMPLATE]] — decision template.
- [[templates/SESSION_UPDATE_TEMPLATE]] — persistent session update template.
- [[templates/EXECUTION_PLAN_TEMPLATE]] — feature-level execution plan template.

## Memory hygiene
- Keep this index navigable. Add new notes here when they become durable project references.
- Link notes using `[[wikilinks]]`; avoid making every trivial fact its own note.
- When information changes, update the canonical note and mark the old decision superseded rather than leaving contradictory instructions in multiple files.
- Record facts, assumptions, open questions and recommendations separately.
