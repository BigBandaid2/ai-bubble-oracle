# Adding a metric

A metric is one file in `oracle/metrics/`. This walkthrough covers the
concepts the engine imposes, a complete worked example on a FRED series, how
to embed a new data source, how credential gating works for licensed vendors,
and how to test the result. `oracle/metrics/_template.py` is the copyable
skeleton for the credential-gated case.

## 1. Concepts you inherit for free

You declare WHAT to measure; the engine owns HOW. Every metric gets the same
treatment, which is what makes the metrics comparable:

- The declared clock. Both eras are fixed in `oracle/thennow.py` (`CLOCK`):
  dot-com 1995-08-09 to 2000-03-10 to 2002-10-09, AI era from 2022-11-30.
  Nothing is fitted; your metric is measured against these dates.
- Daily grid + forward-fill. Your series lands on a gap-free daily grid per
  era. A monthly or quarterly value step-holds across its days. This is why
  cadence can be anything from daily to annual.
- Centered smoothing. A centered moving average, materialized at 90-day
  (default) and 30-day windows; the reader toggles between them and every
  projection shifts. You never smooth your own data.
- Normalization to intensity. The shared 0-1 scale: 0 at the dot-com start
  level, 1 at the declared 2000 peak. You pick which mapping is honest for
  your unit via `type`:
  - `ratio_from_start`: each era indexed to its own start. For prices and
    nominal dollars, where 30 years of inflation and scale drift would
    otherwise dominate.
  - `absolute_level`: levels compared directly. For units that mean the same
    thing in any era: a P/E, a share of GDP that is genuinely comparable, a
    survey index, a spread.
- `direction`: "up" means rising = later-cycle; "down" flips the scale (the
  yield curve falls toward tops).
- `minRange` (optional, default 0.2): the dynamic-range gate. A bounded
  survey index moves less than a price; declare a smaller range so the
  candidacy check is fair, and the check output prints the actual movement.
- The validator is a feature. Two passes gate every projection: candidacy
  (covers both eras, real dynamic range), then shape (rose, peaked, fell in
  the reference era; AI below that peak and moving toward it). A metric that
  fails is still rendered, labeled as a counter-argument, and excluded from
  the blends. Semiconductor production, the yield curve, and consumer
  sentiment all fail today, on purpose. State your expected verdict in the
  PR; "it will not conform, and that is the finding" is a fine contribution.
- Blending. Conforming leaves blend into their branch by weight (readers
  adjust weights live); branches blend into the root headline. Your metric
  joins the math only while it conforms.

## 2. A complete metric on an existing source

Suppose you want commercial and industrial lending as a credit-expansion
tell (FRED series BUSLOANS, monthly since 1947, so it covers both eras).
One file, `oracle/metrics/ci_loans.py`:

```python
"""C&I lending: the credit-expansion tell. Commercial and industrial loans
at commercial banks (Fed H.8 via FRED, monthly since 1947). Nominal dollars,
so each era is indexed to its own start rather than compared raw across 30
years of inflation."""

METRIC = {
    # identity + tree placement. parent is a branch key from _tree.py
    # (valuation, market_concentration, capex, speculation, monetary) or a
    # BRANCH declared by another module. order sorts within the parent.
    "key": "ci_loans", "label": "C&I lending",
    "parent": "speculation", "order": 30,

    # engine declaration
    "kind": "ci_loans",                     # unique; used as the page's src anchor
    "source": ("fred", "BUSLOANS"),         # (source kind, series argument)
    "formula": lambda r: r["value"],        # row dict -> metric value
    "cadence": "monthly",
    "type": "ratio_from_start", "direction": "up",
    "unit": "usd_bn", "unitLabel": "C&I loans $bn",
}
```

That is the whole engine contract. Field notes:

- `source` vs `series`: a single-input metric declares
  `"source": (kind, arg)`. A composite declares
  `"series": {"alias": (kind, arg), ...}` and its formula receives the
  aliases inner-joined by date: see `buffett.py`
  (`formula = lambda r: (r["eq"] / 1000.0) / r["gdp"]`) or
  `tech_leadership.py` (two price tickers). Exactly one of the two.
- `formula` runs per row and may raise `KeyError` / `TypeError` /
  `ZeroDivisionError` on bad rows (the engine tolerates those); anything
  else fails the lint.
- Existing source kinds: `fred` (any FRED series id, keyless CSV endpoint),
  `prices` (Yahoo tickers already in the warehouse), `cape`, `ipo`. The
  registry derives required Yahoo tickers from active metrics, so a new
  `("prices", "^NDX")` metric fetches its own ticker automatically.
