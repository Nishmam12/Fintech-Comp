# Budget Kernel UI: design spec (Opus, 2026-10-19)

**Mockup:** open `docs/design/mockup.html` in a browser. It shows three frames: Mandate (owner, 1280 px), Ask (agent, 1280 px) and Mandate (phone, 390 px). This document is what to build. The mockup is how it should look.

**UI freeze: 2026-10-19 24:00 BST.** After that, only bug fixes. Afnan records the final video on Oct 20 morning; Daniel re-shoots screenshots on Oct 20 morning.

## The idea
The product's claim is "Models propose. The kernel decides." The interface draws that literally:
- A **model proposal** is a *dashed, provisional slip*: grey text on no fill.
- A **kernel verdict** is *solid ink with a stamp* (Approved, Held, Refused) in the state colour.
- The **mandate** is drawn like a *cheque face*: a fine guilloché line pattern (security printing), a serial number made from the mandate id, and the amount in expanded numerals.

Everything else stays quiet: paper, ink and rules. Colour appears only where it means a state.

## Tokens (replace the current ones in `frontend/app/globals.css`)
| Token | Light | Dark | Use |
|---|---|---|---|
| `paper` | `#f1f2ee` | `#121614` | page background |
| `sheet` | `#fbfbf8` | `#1a1f1c` | raised surfaces: cheque, fields, verdicts |
| `ink` | `#17201c` | `#e9ece6` | text, primary buttons, strong rules |
| `ink-2` | `#3a453f` | `#c3cbc4` | secondary text |
| `muted` | `#5e675f` | `#8f998f` | captions, dashed proposal borders |
| `rule` | `#d6d9d1` | `#2c332e` | hairlines |
| `approve` | `#1d6b47` | `#4fb486` | Approved, Settled, Protected, integrity intact |
| `held` | `#9a6700` | `#e0a63a` | Held, Reserved, waiting, Review count |
| `refuse` | `#a8361f` | `#f07a5e` | Refused, Rejected, broken history, Revoke |

**Rules**
- Primary buttons are ink-filled with paper text.
- Secondary buttons have an ink outline.
- Destructive buttons have a `refuse` outline, and turn refuse-filled only on the confirm step.
- **No cobalt or blue anywhere.** No shadows.
- Radius is 0 on surfaces, 6 px on small controls, and 999 px only on the role pill and count badge.

## Type
- **One family: Archivo**, via `next/font/google` with `axes: ["wdth"]`. Remove Bricolage Grotesque and Public Sans.
- **Text:** width 100, weight 400 or 600. Sizes 13, 14, 15 and 16 px; body is 15–16 px.
- **Figures and headings** (the `.fig` class): `font-variation-settings: "wdth" 125`, weight 700, letter-spacing −0.01em, with `tabular-nums` everywhere.
  - Cheque amount: 64 px on desktop, 40 px on a phone.
  - h2: 22 px.
  - Verdict stamp: width 115, weight 800.
- **No ALL CAPS labels. No monospace.** IDs use Archivo width 80 with 0.08em tracking (the cheque serial style).
- **Separators:** commas, not middle dots.

## Shell (`components/App.tsx`)
- **Remove the dark side rail.**
- **Top bar:**
  - Left: brand "Budget Kernel" (fig, 20 px) and the tagline in `muted`.
  - Right: the user's name, a role pill (outlined: Owner, Manager or Agent), and a "Sign out" link.
- **Tab row below the top bar:** text tabs with a 2 px ink underline on the current tab. Review shows a count badge in `held`. Keep the role-aware tab sets exactly as they are.
- **Phone:**
  - The top bar shows the brand and the role pill only. Sign out moves to Settings.
  - Bottom tab bar on `sheet` with a 1 px rule. The current tab is ink, bold, with a 2 px ink line on top.
  - At most 5 tabs (already true).
- Content max width is 1240 px with 28 px padding (16 px on a phone).

