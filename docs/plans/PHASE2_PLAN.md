# Phase 2: robustness features and team split (Oct 15 → Oct 19)

**Why:** the backend milestones (M0–M5) are done ahead of schedule. The extra time goes into features that turn known risks into tested controls, which counts for the security score (30%). Some also make a stronger live demo, which counts for innovation and interaction (30%). The settlement transaction hash stays the top priority: it is deliverable 6 and the on-chain bonus.

**Rules that still apply:**
- Only the lead's session edits `kernel/`, `costledger/`, `db/` and `migrations/`.
- Each member works on their own branch and opens a PR.
- Nothing is marked done without test output.
- **Build cutoff is Oct 19, 20:00 BST.** Oct 20 is for the submission pack only.

---

## 1. New features

### Kernel controls (lead, Opus-reviewed before merge)

| ID | Feature | Closes | Design in one paragraph |
|---|---|---|---|
| **BK-301** | **Velocity limits** | R1 split purchases | Optional scope fields `window_limit` (minor units) and `window_seconds`. Inside `authorize`, under the mandate lock, every grant on the path that has a window limit is checked. The check sums the amounts of reserved, submitted and settled transactions in that grant's whole subtree created within the window; adding this request must not exceed the limit. Attenuation: a child's window limit must be no larger than its parent's whenever the parent has one. Refusal code: `VELOCITY_LIMIT_EXCEEDED`. |
| **BK-302** | **Approval threshold** | (new control) | Optional scope field `review_above`. A request above that amount becomes `proposed` (holds no funds) until the mandate owner approves on their phone. It can only make outcomes stricter. A child's threshold must be no larger than its parent's. This drives the demo moment "agent asks → owner's phone shows it → approve → testnet transfer". |
| **BK-303** | **Mandate-bound settlement services** | R2 | New table `mandate_settlers(mandate_id, principal_id)`. The owner names which service may settle that mandate (`POST /mandates/{id}/settlers`). `_require_settler` checks that binding instead of just `kind = service`. |
| **BK-304** | **Per-principal inference budget** | R7 | Daily micro-USD cap per principal, enforced in the cost ledger alongside the global and route buckets. One agent can no longer drain everyone's model budget. |
| **BK-305** | **Replay before interpret** | R9 | `/agent/request` looks up the idempotency key first. A retry returns the stored decision without paying for a model call again. |
| **BK-306** | **Signed grant receipts** *(stretch)* | (innovation) | Each delegation returns an Ed25519-signed receipt (grant ID, holder, amount, scope hash, expiry), which can be verified offline with the kernel's public key at `GET /.well-known/kernel-key`. |

All of these go into one migration (`005_robustness.sql`, reserved for the lead) and one ADR (`ADR-0008`).

**API contract freeze:** the new scope fields are optional and default to "off". The lead pushes the schema change for BK-301/302 **first** (target Oct 16 morning), so Member 2 builds against the final shape. Until then, treat these fields as optional.

### Settlement hardening (Member 3, on top of BK-075)

| ID | Feature |
|---|---|
| **BK-311** | Wait for a configurable number of confirmations (default 2) before calling `settle_confirm`, and tolerate a re-org back to pending. |
| **BK-312** | Gas-price ceiling. Above it, the transfer waits (stays `submitted`) and is never re-signed with a new nonce. |
| **BK-313** | `settle_fail` only with a verified on-chain proof: a mined receipt with `status = 0`, or the nonce taken by another transaction (security requirement 6.1). |
| **BK-314** | Static recipient → address registry (config file or migration 003). An unknown recipient is refused before signing. |
| **BK-315** | Block-explorer link (Base Sepolia) stored with each transaction and returned by the API, so the dashboard and evidence pack can link to it. |

### Dashboard (Member 2, on top of BK-090)

| ID | Feature |
|---|---|
| **BK-321** | Mobile-first and installable (PWA manifest + icons). Owner screens are designed for a phone first. |
| **BK-322** | Approval inbox: held requests with reason, amount and model trail, plus approve and deny. Polls every 3 s. |
| **BK-323** | **Kill switch:** revoke a grant with one tap and a confirmation step. Shows what was reclaimed and what was already in flight. |
| **BK-324** | Velocity meter per grant (window used / limit) and the approval threshold, once BK-301/302 land. |
| **BK-325** | Explorer links on settled transactions (BK-315). |
| **BK-326** | Playwright smoke test: sign in → mandate view → run one attack scenario. |

