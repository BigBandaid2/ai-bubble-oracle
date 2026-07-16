# AI Bubble Oracle — site-wide integration brief (v2)

Handoff to the implementing (code) agent. **You edit the functional site; the design agent
only edits `/design`.** This v2 supersedes v1: the Then & Now redesign is already integrated
into the live `thennow.html`, and the job now is to bring **every page onto that one system**
plus a set of specific refinements.

## 0. Prime directive: form follows function

Follow the mocks' **aesthetics, hierarchy, and interaction conventions**, but you own the
**implementation**. Where an element is impractical for the hand-rolled stack, conflicts with how
the engine actually works, or it's unclear how a visual maps to real functionality: **omit it and
raise the issue** rather than forcing it or inventing data. End with `REVIEW-NOTES.md`:
implemented / omitted (why) / open questions.

## 1. Current state (read first)

- **`thennow.html` is the reference design** — already integrated (dark data-terminal system:
  hero with the projected-peak date as the punchline, date-led metric cards with canvas
  sparklines, roll-up **tree sidebar**, per-metric **modal** with canvas chart + four
  dual-timeline markers + month-year axis + evidence tiles + derivation summary + weights, and a
  global **Options & assumptions drawer**; topbar `⚙ Options` + `Last update` convention). Reuse
  its CSS tokens and components verbatim — do not re-derive them.
- **The metric set has grown** (see `PIPELINE-PLAN.md`). The live payload tree is now, verbatim:
  ```
  AI bubble bursts (root, peak 2027-11-28, 45%)
    Valuation (roll-up 2027-09-09)
      Price appreciation (roll-up 2027-11-09)
        Nasdaq (leaf 2027-05-05) · S&P 500 (leaf 2028-01-24)
      Valuation multiple (leaf 2026-12-04) · Market cap to GDP (NO PROJECTION)
    Market concentration (roll-up 2026-10-23)  →  Tech leadership (leaf)
    Infrastructure / capex (roll-up 2027-07-11)
      IT investment share (NO PROJECTION) · Tech equipment orders (leaf) · Semiconductor production (NO PROJECTION)
    Speculative activity (roll-up 2029-11-26)  →  Margin debt (leaf) · IPO froth (leaf)
    Monetary & sentiment (NO PROJECTION)  →  Yield curve (NO PROJECTION) · Consumer sentiment (NO PROJECTION)
  ```
  **5 major branches** under root; **6 no-projection nodes** (Market cap to GDP, IT investment
  share, Semiconductor production, and the whole Monetary & sentiment branch) — these are the
  "counter-arguments" that argue beside the headline, not in it. Detected in code as
  `n.valid === false`. This is the reality the refinements below target.
- **`bottomProgress` is now in the payload** — the projected bottom is real data; the earlier
  "no source" gap is closed.
- **Mocks in `/design`:** `about-redesign.html` (done), `thennow-modal-redesign.html` (the modal
  detail study — SVG chart, four dual-timeline markers, evidence tiles, derivation summary),
  **`thennow-page-redesign.html` (NEW — the base landing page: hero + sortable card grid +
  roll-up tree, and a WORKING demo of all seven §4 refinements against the real tree above)**,
  `polymarket-redesign.html`, and `datasources-redesign.html` — **these last two are now faithful
  reskin bases copied verbatim from the live functional `dashboard.html` / `datasources.html`
  (full DOM, tree, drawer, controls, copy preserved)**, plus nav rewired to the mock set. Treat
  mocks as **visual specs**, not code to copy; the engines stay canvas/Python.

## 2. Site-wide changes (all pages)

