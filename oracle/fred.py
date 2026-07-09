"""Fetch FRED series via the keyless fredgraph.csv endpoint.

One tap for every Then-and-Now macro leaf: IT investment and GDP (capex share),
broker-dealer margin loans (speculation), semiconductor industrial production
(infrastructure), corporate equities market value (Buffett indicator), the
10Y-3M yield-curve spread and Michigan consumer sentiment (monetary & sentiment).
All public-domain US government / Fed-hosted data, so the committed CSV fallback
is redistribution-safe, unlike most market-data vendors.

No API key: `fredgraph.csv?id=SERIES` returns two-column CSV
(observation_date,<ID>) with "." for missing values. Verified working with the
default urllib User-Agent (2026-07-08). Re-fetchable each run; the committed CSV
is the outage fallback like every other source (a failed fetch never blanks a
leaf, it just keeps yesterday's data).
"""

import csv
import time
import urllib.error
import urllib.request

from .config import PROJECT_DIR
from . import db

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
FRED_CSV = PROJECT_DIR / "data" / "fred_history.csv"
# Keep committed history from 1990 on (both bubble windows + margin), like CAPE.
MIN_DATE = "1990-01-01"

# Every series the Then-and-Now registry reads. Adding a metric that needs a new
# FRED series = add its ID here and declare the metric; nothing else.
FRED_SERIES = [
    "A679RC1Q027SBEA",    # Private fixed investment: info processing eq + software, $bn SAAR, quarterly
    "GDP",                # Nominal GDP, $bn SAAR, quarterly
    "BOGZ1FL663067003Q",  # Broker-dealers: margin loans & other receivables, $mn, quarterly (Z.1)
    "IPG3344S",           # Industrial production: semiconductors & components, index, monthly
    "A34SNO",             # New orders: computers & electronic products, $mn SA, monthly
    "NCBEILQ027S",        # Nonfinancial corporate equities, market value, $mn, quarterly (Z.1)
    "T10Y3M",             # 10Y minus 3M treasury spread, %, daily
    "UMCSENT",            # U. Michigan consumer sentiment, index, monthly
]


class FredError(Exception):
    pass


def _get(url, retries=4):
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429:
                time.sleep(2 * (attempt + 1))
                continue
            raise FredError(f"HTTP {e.code} for {url}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise FredError(f"failed after {retries} retries: {last}")


def fetch_fred_series(series_id):
    """Return sorted [(date_iso, value)] from MIN_DATE on, or [] on failure."""
    try:
        text = _get(FRED_CSV_URL.format(series=series_id))
    except FredError as e:
        print(f"FRED fetch failed ({series_id}): {e}")
        return []
    out = []
    for i, row in enumerate(csv.reader(text.splitlines())):
        if i == 0 or len(row) < 2:
            continue                       # header: observation_date,<ID>
        d, v = row[0], row[1]
        if v == "." or not v or d < MIN_DATE:
            continue
        try:
            out.append((d, float(v)))
        except ValueError:
            continue
    out.sort()
    return out


def fetch_all_fred(conn):
    """Fetch every registered series, upserting each on success. Per-series
    failures are isolated: one bad series keeps its cached rows and the rest
    still refresh. Returns {series_id: fetched_count}."""
    counts = {}
    for sid in FRED_SERIES:
        rows = fetch_fred_series(sid)
        if rows:
            db.upsert_fred(conn, sid, rows)
            counts[sid] = len(rows)
        else:
            kept = len(db.load_fred(conn, sid))
            counts[sid] = 0
            print(f"FRED {sid}: fetch failed (kept {kept} cached rows)")
        time.sleep(1)  # be polite; ~7 series
    return counts


def import_fred_csv(conn):
    if not FRED_CSV.exists():
        return 0
    rows_by_series = {}
    with open(FRED_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows_by_series.setdefault(r["series_id"], []).append(
                (r["date"], float(r["value"])))
    n = 0
    for sid, rows in rows_by_series.items():
        db.upsert_fred(conn, sid, rows)
        n += len(rows)
    return n


def export_fred_csv(conn):
    FRED_CSV.parent.mkdir(parents=True, exist_ok=True)
    rows = db.load_fred_all(conn)
    with open(FRED_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["series_id", "date", "value"])
        for r in rows:
            w.writerow([r["series_id"], r["date"], r["value"]])
    return len(rows)
