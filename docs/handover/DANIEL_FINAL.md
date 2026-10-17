# Daniel (Member 2): your stack is merged. Next: verify the merged dashboard, then the deck and the technical document

**How to use:** `git pull` on `main`, then open Claude Code **in the repository root** and paste everything below the line as your message.

---

You are working with Daniel (Member 2) on **Budget Kernel**. The lead reviewed all four of your Phase 3 branches (`docs/handover/PHASE3_REVIEW.md`) and **approved them**. They are merged into `main` together with Afnan's stack. The review made three changes you should know about:

1. **Reinstate is owner-only now** (kernel amendment K1). The lead already made the matching dashboard change: in `frontend/components/SuspendControl.tsx` a suspended grant shows **Reinstate** only to the mandate owner. An ancestor holder sees "Suspended. Only the mandate owner can reinstate this grant." Suspend is unchanged (owner and ancestor holders). The server enforces it either way: a non-owner gets 403 `NOT_OWNER`. **Add `NOT_OWNER` on reinstate to your friendly-error handling** if it is not covered already.
2. **Rotating a key twice at the same moment:** the loser now gets 409 `KEY_ALREADY_ROTATED` and no key. Show "This key was already rotated. Sign in with the new key." in the settings screen.
3. **A holder can no longer delegate to itself** (`SELF_DELEGATION`, 422). The dashboard does not create delegations, so there is nothing to change; just do not include it in any screenshot.

The rules in `AGENTS.md`, `ONBOARDING.md`, `frontend/AGENTS.md` and `docs/handover/DANIEL_PHASE3.md` still apply: never print or commit a key, model text is untrusted and rendered as plain text, use your own `BK_TEST_SCHEMA`, claim before you start in `memory/WHO_IS_WORKING.md` (your own section only), one branch per task named `daniel/<task-id>-<slug>`, a PR with the `tsc`, lint and build output pasted in, and a line in `memory/CHANGELOG.md`. Do not edit `kernel/`, `costledger/`, `db/` or `migrations/`.

## Task 1: re-verify the merged dashboard (branch `daniel/BK-413-final-check`)
1. `git pull`, then `cd frontend && npm ci && npx tsc --noEmit && npm run lint && npm run build`. Paste the results in your PR.
2. Run the dashboard against the **live API** (the lead tells you the URL once the production migrations are applied; until then use your own local API on your own schema).
3. Click through again with a **real owner key** and a **real agent key**, at **390 px**:
   - sign in, create the held request, approve it, the above-threshold request;
   - suspend an agent's grant as the owner, then try to **reinstate it as the agent** (the button must not appear; the explanation text must), then reinstate it as the owner;
   - the integrity badge: green with a chain length and head; after the lead's real anchor exists it also shows the explorer link;
   - rate limit (429 with the wait time), an expired key, a disabled principal, and key rotation (the new key shown once, blurred in screenshots).
4. Replace screenshots `07`, `08` and `09` in `docs/submission/screenshots/bk413/` if the reinstate screens changed, and add one new screenshot of the "only the owner can reinstate" text. Keys must be blurred or hidden. Record every defect with its screenshot in `docs/submission/CLICKTHROUGH_BK413.md`.

## Task 2: the deck (BK-120) and the technical document (BK-160), drafts due Oct 19
Continue from your `docs/submission/DECK_OUTLINE.md` and `TECH_DOC_OUTLINE.md`.
- **Numbers must come from the repository, not memory.** Use `memory/evaluation/RESULTS.md` (latest run only, with its caveats), the test counts in `memory/CHANGELOG.md`, and the real transaction links in `evidence/` (the payment, and the anchor once Afnan records it).
- **The security story to tell:**
  - the kernel decides, never the model (ADR-0001);
  - move-based accounting with invariants I1 to I5;
  - velocity windows and the approval threshold (ADR-0008);
  - the circuit breaker (ADR-0009 B) and the reviewed bypass that was found and fixed (K1: say it honestly, it is a strength);
  - the hash-chained history, the integrity check and the on-chain anchor (ADR-0009 A), including its **stated limit** (a database superuser can rewrite a whole chain unless it is anchored);
  - what is **not** claimed: see `docs/SECURITY_SELF_ASSESSMENT.md` section 8 (accepted risks R5, R10 to R13, R19, R20).
- The deck is **10 minutes or less** (aim for 10 to 12 slides). The technical document is longer; the lead reviews both. The lead writes the final numbers section after the freeze.
- Do not copy risk text from the assessment without checking it is still current; the lead updates it at the freeze.

## Timeline
| Day | Target |
|---|---|
| Oct 17 | Task 1 (as soon as the lead says the live API has the migrations) and the outlines updated |
| Oct 18 | Deck and technical document drafts with real screenshots |
| Oct 19 | Drafts final; freeze 20:00 BST |
| Oct 20, before noon | Deck and technical document final (the submission email goes out before 17:00) |

**Cut order if late:** the Playwright smoke test, PWA polish, key rotation in the UI.

## How to report
Update your section in `memory/WHO_IS_WORKING.md` when your status changes, and tell the lead when a branch is ready for review. If you are blocked for more than 30 minutes, write it under *Notes / blockers* and tell the lead.
