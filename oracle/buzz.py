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
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from .config import PROJECT_DIR
from . import db
from .bankruptcy import ENTITIES, USER_AGENT, SEARCH_URL

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
BUZZ_CSV = PROJECT_DIR / "data" / "buzz_history.csv"
BUZZ_META = PROJECT_DIR / "data" / "buzz_meta.json"
NEWS_BACKFILL_START = "20220101000000"

# Bump to force a one-time re-backfill + recalibration when the query changes.
# v2: proximity operators replaced loose keyword co-occurrence.
# v3: broadened from bankruptcy-only to general financial distress.
NEWS_QUERY_VERSION = 3

# Calibration. K_NEWS is a fallback; after each backfill an adaptive value is
# fit to the data (see _calibrate_k) and frozen in buzz_meta.json, so the
# coefficient's scale is stable even as the query evolves.
K_NEWS = 0.008
K_LITIGATION = 10.0
W_NEWS, W_LIT = 0.70, 0.10
DECAY = 0.02          # slow release: max drop per day
DOCKET_FLOOR = 0.90   # while candidates are pending human review
CAP = 0.99

# Financial-distress terms that must appear *near* the entity name (GDELT
# proximity operator) — the nearness requirement kills digest-page
# co-occurrence (a "Top Headlines" roundup with the entity in one bullet and an
# unrelated bankruptcy in another no longer matches). Broadened beyond literal
# bankruptcy to the wider distress narrative (losses, layoffs, funding
# trouble); the LLM pass then filters markers down to genuine trouble, so the
# net can be wide without the markers becoming noisy.
# Kept to ~7 clauses: GDELT rate-limits heavy multi-clause timelinevol backfills
# hard (13 clauses got 429'd persistently; ~5-7 backfills cleanly). These cover
# the distress narrative; near-synonyms (insolvent, liquidation, downturn) were
# dropped as redundant with the LLM doing the fine filtering downstream.
NEAR = 30
DISTRESS_NEAR = ("bankruptcy", "insolvency", "losses", "layoffs",
                 "restructuring", "bailout", "unprofitable")


def _gdelt_query(entity):
    e = entity.lower()
    clauses = " OR ".join(f'near{NEAR}:"{e} {w}"' for w in DISTRESS_NEAR)
    return f"({clauses})"


# --- shared GDELT rate limiter --------------------------------------------
# GDELT's free API is strict (≈1 request / 5 s) and drops you into a penalty
# box after bursts (429, or a plain-text notice with HTTP 200). One getter
# enforces a global minimum spacing and backs off hard on refusal, so every
# call in a run is paced no matter which function makes it.
GDELT_MIN_INTERVAL = 8.0
_last_gdelt = [0.0]


def _gdelt_get(url, timeout=60, tries=4):
    """GET a GDELT URL as JSON (paced + backed off), or None after `tries`."""
    for attempt in range(tries):
        wait = GDELT_MIN_INTERVAL - (time.monotonic() - _last_gdelt[0])
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
            _last_gdelt[0] = time.monotonic()
            if body.lstrip()[:1] in "{[":
                return json.loads(body)
            raise ValueError("non-JSON response (rate-limit notice)")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
                json.JSONDecodeError, ValueError) as e:
            _last_gdelt[0] = time.monotonic()
            backoff = 20 * (attempt + 1)
            print(f"GDELT attempt {attempt + 1} failed ({e}); backoff {backoff}s")
            time.sleep(backoff)
    return None


# --- adaptive calibration + query-version persistence ----------------------

