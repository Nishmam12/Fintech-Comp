# Handover prompt: Member 2 (product, story, evaluation)

**How to use:** clone the repo and finish setup (ONBOARDING.md section 1). Then open Claude Code **in the repository root** and paste everything below the line as your first message. Before pasting, replace `<NAME>` with your name in lowercase, for example `alex`.

---

You are working with me, Member 2 of a 3-person team, on **Budget Kernel**, our entry for the 2026 Shenzhen FinTechathon (Topic F, Agent Wallet). The hard deadline is **2026-10-20 17:00 BST**, and the build freezes on **Oct 19 at 20:00 BST**. The team lead built the backend. My job is the product surface, the story and the evaluation numbers.

## Read first, in this order
1. `AGENTS.md` and `CLAUDE.md`: rules for us both.
2. `ONBOARDING.md`: setup, the claim protocol, and my BK-090 brief in section 4.
3. `docs/plans/PHASE2_PLAN.md`: my tasks, the timeline and the cut order.
4. `docs/SECURITY_SELF_ASSESSMENT.md` sections 1–3: what the product guarantees. Our UI and documents must never claim more than this.
5. `memory/WHO_IS_WORKING.md`: check nobody else claims my paths.

## Rules that are not negotiable
- **Claim first.** Before coding, fill in my section of `memory/WHO_IS_WORKING.md` only (status ACTIVE, task ID, branch, paths). Commit only that file as `claim: <NAME> <task-id>` and push to `main`. Update it when I switch tasks or stop.
- **Branches and PRs.** One branch per task, named `<NAME>/<task-id>-<slug>`. Never commit to `main` except the claim file. Open a PR with test output pasted in; the lead merges.
- **Hands off** `backend/src/budget_kernel/{kernel,costledger,db}/` and `backend/migrations/`. If a task seems to need them, stop and tell me so I can ask the lead.
- **Secrets.** Never print, commit or paste secrets (`.env` is gitignored). Use my own test schema `BK_TEST_SCHEMA=bk_test_<NAME>`, and never run two pytest sessions at once.
- **Untrusted text.** Model output and user text are untrusted. In the UI, render proposal fields, evidence quotes, reasons and audit details as plain text only: no `dangerouslySetInnerHTML`, no Markdown-to-HTML.
- **Honest numbers.** Every number shown or written comes from the API or from a recorded result file. Never round up, never invent, never write "should work" for something not run.
- **Ask, don't guess.** If something is unclear or a decision belongs to the lead, ask me instead of guessing.

## My tasks, in order
1. **BK-090 dashboard** (`frontend/` only; Next.js App Router + TypeScript + Tailwind). Build the 6 screens in ONBOARDING section 4. Get the backend running locally (`cd backend && uv run uvicorn budget_kernel.api.app:app --reload`) and use `scripts/demo.py` and `backend/tests/integration/test_agent_flow.py` as the reference for exact requests.
2. **BK-321..326 dashboard extras** (details in PHASE2_PLAN):
   - mobile-first installable PWA, with the owner screens designed for a phone first
   - approval inbox polling every 3 s
   - one-tap kill switch (revoke with a confirmation step; show the reclaimed and in-flight amounts the API returns)
   - velocity meter and approval threshold
   - block-explorer links on settled transactions
   - a Playwright smoke test

   The velocity and threshold fields (`window_limit`, `window_seconds`, `review_above`) arrive from the lead around Oct 16. Treat them as optional until then. Explorer links come from Member 3.
3. **BK-305 replay before interpret** (`backend/src/budget_kernel/api/` and `routing/` only).
   - In `/agent/request`, look up an existing transaction for (grant_id, idempotency_key) **before** calling the interpreter. If it exists, return the stored decision without any model call.
   - Add a test proving a retry makes zero provider calls.
   - The lookup must not bypass the kernel's holder check: the caller must still be the grant holder.
4. **BK-150 live evaluation** (blocked until the lead shares the API keys privately; put them in `.env` only).
   - Run `uv run --project backend python eval/runner.py --config B`, then `C` (needs the DeepSeek key) and `D` (OpenRouter) if available. Read `eval/README.md` first.
   - Add the results to `memory/evaluation/RESULTS.md` as a new run, with the date, model IDs, prompt version and dataset hash. Report them exactly as measured, including failures and cost.
5. **BK-120 deck** (deliverable 2, a 10-minute talk at most) and **BK-160 technical document draft** (deliverable 1). They tell the same story, so write them together.
   - Technical document sections: problem; architecture; core algorithm (lock → sweep → path check → conditional update → audit; delegation attenuation; idempotency); interpretation and cost control; security design (link the self-assessment); evaluation results; testnet settlement; limitations.
   - Sources: the ADRs in `memory/decisions/`, `README.md`, `docs/SECURITY_SELF_ASSESSMENT.md`, `memory/evaluation/RESULTS.md`.
   - Put drafts in `docs/submission/`. The lead reviews both.
   - Deck flow: problem (agents with money) → why "LLM decides" is unsafe → our design (model proposes, kernel decides) → live demo moments (agent asks → owner approves on phone → testnet transfer; kill switch) → attack results (baseline vs kernel) → security tiers and known limits → what's next.

## Timeline (mine)
- **Oct 15–16:** dashboard screens 1–4, kill switch, BK-305.
- **Oct 17:** attack panel, budget and audit, PWA, velocity meter; live evaluation if I have the keys.
- **Oct 18:** technical document draft, deck draft, Playwright smoke test.
- **Oct 19:** final technical document and deck (freeze at 20:00).
- **Oct 20:** final read-through only.

If I am behind, cut in this order: Playwright smoke test, PWA polish, config D.

## How to work with me
- Start by summarising what you read and proposing the first concrete step. Then build in small, tested increments.
- Before calling anything done, run it and show me the output.
- At each stopping point, update my WHO_IS_WORKING section, and add a line to `memory/CHANGELOG.md` in the PR.
