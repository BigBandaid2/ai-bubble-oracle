# AI Bubble Oracle — design system notes

A fresh, cohesive **dark data-terminal** system applied across the site. Edited in
place; the generated pages (`dashboard.html`, `datasources.html`, `thennow.html`) and
their `oracle/*_template.html` sources were both updated, so the next
`python main.py html` keeps the new look.

## Why this direction
The old palette mixed three slightly different cool-greys (`#1a1f23` panel vs `#1f2937`
border vs `#242b32`) that never resolved into one family, and the muted greys
(`#80838e` / `#6b6e7a`) sat below comfortable contrast on the tiny labels the charts
lean on. The fix is one disciplined **cool-slate ramp** plus a single brand-aligned blue,
so every surface reads as one system and the data — not the chrome — carries the color.

## Tokens
| Token | Old | New | Role |
|---|---|---|---|
| `--bg` | `#0a0b10` | `#0a0d13` | deepest canvas |
| `--panel` | `#1a1f23` | `#12161f` | cards / panels |
| `--panel2` | `#242b32` | `#1b212c` | chips, inputs, buttons |
| `--border` | `#1f2937` | `#242c39` | hairlines (lifted for visibility) |
| `--border2` | — | `#313a49` | stronger dividers / control edges |
| `--text` | `#f4f4f6` | `#eef1f6` | primary text |
| `--muted` | `#80838e` | `#9aa4b3` | secondary text (contrast-lifted) |
| `--muted2` | `#6b6e7a` | `#6a7484` | labels / captions |
| `--accent` | `#0093fd` | `#1677ff` | brand blue — chrome, focus, CTAs |
| `--accent-hi` | — | `#57a6ff` | brighter blue for plotted data + small accent text on dark |
| `--ath` (dot-com line) | `#99a1af` | `#8b93a3` | the receded "then" series |
| `--trigger` (2000 peak) | `#f43437` | `#ff5a44` | the one warm alert color |

Type unchanged: **Inter** (display/body) + **Geist Mono** (numerics, IDs, axis values).

## Principles
1. **Then vs Now is a color duality.** Dot-com history is a quiet grey line; the AI path
   and its projection are the bright blue. Red is reserved *only* for the 2000 peak.
2. **One accent, two weights.** `--accent` (`#1677ff`) for UI chrome; `--accent-hi`
   (`#57a6ff`) for data lines and small labels so they hold up on the dark canvas.
3. **Numbers are monospace + tabular** everywhere, so columns and readouts align.
4. **Density is the feature** — hairline borders, no row striping, no decoration.

## The graph-detail modal (deep pass)
The charts are hand-rolled `<canvas>` 2D drawings (no chart library), so the near-
fullscreen modal was rendering 8–10px fixed labels that looked lost at that size. Changes:
- **HTML stat strip** above the chart — intensity now, matching dot-com date/phase,
  distance from the 2000 peak, pace, projected top — as crisp tabular tiles.
- **HTML legend** for the five series (dot-com / AI / projection / 2000 peak / today /
  convergence) instead of decoding tiny on-canvas text.
- **Detail-mode canvas typography scaled up** (8–10px → 11–12px) with larger plot
  padding, brighter/thicker data lines, and a legible hover readout.
- Framed plot area, refined header + buttons, softened scrim with blur, accent top-hairline.

_Delete this file freely — it's reference only, not used by the build._
