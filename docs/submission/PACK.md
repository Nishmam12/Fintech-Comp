# Submission pack: Budget Kernel (Topic F, Agent Wallet with testnet settlement)

Deadline: 2026-10-20 23:59 Beijing (15:59 UTC). Repository: https://github.com/Nishmam12/Fintech-Comp (branch `main`).

| # | Deliverable | Where | Status on 2026-10-20 |
|---|---|---|---|
| 1 | Technical document | `docs/submission/TECH_DOC_DRAFT.md` (draft 3; export to PDF for sending) | Text final apart from Daniel's pass; figures listed in section 6 are in `docs/submission/screenshots/r3/` and still have to be placed in the exported document |
| 2 | Deck, 10 minutes or less | `docs/submission/DECK_DRAFT.md` is the content and speaker notes; the slides themselves are Daniel's | Slides 1 to 10 are 600 s; slide 11 (numbers) is optional and cut first |
| 3 | Demo video, 5 minutes or less | script in `docs/demo/VIDEO_SCRIPT.md` | **The owner records** (Afnan has left); runbook `docs/demo/RECORDING_RUNBOOK.md`; not recorded yet |
| 4 | Source code and README | this repository, `README.md` | Done. Full non-slow suite 412 passed on 2026-10-20, run on the code before the last login review fixes (login, setup and rate-limit tests 61 passed after them; the slow state machine test was last run 2026-10-19); `demo.py --attacks` 34/34. Login runs on the scratch schema `bk_dev`; production `bk` is not migrated (008 to 010) |
| 5 | Security self-assessment (permission tiers, known risks) | `docs/SECURITY_SELF_ASSESSMENT.md` (draft 3, 2026-10-20) | Done. R1 to R27 (login added); review log to 2026-10-20, including the independent review of the login |
| 6 | Execution evidence (tx hashes, logs) | `evidence/SETTLEMENTS.md`, `evidence/settlements.json`, `anchors.json`; run logs in `eval/results/2026-10-19/` | Settlement and anchor evidence exist (2 payments, 1 anchor). Re-exported by Afnan (84ef79d, timestamps only) |

## On-chain evidence (Base Sepolia, chain 84532, testnet only)
- Settlement 1: `0x2c5665e7908ebb775e03185e5aef9fd9e566b79c21652d7f3c789db1add49090` (block 48155797)
- Settlement 2: `0x7570ccbe8c9ca0aa52c057d2c52e567fece698c28909718e29e3b505f061abf1` (block 48219666)
- History anchor: `0xcb1ba8f8c64413779274509bb7333e9693123cdc8d5e9229ba927b74f5578e2e` (block 48219690)

## Headline numbers and their sources
All in `memory/evaluation/RESULTS.md`; raw files in `eval/results/`.
- 0 unauthorized approvals and 0 invariant violations in every run (kernel scripts 134/134 steps, Runs 5 and 7).
- Attacks: kernel held in 7 of 7 scenarios; the baseline broke in 5 (Run 7).
- Language interface: rules only 51/131; config B 106/131 and 107/131; config C 113/131 on both; 0 unauthorized, 0 wrong-value (Runs 1, 5, 6). Synthetic data, one run per setting.
- Authorization latency 2,327 ms median at a 114.5 ms database round trip; the window and threshold add 64 ms (Run 7).

## Before sending (owner)
The timed list with both email drafts is `docs/submission/OWNER_FINAL.md`.

1. Registration email with the form and passport pages to wangyr@pbcsf.tsinghua.edu.cn (BK-OWN-1).
2. Rotate the database password (self-assessment R17) and delete the OpenRouter and OpenCode keys.
3. Open the repository on GitHub and confirm `main` shows the latest commit and `.env` is not present.
4. Attach or link the six items in the submission email before 15:59 UTC.

## Limits to state if asked
Testnet prototype, no external audit, must not hold real funds; the evaluation is synthetic; a database superuser can rewrite an un-anchored history (R20). See self-assessment section 8.
