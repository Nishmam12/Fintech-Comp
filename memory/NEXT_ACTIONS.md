# Next Actions

Updated 2026-10-18 by memory sync (Haiku). Order matters. Each step names who acts and which model to switch to first.

## Now (Oct 18)
1. **You:** send the BK-OWN-1 registration email. It is not confirmed sent.
2. **You:** rotate the Alibaba model key. The live runs are finished.
3. **You:** decide config C. Recommended: leave it out and write "not run" in the technical document.
4. **You:** tell Daniel to pull `main` and redo his click-through on e42a002. Tell Afnan to rehearse the video on the merged build (Oct 18 evening). Both should set their own presence sections to IDLE or DONE.
5. **You:** run the demo story yourself: agent asks; held request approved; over-limit refusal; five probes trigger a suspension; reinstate; revoke; integrity green; Run all attacks.

## Lead: integration dry run (switch to Sonnet when you say go)
1. Investigate the 2 testnet-mode test failures first (open item 2).
2. Full non-slow suite, then the slow state-machine test.
3. Offline eval: gate 25/25, kernel 134/134, 0 unauthorized.
4. All simulations, then `scripts/demo.py --attacks` from a clean start, local settlement.
5. Re-measure authorization latency and replace the 1.1 s figure.
6. Record the numbers in `RESULTS.md` (Run 6, labelled as the dry run).

## Oct 19
- **13:00:** click-through at 390 px and 1280 px, light and dark, with the demo sign-in buttons.
- **14:00 UI freeze.** Only bug fixes after this.
- **15:00 to 18:00:** Afnan's final video take, on the frozen build, with the real testnet run.
- **Daniel:** re-shoot screenshots from the frozen UI; trim the deck to 10 minutes.
- **20:00 (switch to Opus): Step 12 security pass and build freeze.**
  - Fix the self-assessment figure (open item 1).
  - Add R23 (demo keys, dev-only) and L1 (budget labels).
  - Re-read each risk against the final state.
  - Record the latency figure.

## Oct 20
- **Before noon:** Afnan's final evidence export (`scripts/evidence.py`). Lead writes the final numbers section for the deck and technical document.
- **By 12:00:** Daniel's deck and technical document final.
- **Just before submission:** rotate the DB password; update `.env` on the demo machines.
- **Before 17:00:** you send the submission email.

## Open questions for you
- Config C: go or no-go?
- Config D: define it or drop it from BK-150?
- BK-311 to 315 and BK-321 to 326: finish, or cut as "not needed"?