def _read_meta():
    try:
        return json.loads(BUZZ_META.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_meta(d):
    BUZZ_META.parent.mkdir(parents=True, exist_ok=True)
    BUZZ_META.write_text(json.dumps(d, indent=2), encoding="utf-8")


def get_news_k():
    """The frozen adaptive saturation constant (falls back to K_NEWS)."""
    return _read_meta().get("news_k") or K_NEWS


def _calibrate_k(conn):
    """Set k so a *notable* spike reads as clearly elevated buzz.

    k = the MAX_NOTABLE-th largest daily share across both entities, so the
    smallest notable spike gives sat = share/(share+k) ~ 0.5 and the biggest
    spikes approach the news ceiling. Ties calibration to the notability scale.
    """
    shares = []
    for e in ENTITIES:
        shares += [r["news_share"] for r in db.load_buzz(conn, e)
                   if r["news_share"] and r["news_share"] > 0]
    shares.sort(reverse=True)
    if not shares:
        return K_NEWS
    return max(shares[min(MAX_NOTABLE - 1, len(shares) - 1)], 1e-7)


def fetch_news_timeline(entity, backfill=False):
    """Return [(date_iso, share_pct), ...] from GDELT timelinevol, or None."""
    params = {"query": _gdelt_query(entity), "mode": "timelinevol", "format": "json"}
    if backfill:
        params["startdatetime"] = NEWS_BACKFILL_START
        params["enddatetime"] = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    else:
        params["timespan"] = "3months"
    data = _gdelt_get(GDELT_URL + "?" + urllib.parse.urlencode(params))
    if not data:
        return None
    try:
        per_day = {}
        for p in data["timeline"][0]["data"]:
            d = p["date"][:8]
            iso = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
            per_day[iso] = max(per_day.get(iso, 0.0), float(p["value"]))
        return sorted(per_day.items())
    except (KeyError, IndexError, ValueError, TypeError):
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


def _has_news(conn, entity):
    return any(r["news_share"] is not None for r in db.load_buzz(conn, entity))


def all_backfilled(meta=None):
    bf = (meta or _read_meta()).get("backfilled", {})
    return all(bf.get(e) == NEWS_QUERY_VERSION for e in ENTITIES)


def update_signals(conn):
    """Daily signal refresh: GDELT news + docket totals.

    Migration is spread across runs to stay under GDELT's rate limit: AT MOST
    ONE entity is (re-)backfilled per run — the first one not yet at the current
    query version. Entities already migrated get their light 3-month refresh.
    Old news is cleared only after a successful fetch, so a failed query can
    never wipe the existing coefficient. Returns True if a backfill ran.
    """
    meta = _read_meta()
    bf = dict(meta.get("backfilled", {}))
    today = datetime.now(timezone.utc).date().isoformat()
    did_backfill = False
    for entity in ENTITIES:
        needs = bf.get(entity) != NEWS_QUERY_VERSION or not _has_news(conn, entity)
        if needs:
            if did_backfill:
                print(f"Buzz news ({entity}): backfill deferred to a later run")
            else:
                pairs = fetch_news_timeline(entity, backfill=True)
                if pairs:
                    db.clear_buzz_news(conn, entity)
                    db.upsert_buzz_news(conn, entity, pairs)
                    bf[entity] = NEWS_QUERY_VERSION
                    did_backfill = True
                    print(f"Buzz news ({entity}): {len(pairs)} days backfilled (v{NEWS_QUERY_VERSION})")
        else:
            pairs = fetch_news_timeline(entity, backfill=False)
            if pairs:
                db.upsert_buzz_news(conn, entity, pairs)
                print(f"Buzz news ({entity}): {len(pairs)} days refreshed, latest {pairs[-1][1]:.4f}%")
        total = fetch_docket_total(entity)
        if total is not None:
            db.upsert_buzz_dockets(conn, today, entity, total)
            print(f"Buzz litigation ({entity}): {total} total dockets")

    meta["backfilled"] = bf
    meta["news_query_version"] = NEWS_QUERY_VERSION
    if all_backfilled(meta):
        meta["news_k"] = _calibrate_k(conn)
        print(f"Buzz calibrated: all entities on v{NEWS_QUERY_VERSION}, news_k={meta['news_k']:.6f}")
    _write_meta(meta)   # always write so the file exists for the commit step
    return did_backfill


def sat(v, k):
    return v / (v + k) if v and v > 0 else 0.0


def compute_buzz(master, news_by_date, dockets_pairs, cand_by_date, confirmed, k_news=None):
    """The coefficient over the master axis. None before the first news datum."""
    k = k_news if k_news else K_NEWS
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
        raw = 1 - (1 - W_NEWS * sat(news, k)) * (1 - W_LIT * sat(lit, K_LITIGATION))
        b = max(raw, prev - DECAY)
        if cand_by_date.get(d, 0) > 0 and not (confirmed and d >= confirmed):
            b = max(b, DOCKET_FLOOR)
        b = min(b, CAP)
        if confirmed and d >= confirmed:
            b = 1.0
        buzz.append(round(b, 4))
        prev = b
    return buzz


# --- notable spikes: the news items behind the biggest buzz jumps ----------

MAX_NOTABLE = 15          # combined cap across all entities
PEAK_WINDOW_DAYS = 7      # a spike must be the local max within +/- this window
BUZZ_EVENTS_CSV = PROJECT_DIR / "data" / "buzz_events.csv"


def find_notable_spikes(conn):
    """Top news-share peaks across ALL entities under one shared threshold.

    Local maxima (one per +/-7-day news cycle) from every entity are pooled
    and ranked by share; the threshold is set so at most MAX_NOTABLE survive.
    Returns (spikes, threshold) with spikes = [(entity, date, share), ...].
    """
    peaks = []
    for entity in ENTITIES:
        rows = [(r["date"], r["news_share"]) for r in db.load_buzz(conn, entity)
                if r["news_share"] is not None and r["news_share"] > 0]
        by_date = dict(rows)
        dates = [d for d, _ in rows]
        for d, v in rows:
            lo = (datetime.fromisoformat(d) - timedelta(days=PEAK_WINDOW_DAYS)).date().isoformat()
            hi = (datetime.fromisoformat(d) + timedelta(days=PEAK_WINDOW_DAYS)).date().isoformat()
            window = [x for x in dates if lo <= x <= hi]
            if v == max(by_date[x] for x in window) and d == min(x for x in window if by_date[x] == v):
                peaks.append((entity, d, v))
    peaks.sort(key=lambda p: -p[2])
    kept = peaks[:MAX_NOTABLE]
    threshold = kept[-1][2] if kept else 0.0
    return sorted(kept, key=lambda p: p[1]), threshold


# Layer 2 — heuristic scoring of the candidate pool.
DIGEST_DOMAINS = {"menafn.com", "marketscreener.com", "morningstar.com", "finanznachrichten.de"}
DIGEST_MARKERS = ("top company headlines", "headlines at", "briefing", "wrap-up",
                  "wrap up", "roundup", "round-up", "market talk", "things to know",
                  "up first", "what to watch", "morning brief", "evening brief",
                  "week ahead", "recap", "at a glance", "in brief")
DISTRESS_WORDS = ("bankrupt", "insolven", "chapter 11", "restructur", "liquidat",
                  "collapse", "shut down", "shutting", "wind down", "winding down",
                  "default", "distress", "out of cash", "running out of money", "going under",
                  "losses", "loss", "layoff", "unprofitable", "cash burn", "burning cash",
                  "down round", "funding crunch", "bailout", "cash-strapped", "struggl")


def score_candidate(entity, c):
    t = (c.get("title") or "").lower()
    s = 0
    if entity.lower() in t:                                   s += 3   # headline names the entity
    if any(w in t for w in DISTRESS_WORDS):                   s += 2   # …and talks distress
    if (c.get("domain") or "") in DIGEST_DOMAINS:             s -= 3   # known aggregator
    if any(m in t for m in DIGEST_MARKERS):                   s -= 3   # digest/roundup headline
    return s


def fetch_spike_candidates(entity, date, n=25):
    """Up to n de-duplicated candidate articles for the spike day, or None."""
    d = date.replace("-", "")
    params = {
        "query": _gdelt_query(entity), "mode": "artlist", "maxrecords": str(n),
        "sort": "hybridrel", "format": "json",
        "startdatetime": d + "000000", "enddatetime": d + "235959",
    }
    data = _gdelt_get(GDELT_URL + "?" + urllib.parse.urlencode(params))
    if data is None:
        return None
    out, seen = [], set()
    for a in (data.get("articles") or []):
        title = (a.get("title") or "").strip()
        key = title.lower()[:80]
        if not title or key in seen:
            continue
        seen.add(key)
        out.append({"title": title[:160], "url": a.get("url") or "",
                    "domain": a.get("domain") or ""})
    return out


# Layer 3 — LLM classification (Claude Haiku via the Messages API).
LLM_MODEL = "claude-haiku-4-5-20251001"


def classify_with_llm(entity, date, cands):
    """Index of the genuinely-on-topic headline, -1 for NONE, or None (no key/error)."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    listing = "\n".join(f"{i}. [{c.get('domain', '')}] {c.get('title', '')}"
                        for i, c in enumerate(cands))
    prompt = (
        f"On this day there was a spike in news mentioning \"{entity}\" (the AI company) near "
        f"financial-distress terms. Which ONE of the headlines below, if any, is genuinely "
        f"about {entity}'s OWN financial situation in a troubling light — heavy or mounting "
        f"losses, cash burn, funding difficulty or a down round, layoffs, restructuring, "
        f"insolvency, or bankruptcy risk? Accept substantive coverage of {entity}'s finances "
        f"or viability even if it is not literal bankruptcy. REJECT (answer NONE) headlines "
        f"that only mention {entity} in passing beside some other company's trouble, that are "
        f"purely positive (e.g. a big funding round with no distress angle), or that are news "
        f"digests bundling unrelated stories. Reply with ONLY the number of the best headline, "
        f"or the single word NONE.\n\n{listing}"
    )
    body = json.dumps({
        "model": LLM_MODEL, "max_tokens": 16,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = "".join(b.get("text", "") for b in data.get("content", [])).strip()
        if text.upper().startswith("NONE"):
            return -1
        m = re.search(r"\d+", text)
        if m and 0 <= int(m.group()) < len(cands):
            return int(m.group())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, ValueError) as e:
        print(f"LLM classify failed ({entity} {date}): {e}")
    return None


def select_best_article(entity, date):
    """Pick the on-topic article for a spike: LLM if available, else heuristics.
    Returns {title, url, domain, related} or None if nothing fetched."""
    cands = fetch_spike_candidates(entity, date)
    if not cands:
        return None
    idx = classify_with_llm(entity, date, cands)
    if idx is None:                          # no LLM / failure → heuristics
        best = max(cands, key=lambda c: score_candidate(entity, c))
        related = 1 if score_candidate(entity, best) >= 3 else 0
        return {**best, "related": related}
    if idx == -1:                            # LLM: none genuinely on-topic
        best = max(cands, key=lambda c: score_candidate(entity, c))
        return {**best, "related": 0}
    return {**cands[idx], "related": 1}


MAX_FETCH_PER_RUN = 8    # cap GDELT article calls per run (spikes fill over days)


def update_buzz_events(conn):
    """Select (once) the on-topic article behind each notable spike; cache it.

    Only runs when both entities are on the current query version (so spikes are
    computed on consistent data). Prunes cached articles for dates no longer
    among the notable spikes, and fetches at most MAX_FETCH_PER_RUN new ones per
    run — the rest fill in over subsequent daily runs. Only rows with a URL are
    treated as cached, so transient failures retry.
    """
    if not all_backfilled():
        print("Buzz events: skipped (news backfill still in progress)")
        return None, None
    # Invalidate the whole event cache when the query/classification scheme
    # changes, so every spike is re-selected + re-classified under it (also
    # drops rows cached before the classifier existed).
    meta = _read_meta()
    if meta.get("events_version") != NEWS_QUERY_VERSION:
        cleared = db.clear_buzz_events(conn)
        meta["events_version"] = NEWS_QUERY_VERSION
        _write_meta(meta)
        print(f"Buzz events: cleared {cleared} rows for query v{NEWS_QUERY_VERSION}")
    spikes, threshold = find_notable_spikes(conn)
    pruned = db.delete_buzz_events_not_in(conn, {(e, d) for e, d, _ in spikes})
    cached = {(r["entity"], r["date"]) for r in db.load_buzz_events(conn) if r["url"]}
    todo = [s for s in spikes if (s[0], s[1]) not in cached]
    fetched = 0
    for entity, date, share in todo[:MAX_FETCH_PER_RUN]:
        art = select_best_article(entity, date)
        db.upsert_buzz_event(conn, entity, date,
                             art.get("title") if art else None,
                             art.get("url") if art else None,
                             art.get("domain") if art else None,
                             art.get("related", 1) if art else 1)
        fetched += 1
        tag = "" if not art else ("" if art.get("related") else " [flagged unrelated]")
        print(f"Buzz event ({entity} {date}, {share:.4f}%): "
              f"{(art or {}).get('domain') or 'no article'}{tag}")
    remaining = max(0, len(todo) - fetched)
    print(f"Buzz events: {len(spikes)} spikes (threshold {threshold:.4f}%), "
          f"{fetched} fetched, {pruned} pruned, {remaining} deferred to later runs")
    return spikes, threshold


def import_buzz_events_csv(conn):
    if not BUZZ_EVENTS_CSV.exists():
        return 0
    n = 0
    with open(BUZZ_EVENTS_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rel = row.get("related")
            db.upsert_buzz_event(conn, row["entity"], row["date"],
                                 row["title"] or None, row["url"] or None,
                                 row["domain"] or None,
                                 int(rel) if rel not in (None, "") else 1)
            n += 1
    return n


def export_buzz_events_csv(conn):
    BUZZ_EVENTS_CSV.parent.mkdir(parents=True, exist_ok=True)
    rows = db.load_buzz_events(conn)
    with open(BUZZ_EVENTS_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["entity", "date", "title", "url", "domain", "related"])
        for r in rows:
            rel = r["related"] if r["related"] is not None else 1
            w.writerow([r["entity"], r["date"], r["title"] or "", r["url"] or "",
                        r["domain"] or "", rel])
    return len(rows)


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
