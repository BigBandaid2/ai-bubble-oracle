"""H100 rental price — Phase-4 workaround data source.

The Polymarket condition resolves on the SiliconData Silicon Index (SDH100RT),
which is published only via Bloomberg / enterprise API — no public feed. Until
that access exists (future plan), we track a free public PROXY: the median
on-demand price of verified H100 SXM offers on the Vast.ai marketplace, whose
level tracks the published index closely (~$2.2 median vs. the ~$2.16 SDH100RT
quoted in SiliconData's Sept-2025 post).

The proxy is a leading indicator, not the resolution source: it accumulates one
reading per collection day. A few real index values quoted in public
SiliconData posts are seeded for historical context.
"""

import csv
import json
import statistics
import urllib.error
import urllib.parse
import urllib.request

from .config import PROJECT_DIR
from . import db

# The only data that must persist between runs (Yahoo prices are re-fetchable,
# but Vast.ai exposes only current offers). Kept as a small committed CSV so the
# public repo doesn't churn on the multi-MB SQLite file.
H100_CSV = PROJECT_DIR / "data" / "h100_history.csv"

VAST_URL = "https://console.vast.ai/api/v0/bundles/"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# Real index values quoted in public SiliconData posts, for historical context
# on the chart (the live proxy only accumulates going forward). Each is tagged
# with its index tier — the two are a genuine resolution ambiguity.
#   neocloud (SDH100RT), spot-like marketplace tier:
#     https://www.silicondata.com/blog/h100-rental-market-update-september-2025
#   hyperscaler, reserved/committed tier (~3x premium):
#     https://www.silicondata.com/blog/h100-hyperscaler-index-april-2026
SEED_POINTS = [
    ("2025-08-15", "neocloud",    "silicondata_published", 2.24),
    ("2025-09-15", "neocloud",    "silicondata_published", 2.13),
    ("2025-09-30", "neocloud",    "silicondata_published", 2.16),
    ("2026-03-01", "hyperscaler", "silicondata_published", 7.50),
    ("2026-03-23", "hyperscaler", "silicondata_published", 7.52),
    ("2026-03-30", "hyperscaler", "silicondata_published", 7.44),
    ("2026-04-20", "hyperscaler", "silicondata_published", 7.48),
]


def fetch_h100_proxy():
    """Return {usd_hr, low, n} for verified on-demand H100 SXM offers, or None.

    usd_hr = median per-GPU $/hr (the index proxy); low = cheapest; n = sample.
    """
    query = {
        "gpu_name": {"eq": "H100 SXM"},
        "rentable": {"eq": True},
        "verified": {"eq": True},
        "type": "on-demand",
        "order": [["dph_total", "asc"]],
        "limit": 300,
    }
    url = VAST_URL + "?" + urllib.parse.urlencode({"q": json.dumps(query)})
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        print(f"H100 proxy fetch failed: {e}")
        return None

    per_gpu = sorted(
        o["dph_total"] / o["num_gpus"]
        for o in data.get("offers", [])
        if o.get("num_gpus") and o.get("dph_total")
    )
    if not per_gpu:
        return None
    return {"usd_hr": round(statistics.median(per_gpu), 3),
            "low": round(per_gpu[0], 3), "n": len(per_gpu)}


def import_h100_csv(conn):
    """Restore accumulated H100 readings from the committed CSV into the DB."""
    if not H100_CSV.exists():
        return 0
    n = 0
    with open(H100_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            db.upsert_h100(
                conn, row["date"], row["index_type"], row["source"],
                float(row["usd_hr"]),
                float(row["low"]) if row["low"] else None,
                int(row["n"]) if row["n"] else None,
            )
            n += 1
    return n


def export_h100_csv(conn):
    """Write all H100 readings back to the committed CSV for the next run."""
    H100_CSV.parent.mkdir(parents=True, exist_ok=True)
    rows = db.load_h100(conn)
    with open(H100_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "index_type", "source", "usd_hr", "low", "n"])
        for r in rows:
            w.writerow([r["date"], r["index_type"], r["source"], r["usd_hr"],
                        "" if r["low"] is None else r["low"],
                        "" if r["n"] is None else r["n"]])
    return len(rows)
