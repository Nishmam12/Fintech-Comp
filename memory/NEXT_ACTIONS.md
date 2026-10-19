# Next Actions

Updated 2026-10-19 20:45 UTC by the lead session (Opus). Order matters. Each step names who acts.

**Deadline: 2026-10-20 23:59 Beijing = 15:59 UTC = 16:59 UK = 21:59 Dhaka.** The lead's machine runs on Dhaka time (UTC+6), and session hooks label it "BST": that is not UK time. Quote times in UTC.

## Done tonight (Oct 19, UTC)
- UI revision 3 frozen on `main`: all seven screens rebuilt, `npm run check:layout` passes at 1366, 1920, 2560, 1024 and 390 px.
- Run 7 dry run on the frozen build: 366 tests plus the slow state machine; `demo.py --attacks` 34/34; latency 2,327 ms at a 114.5 ms round trip (`RESULTS.md`).
- Step 12 security pass: self-assessment draft 3 (R23, R24, R6, R18, config C figures).
- Deck trim (draft 3) merged; config C, test count and latency corrected in the deck and technical document.

## Now (before sleeping)
1. **You:** send the BK-OWN-1 registration email if it has not gone. It is the one deadline only you can meet.
2. **You:** delete the OpenRouter key in its console (config C is finished) and rotate the Alibaba key. The OpenCode key was already removed from `.env`; delete it in its console too.
3. **You:** click through the full story on the frozen UI at 1366, 1920 and 390 px: agent asks; held request approved; over-limit refusal; five probes trigger a suspension; owner reinstates; revoke; history seal green; Run all attacks. Report anything broken.

## Oct 20 (times UTC)
- **By 06:00, Afnan:** final video take on the frozen build (BK-140), then the evidence export (`scripts/evidence.py`, BK-130).
- **By 08:00, Daniel:** re-shoot deck and technical-document screenshots from the frozen UI (1280x800 plus one 390x844 phone shot); final deck and technical document (BK-120, BK-160).
- **By 09:00, lead (Opus):** final numbers slide and section; last read of the self-assessment against the final build.
- **By 12:00, lead:** assemble the six-item submission pack (BK-110).
- **Just before submission, you:** rotate the DB password; update `.env` on the demo machines.
- **Before 15:59 UTC, you:** send the submission email.

## Open questions for you
- Config D: drop it from BK-150 (recommended: it was never defined).
- BK-311 to 315 and BK-321 to 326: mark as cut ("not needed for the submission"), or list what is already covered (recommended: mark covered items DONE with evidence, cut the rest).
- Attack lab names are lower-case ("concurrency overspend"); a one-line fix for Afnan if you want it before the video.