**Navigation + landing (production-visible):**
- **`thennow.html` becomes the landing page / home** of aibubbleoracle.com, publicly visible
  (drop the `noindex`/WIP-only posture — coordinate the WIP badge's fate with the human).
- **Nav order + labels, identical on every page:**
  `Then and Now` (→ thennow.html, home) · `Polymarket` (→ dashboard.html) · `Data Sources`
  (→ datasources.html) · `About` (→ about.html). The brand mark/word links to `thennow.html`.
- Mark the current page `.active`. Keep the shared `⚙ Options` + `Last update` topbar convention
  where a page has options (thennow, Polymarket, Data Sources); About has no Options button.

**One coherent system, every page:** same `:root` tokens, topbar, type scale, panel/border
treatment, `#opts-btn`/`#topsub`, scrollbars, and drawer pattern as `thennow.html`. No page should
look like it predates the redesign.

## 3. Per-page rework

### A. Then and Now (`thennow.html`) — landing. Apply the seven refinements in §4.

### B. Polymarket (`dashboard.html`) — the "AI bubble burst in 2026?" condition tracker
Mock: `polymarket-redesign.html` — **a faithful reskin base copied from the live functional
`dashboard.html`** (it already carries the unified dark tokens, topbar/nav, `#opts-btn`, the global
`#drawer`, the `<main id="charts">` card grid, AND the `<aside><div id="tree">` roll-up tree).
**The rework here is primarily aesthetic with modest DOM impact — do NOT restructure the page.**
- **Keep every element, control, and copy string** from the functional page: all condition/metric
  charts, the roll-up **tree sidebar** (core functionality, same as thennow — never drop it), the
  Options/Ambiguities **drawer**, the verdict line, thresholds, and **every number shown on a card**.
- **No drill-in modal.** Polymarket cards are **not** intended to open a detail modal — all the
  information on a card today must stay on the card. Do not add a thennow-style modal here.
- **Aesthetic only:** align spacing/type/card treatment to thennow's system where it is a pure skin
  change; you may apply the §4.3 root/roll-up/leaf + branch level cues to the tree/cards. Nav becomes
  the shared 4-link set (Then and Now · Polymarket · Data Sources · About); "Dashboard" → "Polymarket".
- Any DOM change beyond a skin needs a **strong justification**; otherwise leave the structure alone.

### C. Data Sources (`datasources.html`) — feeds + pipeline + ambiguities
Mock: `datasources-redesign.html` — **also a faithful reskin base copied from the live functional
`datasources.html`.** Keep **all** current elements, copy, controls, feeds, the ETL asset graph,
the sidebar, and the ambiguities. **Reserve edits to surface aesthetics; do not change the DOM
without a very strong justification.** Apply the shared tokens/topbar/nav (4-link set) and the
shared drawer treatment. This page stays the **"full method" target** the thennow derivation
summary links to — keep the per-source anchors (e.g. `#src:yahoo`) intact.

### D. About (`about.html`) — DONE as a mock (`about-redesign.html`)
Copy rewritten to center **Then & Now** (the dot-com-clock thesis) while keeping the Polymarket
origin story and the author's casual, self-deprecating voice; broken up with a thesis callout, a
then→now analogy strip, stat tiles, and stack chips. Port that copy + layout into `about.html`.

## 4. Then & Now refinements (the human's specific comments)

**Live-code hook map** (line numbers from the current `thennow.html`; the same code lives in
`oracle/thennow_template.html`). `thennow-page-redesign.html` shows the finished behavior for all
of these:
- **Card "suppressed" text** — `makeCard()`, the `.date` line renders `"suppressed"` when
  `n.valid === false`. Change that string to **"No Projection"** (and it already dims via the
  inline `--muted2` style). The foot already reads "does not fit the analog" — keep it.
- **Tree marker** — `treeNode()` builds `<span class="sdot ${n.wip ? "wip" : "live"}">`, i.e. only
  two states. Add a **third `nop` state** (grey) for `n.valid === false`:
  `n.wip ? "wip" : n.valid === false ? "nop" : "live"`, and add `.sdot.nop` CSS. The tree `sdate`
  already prints `"no fit"` for suppressed — restyle it muted to match.
- **Level cue** — `tierOf(n)` already returns the tier text used in the card `.tier` and is the
  hook for the root/roll-up/leaf pip styling in §4.3.
- **Collapse state** — `const collapsed = new Set()` and the caret handler already exist
  (`treeNode`, the `.caret` click toggles `.schildren.collapsed`). §4.4 reuses this exact set; the
  new work is making `renderCards()` read it (see below), enlarging the caret, and adding the
  header toggle.
- **Cards render** — `renderCards()` / `orderedChildren()` walk the tree in order and currently
  sort only WIP-last. This is where the §4.2 sort and the §4.4 collapse-filter hook in.

### 4.1 Suppressed metrics (the counter-arguments)
- **Tree marker:** metrics with **no projection** (suppressed counter-arguments) get a **grey**
  dot — distinct from the accent-blue "has a projection" dot and the hollow "not wired / WIP" dot.
  Three tree states: `has projection` (accent), `no projection / suppressed` (grey filled),
  `not wired / WIP` (hollow). Update the sidebar legend to match.
- **Card text:** change the card's **"suppressed"** label to **"No Projection."** Keep the metric
  readable (it still has a chart and a counter-argument observation) — it just doesn't assert a date.

### 4.2 Sort control (main body)
Add a sort control above the card grid (segmented control in the thennow style): **Tree order**
(default) · **Projected date** · **A–Z**. Suppressed/no-projection cards sort last under "Projected
date." Persist the choice (localStorage) like the rest of the page state.

### 4.3 Root / roll-up / leaf + major-branch distinction (thennow AND Polymarket)
A **light** visual system, no palette bloat:
- **Level:** distinguish **root** (the headline blend) vs **roll-up** (a parent that blends
  children) vs **leaf** (an end metric). Use the existing tier text plus a subtle level cue — e.g.
  a small hierarchy glyph before the name and three restrained tier-pill styles (root: accent
  outline; roll-up: neutral; leaf: plain). Do **not** use a coloured left-border card accent.
- **Major branch:** group/mark cards by their top-level branch (Valuation, Monetary & sentiment,
  WIP…) — e.g. a subtle branch section header over the grid, or a small branch tag shared between
  the card and its tree row so you can trace a card to its branch. Keep it neutral/tonal, not a
  rainbow.

### 4.4 Tree collapse / expand
- **Collapsing a branch hides that branch's cards from the main body** (re-render the grid to
  exclude collapsed subtrees; respect the active sort).
