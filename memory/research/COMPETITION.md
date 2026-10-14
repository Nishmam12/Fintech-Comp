# Competition — 2026 Shenzhen International FinTech Competition (FinTechathon), International Track

**Sources (accessed 2026-10-15):**
- PBCSF *Appendix 2 — Problem Description and Competition Rules for International Track* (PDF, 4 pages), via https://drive.scmc.cmu.ac.th/s/2jKErkTJpFmcxYF
- CMU repost: https://ird.oou.cmu.ac.th/2026-shenzhen-international-fintech-competition/
- Official site: https://fintechathon.g-ican.com (JS-rendered; not readable by fetch)

## Hard facts
- **Theme:** "AI as a Financial Participant": an AI agent that completes real tasks in a financial scenario.
- **Deadline (registration AND submission):** 2026-10-20 23:59 Beijing (UTC+8) = **17:00 London (BST)** = 15:59 UTC. You can resubmit until then, and the latest version counts.
- **Scoring:** Task completion **40%** · Security & compliance **30%** · Innovation & interaction **30%** · On-chain challenge bonus 0–5 points. All six topics are scored on the same criteria.
- **Topics (pick one):**
  - A — Personal Finance Assistant
  - B — Wealth Advisory Agent
  - C — Cross-border & Student Finance
  - D — Insurance Assistant
  - E — SME Finance Copilot
  - F — Agent Wallet (autonomous on-chain: asset management, transaction execution, risk control)
- **Team:** 2–5 full-time students at overseas institutions. At least 60% must be non-Chinese nationals. Nobody may be on more than one team.
- **Language:** English.
- **Registration:** official form plus each member's passport bio page, emailed to wangyr@pbcsf.tsinghua.edu.cn. Same deadline as submission.

## Submission checklist (map each to a task)
1. **Technical documentation:** system architecture, core algorithm description, security design.
2. **Presentation deck:** a final presentation of 10 minutes or less.
3. **Demo video:** optional, 5 minutes or less.
4. **Source code:** README, **GitHub repository link**, deployment instructions, test cases.
5. **Security self-assessment report:** **permission-tier implementation** and a **known-risk list**.
6. **Execution evidence:** non-on-chain topics need simulated-account/sandbox operation logs plus the demo video. The on-chain topic needs **real on-chain transaction hashes**.

## Later dates
Online review Oct 20–31 · finalists announced Oct 31 · Shenzhen visit Nov 20 · grand final Nov 21–23 (at least one member must attend in person).

## Implications for Budget Kernel
- The kernel's grant hierarchy *is* the "permission-tier implementation" deliverable (5). THREAT_MODEL plus RISKS feed the known-risk list.
- Task completion (40%) needs a visible agent finishing user tasks end-to-end, not only infrastructure. That is the main framing risk.
- Topic choice is open (see OPEN_QUESTIONS OQ-008).
