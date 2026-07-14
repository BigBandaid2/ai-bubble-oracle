"""Generic keyed-series storage helpers for contributed sources.

A contributed source that stores plain (series_id, date, value) rows can use
the shared `ext_series` table (see oracle/db.py) plus these CSV round-trip
helpers, and never needs to touch db.py at all:

    from . import _generic
    from .. import db

    def update(conn):
        restored = _generic.import_ext_csv(conn, "mysource")
        rows = _fetch()                       # [(date_iso, value), ...]
        if rows:
            db.upsert_ext(conn, "mysource", "MY_SERIES", rows)
        else:
            print(f"mysource: fetch failed (kept {restored} cached rows)")
        _generic.export_ext_csv(conn, "mysource")

The CSV lives at data/ext_<kind>.csv with columns series_id,date,value. Lines
starting with '#' are provenance comments (source URL, retrieval date, terms),
the same convention as data/ipo_issuance.csv — put your citation there. Sources
whose upstream terms prohibit redistribution must NOT export a CSV at all
(declare redistributable=False, csv=None in the SOURCE spec; the spec lint
enforces that no data/ext_<kind>.csv exists for them).
"""

import csv

from ..config import PROJECT_DIR
from .. import db


def _path(kind):
    return PROJECT_DIR / "data" / f"ext_{kind}.csv"


def import_ext_csv(conn, kind):
    """Load the committed fallback CSV into ext_series. Returns rows imported."""
    p = _path(kind)
    if not p.exists():
        return 0
    by_series = {}
    with open(p, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(row for row in f if not row.startswith("#")):
            by_series.setdefault(r["series_id"], []).append((r["date"], float(r["value"])))
    n = 0
    for sid, rows in by_series.items():
        db.upsert_ext(conn, kind, sid, rows)
        n += len(rows)
    return n


def export_ext_csv(conn, kind, header_comment=None):
    """Persist a source's ext_series rows back to its committed CSV. Pass
    header_comment (str or list of lines) to write provenance '#' lines."""
    p = _path(kind)
    p.parent.mkdir(parents=True, exist_ok=True)
    rows = db.load_ext_all(conn, kind)
    with open(p, "w", newline="", encoding="utf-8") as f:
        if header_comment:
            lines = [header_comment] if isinstance(header_comment, str) else header_comment
            for line in lines:
                f.write(f"# {line}\n")
        w = csv.writer(f)
        w.writerow(["series_id", "date", "value"])
        for r in rows:
            w.writerow([r["series_id"], r["date"], r["value"]])
    return len(rows)
