# Your remaining steps, in order (times are Dhaka, the deadline is 21:59)

Everything below needs you: a camera, your passport, your mailbox or your accounts. The code, tests, docs and screenshots are done and pushed.

| By (Dhaka) | Step | Time it takes |
|---|---|---|
| 15:30 | **1. Send the registration email** (draft A below). Do this first: it has its own deadline and the organiser may reply with a problem. | 10 min |
| 17:00 | **2. Record the video**, following `docs/demo/RECORDING_RUNBOOK.md`. Check it is **5:00 or less** before saving. | 60 to 90 min |
| 18:00 | **3. Rotate the secrets** (list below). | 15 min |
| 19:00 | **4. Collect Daniel's files**: the deck as a PDF, the technical document as a PDF. Open both and page through them once. | 10 min |
| 19:30 | **5. Check the repository on GitHub** (list below). | 5 min |
| 20:00 | **6. Send the submission email** (draft B below). | 10 min |
| 20:30 | **7. Confirm** the organiser's reply, or send a short follow-up. The latest version before 21:59 counts, so there is room for one correction. | |

Leave at least an hour between sending and the deadline.

## 1. Registration email (draft A)
To: wangyr@pbcsf.tsinghua.edu.cn
Subject: Registration: Budget Kernel, Topic F (Agent Wallet), Shenzhen FinTechathon 2026

> Dear organisers,
>
> Please find attached the completed registration form and the passport bio pages of our team members for the 2026 Shenzhen FinTechathon, Topic F (Agent Wallet with testnet settlement).
>
> Team: Budget Kernel
> Team lead: Nabil Ishmam (nabish0099@gmail.com)
> Repository: https://github.com/Nishmam12/Fintech-Comp
>
> Please confirm that you have received the registration.
>
> Kind regards,
> Nabil Ishmam

Attach: the form, and the passport bio page of **each** member (you, Daniel, Afnan). Ask Daniel and Afnan to send you theirs now if you do not have them. Fill in the team name and the names exactly as on the passports.

## 4. What Daniel hands over
- Deck PDF (10 minutes or less when spoken; slide 11, the numbers, is optional and cut first).
- Technical document PDF with the figures from `docs/submission/screenshots/r3/` placed in it.
- Ask him to open each PDF on another machine and check that the screenshots are in and the text is not cut.

## 3. Rotate the secrets (nothing here can be done by me)
1. **Database password** (Supabase, project settings, database): set a new one. Update `DATABASE_URL` in your local `.env` only. Never paste it into a chat.
2. **OpenRouter key and OpenCode key**: delete them in each service's dashboard.
3. **Alibaba key**: rotate it.
4. After rotating the database password, restart the API (the old one will lose its connection).

Do this after the recording, not before: the recording uses the running API.

## 5. Check GitHub before sending
Open https://github.com/Nishmam12/Fintech-Comp:
- The newest commit is the one you expect (`git log --oneline -1` locally; compare the hash).
- There is no `.env` file in the file list (I checked: none is tracked, and `.env`, `.env.local` are ignored).
- `README.md` renders, and its dashboard and login instructions match what you did on screen.

## 6. Submission email (draft B)
To: wangyr@pbcsf.tsinghua.edu.cn (use the submission address from the organiser's instructions if it differs)
Subject: Submission: Budget Kernel, Topic F (Agent Wallet), Shenzhen FinTechathon 2026

> Dear organisers,
>
> Our submission for Topic F, Budget Kernel: agents propose, a deterministic kernel decides.
>
> 1. Technical document (PDF): attached
> 2. Presentation deck (PDF, 10 minutes): attached
> 3. Demo video (5 minutes or less): <link, or attached>
> 4. Source code and README: https://github.com/Nishmam12/Fintech-Comp (branch main)
> 5. Security self-assessment, with the permission tiers and known risks: docs/SECURITY_SELF_ASSESSMENT.md in the repository
> 6. Execution evidence (transaction hashes and logs): evidence/ and eval/results/ in the repository. On Base Sepolia (testnet): settlements 0x2c5665e7908ebb775e03185e5aef9fd9e566b79c21652d7f3c789db1add49090 and 0x7570ccbe8c9ca0aa52c057d2c52e567fece698c28909718e29e3b505f061abf1, and the history anchor 0xcb1ba8f8c64413779274509bb7333e9693123cdc8d5e9229ba927b74f5578e2e
>
> This is a testnet prototype with no external audit. It must not hold real funds, and the evaluation uses synthetic data.
>
> Kind regards,
> Nabil Ishmam, on behalf of the team

Video: if the file is large, upload it to a link anyone can open (no sign-in) and put the link in item 3. Open the link in a private window before sending.

## While recording: three reminders
- Do not say "secure". Say what was measured: 0 unauthorized approvals in every run, the kernel held in 7 of 7 attacks, synthetic data, testnet only.
- Do not say the payment on screen settled on chain: the demo runs in simulated settlement. The two explorer pages are earlier real transfers.
- Do not claim password reset by email, multi-factor sign-in or identity checks: none exist.
