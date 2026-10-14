# ADR-0002: Shared Project Memory with Optional Obsidian Vault

- **Status:** ACCEPTED
- **Date:** 2026-10-15
- **Owner:** Project owner

## Context
Claude and GPT/Codex will work in the same IDE, but their chat histories and agent-specific memory are not one shared universal state. The project needs durable notes that track current work, past decisions, architecture and future plans.

## Decision
The Git repository's Markdown files are the canonical shared memory. `AGENTS.md` carries common agent rules; `CLAUDE.md` provides Claude-specific entry instructions. `memory/INDEX.md`, `CURRENT_STATE.md`, `TASK_BOARD.md`, `NEXT_ACTIONS.md`, ADRs and logs are maintained through a defined update protocol. Obsidian may open the repository root as a vault to visualize and navigate linked notes.

Do not use an independently copied Obsidian vault as a competing source of truth. Obsidian Graph View is a note-link visualization, not a literal neural network and not automatic model memory.

## Consequences
- Both agents must read relevant files and write updates into the same repo.
- A single-writer rule avoids overlapping edits; reviewers can inspect read-only.
- Git history records memory changes and enables rollback.
- Memory notes must be concise, linked and free of secrets/private chain-of-thought.

## Evidence and validation
Verify that the chosen IDE extensions recognize `AGENTS.md` / `CLAUDE.md`. Regardless of automatic discovery, the master prompt explicitly tells each agent to read the entry files and memory index.

## Revisit when
An IDE or agent runtime offers a reliable shared project-memory integration that complements rather than fragments the repository as the source of truth.
