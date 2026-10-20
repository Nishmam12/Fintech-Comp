# Demo video script (final): about 4:30 finished, hard limit 5:00

> **The animated film is now planned in [`STORYBOARD.md`](STORYBOARD.md)** (4:00, voice-over 411 words, build brief for Claude Opus and Remotion). This file is the **fallback**: a live screen recording of the same story, if there is no time to build the animation.

Rules from the organiser: the demo video is **optional and 5 minutes or less**. (The 10 minutes is the limit for the deck presentation, not the video.) Aim for about 4:30 finished, which leaves 30 seconds of margin.

Speak at a calm pace, about 140 words a minute: the 387 words below take about 2:45 to say. The rest of the time is clicking and the screen filling (about 5 seconds a screen), so each clip has a **target length** that includes the on-screen actions. Record each clip separately and join them; a bad clip can be redone alone. The set-up, the usernames and "what to do if something goes wrong" are in `RECORDING_RUNBOOK.md`; this file is what you say and show.

Everything on screen is real and runs on the final build: sign-in, setup, the kernel's decisions, the attack lab. Settlement in the take is simulated, and the script says so.

| Clip | On screen | Words | Spoken | Target clip length |
|---|---|---|---|---|
| 1 | The sign-in screen | 40 | 0:17 | 0:20 |
| 2 | Slide 2 of the deck (the diagram) | 36 | 0:15 | 0:18 |
| 3 | Create account, Setup | 84 | 0:36 | 0:55 |
| 4 | The agent signs in and asks | 62 | 0:27 | 0:40 |
| 5 | Held request, owner approves | 27 | 0:12 | 0:30 |
| 6 | Probing, suspension, reinstate | 22 | 0:09 | 0:30 |
| 7 | Attack lab | 51 | 0:22 | 0:35 after cutting the wait |
| 8 | Seal, then the explorer | 58 | 0:25 | 0:35 |
| 9 | Closing screen | 7 | 0:03 | 0:08 |
| | | **387** | **2:46** | **4:31** |

Clips 3 to 7 are longer than the speech because you are clicking and the screens take about 5 seconds to fill. Talk over the waits where you can; cut the rest when you join the clips.

---

## Clip 1: the problem (sign-in screen)
**Show:** the sign-in screen, the cheque and the tagline. Do not click anything yet.

> AI agents are starting to spend money. And if a language model can authorise a payment, one bad prompt can drain the wallet. Budget Kernel puts a deterministic gate between the model and the money. Models propose. The kernel decides.

## Clip 2: the idea (deck slide 2, the diagram)
**Show:** the diagram slide. Point at "model", then "kernel", then "settlement".

> The model only proposes. Plain code, not a model, checks the mandate, the scope, the limits and the balance, inside one database transaction, and reserves the money. Nothing a model says is ever trusted as authorisation.

## Clip 3: a real account and setup (about 40 seconds on screen)
**Show:** back in the browser. Click **Create account**. Type your name, a username, the passphrase twice; click the eye once to show it. **Create account**. On **Setup**: **Create the mandate** with the defaults. Type `Research bot`, **Add agent**; **Copy the key**, then **I have stored it**. **Give this agent a budget**. **Open the dashboard**. End on the cheque and **Who may spend**.

> A person creates an account with a password. It is hashed, five wrong tries lock it, and the session disappears when you reload. A new account has no money. The owner funds a mandate, here a thousand dollars, of which a hundred is protected and can never be spent. Then the owner creates an agent. Its key is shown once. And gives it a narrower budget: three hundred dollars, at most a hundred for one payment, and anything above sixty needs the owner's approval.

## Clip 4: the agent asks (a second tab)
**Show:** open a new tab. **Use an API key instead**, paste the key, **Sign in with the key**. **Ask**. Click the 20 USD example, **Send to the kernel**: *Approved*. Then the 150 USD example, **Send**: *Refused*.

> The agent signs in with its own key. A plain-language request becomes a typed proposal on the left. It is untrusted. The kernel's verdict is on the right. Twenty dollars is inside the grant, so it is approved and the money is reserved. A hundred and fifty is over the limit, so it is refused, with a reason, and nothing is reserved.

## Clip 5: a held request (agent tab, then owner tab)
**Show:** agent tab, the 80 USD example: *Held*. Switch to the owner tab, **Review**, **Approve**; the inbox empties.

> Eighty dollars is above this agent's approval line. So the kernel holds it and reserves nothing. Only the owner can approve, and approving runs every check again.

## Clip 6: probing is stopped (agent tab, then owner tab)
**Show:** agent tab: send the 150 USD request four more times; the fifth says the grant was suspended. Owner tab, **Mandate**: Research bot is *suspended*; **⋯**, **Reinstate this grant**, **Confirm reinstate**.

> An agent that keeps testing its limits is suspended automatically after five refusals. Only the owner can reinstate it. The agent cannot.

## Clip 7: the attack lab (owner tab)
**Show:** **Attack lab**. Click **Run** on *Concurrent overspend* only. It takes about 30 seconds: keep talking, or cut the wait. *Broken* without the kernel, *Held* with it.

> The same attack runs against an intentionally unsafe baseline and against the real kernel, on a real database. Eight payments arrive at once, for a budget that covers three. The baseline spends twenty-four hundred dollars against a nine hundred dollar budget. The kernel approves exactly three, and reserves exactly nine hundred.

## Clip 8: the evidence (owner tab, then two explorer tabs)
**Show:** **Mandate**, point at the green seal. Then the settlement tab, then the anchor tab (links in the runbook).

> The history is hash-chained, and the seal checks it. Two kernel-approved payments settled on Base Sepolia, a public testnet, and the head of the history is anchored there too, so editing the past is detectable. These came from earlier runs. This take uses simulated settlement. It is a testnet prototype, not audited, and must not hold real funds.

## Clip 9: close
**Show:** the sign-in screen, or the repository page.

> Budget Kernel. Agents propose. The kernel decides.

---

## Checks before you save the file
- **Length is 5:00 or less.** Check the exported file, not the timeline.
- Sound is clear in the first ten seconds; no notifications, no terminal, no `.env` on screen.
- The agent key shown on screen is a throwaway demo key on a scratch schema. Say "demo key" if it is visible for more than a second.
- The username and passphrase you type are a demo account. Do not type a real password.

## If you are over 5:00
Cut in this order: the clip 7 wait (speed it up or cut it), then clip 2 (clip 1 already says it), then the second half of clip 3.

## If you want it shorter (about 3:00)
Drop clips 2 and 6. The story still holds: account, setup, ask, held, attack lab, evidence.

## Do not say
- "Secure" or "unhackable". Say what was measured: 0 unauthorised approvals in every run, the kernel held in 7 of 7 attacks, synthetic data, testnet only.
- That the payment on screen settled on chain: it did not; the two explorer pages are earlier real transfers.
- Anything about password reset by email, multi-factor sign-in or identity checks: none exist.