---

## 2. Who does what

The lead built M0 to M5, so phase 2 is deliberately weighted toward Members 2 and 3. The lead keeps only the kernel design work, plus review and merge.

### Lead (Nishmam + Claude): design, review, merge
- **Kernel core:** BK-301 velocity limits and BK-302 approval threshold. They change the money logic, so they stay with the code's author. The schema is pushed first, as the contract freeze.
- **Review and merge** every PR. Kernel-touching PRs also get the Opus review.
- **Final security pass** and the self-assessment update (Oct 19).
- **Owner actions:** registration email, DB password rotation, share the model API keys privately with the team, final submission email.

### Member 2 (RTX 2070 Super): product, story and evaluation
- BK-090 dashboard + BK-321 to 326.
- **BK-305** replay before interpret. This is in `api/` and `routing/`, not the kernel. Test: a retry with the same key makes no second model call.
- **BK-150 Live evaluation:** run `eval/runner.py --config B`, `C` and `D` once the lead shares the keys. Record the results in `memory/evaluation/RESULTS.md` with model IDs and dates. Report numbers exactly as measured.
- **BK-120 Deck** (deliverable 2, 10 minutes or less).
- **BK-160 Technical document draft** (deliverable 1). The deck and the document tell the same story, so they're written together. Sources: the ADRs, the README, the self-assessment and RESULTS.md. The lead reviews it.

### Member 3 (RTX 5060): chain, evidence and video
- BK-075 settlement adapter + BK-311 to 315.
- **BK-303** mandate-bound settlement services. This is the one kernel change a member makes, because it is part of settlement. It touches `kernel/ops.py` `_require_settler` plus a table in migration 003. The PR needs the lead's review and the Opus review.
- **BK-304** per-principal inference budget *(stretch, after BK-311..315)*. Changes to `costledger/` follow the same review rule.
- **BK-130 Execution evidence pack** (deliverable 6): a script that exports every testnet transaction (hash, explorer link, amount, kernel transaction ID, audit trail) to `evidence/` as Markdown and JSON.
- **BK-140 Demo video** (deliverable 3, 5 minutes or less): write the script, record and edit once the dashboard and settlement work end to end.

### Ownership exception
The rule "only the lead edits kernel, costledger, db and migrations" is relaxed for **BK-303** and **BK-304** only. Each needs:
- its own branch
- a claim on WHO_IS_WORKING
- tests
- the lead's review and the Opus review before merge

Migration numbers: **003** is Member 3's (settlement + `mandate_settlers`), and **005** is the lead's (BK-301/302).

---

## 3. Timeline

| Day | Lead | Member 2 | Member 3 |
|---|---|---|---|
| **Oct 15 (today)** | ADR-0008; share keys privately; owner email | Set up; scaffold `frontend/`; sign-in + mandate view | Set up; verify USDC contract; create and fund testnet wallet (report back) |
| **Oct 16** | Push the BK-301/302 schema (contract freeze); implement | Agent request box, approval inbox, kill switch; BK-305 | Signing + `on_submit` + broadcast + reconciler with a fake chain; BK-303 |
| **Oct 17** | Opus review of 301/302; review PRs | Attack panel, budget/audit, PWA, velocity meter; live eval B/C/D | **First real Base Sepolia transfer + hash**; BK-311 to 314 |
| **Oct 18** | Merge settlement + BK-303 (Opus review); integration run | Tech doc draft + deck draft; Playwright smoke | BK-315; evidence-pack script; video script; BK-304 if time |
| **Oct 19** | Final security pass (Opus); review tech doc; freeze at 20:00 | Tech doc + deck final | Record + edit video |
| **Oct 20 (by 12:00)** | Assemble the 6 deliverables; email before 17:00 BST | Final read of doc + deck | Final evidence export |

## 4. Cut order if late
1. BK-306 signed receipts.
2. BK-326 Playwright smoke and PWA polish.
3. Config D (OpenRouter).
4. BK-304 per-principal budget (stays disclosed as R7).

**Never cut:** BK-075 with a real transaction hash, kernel tests and invariants, and the six deliverables.

## 5. Opus review gates
1. ADR-0008 and BK-301 to 305 before merge.
2. The BK-075 settlement PR against security requirements 6.1 to 6.6.
3. Oct 19 final security pass, and the self-assessment updated so that closed risks show their new tests.
