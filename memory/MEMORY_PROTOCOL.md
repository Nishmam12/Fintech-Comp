# Persistent Shared Memory Protocol

## Purpose
Provide Claude and GPT/Codex with a durable, shared project map that survives conversation resets and records what was done, why decisions were made, what remains unresolved, and what should happen next.

The memory system is repository-first. Chat history is supplemental, not authoritative. Obsidian can visualize and edit the same Markdown files, but it is not a separate copy of the project state.

## Sources of truth and precedence
When files conflict, resolve them in this order:
1. Current source code, executable tests and database migrations for what is actually implemented.
2. Accepted Architecture Decision Records (ADRs) for intentional architectural choices, unless later superseded.
3. `memory/CURRENT_STATE.md` for the latest verified status snapshot.
4. `memory/TASK_BOARD.md` and `memory/NEXT_ACTIONS.md` for the current execution queue.
5. The master plan and architecture docs for the intended design.
6. Session logs and chat history as historical context only.

A plan is not proof of implementation. A log is not a substitute for code/tests. When a conflict is found, do not silently choose a version: investigate, record the discrepancy and correct the canonical document.

## At the beginning of a task
1. Check `git status` and do not overwrite uncommitted work.
2. Read `memory/INDEX.md`, `memory/CURRENT_STATE.md`, `memory/TASK_BOARD.md`, and `memory/NEXT_ACTIONS.md`.
3. Read only the design notes needed for the task.
4. Identify the task ID, expected result, acceptance criteria and relevant invariants.
5. For work likely to cross several context windows, create/update an execution plan in `docs/plans/` (create that directory if needed) using `memory/templates/EXECUTION_PLAN_TEMPLATE.md`.

## During a task
- Update the task status when work materially starts, becomes blocked, enters review or finishes.
- Record new assumptions as `ASSUMPTION`; do not present them as verified facts.
- Record a significant design choice in an ADR with context, options, decision, consequences and status.
- For research, preserve source title, URL, publisher/owner, access date, relevant claim and confidence/limitation. Do not paste large copyrighted text.
- When a test fails, preserve the failure and diagnosis. Never edit a result to make a test appear successful.
- Avoid logging secrets, access tokens, real user financial data, chain-of-thought, or long raw conversation transcripts.

## At the end of each meaningful work session
Before claiming completion:
1. Run relevant tests and inspect their actual exit status/output.
2. Review `git diff` for unintended or unrelated changes.
3. Update the task status and acceptance evidence in `TASK_BOARD.md`.
4. Update `CURRENT_STATE.md` with verified milestone state, blockers and test status.
5. Update `NEXT_ACTIONS.md` with the next 1–5 concrete actions.
6. Add a concise entry to `CHANGELOG.md` and `logs/SESSION_LOG.md`.
7. Update affected architecture, routing, cost, threat-model or evaluation notes.
8. Create/update an ADR if a lasting decision was made or changed.
9. End the user-facing summary with files changed, tests run, results, known issues and the next action.

If interrupted before all updates, write an explicit `MEMORY UPDATE INCOMPLETE` note into the session log and identify what remains to be synchronized.

## Memory quality
- Store durable facts, concise rationales, accepted decisions, measured results, constraints and next actions.
- Do not store hidden chain-of-thought or ask another model to reconstruct it. Store a brief decision summary and evidence instead.
- Separate `FACT`, `ASSUMPTION`, `PROPOSAL`, `DECISION`, `RISK` and `OPEN QUESTION` labels where ambiguity could matter.
- Mark superseded statements instead of deleting historical reasoning that explains an important change.
- Use ISO dates (`YYYY-MM-DD`) and Asia/Dhaka local time where a timestamp is needed.
- Keep `CURRENT_STATE.md` short enough to load quickly. Put detail in topic notes and link them.
- Never claim an implementation or test exists because a plan mentions it. Verify the workspace.

## Claude + GPT shared IDE protocol
- The model doing implementation is the **writer** for that task. The other model should be assigned reviewer/adversarial tester unless work is isolated in another Git worktree.
- Before handing work to the other model, persist a handoff note describing task ID, branch/commit or working-tree status, changed files, tests run, known issues, and exact review request.
- Reviewers should report findings with file/line references and reproducible tests rather than directly changing canonical files by default.
- No two agents should concurrently modify `CURRENT_STATE.md`, `TASK_BOARD.md`, the same ADR or the same core authorization files.
- After review, the writer resolves findings and updates memory.

## Obsidian behavior
- Open the repository root as the vault; do not maintain a separate independent vault copy.
- Use wikilinks for durable relationships between requirements, architecture, tasks, decisions, risks and evaluation results.
- Use Graph View to inspect missing links, orphan notes and clusters. A graph is a navigation aid; it does not prove reasoning quality or make an LLM automatically aware of notes.
- Keep sensitive local settings out of Git as appropriate. Never put secrets or real financial documents in a synced vault without an approved data policy.


## Handoff between agents
Use [[AGENT_HANDOFF]] when one model implements and the other reviews. The handoff must name the branch/commit or working-tree state, task, files changed, checks run, defects and exact review request. Do not treat the second model's review summary as verified until findings are reproduced or adjudicated.
