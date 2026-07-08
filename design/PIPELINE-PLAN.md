# Then & Now data-pipeline plan (approved 2026-07-08)

The goal: one pipeline that turns *any* time series spanning both eras into a
leaf on the roll-up tree, as universally as the data allows.

## Converged model

- **Declared Nasdaq cycle clock** (not derived from any metric):
  `start 1995-08-09 (Netscape IPO) · peak 2000-03-10 (Nasdaq top) · bottom
  2002-10-09 · ai_start 2022-11-30 (ChatGPT)`. Every metric is measured against
  this shared clock, which is what keeps the parent blend coherent.
- **Per-metric-type normalization.** The universal layer is the 0-1 **intensity**
  (0 = the metric's value at the cycle start, 1 = its value at the declared peak
  date, so the Nasdaq crest sits on the peak marker). How the raw value gets there
  is per metric: `ratio_from_start` (index to the era's own start, e.g. price) or
  `absolute_level` (compare absolute levels across eras, e.g. CAPE). Never force
  every metric to "start at 1".
- **Daily compute, centered smoothing, weekly plot.** Compute on a common **daily**
  grid so the headline moves every rebuild; smooth with a **centered** N-day mean
  (default 90d "3-month"; 30d "1-month") anchored so intensity = 100% lands on the
  declared peak (the AI leading edge necessarily falls back to trailing, no future
  data). Ship **exact daily-derived scalars** + a **weekly** downsampled series for
  the plot/hover/CSV.
- **Raw look-through travels the whole pipe.** The metric's value in **native
  units** (plus the underlying raw columns) is carried to the payload, so hover/CSV
  always show the real thing (Nasdaq 4,376 / ~26,000) beside the normalized line.
- **Smoothing options are materialized permutations.** Each option is its own
  dataset; the global Options drawer toggle swaps which one the graphs read, so
  changing it visibly moves the projected date.
- **Two-pass validation + committed observations.** Candidacy (both-era coverage,
  density, dynamic range) early; shape (interior peak, monotone-enough ramp / cross
  count, AI below peak and moving in the declared direction) after smoothing.
  Output `{valid, checks[], observations}`; the verdict + numbers are computed and
  authoritative, a cached/hash-gated Haiku call writes 1-3 sentences on top
  (deterministic fallback, rare regeneration). Non-conforming metrics render with
  the projection/markers **suppressed** and shown as a labeled counter-argument.

## Metric-definition registry (adding a metric = one declaration)

```
{ key, label, parent,
  source,     # loader + raw table (prices:^IXIC, prices:^GSPC, cape, ...)
  columns,    # raw fields to pull
  formula,    # fn(cols) -> metric input; MAY combine fields (num/den, spreads)
  cadence,    # daily | monthly
  type,       # ratio_from_start | absolute_level   (governs normalization)
  direction,  # up | down
  unit }      # native-unit label for look-through
```

Two transforms: `formula` (raw -> metric input, declared per metric) then the
generic `type` normalization (metric input -> 0-1 intensity). The engine walks the
registry; everything downstream is generic.

## Pipeline as assets (maps 1:1 to the datasources IR)

`raw.<src>` -> `<src>_daily` (finest cadence, trimmed to the era windows) ->
`stg_filled` (gap-free daily; monthly stays monthly) -> `int_value` (apply
formula) -> `int_smoothed[opt]` (centered N-day; one asset per smoothing option)
-> `int_validated` (checks + verdict + observations) -> `int_normalized`
(declared-clock progress + intensity) -> `fct_projection` (match, peak/bottom,
dates; suppressed if invalid) -> `exposure.thennow` (weekly series + daily scalars
+ verdict).

## Tree (after S&P lands)

`Valuation -> { Price appreciation -> [Nasdaq, S&P 500], Valuation multiple ->
[CAPE] }` plus the WIP branches (concentration, capex, speculation). Equal-weight
blends by default; weights adjustable per parent in its detail view.

## Confirmed defaults

Equal-weight blends · CSV matches the in-page weekly series · Haiku observations
cached + hash-gated (rare regeneration after first populate).

## Phasing (each ships + verifies live)

1. **Foundation:** registry + declared clock + daily-centered compute + weekly
   payload, reproducing today's Nasdaq + CAPE. Same payload contract, so no
   template change; only visible effect is smoother weekly lines and daily-lively
   scalars (numbers may nudge vs the old monthly compute).
2. **Validator** (two passes) + committed LLM observations; non-conforming handled.
3. **S&P 500** leaf + the Price-appreciation sub-blend.
4. **Smoothing permutations** + the Options-drawer toggle.

_Reference doc; not used by the build._
