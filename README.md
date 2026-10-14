# Budget Kernel — Project Workspace & Memory System

This repository is the **shared source of truth** for Budget Kernel. Claude and GPT/Codex may have separate chat histories, but they must rely on the same version-controlled project state, decisions, plans, tests and logs.

## Start here

**New team member? Read [`ONBOARDING.md`](ONBOARDING.md) first** (setup in 15 minutes, how we claim work, your starting task).

1. Read [`AGENTS.md`](AGENTS.md) for common coding-agent rules. Claude Code also reads [`CLAUDE.md`](CLAUDE.md).
2. Read [`memory/INDEX.md`](memory/INDEX.md), then only the memory notes relevant to the current task.
3. Read [`memory/CURRENT_STATE.md`](memory/CURRENT_STATE.md) and [`memory/TASK_BOARD.md`](memory/TASK_BOARD.md) before doing project work.
4. After meaningful work, update the shared memory files according to [`memory/MEMORY_PROTOCOL.md`](memory/MEMORY_PROTOCOL.md).
5. Run the relevant tests and record actual outcomes before marking a task done.

## Suggested Obsidian setup

Open this repository root as an Obsidian vault. The project notes are ordinary Markdown files, and the `[[wikilinks]]` connect the roadmap, architecture, decisions, risks, research, and task state. Use Graph View to explore the knowledge graph. Obsidian is a visualization and navigation layer; it does not automatically give either LLM access to every note. The coding agent must explicitly read relevant files from the shared workspace.

Keep `.obsidian/` personal preferences local unless the team intentionally decides to share vault configuration. Do not store API keys, credentials, real customer statements, account identifiers, or private financial data in the vault.

## Collaboration rule

Use one **implementation writer** at a time for shared code and canonical memory files. The other model can review read-only and suggest patches/test cases. If both need to implement in parallel, use separate Git worktrees/branches and reconcile changes before merging; do not have both agents edit `CURRENT_STATE.md`, the same ADR, or the same code files concurrently.

## Initial status

This starter kit contains a proposed project structure and operating protocol. It does **not** mean that the application code exists or that any milestone has been completed. All implementation status starts as `NOT STARTED` until verified in the repository.