## Mandate (`components/MandateView.tsx` + `IntegrityBadge.tsx`)
1. **Cheque** (full width, the one bold element):
   - **Surface:** `sheet` with a 1 px ink border.
   - **Guilloché:** an SVG behind the content, generated client-side. Copy the script from the mockup into a small `components/Guilloche.tsx`, which needs no data.
   - **Header row:**
     - Left: "Spending mandate, issued by {owner_name}".
     - Right: serial "No. {first 8 hex of mandate id, as XXXX XXXX}, valid to {date}".
   - **Amount:** the total (fig) with "USD" smaller beside it.
   - **One sentence:** "Agents below may spend within their limits. {reserve} is held back and can never be spent."
   - **Allocation bar:** 12 px high with a 1 px ink border. Segments: Spent (`ink`), Waiting to settle (`held`), Free (`sheet` with a fine vertical hatch, as in the mockup), Protected (`approve`).
   - **Legend:** swatch, label, then the figure.
2. **Two columns** (7 : 5, stacking on a phone):
   - **Left: "Who may spend"**, a ledger, not cards.
     - The table starts with a 2 px ink top rule.
     - Header row (13 px muted): Holder, Free, Reserved, Spent.
     - One row per grant, indented by depth with a 2 px `rule` left border per level.
     - The name is bold, with a role line under it: "Owner's root grant", "Manager, may pass authority on" or "Agent". Add ", N refused in the last 10 min" when there are strikes.
     - Figures are right-aligned, with Free in fig.
     - Under the row, a limits line: "Up to X per payment", "Your approval above Y", and "This hour U of L" with a thin meter.
     - Status: show a small stamp next to the name only when the grant is not active ("Suspended", "Revoked", "Expired"). Use `held` for suspended and `refuse` for revoked.
     - **The "⋯" button** opens the existing Manage controls (SuspendControl, RevokeControl) in a popover or an inline panel under the row. **Keep every confirm step and every visibility rule unchanged**: owner-only reinstate, and `canManage`.
     - On a phone, show only the name, Free and ⋯.
   - **Right column:**
     - **Seal** (replaces the two green boxes, invariants and integrity): a 56 px circular seal (two rings and a check) in `approve`. Beside it, "History intact, N records" plus one sentence and "View on explorer" when there is an anchor.
     - If the invariants fail or the history is broken, the seal turns `refuse` with a cross, and says exactly what broke (`broken_at`, the reason, or the violation count). The invariant check is folded into the same seal line: "Ledger checks pass".
     - **"Decisions" stream:** the last 10 transactions as proposal → verdict pairs.
       - Proposal slip: "{holder_name} asked" plus "Pay {amount} to {recipient} for {category}".
       - Verdict: a stamp (Approved, Held, Refused, Settled, Released) plus one plain sentence from `reasonText`.
       - Settled rows add "View on explorer".
       - The subtitle explains it once: "Left, what the model proposed. Right, what the kernel decided."
3. Keep "Updated {time}" and Refresh, small, at the right of the "Who may spend" heading.

## Ask (`components/AskView.tsx`)
- **Left column (5):**
  - h2 "Ask to pay".
  - "Spend from" select.
  - "Request, in your own words" textarea.
  - Example chips: outlined, with the expected outcome under each.
  - Primary button **"Send to the kernel"**.
- **Right column (7, `aria-live="polite"`):** one large proposal → verdict pair.
  - **Proposal slip:** "The model read it as" with amount, recipient and category in bold, plus "Untrusted. The model only proposes." When the request was not sent to the kernel, the slip says why.
  - **Verdict:** a large stamp (22 px, 3 px border) and the plain reason at 20 px.
  - **Below, a rule, then one consequence sentence:**
    - Refused: "Nothing was reserved. This refusal counts as N strike(s); at 5 in 10 minutes the grant is suspended until the owner reinstates it."
    - Held: "No money is reserved until the owner approves."
    - Approved: "{amount} is reserved for this payment."
  - **Before anything is asked:** an empty dashed slip saying "Your request will appear here, next to the kernel's decision."
