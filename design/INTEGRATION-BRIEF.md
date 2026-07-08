# Then & Now redesign — integration brief (handoff to the implementing agent)

You are integrating a completed **design study** into the functional AI Bubble Oracle
site. A prior design pass already made some **in-place edits**; a larger **mock** now
exists in `design/thennow-modal-redesign.html`. This brief tells you what's done, what to
build, the design rationale, and — importantly — where to use your own judgment.

## 0. Prime directive: form follows function

Follow the mock's **aesthetics and hierarchy**, but you own the **implementation**. Where a
proposed element is impractical given the stack, conflicts with how the data/engine actually
works, or it's unclear how the visual maps to real functionality: **lean toward omitting it
and raising the issue for review** rather than forcing it. Do not invent data to satisfy a
visual. An honest omission + a flagged question beats a fabricated element.

At the end, produce a short `REVIEW-NOTES.md` listing: (a) what you implemented, (b) what you
omitted and why, (c) open questions for the human.

## 1. The two reference points — read both fully first

- **The mock (the target aesthetic):** `design/thennow-modal-redesign.html` — a standalone,
  self-contained page. It renders the graph in **SVG** and **ports a JS copy of the engine**
  (`blend`/`match`/`evaluate`) only because it must stand alone. Treat it as a **visual spec**,
  not code to copy verbatim.
