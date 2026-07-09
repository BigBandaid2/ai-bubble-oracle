"""Import the IPO-froth seed (monthly counts + average first-day returns).

Source: Jay R. Ritter, "IPO Data" (University of Florida), IPOALL.xlsx —
https://site.warrington.ufl.edu/ritter/ipo-data/ — monthly IPO counts and
average first-day returns back to 1960, using Ritter's "net" IPO definition
(excludes SPACs, penny stocks, units, closed-end funds, ADRs, banks/S&Ls).

Unlike the fetched sources, this is an AUTHORED SEED: Ritter refreshes the file
roughly annually (Dec-Jan), so data/ipo_issuance.csv is converted from the
spreadsheet by hand when he does and committed with attribution. There is no
live fetch; the import is idempotent. Months with no IPOs carry a NULL return
(never 0), so forward-filling holds the last real reading.
"""

import csv

from .config import PROJECT_DIR
from . import db

IPO_CSV = PROJECT_DIR / "data" / "ipo_issuance.csv"


def _num(s, cast=float):
    s = (s or "").strip()
    if not s:
        return None
    try:
        return cast(s)
    except ValueError:
        return None


def import_ipo_csv(conn):
    """Load the committed seed into ipo_issuance. Returns rows imported."""
    if not IPO_CSV.exists():
        return 0
    rows = []
    with open(IPO_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(row for row in f if not row.startswith("#")):
            rows.append((r["month"], _num(r["avg_first_day_return"]),
                         _num(r["ipo_count_gross"], int), _num(r["ipo_count_net"], int)))
    if rows:
        db.upsert_ipo(conn, rows)
    return len(rows)
