# AI Bubble Oracle

Live: https://aibubbleoracle.com

Is the AI boom the dot-com bubble again? This site answers with data instead of
vibes: twelve metrics, each computed the same way across both eras from open
sources, each honestly labeled when it argues against the analogy. The engine
projects a peak date only from the metrics that actually fit the dot-com shape,
and shows the ones that don't as counter-arguments right beside them.

The repo is a pure-stdlib Python static-site generator. No frameworks, no
third-party packages, no build step: `python main.py update` fetches the data,
computes everything, and writes four self-contained HTML pages.

## The pages

| Page | What it is |
|---|---|
| [thennow.html](https://aibubbleoracle.com/thennow.html) | The landing page: the Then & Now roll-up tree, per-metric cards, projected-peak headline, adjustable weights and assumptions |
| [dashboard.html](https://aibubbleoracle.com/dashboard.html) | The Polymarket tracker: live monitoring of the "AI bubble burst in 2026?" market's six resolution conditions |
| [datasources.html](https://aibubbleoracle.com/datasources.html) | Every pipeline documented asset by asset: schemas, transforms, lineage graphs, a real example row traced through each stage, and the licensing/ambiguity notes |
| [about.html](https://aibubbleoracle.com/about.html) | Why the project exists and what it does and doesn't claim |

## How the Then & Now engine works

Everything runs on a declared clock, not a fitted one (`oracle/thennow.py`):

- dot-com era: 1995-08-09 (Netscape IPO) to the 2000-03-10 peak to the
  2002-10-09 bottom; AI era: 2022-11-30 (ChatGPT launch) to today.
- Each metric lands on a gap-free daily grid (published values forward-fill,
  a step-hold, never interpolation), gets a centered moving average (90-day
  default, 30-day alternative, both shipped and toggleable on the page), and
  is normalized to a shared 0-1 intensity: 0 at the dot-com starting level,
  1 at the declared 2000 peak. `ratio_from_start` metrics index each era to
  its own start (prices, nominal dollars); `absolute_level` metrics compare
  levels directly (CAPE, survey indexes, spreads).
- A two-pass validator gates every projection. Only a series that rose,
  peaked, and fell in the reference era, with the AI reading below that peak
  and moving toward it, earns a projected date. A series that fails is still
  shown, labeled as a counter-argument, and kept out of the roll-up math.
  Today the yield curve, consumer sentiment, and semiconductor production
  volume all argue against the analogy, and the site says so.
- Conforming leaves blend into branch curves (weights adjustable on the
  page), branches blend into the root headline. A cached, hash-gated Claude
  Haiku call writes one or two sentences of observation per metric on top of
  the computed verdict; without an API key a deterministic fallback runs and
  the build never blocks.

The current tree: Valuation (Nasdaq + S&P 500 price appreciation, Shiller
CAPE, market cap to GDP), Market concentration (Nasdaq/S&P leadership ratio),
Infrastructure/capex (IT investment share, tech equipment orders, and the
semiconductor-volume counter-argument), Speculative activity (margin debt,
IPO first-day pops), and Monetary & sentiment (yield curve, Michigan
sentiment, both currently counter-arguments).

## Quick start

Python 3.10+ and nothing else.

```
git clone https://github.com/BigBandaid2/ai-bubble-oracle
cd ai-bubble-oracle
python main.py update     # fetch all sources, rebuild oracle.db, write the pages
python -m http.server     # open http://localhost:8000/thennow.html
```

The first `update` fetches full history (a few minutes). Every fetcher
degrades gracefully offline: committed CSV fallbacks under `data/` restore the
warehouse, so `python main.py html` rebuilds the site with no network at all.
`oracle.db` is a disposable artifact and is never committed.

| Command | What it does |
|---|---|
| `python main.py update` | Fetch every active source, rebuild events, regenerate all pages |
| `python main.py html` | Regenerate all pages from cached data (no network) |
| `python main.py status` / `events` | Condition-tree report / historical threshold crossings |
| `python main.py check` | The contributor lint: validates every module spec, no network needed |
| `python main.py payload` | Dump the page payloads as sorted JSON (for byte-diffing a change) |
| `python main.py verify-pages` | Prove the committed pages match their templates |

## The module system

A metric is one file. Drop a module in `oracle/metrics/`, export a `METRIC`
dict, and the registry (`oracle/registry.py`) discovers it, validates it,
places it in the tree, runs it through the engine, and documents it on the
Data Sources page. No other file needs to change.

```python
METRIC = {
    "key": "margin_debt", "label": "Margin debt", "parent": "speculation", "order": 10,
    "kind": "margin", "source": ("fred", "BOGZ1FL663067003Q"),
    "formula": lambda r: r["value"] / 1000.0, "cadence": "quarterly",
    "type": "ratio_from_start", "direction": "up",
    "unit": "usd_bn", "unitLabel": "Margin loans $bn",
    "ir": { ... },   # its Data Sources documentation (chains, graph, overview)
}
```

Data sources are modules too (`oracle/sources/`), each exporting a `SOURCE`
spec with its fetch logic, committed-CSV fallback, and update ordering. A
source that stores plain dated values can use the shared `ext_series` store
and never touch the schema. A metric module may embed its own `SOURCE`, so a
complete contribution really is a single file. `oracle/metrics/_template.py`
is a heavily commented skeleton, and `docs/ADDING-A-METRIC.md` is the full
walkthrough.

### Activation and credential-gated sources

Every module declares what it needs:

- `requires`: env var names (API tokens, license hosts). A module whose
  variables are unset is skipped and rendered as an inert stub row in the
  sidebar tree, labeled with what it needs. It never enters the math.
- `enabled_by_default: False` plus `ORACLE_ENABLE=<key>` (comma-separated env
  var) turns a committed-but-off module on in your own clone or fork with
  zero code edits. `ORACLE_DISABLE=<key>` forces one off.

This is how licensed-data metrics work here: a Bloomberg, Refinitiv, or ICE
module can be committed, reviewed, and maintained in this repo, deactivated
on the public site, and activated by anyone who supplies their own
credentials. The public site is public-data-only by construction: the nightly
workflow sets no `ORACLE_*` variables, and `python main.py check` fails if
anyone tries to add one. Sources declaring `redistributable: False` must set
`csv: None`; the lint fails the build if licensed data is ever committed.

See `.env.example` for the variable conventions.

## Adopt it for your own analysis

The dot-com/AI comparison is data, not architecture. Two declarations pin it:

- `CLOCK` and `PHASES` in `oracle/thennow.py`: the four dates and the phase
  bands every metric is measured against.
- `oracle/metrics/_tree.py`: the root and pillar branches metrics attach to.

Fork the repo, change those, and the same engine compares any two cycles you
can find daily-or-slower data for: the 1980s Japan bubble against today's
Nikkei, crypto 2017 against crypto 2021, housing 2006 against wherever you
think housing is now. One fork per analog pair; every metric module, the
validator, the smoothing options, and all three pages come along unchanged.

## The Polymarket condition tracker

The project's original core, still running nightly: unofficial monitoring of
the Polymarket market "AI bubble burst in 2026?", which resolves YES if at
least 3 of 6 conditions occur within a 90-day window.

| Condition | Trigger | Source |
|---|---|---|
| `nvda_down_50` | NVDA down 50% from all-time high | Yahoo Finance |
| `soxx_down_40` | SOXX down 40% from all-time high | Yahoo Finance |
| `supplier_down_50` | Any of TSM, ASML, AVGO, ANET, SMCI down 50% from ATH | Yahoo Finance |
| `h100_rental_dollar` | H100 rental at or under $1.00/hr for 5 straight days | Vast.ai proxy |
| `openai_bankruptcy` / `anthropic_bankruptcy` | Chapter 7/11 filing | CourtListener/RECAP daily scan |

Details that matter:

- The rules' ambiguities (closing vs intraday all-time high, trailing vs
  instant 90-day window, which H100 index tier) are exposed as live toggles
  on the page, not silently decided.
- The bankruptcy scan never flips a condition by itself. Candidates open a
  GitHub issue for human review; a filing counts only after it is confirmed
  in `CONFIRMED_BANKRUPTCIES` in `oracle/config.py`. The scan is validated
  against FTX's 2022 Chapter 11 wave.
- The H100 condition resolves on SiliconData's paywalled index, so the site
  tracks a free proxy (Vast.ai on-demand median for the neocloud tier) and
  says exactly that on the Data Sources page.
- The condition tree lives in `oracle/config.py` (`CONTRACT`); adding a
  condition is adding a node there.

## Automation

- A GitHub Action (`.github/workflows/daily-update.yml`) runs
  `python main.py update` at 22:30 UTC daily, commits the regenerated pages
  plus accumulated data CSVs, and opens alert issues for bankruptcy
  candidates or a sustained GDELT throttle. Each push auto-deploys via
  Vercel.
- PR CI (`.github/workflows/pr-check.yml`) runs `compileall`,
  `python main.py check`, and `python main.py verify-pages`: deterministic,
  no network, no credentials. A full live build exists as a
  manually-dispatched job.
- `ANTHROPIC_API_KEY` is the only secret, and it is optional.

## Data licensing

Code and data have different rules here. The code is Apache-2.0; files under
`data/` are data, each carrying its upstream terms in a `#` provenance header
and on the Data Sources page.

| Data | Committed? | Terms |
|---|---|---|
| FRED series (`fred_history.csv`) | Yes, fallback | US government data, public domain |
| Ritter IPO stats (`ipo_issuance.csv`) | Yes, authored seed | Academic data, citation carried in the file |
| Shiller CAPE via multpl (`cape_history.csv`) | Yes, fallback | Public table, cited |
| Yahoo Finance prices | No, runtime fetch | Unofficial public API, not redistributed |
| H100 proxy, Polymarket, bankruptcy, buzz CSVs | Yes | Our own measurements of public APIs |
| FINRA margin stats | Never | Terms bar committing copies (Z.1 used instead) |
| WSTS semiconductor billings | Never | File prohibits reproduction (cited only) |
| massive.com / Polygon | Never | Terms bar committing fetched data; also lacks pre-2002 depth |

The last three rows are documented decisions, kept so the next contributor
doesn't re-litigate them. The lint enforces the rule mechanically: a source
declared `redistributable: False` fails the build if data for it is committed.

## License

Apache License 2.0 for the code (see [LICENSE](LICENSE) and
[NOTICE](NOTICE)). `data/` files are data, not code, and carry their own
upstream terms as described above.