- **The live code (the thing you're editing):**
  - `thennow.html` (generated) and `oracle/thennow_template.html` (source). **They are byte-identical except line ~211 `const DATA = __DATA__;`.**
  - `oracle/thennow.py` — the real engine (Python). `oracle/thennow_page.py` — generation.
  - `oracle/dashboard_template.html` — the source of the topbar/drawer conventions to reuse.

## 2. CRITICAL build mechanics

- **Pages are generated.** `thennow.html` is produced by `python main.py html`, which injects
  the JSON payload into `oracle/thennow_template.html` (`__DATA__` → data). **Always edit the
  template.** If you can run `python main.py html`, edit the template and regenerate. If you
  cannot (no DB/deps), edit BOTH the template and the generated `thennow.html` with identical
  changes so they don't drift. Same rule for `dashboard.html`/`datasources.html` and their
  templates. Verify parity: `diff <(grep -v 'const DATA' oracle/thennow_template.html) <(grep -v 'const DATA' thennow.html)` should be empty.
- **The engine is Python, not JS.** The live page receives already-computed values in `DATA`
  (projected dates, intensities, phases, per-node arrays). **Do not port the mock's JS engine.**
  If the payload lacks a value you need (see the bottom-date note below), extend
  `oracle/thennow.py` to emit it, or compute it client-side from values already in `DATA` — and
  say which you did.
- **The charts are hand-rolled `<canvas>` 2D** (`drawNode(canvas, node, detail)` in the
  template). The mock uses SVG. **Do not swap the stack to SVG unless you have a strong reason
  and flag it.** Everything the mock shows is achievable on canvas: dashed lines
  (`setLineDash`), one area fill (`createLinearGradient`), text, and markers. HTML chrome
  (stat strip, legend, marker labels) should be **HTML elements positioned over the canvas**,
  exactly as the live modal already does for its legend/stat strip.

## 3. What has ALREADY been done in place — do not redo

- **Unified dark palette** across `thennow`, `dashboard`, `datasources`, `about` (+ templates).
  Tokens are in §6. Semantic colors updated (`--ath`→dot-com grey, `--trigger`→peak red).
- **Modal was restyled** in the live `thennow`: HTML stat strip (`.modal-statstrip`/`.mstat`),
  HTML legend (`.modal-legend`), framed plot (`.modal-chartwrap`), corner-ish actions, scaled
  detail-mode canvas type, brighter data lines (`--accent-hi`), convergence marker, tooltip.
- **Gradients removed** except one area fill. **Stat tiles** fixed to vertical stacks.

So the live modal is partway there. The work below is the **delta from the live state to the mock.**

## 4. What to build (delta), in priority order

Each item: follow the mock's look; apply the judgment rule in §0.

**A. Topbar convention (easy, do first).** Right-align a `⚙ Options` button + a muted
`Last update: …` line, reusing the dashboard's exact `#opts-btn` and `#topsub` pattern
(`oracle/dashboard_template.html`). The live page already computes the timestamp
(`document.getElementById("topsub").textContent = "Last update: " + DATA.updated…`) — wire the
real value, don't hardcode.

**B. Page hero — the peak date is the punchline.** Add a hero band above the content that
leads with the **headline (root) projected peak date**, huge, with a one-line plain-English
lead and the range/as-of chips. The single most important principle of this whole redesign:
**the projected peak date is the thesis and must be the loudest element on every surface**
(hero, each card, and the modal). Everything else is supporting evidence.

**C. Metric cards — date-led.** Restyle each metric card so its **projected date** dominates,
with a mini sparkline and the intensity/phase as a small footer. WIP branches stay as
"not wired yet" (no chart), matching the engine. Cards open the full detail view on click.

**D. Sidebar roll-up tree — PRESERVE.** The existing sidebar tree (hierarchy of how metrics
roll up to the headline) is **load-bearing and must not be dropped.** Keep it; restyle to match.
Tree rows and cards are both entry points to a metric's full view.

**E. Modal detail view — the graph is the centerpiece.** Bring the live modal up to the mock:
  - **Peak date leads** the modal header (label + big date + one-line sub). Metric-specific.
  - **Graph upgrades** (on canvas): four vertical **markers — start / today / peak / bottom** —
    each labelled with **both timelines** (AI date over dot-com date); the start marker names the
    kickoff events (ChatGPT launch / Netscape IPO). A **month-year x-axis on the AI era**
    (actual solid, projected dashed). **Dot-com line = grey DASHED, drawn only up to the
    convergence point**; past convergence, only the **blue dashed projection** continues, on to
    the **bottom**. One restrained area fill under the actual AI line (Bloomberg-style) — no
    other gradients.
  - **Supporting-evidence** stat tiles below the chart (subordinate to the date).
  - **"How this date is derived" = a SUMMARY** (a few steps) + a link to the **Data Sources**
    page for the full method. Keep the metric-specific "vs dot-com" note in the modal.
  - **Download CSV + the × close in the top-right corner** of the modal.

**F. Global "Options & assumptions" drawer.** These are **global**, not per-metric. Replace the
live modal's per-metric options block (`#modal-opts`/`optionsHtml`) with a single page-level
right-side **drawer** opened by the topbar `⚙ Options` button (mirror the dashboard drawer:
`#drawer`, `renderOptions()`). The modal side panel then holds only the derivation summary.

## 5. Known gaps / things to flag, not guess

- **Bottom date has no data source yet.** `oracle/thennow.py` projects the *peak* only. The
  mock computes the *bottom* client-side by extending the arc at the node's pace to the dot-com
  crash low (~progress 159, Oct 2002). Decide: add it to the Python payload, or compute in JS
  from existing `DATA` — and flag it. If neither is clean, **omit the bottom marker and raise it.**
- **"Full method" target.** The derivation summary links to Data Sources for the detail. If that
  section doesn't exist there yet, either add a concise method section to `datasources.html` or
  link to the closest existing anchor — and note it. Don't leave a dead link.
- **Marker-label crowding.** Today and peak markers can sit close on narrow widths. The mock
  staggers them into two rows. If labels collide at real widths, simplify (fewer dual labels, or
  abbreviate) rather than overlap.
- **Weights UI.** The live cards have adjustable child weights (`weightsBlock`). The mock didn't
  re-mock that control. Preserve the existing weights functionality; fit it into the new card/modal
  styling. If it doesn't fit cleanly, keep it working and flag the styling gap.

## 6. Design tokens (already in the live `:root` — use these, add none casually)

```
--bg #0a0d13   --panel #12161f   --panel2 #1b212c   --border #242c39   --border2 #313a49
--text #eef1f6 --muted #9aa4b3   --muted2 #6a7484
--accent #1677ff (brand; UI/chrome/CTAs)   --accent-hi #57a6ff (brighter; plotted data + small accent text on dark)
--then #8b93a3 (dot-com "past" line, grey)  --peak #ff5a44 (2000 peak / peak marker)  --bottom #3fb27f (crash-bottom marker)
font: Inter (display+body) + Geist Mono (numerics/IDs/axis)
```

Rules: dark cool-slate only (no beige/gradient washes). One accent, two weights. Red = peak,
green = bottom — the only two semantic event colors. **Type sizes were bumped up** for an older,
higher-net-worth audience — keep secondary text ≥ ~12px; nobody should need to zoom.

## 7. The human's stated preferences (honor these)

- Edit **in place**; **dark "data-terminal"** feel.
- **Preserve core page structure** — the roll-up **tree sidebar cannot be dropped**.
- **Every metric needs a full-size view** (modal is fine).
- **Minimize gradients** (one area fill under the line is OK — "Bloomberg occasionally does it").
- **Keep in mind the hand-rolled stack** — don't design anything excessively hard to do without
  changing it.
- **Bigger fonts** where there's space and little text.
- **Follow the dashboard's conventions** (the `Options` + `Last update` topbar pattern).
- **Peak date is the punchline** across the whole page, not just the modal. Its post-crash
  **bottom date** should be marked/labelled on the graph like the peak. The graph needs a real
  **month-year** x-axis (AI era). Each marker expresses the **dual parallel timelines**.

## 8. Definition of done

- Template + generated page in parity; site still builds (`python main.py html` if runnable).
- Peak date is unmistakably the first thing the eye lands on, on the page and in the modal.
- Tree sidebar intact and functional; every wired metric opens a full view; WIP handled honestly.
- Options drawer global; derivation is a per-metric summary linking to Data Sources.
- Palette/type match the tokens above; gradients minimized.
- `REVIEW-NOTES.md` written: implemented / omitted (with why) / open questions.
