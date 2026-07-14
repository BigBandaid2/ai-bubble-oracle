"""Bankruptcy-docket monitoring — Phase 3 data source.

Resolves the OpenAI / Anthropic bankruptcy conditions from CourtListener's
free RECAP search API (federal court dockets; Chapter 7/11 petitions appear
here within hours of filing). The scan runs daily:

    caseName:(<entity>) AND chapter:(7 OR 11)

then applies an exact-substring name gate, because the search engine stems
aggressively (a personal Chapter 7 by one "Chad Michael Anthrop" matches the
query for Anthropic; the substring gate removes it).

IMPORTANT — human gate: a candidate docket NEVER flips the condition by
itself. Subsidiaries, adversary proceedings, and name collisions all need a
human read. The condition becomes met only when a filing is confirmed in
CONFIRMED_BANKRUPTCIES (oracle/config.py); the dashboard surfaces candidate
counts so a nonzero day is impossible to miss.
"""

import csv
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from ..config import PROJECT_DIR
from .. import db

SEARCH_URL = "https://www.courtlistener.com/api/rest/v4/search/"
USER_AGENT = "ai-bubble-oracle/1.0 (public data monitor; github.com/BigBandaid2/ai-bubble-oracle)"
BANKRUPTCY_CSV = PROJECT_DIR / "data" / "bankruptcy_history.csv"

# entity display name -> substring the case name must actually contain
ENTITIES = {"OpenAI": "openai", "Anthropic": "anthropic"}


def fetch_bankruptcy_candidates(entity):
    """Return {'candidates': n, 'matches': [...]} for one entity, or None on error."""
    needle = ENTITIES[entity]
    query = f"caseName:({entity}) AND chapter:(7 OR 11)"
    url = SEARCH_URL + "?" + urllib.parse.urlencode({"type": "r", "q": query})
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    data = None
    for attempt in range(3):   # the search endpoint is occasionally slow
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            break
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            print(f"Bankruptcy scan attempt {attempt + 1} failed for {entity}: {e}")
            time.sleep(3 * (attempt + 1))
    if data is None:
        return None

    matches = [
        {"case": r.get("caseName"), "court": r.get("court_id"),
         "chapter": r.get("chapter"), "filed": r.get("dateFiled")}
        for r in data.get("results", [])
        if needle in (r.get("caseName") or "").lower()   # exact-substring gate vs. stemming noise
    ]
    return {"candidates": len(matches), "matches": matches}


def scan_all(conn):
    """Daily scan for every entity; records one row per entity per day."""
    today = datetime.now(timezone.utc).date().isoformat()
    results = {}
    for entity in ENTITIES:
        r = fetch_bankruptcy_candidates(entity)
        if r is None:
            continue
        db.upsert_bankruptcy(conn, today, entity, r["candidates"])
        results[entity] = r
        for m in r["matches"]:
            print(f"  !! candidate filing ({entity}): {m['case']} [{m['court']} ch.{m['chapter']} {m['filed']}] — needs human review")
    return results


def import_bankruptcy_csv(conn):
    if not BANKRUPTCY_CSV.exists():
        return 0
    n = 0
    with open(BANKRUPTCY_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            db.upsert_bankruptcy(conn, row["date"], row["entity"], int(row["candidates"]))
            n += 1
    return n


def export_bankruptcy_csv(conn):
    BANKRUPTCY_CSV.parent.mkdir(parents=True, exist_ok=True)
    rows = db.load_bankruptcy(conn)
    with open(BANKRUPTCY_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "entity", "candidates"])
        for r in rows:
            w.writerow([r["date"], r["entity"], r["candidates"]])
    return len(rows)


def update(conn):
    # Bankruptcy conditions: daily CourtListener docket scan (candidates only
    # count after human confirmation in config.CONFIRMED_BANKRUPTCIES).
    import_bankruptcy_csv(conn)
    scans = scan_all(conn)
    for entity, r in scans.items():
        print(f"Bankruptcy scan ({entity}): {r['candidates']} candidate Ch.7/11 filings")
    bk_kept = export_bankruptcy_csv(conn)
    print(f"Bankruptcy history: {bk_kept} scan rows in data/bankruptcy_history.csv")


SOURCE = {
    "kind": "bankruptcy", "label": "CourtListener/RECAP docket scan",
    "requires": [], "redistributable": True, "csv": "data/bankruptcy_history.csv",
    "ddl": None, "order": 70, "date_col": "date", "value_col": "candidates",
    "update": update, "load": None,
}