- The model trail stays available in a collapsed "How the model read this request" section under the consequence line.

## Review (`components/ReviewView.tsx`): Daniel
- Each held request is a **cheque awaiting signature**: a `sheet` surface with a 1 px ink border and no guilloché, so only the mandate has it.
  - "{holder} asks to pay"
  - The amount (fig, 40 px), recipient and category
  - "Held because …" in `held`
  - The proposal in a collapsed dashed slip
- **Buttons:** "Approve" (ink filled) and "Deny" (outline). Non-owners see the waiting sentence instead, unchanged.
- **Empty state:** "Nothing is waiting for you. Requests above an agent's approval limit appear here."

## Settings and Sign-in: Daniel
- **Settings:** an identity block listing name, role, mandate serial and key expiry. Under it, "Rotate key" as an outline button with the existing confirm. Sign out appears here on phones.
- **Sign-in:**
  - Replace the dark left panel with the cheque treatment: a guilloché panel with the tagline in fig, 56 px.
  - Demo buttons are outline buttons, one per person, showing name and role ("Nabil, owner").
  - Below them, "Or paste an API key".
  - The B1 behaviour (no buttons in production builds) must stay.
- **Toast:** an ink-filled bar with paper text, bottom centre, auto-dismissed after 4 s (keep the logic).

## Activity and Attack lab: Afnan
- **Activity:**
  - A timeline with a 2 px rule down the left. Each event is a dot in its state colour plus the existing sentence, with the time on the right.
  - Group events under day headings ("Today", "Yesterday").
  - The inference budget becomes a compact ledger table: label, spent, cap, remaining.
  - Put agent buckets (named) first and internal buckets (global, primary, escalation, eval, retries) under a "System budgets" sub-heading.
- **Attack lab:**
  - A ledger with one row per attack: name, one-line description, then two verdict cells, "Without the kernel" and "With Budget Kernel", each with a stamp ("Broken" in refuse, "Held" in approve) and the measured sentence.
  - Show money values as money, not raw minor units.
  - Per-row run buttons are outline; **"Run all attacks"** is the only ink-filled button.

## Accessibility and quality floor
- Contrast: text on `paper` and `sheet` at least 4.5:1. Check `muted` on `paper`, and the stamp colours on `sheet`.
- Visible focus: a 2 px ink outline with 2 px offset.
- Reduced motion: no animation except the toast.
- Everything works at 390 px with no horizontal scroll.
- Dark mode uses the dark column of the token table. Guilloché strokes become `#26302a` / `#2e382f`.
- Model and user text is rendered as plain text only. This is unchanged and must stay so.

## Who builds what (today, before 24:00 BST)
| Who | Files | Due (BST) |
|---|---|---|
| **Lead session (Sonnet)** | `globals.css`, `layout.tsx` (fonts), `App.tsx` (shell), `components/Guilloche.tsx`, `MandateView.tsx`, `IntegrityBadge.tsx` (seal), `AskView.tsx`, plus the token classes everyone uses | Tokens and shell pushed by **12:00** so others can build on them; Mandate and Ask by **17:00** |
| **Daniel** | `ReviewView.tsx`, `SettingsView.tsx`, `SignIn.tsx`, `Toast.tsx`, `SuspendControl.tsx` / `RevokeControl.tsx` restyle (behaviour unchanged) | Branch from `main` **after 12:00**; PR by **20:00** |
| **Afnan** | `ActivityView.tsx`, `SimulationView.tsx`, `lib/describe.ts` (if needed) | Branch from `main` **after 12:00**; PR by **20:00** |
| **Lead (you)** | Click-through of the whole story at 1280 and 390 px, light and dark | **21:00**; fixes until 24:00 |

Every PR: `tsc`, lint and build pasted in; screenshots at 1280×800 and 390×844; no change to server calls, permissions or plain-text rendering.