- A module can export `METRICS = [A, B]` (several leaves) and/or `BRANCH`
  (a sub-roll-up node); `price.py` does both and is the exemplar.

### The `ir` block

Public metrics also carry their Data Sources documentation in the module, as
an `ir` dict beside the engine fields. It is JSON prose (never lambdas) and
becomes the metric's group on datasources.html: the asset-by-asset chain, the
lineage graph, and the overview with options / ambiguities / caveats /
cardinality. The compact `leaf_chain` form covers the standard
source-to-graph pipeline; you write the prose that is specific to your metric
and the generator (`oracle/datasources.py::_build_ir`) fills in the six
mechanical stages:

```python
    "ir": {
        "group": "tn_ci", "group_name": "C&I lending (WIP)",
        "foreign_from": "C&I LOANS",
        "leaf_chain": {
            "p": "ci", "cadence": "monthly",
            "src": {
                "id": "raw.fred_busloans", "dbt": "source('fred','BUSLOANS')",
                "grain": "one CSV document (monthly H.8 series)",
                "why": "The credit-expansion tell: ...",
                "desc": "FRED fredgraph.csv for BUSLOANS (...), keyless, public domain, monthly since 1947. oracle/sources/fred.py.",
                "tx": "HTTP GET fredgraph.csv?id=BUSLOANS",
                "card": "one document, monthly since 1947.",
            },
            "raw": {
                "id": "fred_ci", "grain": "one row per month",
                "why": "The landed series.", "desc": "...",
                "schema": [
                    {"col": "date", "type": "TEXT", "kind": "key", "ex": "{{asOf}}"},
                    {"col": "value", "type": "REAL", "kind": "pass",
                     "ex": {"live": "rawNow"}, "note": "$bn SA"},
                ],
                "card": "monthly since 1990 (committed CSV fallback).",
            },
            "metricWhy": "Applies the declared formula: the loan stock itself.",
            "metricDesc": "Registry: formula = value, type = ratio_from_start: ...",
            "metricTx": "value = C&I loans $bn", "metricNote": "$bn",
            "graphWhy": "One sentence on what this leaf argues.",
        },
        "graph": {"vchain": {
            "ids": ["raw.fred_busloans", "fred_ci", "stg_ci_filled", "int_ci_metric",
                    "int_ci_smoothed", "int_ci_intensity", "int_ci_validated", "graph.ci_loans"],
            "shorts": {"raw.fred_busloans": "raw: fred BUSLOANS", "graph.ci_loans": "graph: C&I lending"},
        }},
        "source_info": {
            "blurb": "...", "options": [...], "ambiguities": [...],
            "caveats": [...], "cardinality": [...],
        },
    },
```

Live example values are placeholders, filled from the real warehouse at
generate time: `{{token}}` inside any string (`{{asOf}}` `{{rawNow}}`
`{{intensityPct}}` `{{checksPass}}` `{{checksN}}` `{{projDash}}`
`{{verdictLong}}` and friends), or `{"live": "rawNow", "scale": 1000}` where
a typed number is needed. Never paste today's numbers as literals; they would
be stale by tomorrow's build.

Graph forms: `vchain` (straight 8-node chain), `join` (two inputs at the top,
see `buffett.py`), or `explicit` geometry for unusual layouts (see
`_tree.py`). Composite metrics whose inputs land in other pipelines list them
in `stgUpstream` and set `src`/`raw` to `None` (see `tech_leadership.py`).

`python main.py check` validates the block's structure and that it is pure
JSON. A metric without `ir` still runs; it just goes undocumented, which is
fine while you iterate and not fine in the PR.

## 3. Embedding a new data source

If the data does not come from an existing kind, export a `SOURCE` from the
same module (or a new file in `oracle/sources/`):