- **Bigger caret hit target:** the collapse/expand control is tiny today — give it a comfortable
  ~24px tappable area (padding/min-size), keep the glyph small.
- **Tree-level toggle:** one control in the tree header that reads **"Collapse all"** when
  everything is expanded (collapses to the top-level roots) and **"Expand all"** when any branch is
  collapsed. Wire it to the same collapse state the carets use.

### 4.5 Landing hero + tree polish (latest comments — reflected in `thennow-page-redesign.html`)
- **Top kicker line:** `AI BUBBLE BURSTS · CONSIDERING <accent>VALUATION + CONCENTRATION + CAPEX +
  MONETARY</accent>` (the four branch families, accent-blue; mono uppercase as today).
- **Drop the analog stat row** under the peak-date hero (the "At peak / Dot-com peak / Blended
  intensity" trio read as filler) — the big date stands alone.
- **Shorten the hero verdict** to one line: *"Every graph below compares the journey of the Dot-com
  bubble against our current AI era. How far are we? Each metric has an opinion."*
- **Declutter the roll-up tree:** it was too busy. **Remove the status dots on root and branch rows**
  (keep a dot only on **leaf** rows — grey = No Projection, accent = has projection). **Remove the
  per-row PEAK dates** from the tree entirely. Let the metric **label take the freed width** (more of
  the string visible). In the live `treeNode()` this means dropping the `sdate` span and gating the
  `sdot` to leaves.
- **LEAF chip → green** (root stays amber, roll-up stays blue) so the three tiers read at a glance.
- **Cards and tree rows open the metric's full view** (in the mock they navigate to
  `thennow-modal-redesign.html`; on the live page they call `openNode()` → the existing modal). Wire
  the **shared 4-link nav** across every page.

