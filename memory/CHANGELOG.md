# Project Changelog

This is a concise record of meaningful project changes. Detailed per-session notes live in [[logs/SESSION_LOG]].

## 2026-10-15 — Shared memory and operating system drafted
- Added repository-first shared-memory protocol for Claude and GPT/Codex.
- Added project state, task board, next actions, ADR index, architecture/routing/evaluation placeholders and Obsidian navigation conventions.
- Established that model training is deferred, the shared repository is canonical, and model output never authorizes a transaction.
- No application code or tests are claimed as completed by this starter kit.
- 2026-10-15: Repo created and pushed (Nishmam12/Fintech-Comp). Model-role agents, presence board, Supabase env + skills. Competition rules recorded (Topic F). Backend skeleton + DB tests. ADR-0004..0007 accepted; ADR-0003 amended (Supabase, testnet).
- 2026-10-15: Added migration 001_core and the deterministic kernel (ops, funds, sweep, invariants, scope attenuation). 65 tests pass on Supabase. Test-helper bugs found and fixed (child expiry default, idempotency timestamps); no kernel defects found by the suite.
- 2026-10-15: Independent Opus review of the kernel: no money-creation/loss or authority-amplification path found. Fixed all findings: settlement steps now require a service principal (owner only for simulated start/confirm; never settle_fail); asserts replaced by KernelInvariantError; post-lock clock (clock_timestamp) replaces SQL now(); idempotency keys case-sensitive; needs_review in payload hash; wider KernelBusy mapping; statement_timeout 5 s; owner review (approve/deny) + proposal TTL; on_submit hook inside the settle-start transaction for ADR-0007; operation body in a savepoint so a refused op still commits the sweep. Added I5 (ledger_movements reconcile to grant buckets), HTTP API, 25 more tests. 90 tests pass.
