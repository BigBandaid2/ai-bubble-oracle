"""Polymarket data source — the market's own implied probability over time.

Fetches the daily YES-price history of the "AI bubble burst in 2026?" market
from Polymarket's public CLOB API, so the contract's own implied chance of
resolving YES can be plotted alongside the underlying conditions.

The full history is re-fetchable each run (interval=max), but a stalled API
shouldn't blank the chart — so readings are cached in a small committed CSV and
used as a fallback.
"""

import csv
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone

from ..config import PROJECT_DIR
from .. import db

# YES (outcome index 0) CLOB token id for "AI bubble burst in 2026?"
# (event ai-bubble-burst-by; market created 2025-11-20). The prices-history
# endpoint keys on the token id, not the condition id.
YES_TOKEN = "95143949049440805515065120245245136072200903084986833252741074455111459269340"
HISTORY_URL = ("https://clob.polymarket.com/prices-history"
               "?market={token}&interval=max&fidelity=1440")
POLYMARKET_CSV = PROJECT_DIR / "data" / "polymarket_history.csv"
USER_AGENT = "Mozilla/5.0 (compatible; ai-bubble-oracle/1.0)"


def fetch_market_history():
    """Return [(date_iso, yes_prob), …] daily (last value per UTC date), or []."""
    url = HISTORY_URL.format(token=YES_TOKEN)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        print(f"Polymarket fetch failed: {e}")
        return []

    per_day = {}
    for point in data.get("history", []):
        d = datetime.fromtimestamp(point["t"], tz=timezone.utc).date().isoformat()
        per_day[d] = round(float(point["p"]), 4)   # last point of the day wins
    return sorted(per_day.items())


def import_polymarket_csv(conn):
    if not POLYMARKET_CSV.exists():
        return 0
    rows = []
    with open(POLYMARKET_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append((row["date"], float(row["yes_prob"])))
    db.upsert_polymarket(conn, rows)
    return len(rows)


def export_polymarket_csv(conn):
    POLYMARKET_CSV.parent.mkdir(parents=True, exist_ok=True)
    rows = db.load_polymarket(conn)
    with open(POLYMARKET_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "yes_prob"])
        for r in rows:
            w.writerow([r["date"], r["yes_prob"]])
    return len(rows)


def update(conn):
    # Polymarket's own implied YES-probability over time. Full history is
    # re-fetchable; the CSV is a fallback so a stalled API doesn't blank the chart.
    pm_restored = import_polymarket_csv(conn)
    pm_hist = fetch_market_history()
    if pm_hist:
        db.upsert_polymarket(conn, pm_hist)
        print(f"Polymarket: fetched {len(pm_hist)} daily points "
              f"({pm_hist[0][0]}..{pm_hist[-1][0]}, latest {pm_hist[-1][1] * 100:.0f}% YES)")
    else:
        print(f"Polymarket: fetch failed (kept {pm_restored} cached points)")
    pm_kept = export_polymarket_csv(conn)
    print(f"Polymarket history: {pm_kept} points in data/polymarket_history.csv")


SOURCE = {
    "kind": "polymarket", "label": "Polymarket CLOB (market YES probability)",
    "requires": [], "redistributable": True, "csv": "data/polymarket_history.csv",
    "ddl": None, "order": 60, "date_col": "date", "value_col": "yes_prob",
    "update": update, "load": None,
}