```python
from .. import db
from ..sources import _generic

_KIND, _SERIES = "widgets", "WIDGET_INDEX"

def _fetch():
    """Return sorted [(date_iso, value_float), ...] or [] on failure."""
    ...  # urllib.request against the vendor endpoint

def update(conn):
    restored = _generic.import_ext_csv(conn, _KIND)
    rows = _fetch()
    if rows:
        db.upsert_ext(conn, _KIND, _SERIES, rows)
        _generic.export_ext_csv(conn, _KIND, header_comment="source: ..., retrieved ..., terms: ...")
        print(f"{_KIND}: fetched {len(rows)} rows ({rows[0][0]}..{rows[-1][0]})")
    else:
        kept = len(db.load_ext(conn, _KIND, _SERIES))
        print(f"{_KIND}: fetch failed (kept {kept or restored} cached rows)")

SOURCE = {
    "kind": _KIND, "label": "Widget index (vendor)",
    "requires": [],                       # env vars; non-empty = credential-gated
    "redistributable": True,              # False forbids any committed CSV
    "csv": "data/ext_widgets.csv",        # committed fallback, or None
    "ddl": None,                          # ext_series needs no bespoke schema
    "order": 80,                          # update() sequencing in cmd_update
    "date_col": "date", "value_col": "value",
    "update": update,
    "load": lambda conn, arg: db.load_ext(conn, _KIND, arg or _SERIES),
}
```

The `ext_series` store (`source_kind, series_id, date, value`) plus the
`_generic` CSV round-trip means a plain dated series never touches `db.py`.
A source with a genuinely bespoke schema declares `ddl` and its own load
(see `oracle/sources/ipo.py`). The non-negotiables:

- `update()` never raises on network failure; it prints the cached-rows line.
- Committed CSVs carry a `#` provenance header (the `header_comment` above).
- `redistributable: False` requires `csv: None`, and the lint fails the
  build if `data/ext_<kind>.csv` ever appears for that kind.

## 4. Credential-gated vendors (Bloomberg, Refinitiv, ICE)

Start from `oracle/metrics/_template.py`; it is the working skeleton of this
exact case and doubles as the CI fixture proving the gating path. The
declaration surface:

```python
SOURCE["requires"] = ["BLOOMBERG_API_HOST", "BLOOMBERG_API_TOKEN"]
SOURCE["redistributable"] = False; SOURCE["csv"] = None
METRIC["enabled_by_default"] = False
METRIC["requires_label"] = "Bloomberg license"
```

On the public site the metric renders as an inert stub row in the sidebar
tree ("requires Bloomberg license"), never blends, and ships no data. Anyone
who clones the repo activates it with:

```
export BLOOMBERG_API_HOST=... BLOOMBERG_API_TOKEN=...
ORACLE_ENABLE=your_metric_key python main.py update
```

How a real Bloomberg module would be structured (a sketch, deliberately not
committed as code):

- Prefer the HTTP surface. Bloomberg HAPI, Refinitiv RDP, and ICE's data
  APIs are all reachable with `urllib.request` plus token auth, which keeps
  the stdlib rule intact: `_fetch()` requests the history for one identifier,
  parses JSON or CSV, and returns `[(date, value), ...]`.
- The desktop BLPAPI SDK is a third-party package and cannot be committed
  here. If that is your only access path, keep the SDK call in your fork, or
  have a small out-of-repo script write the rows and load them locally;
  either way the committed module stays honest about what it does.
- The docstring states plainly which endpoints are implemented and which are
  sketches. `main.py check` lints the module either way (it validates specs
  without credentials or network), and the module needs no committed data to
  be reviewable: that is the point of the gating design.
- Mind the era requirement: whatever the vendor sells, the series must reach
  1995-08-09 or the validator will reject it.

## 5. Testing your metric

```
python main.py check                 # spec lint: fields, formula probe, ir structure
python main.py update                # fetch + build (or `html` if data is cached)
python -m http.server                # eyeball thennow.html and datasources.html
```

Then the drills:

- Gating: `ORACLE_DISABLE=<your_key> python main.py html` should demote your
  metric to a tree stub and re-blend without it; unsetting restores it. For
  a gated module, run once without credentials (expect the skip line and the
  stub) and once with `ORACLE_ENABLE` + credentials.
- Verdict: read your metric's modal on thennow.html. Does the validator
  verdict match what you claimed in the PR? A surprise there is a data
  problem or a framing problem; investigate before shipping.
- Payload stability: if your PR is a refactor, prove byte-equality with
  `python main.py payload` before/after (see CONTRIBUTING). A new metric
  adds payload; say so.
- Offline: delete `oracle.db`, disconnect, and run `python main.py update`.
  Your source should restore from its committed CSV (or skip cleanly) and
  the build should finish.

## 6. Payload-stability rules

The committed pages are the product; their JSON payload is treated as an
interface. A PR either leaves the payload byte-identical (refactors) or
documents exactly which keys it adds or changes and why (features). Never
reorder or rename existing payload fields casually: the page JS, the CSV
export, and downstream readers of the published pages all consume it.
