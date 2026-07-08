# Then & Now redesign — integration review notes

Integrated `design/thennow-modal-redesign.html` into the live page. Edited the
source `oracle/thennow_template.html` and regenerated with `python main.py html`
(template ↔ generated parity verified for all three pages). No console errors on
thennow / datasources / dashboard.

## (a) Implemented

- **Palette/tokens** already applied by the prior design pass were kept. Added
  `--then` / `--peak` / `--bottom` / `--accent-dim` / `--panel3` so the mock's CSS
  and the canvas colors resolve. Removed unused `--met` / `--notmet`.
- **A. Topbar** — right-aligned `⚙ Options` + `Last update: …`, reusing the
  dashboard `#opts-btn` / `#topsub` convention. Wired to a real timestamp: added
  `updated` (db `last_update`) to the `oracle/thennow.py` payload; falls back to
  `asOf` if the DB has no timestamp.
- **B. Hero** — the root projected peak date is the loudest element (clamp up to
  ~88px), with an eyebrow, one-line lead, the start→today→peak→bottom arc, and
  range / metrics-live / as-of chips.
- **C. Metric cards** — date-led `.mcard`: "Projected peak" + big date dominate,
  a canvas mini-sparkline (dot-com dashed to convergence, dashed projection, solid
  AI, convergence dot), phase + intensity footer. WIP branches are honest ("not
  wired yet", no chart). Cards open the full modal on click.
- **D. Sidebar roll-up tree** — preserved and restyled to the mock (collapsible
  carets, live/WIP dots, per-row peak date). Tree rows and cards are both entry
  points to a metric's full view.
- **E. Modal** — breadcrumb; `Projected peak — <metric>` label + big date + sub;
  phase **ribbon** with a "you are here" marker; HTML **legend**; the **canvas**
  chart with grey dot-com **dashed, only to the convergence point**, a blue
  **dashed projection** continuing past convergence through the peak to the
  **bottom**, one **area fill** under the actual AI line, four vertical **markers**
  (start / today / peak / bottom) each with an **HTML dual-timeline chip** (AI date
  over dot-com date; the start chip names ChatGPT / Netscape), and a **month-year
  AI x-axis** (solid actual → dashed projected). **Evidence tiles** below the chart.
  **Hover** crosshair with an HTML readout (AI date · %, dot-com and AI values).
  Derivation is a **3-step summary** + a **"full method & sources ↗"** link to Data
  Sources. **Download CSV** and **×** sit in the **top-right corner**.
- **F. Global Options & assumptions drawer** — opened by the topbar `⚙ Options`,
  8 shared items. Replaced the per-metric options block; the modal side now holds
  only the derivation.
- **Weights preserved** — the adjustable child weights live in the parent's modal
  side panel; changing them recomputes the node + ancestors and re-renders the
  hero, cards, tree, and modal live.
- **CSV** kept (raw / smoothed / multiple_x / intensity + projected AI-lifecycle
  rows).

## (b) Omitted / changed, and why

- **Kept the hand-rolled `<canvas>` stack — did not swap to SVG.** Per the brief.
  Marker labels, hover, legend, ribbon, and tiles are HTML positioned over/around
  the canvas (the brief's suggested pattern). Everything the mock shows is present.
- **Dropped the old "hide graph / show-all" card controls.** The mock has no
  per-card hide; cards are pure entry points and the tree is the navigation. If you
  want hide back, easy to re-add.
- **Bottom marker/date is computed client-side** from `DATA` (each node's measured
  pace × the dot-com crash-low progress), not added to the Python payload — it is
  purely derived from values already in `DATA`, so no engine change was needed.
  See open question 1.
- **"Full method" link** points at the existing per-graph Data Sources pipeline
  (`datasources.html#src:tn_price` / `tn_cape` / `tn_valuation`) — the closest
  existing anchor. No dedicated prose method section exists there yet. See open
  question 2.
- **Weights control placement** — put in the parent's modal side panel (the mock
  didn't re-mock the control). Works and restyled; trivial to relocate.

## (c) Open questions for you

1. **Bottom date source of truth.** Keep the client-side derivation, or make it
   canonical in `oracle/thennow.py` (so it's in the payload and CSV headers)? Both
   produce the same number.
2. **Data Sources "full method".** Want a concise prose method section added to
   `datasources.html` (anchors / smoothing / matching / projection) for the link to
   target, instead of the per-pipeline anchor? Happy to write it.
3. **Marker crowding.** Today and peak markers can sit close; the two-row stagger
   handles current widths. At very narrow widths, prefer dropping the dual labels to
   single, or hiding the least-important marker?
4. **"Metrics live 1 of 4"** counts top-level branches (Valuation wired;
   concentration / capex / speculation WIP). Confirm that framing vs. counting
   leaves (which would read "2").
5. **Peak label.** The peak marker reads "Feb 2000" (the smoothed monthly top); the
   famous intraday high was 2000-03-10. The drawer explains the smoothing. OK as is?
