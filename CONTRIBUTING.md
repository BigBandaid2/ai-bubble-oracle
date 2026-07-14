# Contributing

Thanks for looking. This project is deliberately small-surface: one Python
process, no dependencies, four static pages. Most contributions are one new
file. This document is the ground rules; the mechanics of adding a metric are
in [docs/ADDING-A-METRIC.md](docs/ADDING-A-METRIC.md).

## Ground rules

1. Pure stdlib. No third-party Python packages, ever, including "just one
   small one". `urllib.request`, `sqlite3`, `json`, `csv`, and `re` have
   carried the whole site so far. If a vendor integration truly cannot be
   done over HTTP with the stdlib, it lives in your fork, not here.
2. The public site is public-data-only, by construction. The nightly
   workflow sets no `ORACLE_*` variables, and `python main.py check` fails
   any PR that adds one to `daily-update.yml`. Credential-gated modules are
   welcome in the repo, deactivated (see the private-source policy below).
3. Every commit is shippable. The nightly Action builds `main` and deploys
   whatever it produces. There is no develop branch and no feature-flag
   debt: if your change lands in halves, each half must build a correct
   site.
4. Fetchers never take the build down. Network code follows the "kept N
   cached" idiom: import the committed CSV fallback, try the fetch, upsert
   what you got, export the CSV, and print a one-line summary either way.
   An API being down (or throttled) is a normal Tuesday, not an exception.
5. Honesty beats a greener dashboard. A metric that argues against the
   dot-com analogy renders as a labeled counter-argument; that is a feature,
   not a bug to fix. Never tune a formula, window, or gate to force a
   verdict. The same goes for copy: no fake precision, and the word is
   "analogy", never "analog".

## Dev loop

```
python main.py update        # full fetch + rebuild (first run takes a few minutes)
python main.py html          # rebuild pages from cached data, no network
python -m http.server        # browse http://localhost:8000/thennow.html
python main.py check         # the contributor lint (what PR CI runs)
python main.py verify-pages  # committed pages match their templates
python main.py payload       # sorted-JSON payload dump, for byte-diffing
```

The payload dump is the tool for proving a refactor changed nothing:

```
python main.py payload > before.json
# ...make your change, then: python main.py html
python main.py payload > after.json
git diff --no-index before.json after.json
```

An empty diff means the pages are byte-stable. A non-empty diff is fine when
it is intended: say exactly what changed and why in the PR.

## Data rules

- Licensed data is never committed. A `SOURCE` with `redistributable: False`
  must set `csv: None`; the lint fails the build if a committed file for
  that kind appears. FINRA, WSTS, and massive.com are documented precedents
  (see the README licensing table) - do not re-add them.
- Committed CSVs carry provenance. Every authored or seeded file under
  `data/` starts with `#` comment lines saying where the data came from,
  when it was retrieved, and under what terms.
- No fabricated data, anywhere. Not in fixtures, not in placeholders, not
  in "representative examples". `_template.py`'s fetch returns an empty
  list and says so in its docstring; follow that pattern. Example values on
  the Data Sources page are materialized from the real warehouse at
  generate time.
- Metrics need history. The engine measures both eras, so a series must
  have an observation on or before 1995-08-09 and be current. The validator
  will honestly reject anything that cannot cover both windows.

## Private / licensed sources (Bloomberg, Refinitiv, ICE, ...)

Committed, reviewed, and off by default. The pattern:

- `SOURCE["requires"]` lists the env vars (e.g. `BLOOMBERG_API_TOKEN`);
  `redistributable: False`, `csv: None`.
- `METRIC["enabled_by_default"] = False` plus a human-readable
  `requires_label` (the public site shows the metric as an inert tree stub
  with that label).
- A cloner activates it with `ORACLE_ENABLE=<key>` plus their credentials.
  Nothing about the public build changes.
- The module's docstring must be honest about what is implemented and what
  is a sketch. Untestable code presented as tested is the one thing that
  gets a PR closed without discussion.

## PR checklist

- [ ] `python main.py check` is green (PR CI runs exactly this).
- [ ] `python main.py verify-pages` is green after regenerating.
- [ ] Payload byte-diff is empty, or the diff is described in the PR.
- [ ] No new dependencies; no licensed data committed; new CSVs carry
      provenance headers.
- [ ] New metrics: one module file, `ir` block included (that block is the
      metric's Data Sources documentation), verdict expectation stated in
      the PR (conforms or counter-argument, and why).
- [ ] Copy follows the house voice: plain language, no hype, "analogy" not
      "analog", counter-arguments labeled as such.

## Where things live

| Path | What |
|---|---|
| `main.py` | CLI: update / html / check / payload / verify-pages |
| `oracle/registry.py` | Module discovery, activation gating, tree assembly, the lint |
| `oracle/metrics/` | One file per metric (`_tree.py` = root + pillars, `_template.py` = skeleton) |
| `oracle/sources/` | One file per data source (`_generic.py` = ext_series CSV round-trip) |
| `oracle/thennow.py` | The engine: declared clock, grids, smoothing, validator, roll-up |
| `oracle/datasources.py` | Data Sources payload + the IR generator (`_build_ir`) |
| `oracle/*_template.html` | Page templates; `__DATA__` is replaced with the JSON payload |
| `data/` | Committed CSV fallbacks and accumulated histories, with provenance |
| `.github/workflows/` | `daily-update.yml` (nightly build) and `pr-check.yml` (CI) |