### 4.6 Metric-detail modal — responsive (reflected in `thennow-modal-redesign.html`)
The modal currently loses the graph and overlaps at small widths. Priority: **after the headline
peak date, the graph is the most important element and must NEVER be hidden**; the **projected-peak
red line + label is the single most important item on the graph** and is never dropped.
- **Guaranteed graph height** — give the chart container a height floor so it can't collapse to zero
  when the layout stacks (mock: `.chartwrap { min-height: 240px }`, and at ≤1000px it becomes a fixed
  `height: clamp(240px, 42vh, 360px)` instead of `flex:1`). On the live page the chart is `<canvas>`:
  ensure its wrapper keeps a real height at every width and the canvas re-sizes to it (the resize
  handler already redraws — just don't let the wrapper collapse).
- **Modal scrolls, stacks cleanly** — at ≤1000px stack the side/derivation panel BELOW the chart and
  let the modal scroll (`overflow: hidden auto`); the side panel flows into that scroll (`overflow:
  visible`) instead of a nested scroll. **Critical:** when stacked, set the body/main columns to
  `flex: none` (+ `min-height: auto`) — if `.m-main` stays `flex: 1` inside a fixed-height column it
  shrinks below its content (`min-height:0`) and the evidence tiles overflow and **overlap the "How
  this date is derived" panel**. `flex: none` makes each block take its natural height so nothing
  overlaps and the modal simply scrolls. At ≤600px go full-bleed (`inset:0`, no radius), tighten
  padding, and **pin the close button** (`.m-corner { position: fixed }`) so it stays reachable.
- **Marker labels degrade gracefully** — the four vertical markers (start / today / peak / bottom)
  keep their LINES at all widths, but when the chart is tight (mock gate: chart width < 520px) **drop
  only the START and PROJECTED BOTTOM chip labels**; **today and the peak label always stay**. Shrink
  the remaining chip type on phones. Never hide the peak marker or its label.
- Applies to the live `openNode()` modal in `thennow.html` / `oracle/thennow_template.html`; the same
  three moves (height floor, stack+scroll+pinned close, label-drop-order) port directly to the canvas
  renderer.

## 5. Build mechanics (unchanged, still critical)

- Pages are generated from `oracle/*_template.html` via `python main.py html` (`__DATA__`
  injection). **Edit the template**; if you can run the build, regenerate; if not, edit BOTH
  template and generated file identically and verify parity
  (`diff <(grep -v 'const DATA' tmpl) <(grep -v 'const DATA' generated)` empty).
- **The engine is Python** (`oracle/thennow.py`, dashboard/datasources generators); the browser
  gets precomputed `DATA`. Don't port the mock's standalone JS engine. If a refinement needs a
  value not in the payload, add it in Python or derive it client-side from existing `DATA` — say
  which.
- **Charts are hand-rolled `<canvas>`.** Keep them; reskin. HTML chrome (stat strip, legend,
  marker labels, sort control, tree) sits over/around the canvas as HTML, as thennow already does.
- Coordinate with `PIPELINE-PLAN.md` — the metric set/validator there is authoritative for which
  metrics are suppressed counter-arguments vs projecting leaves.

## 6. Design tokens (already in the live `:root` — use these)

```
--bg #0a0d13  --panel #12161f  --panel2 #1b212c  --panel3 #222a37  --border #242c39  --border2 #313a49
--text #eef1f6  --muted #9aa4b3  --muted2 #6a7484
--accent #1677ff (chrome/CTAs)  --accent-hi #57a6ff (plotted data + small accent text)
--then #8b93a3 (dot-com "past" line)  --peak #ff5a44 (peak marker)  --bottom #3fb27f (bottom marker)
font: Inter + Geist Mono (numerics/axis). Type sizes were raised for an older audience — keep
secondary text ≥ ~12px. Gradients minimized to one area fill under the actual line.
```

Line convention: dot-com = **grey dashed**, drawn only to the convergence point; past today only
the **blue dashed** projection continues, on to the bottom.

## 7. Definition of done

- All four pages share one system (tokens, topbar/nav with the new labels, drawer, type).
- `thennow.html` landing: suppressed metrics greyed in the tree + "No Projection" on cards; sort
  control; root/roll-up/leaf + branch distinction; collapse hides body cards; bigger carets +
  collapse/expand-all toggle.
- Polymarket: verdict-led hero, reskinned condition cards + modal, shared drawer, level distinction.
- Data Sources: shared system, tree-styled source nav, shared drawer, per-metric method anchor.
- About: new Then & Now copy ported from `about-redesign.html`.
- Templates + generated pages in parity; site builds; `REVIEW-NOTES.md` written.

_Mocks are visual references in `/design`. Canonical mock source is `C:\workspace\ai-bubble-oracle\design\`._
