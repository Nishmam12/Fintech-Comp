# UI revision 3: build your screens (Daniel, Afnan)

Freeze is **24:00 BST tonight (Oct 19)**. PR by 22:30 so there is time to fix. Lead has pushed the foundation (commit a199f5b+):
the shell, the shared components, **Sign-in, Mandate and Ask** (done, do not touch). Pull `main` first.

Look at the target first: open `docs/design/mockup.html` (gallery; or `?screen=review|activity|attack|settings`), read `docs/design/UI_SPEC.md`
("Layout system" and the screen table).

## Who builds what
| Owner | Screens | Branch |
|---|---|---|
| Daniel | `ReviewView.tsx` (8 + 4: held cheques, "Approval rules" on the right), `SettingsView.tsx` (6 + 6), `Toast.tsx` restyle, the Suspend and Revoke panels' styling | `daniel/BK-R3-review-settings` |
| Afnan | `ActivityView.tsx` (8 + 4: timeline grouped by day, counters + model budgets on the right), `SimulationView.tsx` (the attack ledger: 7 equal rows, "Run all attacks" in the heading) | `afnan/BK-R3-activity-attack` |

Claim your row in `memory/WHO_IS_WORKING.md`, branch from `main`, open a PR. Do not edit `App.tsx`, `ui.css`, `components/ui/*`, `kernel/`, `db/`.
If you need a change there, tell the lead. No changes to `lib/api.ts` request paths or permission checks.

## How a view is built
1. Return `<Section>`s (a fragment). `App` puts them in the 12-column grid. Spans are only 12, 8 + 4 or 6 + 6.
2. In your view file set `export const native = true;` (it is `false` now, which makes App wrap the old content in one section).
3. Use what exists: `Section` (heading, scrolling body, optional `head` rows and `foot`), `Filler` (ruled empty rows; one plain sentence),
   `Cheque`, `Stamp`, `ProposalVerdict`, `Seal`, and the CSS classes in `app/ui.css` (`row`, `name`, `num`, `cells`/`cell`, `held-cheque`,
   `day`, `tl`, `dot`, `attack-body`/`atk`, `btn`, `btn ghost`, `field`). Read `MandateView.tsx` and `AskView.tsx` as the examples.
4. **Rules that make it symmetric**
   - Everything is `rem`. No `px` except 1 px hairlines. No `max-width` containers. Nothing centred in a void.
   - Halves share heading top and bottom (Section does this). Rows are `--row` (3.5rem) tall. Empty space is `Filler` rows, never blank.
   - Lists scroll inside their Section body; the page itself never scrolls at 1024 px and wider.
   - Sentence case, no ALL-CAPS labels. Money with units ("80.00 USD"; `figure()` in MandateView for the large number). Colour never alone: the word carries it too.
   - Everything model- or user-derived is rendered as plain text.
5. **Phone (< 768 px):** the page scrolls, one column; the CSS in `ui.css` already handles rows and sections. Check it.

## Check before you push (paste the output in the PR)
```
cd frontend
npx tsc --noEmit && npx eslint components app lib
npm run check:reasons
npm run check:layout        # needs the API on :8000, `npm run dev`, and `uv run --project backend python scripts/demo_seed.py` first
```
`check:layout` signs in with the demo accounts and checks every screen at 1366, 1920, 2560, 1024 and 390 px: no side gaps, no page scroll,
equal section bottoms and heading tops, uniform scale. It must print `ALL CHECKS PASS`. Then look at it yourself at 1366 and 390.
The state call takes about 5 s from this network, so wait for the screen to fill before judging it.

## Content to keep (behaviour unchanged)
- Review: Approve and Deny call the same endpoints; the untrusted model proposal stays a collapsed "Model proposal (untrusted)". Only the owner sees Review.
- Settings: key rotation with its confirmation and the one-time key display; **add a Sign out button** (on phones the top bar has one too).
- Activity: every event keeps its plain-language line (`lib/describe.ts`); budget names stay as they are.
- Attack lab: scenarios, "Run again", results exactly as the API returns them, "Run all attacks".
