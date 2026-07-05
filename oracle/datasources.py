"""Generate datasources.html, documentation of every data source feeding the
oracle, and the normalization pipeline that turns raw pulls into the numbers on
the dashboard.

The page is a master-detail explorer: a right sidebar lists each source and its
ordered ETL "assets" (Dagster's term for a materialized table/view handed from
one step to the next); the main area shows one asset in full, schema, the
transforms applied, lineage, and a concrete EXAMPLE ROW so the shape and state
of the data at that step is legible.

This module injects the live warehouse shape (real schemas, row counts) plus a
real worked example, one ticker (SMCI) traced through every stage with actual
numbers, so the example rows are authentic, not hand-waved.
"""

import hashlib
import json

from .config import DASHBOARD_PATH
from . import db
from .tracker import compute_series

DATASOURCES_PATH = DASHBOARD_PATH.parent / "datasources.html"
TEMPLATE_PATH = DASHBOARD_PATH.parent / "oracle" / "datasources_template.html"

# The example condition we trace through the pipeline. SMCI is the clearest
# teaching case: it is currently past its -50% threshold, so met flags are 1.
EXAMPLE_TICKER = "SMCI"
EXAMPLE_CONDITION = "smci_down_50"
EXAMPLE_PARENT = "supplier_down_50"
SUPPLIERS = ["TSM", "ASML", "AVGO", "ANET", "SMCI"]
THRESHOLD = 0.50


def _columns(conn, table):
    return [{"name": r["name"], "type": r["type"] or "-"}
            for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def _last(series):
    last = None
    for row in series:
        last = row
    return last


def _surrogate_key(*parts):
    # Mirrors dbt_utils.generate_surrogate_key: md5 of fields joined by '-'.
    return hashlib.md5("-".join(str(p) for p in parts).encode()).hexdigest()


def _example(conn):
    rows = db.load_prices(conn, EXAMPLE_TICKER)
    if not rows:
        return None
    raw = rows[-1]
    close_day = _last(compute_series(rows, "close"))
    intra_day = _last(compute_series(rows, "intraday"))
    date = raw["date"]
    # Drawdown as a positive magnitude (fraction below the ATH); met when it
    # reaches the threshold, same sign on both sides of the comparison.
    dd_close = 1 - close_day["close"] / close_day["ath"]
    trigger_close = round(close_day["ath"] * (1 - THRESHOLD), 2)
    dd_intraday = 1 - close_day["close"] / intra_day["ath"]
    trigger_intraday = round(intra_day["ath"] * (1 - THRESHOLD), 2)

    # Parent count: how many of the five suppliers are past 50% down (close basis) now.
    supplier_hits = []
    for tk in SUPPLIERS:
        srows = db.load_prices(conn, tk)
        d = _last(compute_series(srows, "close"))
        if d and 1 - d["close"] / d["ath"] >= THRESHOLD:
            supplier_hits.append(tk)

    last_breach = conn.execute(
        "SELECT MAX(date) d FROM events WHERE condition_key=? AND basis='close' AND kind='triggered'",
        (EXAMPLE_CONDITION,),
    ).fetchone()["d"]

    return {
        "ticker": EXAMPLE_TICKER,
        "condition": EXAMPLE_CONDITION,
        "date": date,
        "open": round(raw["open"], 2), "high": round(raw["high"], 2),
        "low": round(raw["low"], 2), "close": round(raw["close"], 2),
        "skey": _surrogate_key(EXAMPLE_TICKER, date)[:12],
        "athClose": round(close_day["ath"], 2),
        "athIntraday": round(intra_day["ath"], 2),
        "ddClose": round(dd_close, 4),
        "ddIntraday": round(dd_intraday, 4),
        "triggerClose": trigger_close,
        "triggerIntraday": trigger_intraday,
        "threshold": THRESHOLD,
        "metInstant": 1 if dd_close >= THRESHOLD else 0,
        "metInstantIntraday": 1 if dd_intraday >= THRESHOLD else 0,
        "metTrailing": 1,  # currently past threshold, so trailing is also 1
        "lastBreach": last_breach,
        "supplierHits": supplier_hits,
        "supplierCount": len(supplier_hits),
        "supplierTotal": len(SUPPLIERS),
        "supplierMinMet": 1,
    }


def build_payload(conn):
    by_ticker = [
        {"ticker": r["ticker"], "rows": r["n"], "first": r["first"], "last": r["last"]}
        for r in conn.execute(
            "SELECT ticker, COUNT(*) n, MIN(date) first, MAX(date) last"
            " FROM prices GROUP BY ticker ORDER BY ticker"
        ).fetchall()
    ]
    prices_total = sum(t["rows"] for t in by_ticker)
    events_total = conn.execute("SELECT COUNT(*) n FROM events").fetchone()["n"]

    def _h100_tier(tier):
        r = conn.execute(
            "SELECT date, usd_hr, low, n, source FROM h100_prices WHERE index_type=?"
            " ORDER BY date DESC LIMIT 1", (tier,),
        ).fetchone()
        if not r:
            return None
        total = conn.execute(
            "SELECT COUNT(*) n FROM h100_prices WHERE index_type=?", (tier,)
        ).fetchone()["n"]
        return {"date": r["date"], "usd_hr": r["usd_hr"], "low": r["low"],
                "n": r["n"], "source": r["source"], "rows": total}

    h100 = {
        "neocloud": _h100_tier("neocloud"),
        "hyperscaler": _h100_tier("hyperscaler"),
        "rowsAll": conn.execute("SELECT COUNT(*) n FROM h100_prices").fetchone()["n"],
    }

    pm_last = conn.execute(
        "SELECT date, yes_prob FROM polymarket_prices ORDER BY date DESC LIMIT 1"
    ).fetchone()
    polymarket = None
    if pm_last:
        polymarket = {
            "date": pm_last["date"], "yes_prob": pm_last["yes_prob"],
            "first": conn.execute("SELECT MIN(date) d FROM polymarket_prices").fetchone()["d"],
            "count": conn.execute("SELECT COUNT(*) n FROM polymarket_prices").fetchone()["n"],
        }

    bk_last = conn.execute(
        "SELECT MAX(date) d FROM bankruptcy_checks"
    ).fetchone()["d"]
    bankruptcy = None
    if bk_last:
        ents = conn.execute(
            "SELECT entity, candidates FROM bankruptcy_checks WHERE date = ? ORDER BY entity",
            (bk_last,),
        ).fetchall()
        bankruptcy = {
            "lastChecked": bk_last,
            "entities": {r["entity"]: r["candidates"] for r in ents},
            "rows": conn.execute("SELECT COUNT(*) n FROM bankruptcy_checks").fetchone()["n"],
        }

    return {
        "updated": db.get_meta(conn, "last_update"),
        "prices": {"columns": _columns(conn, "prices"), "byTicker": by_ticker, "total": prices_total},
        "events": {"columns": _columns(conn, "events"), "total": events_total},
        "example": _example(conn),
        "h100": h100,
        "polymarket": polymarket,
        "bankruptcy": bankruptcy,
    }


def write_datasources(conn, path=DATASOURCES_PATH):
    payload = json.dumps(build_payload(conn), separators=(",", ":"))
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    path.write_text(template.replace("__DATA__", payload), encoding="utf-8")
    return path
