# Claude Code Instructions — Budget Kernel

Use the repository's `AGENTS.md` as the shared project contract. This file contains Claude-specific entry instructions only; do not duplicate the entire project specification here.

At the start of project work:
1. Read `memory/INDEX.md`, `memory/CURRENT_STATE.md` and the relevant `memory/TASK_BOARD.md` item.
2. Follow the shared memory update protocol in `memory/MEMORY_PROTOCOL.md`.
3. Inspect repository state before edits and protect uncommitted changes.

Use the relevant design document only when needed. For code changes, verify behavior with tests. Before ending a meaningful work session, persist what changed, what was tested, remaining defects, decisions made, and the next concrete action to the shared Markdown files. Never store private chain-of-thought; store concise decisions and evidence.

Keep the deterministic authorization boundary intact. Model output can produce a proposal, never a trusted authorization decision. When a task involves a significant architectural choice, create/update an ADR rather than burying it in chat.
