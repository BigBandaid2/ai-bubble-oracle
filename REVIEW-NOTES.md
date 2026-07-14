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

## (c) Open questions — resolved

1. **Bottom date source of truth.** RESOLVED: made canonical. `oracle/thennow.py`
   now defines `BOTTOM_PROG` (the declared 2002 low as a progress %, a pure clock
   constant), `_evaluate` emits `projectedBottomDate` per node, and the payload
   carries top-level `bottomProgress`. The client reads `DATA.bottomProgress` and its
   own `evaluate` recomputes `projectedBottomDate`, so the bottom stays live under
   weights / match mode / smoothing. `bottomIso` + the empirical-argmin IIFE removed.
2. **Data Sources "full method".** RESOLVED: kept the per-pipeline anchors
   (`datasources.html#src:tn_*`). No dedicated cross-cutting method section added.
3. **Marker crowding.** RESOLVED: added a `max-width: 640px` rule that drops each
   marker chip's second line (the dot-com date) and shrinks it to label + AI date;
   the dot-com value stays available in the hover readout. Tiles go single-column too.
4. **"Metrics live".** RESOLVED: switched to counting wired leaf metrics, so the hero
   chip reads "Metrics live **3**" (Nasdaq + S&P + CAPE) rather than "1 of 4" branches.
5. **Peak label.** RESOLVED: kept as is. The peak marker uses the declared 2000-03-10
   peak (shown "Mar 2000") and the Options drawer explains the smoothing nuance.

---

# v2 — site-wide integration (INTEGRATION-BRIEF.md v2)

Brought every page onto the Then & Now system and applied the §4 refinements +
§4.5 landing polish. Edited the templates (`oracle/*_template.html`), regenerated
with `python main.py html`, verified template↔generated parity and each page live
in the preview (no console errors on any page).

## (a) Implemented

- **Site-wide nav** — one 4-link set on every page: `Then and Now` (thennow.html,
  home) · `Polymarket` (dashboard.html) · `Data Sources` (datasources.html) ·
  `About` (about.html), current page `.active`, brand mark links home. "Dashboard"
  renamed to "Polymarket". Mock `-redesign.html` links mapped to the real names;
  the `#src:yahoo` anchor kept intact.
- **thennow is now the public landing** — dropped `noindex`/`nofollow`, gave it a
  real landing `<title>` + description. The loud WIP badge became a subtle muted
  **"Experimental"** pill (your call).
- **Hero (§4.5)** — kicker `AI bubble bursts · considering VALUATION + CONCENTRATION
  + CAPEX + MONETARY` (accent), a peak-lbl dot line, the big projected-peak date
  alone, and the one-line verdict. Dropped the analog arc (start→today→peak→bottom)
  and the range/metrics-live/as-of chips.
- **Sort control (§4.2)** — segmented Tree order / Projected date / A–Z, persisted
  in `localStorage`; no-projection cards sink last under "Projected date". A live
  count ("N shown · M no projection") sits beside the "Metrics" title.
- **Level + branch cues (§4.3)** — level pip on each card (root = amber, roll-up =
  blue, **leaf = green**); a branch-colored left stripe on cards (`::before`) and on
  top-level tree branch rows, keyed to five low-chroma branch hues. No colored
  left-border for the *level* (that stays the pip).
- **No-projection metrics (§4.1)** — card date reads **"No Projection"** (was
  "suppressed"); its sparkline is muted + dashed with the projection dropped; the
  card stripe goes dashed-grey.
- **Tree declutter (§4.4 + §4.5)** — status dots are now **leaf-only** with three
  states (accent = has projection, grey = no projection, hollow = WIP); removed the
  per-row PEAK dates so labels take the freed width; carets enlarged to a ~22px
  tappable target; a **Collapse all / Expand all** toggle in the tree header; and
  **collapsing a branch now hides its cards** from the body (re-renders, respects
  the active sort). Legend trimmed to the two leaf-dot meanings.
- **Cards + tree rows open the modal** — both call the existing `openNode()`
  (canvas modal kept; no SVG swap).
- **Polymarket + Data Sources** — already on the unified system (the redesign mocks
  are verbatim copies of the live pages with only nav changed), so the rework here
  was **nav rewiring only**; the roll-up tree sidebar, the Options/Ambiguities
  drawer, every control/number/copy, and the ETL asset graph are untouched.
- **About** — ported the mock's layout + voice (thesis pull-quote, then→now clock
  strip, stat tiles, stack chips, casual tone). Kept the SEO/OG/Twitter meta and
  the Vercel analytics tag from the live page.

## (b) Omitted / changed, and why

- **§4.3 level/branch cues NOT applied to Polymarket.** The Polymarket mock
  (`polymarket-redesign.html`) is a byte-for-byte copy of the live page with only
  the nav changed — it does **not** show pips or branch stripes on that tree/cards —
  and §B repeatedly says "do not restructure / a DOM change needs strong
  justification." So I left the Polymarket tree/cards as-is. See open question 1.
