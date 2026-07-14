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

from ..config import PROJECT_DIR
from .. import db

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


def update(conn):
    # IPO froth seed (Ritter monthly stats; authored CSV, refreshed ~annually).
    ipo_rows = import_ipo_csv(conn)
    print(f"IPO seed: {ipo_rows} monthly rows from data/ipo_issuance.csv")


SOURCE = {
    "kind": "ipo", "label": "IPO stats seed (Ritter, Univ. of Florida)",
    "requires": [], "redistributable": True, "csv": "data/ipo_issuance.csv",
    "ddl": None, "order": 40, "date_col": "month", "value_col": "avg_first_day_return",
    "update": update, "load": lambda conn, arg: db.load_ipo(conn),
}
