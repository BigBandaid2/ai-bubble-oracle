"""Bankruptcy-buzz coefficient — signals and computation.

A synthetic 0–1 index per entity that makes the bankruptcy charts informative
between filings. Composition (noisy-OR of independent evidence):

  raw_t  = 1 − (1 − 0.70·sat(news_t)) · (1 − 0.10·sat(litigation_t))
  buzz_t = min(0.99, max(raw_t, buzz_{t−1} − 0.02))      # fast rise, slow release
  buzz_t = max(buzz_t, 0.90)  while docket candidates are pending review
  buzz_t = 1.00               from the human-confirmed filing date (config)

  sat(v) = v / (v + k)  — saturating, so no single component reaches its cap.

Signals:
  A. news_share — GDELT timelinevol: the entity + bankruptcy-flavored keywords
     as a share (%) of all global coverage that day. Backfilled from 2022.
  B. candidates — the CourtListener Chapter 7/11 docket scan (bankruptcy.py).
  C. dockets_total — total federal dockets naming the entity; its 30-day
     growth is a mild litigation-distress pulse (no history before first scan).

The buzz coefficient is PRESENTATION AND EARLY WARNING ONLY: the condition's
met state still comes solely from a docket plus human confirmation. Weights
and saturation constants are editorial calibration, documented on the Data
Sources page.
"""

import csv
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from .config import PROJECT_DIR
from . import db
from .bankruptcy import ENTITIES, USER_AGENT, SEARCH_URL

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
BUZZ_CSV = PROJECT_DIR / "data" / "buzz_history.csv"
NEWS_BACKFILL_START = "20220101000000"

# Calibration (editorial): news share (%) at which sat() = 0.5, and the
# 30-day new-docket count at which the litigation pulse saturates halfway.
# K_NEWS was fit to the 2022-2026 backfill: median day ~0%, p90 ~0.001%,
# historical max 0.027% -> buzz ~0.04 calm, ~0.54 at the historical peak.
K_NEWS = 0.008
K_LITIGATION = 10.0
W_NEWS, W_LIT = 0.70, 0.10
DECAY = 0.02          # slow release: max drop per day
DOCKET_FLOOR = 0.90   # while candidates are pending human review
CAP = 0.99


def _gdelt_query(entity):
    return f'"{entity}" (bankruptcy OR insolvency OR "chapter 11")'


def fetch_news_timeline(entity, backfill=False):
    """Return [(date_iso, share_pct), ...] from GDELT timelinevol, or None."""
    params = {"query": _gdelt_query(entity), "mode": "timelinevol", "format": "json"}
    if backfill:
        params["startdatetime"] = NEWS_BACKFILL_START
        params["enddatetime"] = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    else:
        params["timespan"] = "3months"
    url = GDELT_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(4):   # GDELT: 1 request / 5s, with a penalty box
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read().decode("utf-8")
            data = json.loads(body)
            per_day = {}
            for p in data["timeline"][0]["data"]:
                d = p["date"][:8]
                iso = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
                per_day[iso] = max(per_day.get(iso, 0.0), float(p["value"]))
            return sorted(per_day.items())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, IndexError) as e:
            print(f"GDELT news fetch attempt {attempt + 1} failed for {entity}: {e}")
            time.sleep(15 * (attempt + 1))
    return None


def fetch_docket_total(entity):
    """Total federal dockets naming the entity (litigation pulse), or None."""
    url = SEARCH_URL + "?" + urllib.parse.urlencode(
        {"type": "r", "q": f"caseName:({entity})"})
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return int(json.loads(resp.read().decode("utf-8")).get("count") or 0)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as e:
            print(f"Docket-total fetch attempt {attempt + 1} failed for {entity}: {e}")
            time.sleep(5 * (attempt + 1))
    return None


def update_signals(conn):
    """Daily signal refresh: GDELT news (backfill on first run) + docket totals."""
    today = datetime.now(timezone.utc).date().isoformat()
    for i, entity in enumerate(ENTITIES):
        if i:
            time.sleep(6)   # GDELT rate limit
        backfill = not db.load_buzz(conn, entity)
        pairs = fetch_news_timeline(entity, backfill=backfill)
        if pairs:
            db.upsert_buzz_news(conn, entity, pairs)
            print(f"Buzz news ({entity}): {len(pairs)} days "
                  f"({'backfill' if backfill else 'refresh'}), latest {pairs[-1][1]:.4f}%")
        total = fetch_docket_total(entity)
        if total is not None:
            db.upsert_buzz_dockets(conn, today, entity, total)
            print(f"Buzz litigation ({entity}): {total} total dockets")


def sat(v, k):
    return v / (v + k) if v and v > 0 else 0.0


def compute_buzz(master, news_by_date, dockets_pairs, cand_by_date, confirmed):
    """The coefficient over the master axis. None before the first news datum."""
    dock = dict(dockets_pairs)
    dock_dates = sorted(dock)
    buzz, prev, started = [], 0.0, False
    news = None
    for i, d in enumerate(master):
        if d in news_by_date:
            news, started = news_by_date[d], True
        if not started:
            buzz.append(None)
            continue
        # litigation pulse: new dockets over the trailing ~30 days
        lit = 0.0
        past = [x for x in dock_dates if x <= d]
        if past:
            cur = dock[past[-1]]
            base = dock[max((x for x in dock_dates if x <= master[max(0, i - 30)]),
                            default=past[0])]
            lit = max(0, cur - base)
        raw = 1 - (1 - W_NEWS * sat(news, K_NEWS)) * (1 - W_LIT * sat(lit, K_LITIGATION))
        b = max(raw, prev - DECAY)
        if cand_by_date.get(d, 0) > 0 and not (confirmed and d >= confirmed):
            b = max(b, DOCKET_FLOOR)
        b = min(b, CAP)
        if confirmed and d >= confirmed:
            b = 1.0
        buzz.append(round(b, 4))
        prev = b
    return buzz


def import_buzz_csv(conn):
    if not BUZZ_CSV.exists():
        return 0
    n = 0
    by_entity = {}
    with open(BUZZ_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["news_share"]:
                by_entity.setdefault(row["entity"], []).append((row["date"], float(row["news_share"])))
            if row["dockets_total"]:
                db.upsert_buzz_dockets(conn, row["date"], row["entity"], int(row["dockets_total"]))
            n += 1
    for entity, pairs in by_entity.items():
        db.upsert_buzz_news(conn, entity, pairs)
    return n


def export_buzz_csv(conn):
    BUZZ_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(BUZZ_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "entity", "news_share", "dockets_total"])
        n = 0
        for entity in ENTITIES:
            for r in db.load_buzz(conn, entity):
                w.writerow([r["date"], entity,
                            "" if r["news_share"] is None else r["news_share"],
                            "" if r["dockets_total"] is None else r["dockets_total"]])
                n += 1
    return n