- **About numbers corrected to reality.** The mock's copy predates the big bang: it
  claimed **"2 metrics wired"** with "concentration, capex and speculation on deck".
  Twelve leaf metrics across all five branches are now wired (PIPELINE-PLAN.md is
  authoritative), so I updated the stat to **12** ("seven project a date, five argue
  against the analog"), rewrote the now-done "wire the greyed-out branches" roadmap
  bullet, and added FRED + Ritter to the data-sources list. Per the prime directive,
  I did not ship a number the engine contradicts.
- **Branch cue = stripe only**, matching the mock; I did not add a separate per-card
  branch *tag* (considered in §4.3's "e.g."). Card stripe color + branch-row stripe
  color are the shared trace.
- **Card foot keeps the cycle phase** (e.g. "Acceleration") — real data — rather than
  the mock's "Leaf metric" level label, which the pip already conveys.
- **Kept a 2-item tree legend** (has-projection / no-projection) rather than dropping
  it entirely as the mock does, for the older audience the brief calls out.
- **§7 says "reskinned condition cards + modal" for Polymarket, but §B says NO
  drill-in modal.** Followed the specific §B instruction: no modal added to Polymarket.

## (c) Open questions

1. **Level/branch cues on Polymarket?** §4.3 names "thennow AND Polymarket", but the
   Polymarket mock doesn't implement them and §B warns against DOM changes. I left
   Polymarket nav-only. If you want the root/roll-up/leaf pips + branch stripes on
   the Polymarket condition tree/cards too, it's a light additive skin — say the word.
2. **"Experimental" tag** — you chose the subtle muted pill over removing it or
   keeping the loud WIP badge. Confirm the wording ("Experimental") reads right for
   the public landing.
3. **Sparkline stays canvas** (per the brief). The mock's SVG sparkline geometry was
   illustrative; the live cards bind each node's real weekly series.

## (d) Follow-up refinement — no-projection charts + "analogy"

- **No-projection cards + modal now draw the whole story.** A counter-argument
  metric previously clipped both curves at the (meaningless) convergence point.
  Now the **entire dot-com era is drawn to its 2002 conclusion** (grey dashed) and
  the **AI line is blue, stopping at today with no forward projection**. For these
  metrics the AI line is placed by ELAPSED TIME (`PROG_AI`) rather than by an
  intensity match, so it always spans its real ~79% extent instead of collapsing
  (e.g. sentiment, whose level sits below the dot-com start, previously degenerated
  to a vertical line). Implemented as `n.valid === false` branches in `aiPlot` /
  `aiOrdAt` / `aiProgFromDays` + a `todayProg(n)` helper; the modal today-marker
  then reads the time-equivalent dot-com date (Jul 2026 ≈ Mar 1999), the projected
  axis leg + Peak/Bottom markers + those legend items are suppressed, and the hover
  shows no AI value past today.
- **Wording:** the card foot reads **"does not fit dot-com analogy"**, and "analog"
  was replaced with **"analogy"** everywhere (templates, engine copy, the LLM prompt
  + fallback, the committed observation cache, About). Cached Haiku observations were
  edited in place; the shape-hash is state-based, so this doesn't trigger regen.

## (e) OSS refactor addendum (2026-07-14, phases P0-P6)

- **The module system is live.** A metric is one file in `oracle/metrics/`
  (engine declaration + `ir` documentation block); a source is one file in
  `oracle/sources/`. `oracle/registry.py` discovers, lints, gates
  (`requires` env vars + `enabled_by_default`/`ORACLE_ENABLE`/`ORACLE_DISABLE`),
  assembles the tree, and orders the Data Sources IR. Payload proofs: P1 and P2
  byte-equal to the pre-refactor baseline; P4 added exactly `DATA.ir` +
  `DATA.srcGroups`. The datasources template lost ~101KB of hand-maintained
  tn_ literals after an in-browser dual-build matched all 18 groups.
- **Two deliberate micro-diffs, documented here.** (1) IR asset order is now
  the tree's post-order walk, so `int_valuation_blend` is emitted after the
  Buffett chain instead of before it; the only visible effect is the ordering
  of downstream pills on a couple of shared asset pages (e.g.
  `int_bf_intensity`). (2) Stale post-P1 paths inside the Data Sources prose
  (`oracle/fred.py` etc.) were corrected to `oracle/sources/*`.
- **Root redirect fixed to the landing page.** `vercel.json` still sent `/`
  to `dashboard.html` from before the design-integration phase made Then & Now
  the landing; it now redirects to `/thennow.html` (Polymarket stays in the nav).
- **Docs shipped:** README rewrite (Then & Now-first, module system,
  adopt-for-your-own-analysis, data-licensing table), CONTRIBUTING.md,
  docs/ADDING-A-METRIC.md, issue/PR templates, `.env.example`,
  `oracle/metrics/_template.py` (the credential-gated skeleton, also the CI
  lint fixture). PR CI (`pr-check.yml`) = compileall + `main.py check` +
  `verify-pages`, deterministic and credential-free.
