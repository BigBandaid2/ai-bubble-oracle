"""Fetch the Shiller CAPE (S&P 500 cyclically-adjusted P/E), monthly.

Source: multpl.com's public "Shiller PE by month" table, derived from Robert
Shiller's long-horizon dataset, reaching back to the 1870s. This is the
Then-and-Now valuation-multiple leaf. Unlike raw price, a P/E multiple is
comparable in absolute terms across eras, so it is the "how expensive" signal
that sits beside price appreciation under the Valuation parent.

No API key; the table is simple and stable enough to parse with the stdlib.
Re-fetchable each run, with the committed CSV kept as a fallback like the
other sources.
"""

import csv
import re
import time
import urllib.error
import urllib.request
from datetime import datetime

from ..config import PROJECT_DIR
from .. import db

CAPE_URL = "https://www.multpl.com/shiller-pe/table/by-month"
CAPE_CSV = PROJECT_DIR / "data" / "cape_history.csv"
USER_AGENT = "Mozilla/5.0 (compatible; ai-bubble-oracle/1.0; +https://aibubbleoracle.com)"
# The full series runs to the 1870s; we only need both bubble windows plus a
# margin, so keep it from 1990 on to hold the committed CSV to a few hundred rows.
MIN_YEAR = 1990

# Rows render as: <td>Mar 1, 2000</td>\n<td>\n&#x2002;\n43.22\n</td>
_ROW_RE = re.compile(r"<td>([A-Za-z]{3} \d{1,2}, \d{4})</td>\s*<td>[\s\S]*?([\d.]+)\s*</td>")


class CapeError(Exception):
    pass


def _get(url, retries=4):
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429:
                time.sleep(2 * (attempt + 1))
                continue
            raise CapeError(f"HTTP {e.code} for {url}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise CapeError(f"failed after {retries} retries: {last}")


def fetch_cape():
    """Return sorted [(date_iso, cape)] from MIN_YEAR on, or [] on failure.

    Historical rows are dated the 1st; the newest row can be mid-month, so all
    points are normalized to the month's first day (this series is monthly).
    """
    try:
        html = _get(CAPE_URL)
    except CapeError as e:
        print(f"CAPE fetch failed: {e}")
        return []
    out = {}
    for dstr, val in _ROW_RE.findall(html):
        try:
            d = datetime.strptime(dstr, "%b %d, %Y").date()
        except ValueError:
            continue
        if d.year < MIN_YEAR:
            continue
        out[d.replace(day=1).isoformat()] = float(val)
    return sorted(out.items())


def import_cape_csv(conn):
    if not CAPE_CSV.exists():
        return 0
    rows = []
    with open(CAPE_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append((r["date"], float(r["cape"])))
    db.upsert_cape(conn, rows)
    return len(rows)


def export_cape_csv(conn):
    CAPE_CSV.parent.mkdir(parents=True, exist_ok=True)
    rows = db.load_cape(conn)
    with open(CAPE_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "cape"])
        for r in rows:
            w.writerow([r["date"], r["cape"]])
    return len(rows)


def update(conn):
    # Shiller CAPE valuation multiple (Then-and-Now valuation leaf). Re-fetchable;
    # the committed CSV is a fallback so a stalled fetch doesn't blank the leaf.
    cape_restored = import_cape_csv(conn)
    cape_rows = fetch_cape()
    if cape_rows:
        db.upsert_cape(conn, cape_rows)
        print(f"CAPE: fetched {len(cape_rows)} monthly points "
              f"({cape_rows[0][0]}..{cape_rows[-1][0]}, latest {cape_rows[-1][1]})")
    else:
        print(f"CAPE: fetch failed (kept {cape_restored} cached points)")
    cape_kept = export_cape_csv(conn)
    print(f"CAPE history: {cape_kept} points in data/cape_history.csv")


SOURCE = {
    "kind": "cape", "label": "Shiller CAPE via multpl.com",
    "requires": [], "redistributable": True, "csv": "data/cape_history.csv",
    "ddl": None, "order": 20, "date_col": "date", "value_col": "cape",
    "update": update, "load": lambda conn, arg: db.load_cape(conn),
}
