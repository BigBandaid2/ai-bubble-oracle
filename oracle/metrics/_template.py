"""TEMPLATE — copy this file to add a metric (drop the leading underscore).

Underscore-prefixed modules are never discovered by the registry, so this file
does not affect any build. `python main.py check` loads it explicitly as the
lint fixture that proves the credential-gating path, which also means every
field below is validated in CI — keep it correct when editing.

The full walkthrough lives in docs/ADDING-A-METRIC.md. The short version:

1. Rename this file (e.g. oracle/metrics/ndx_pe.py) and rename EXAMPLE_* below.
2. If your data comes from an EXISTING source (fred, prices, cape, ipo), delete
   the SOURCE block and reference that kind in METRIC["source"]/["series"].
3. If it needs a NEW source, fill in SOURCE. A source that stores plain dated
   values can use the shared ext_series store (upsert_ext/load_ext + the
   _generic CSV round-trip) and never touch db.py.
4. Credential-gated (Bloomberg, Refinitiv, ICE, ...) sources: list the env vars
   in `requires`, set `enabled_by_default: False`, and set
   `redistributable: False` with `csv: None` — licensed data must NEVER be
   committed to this repository. The public site build skips your module (it
   renders as a tree stub); anyone who clones the repo activates it with
   ORACLE_ENABLE=<key> plus their own credentials.
5. Hard rules: pure stdlib; the update() must degrade gracefully offline
   ("kept N cached" idiom, never raise on network failure); no fabricated
   sample data anywhere; the metric needs an observation on or before
   1995-08-09 and current data, or the validator will (honestly) reject it.
"""

import os

from .. import db
from ..sources import _generic

# --------------------------------------------------------------------- source
# Delete this block if you are reading from an existing source kind.

_KIND = "example"                      # the kind METRIC references below
_SERIES = "EXAMPLE_SERIES_ID"          # this source's series identifier


def _fetch():
    """Return sorted [(date_iso, value_float), ...] from the vendor API, or []
    on failure. PLACEHOLDER: returns [] until you implement the real call —
    never fabricate data here. Read credentials from os.environ (they are
    guaranteed present when this runs, because the registry gates on
    SOURCE["requires"] before calling update())."""
    _token = os.environ.get("EXAMPLE_API_TOKEN")
    return []


def update(conn):
    restored = _generic.import_ext_csv(conn, _KIND)   # no-op when csv is None
    rows = _fetch()
    if rows:
        db.upsert_ext(conn, _KIND, _SERIES, rows)
        print(f"{_KIND}: fetched {len(rows)} rows ({rows[0][0]}..{rows[-1][0]})")
    else:
        kept = len(db.load_ext(conn, _KIND, _SERIES))
        print(f"{_KIND}: fetch failed or unimplemented (kept {kept or restored} cached rows)")


SOURCE = {
    "kind": _KIND, "label": "Example licensed vendor (template)",
    # env vars that must be set for this source to activate:
    "requires": ["EXAMPLE_API_TOKEN"],
    # licensed data must never be committed; fetch-at-runtime only:
    "redistributable": False, "csv": None,
    "ddl": None,                        # ext_series needs no bespoke schema
    "order": 90, "date_col": "date", "value_col": "value",
    "update": update,
    "load": lambda conn, arg: db.load_ext(conn, _KIND, arg or _SERIES),
}

# --------------------------------------------------------------------- metric
METRIC = {
    # identity + tree placement (parent = a branch key from metrics/_tree.py
    # or a BRANCH another module declares; order sorts within the parent)
    "key": "example_metric", "label": "Example metric", "parent": "valuation", "order": 90,

    # engine declaration: formula maps a row (single source) or an alias dict
    # (multi-series composite) to the metric's input value
    "kind": "example_metric", "source": (_KIND, _SERIES),
    "formula": lambda r: r["value"], "cadence": "monthly",
    "type": "ratio_from_start",         # or "absolute_level"
    "direction": "up",                  # or "down" (falling = later-cycle)
    "unit": "example_unit", "unitLabel": "Example",

    # activation: committed but OFF for the public site; a cloner activates it
    # with ORACLE_ENABLE=example_metric + the credentials above
    "enabled_by_default": False,
    "requires": [],                     # env vars beyond the source's
    "requires_label": "vendor license", # tree-stub wording on the public site
}
