"""Generate a self-contained dashboard.html from raw price data.

Unlike the CLI report, the dashboard does NOT ship a pre-evaluated condition
tree. Interpretation (all-time-high basis, 90-day window mode) is chosen
interactively in the browser, so the payload ships the raw material and the
page recomputes the whole tree client-side on every toggle:

  - a master date axis (union of all tickers' trading days, from a buffer
    before CHART_START so the trailing-90d window is correct at the left edge)
  - per drawdown leaf: the close-price line, and for each ATH basis
    (close / intraday) the running ATH, the trigger level, and a per-day
    instant-met bitstring, all aligned to the master axis
  - each leaf's full-history "last instant-met" date per basis (may predate
    the chart), so "last met" is accurate even for old crossings

Everything is inlined (JSON + CSS + JS), so the file works offline from disk.
"""

import json
from datetime import date, datetime, timedelta, timezone

from .config import (BASES, CHART_START, CONFIRMED_BANKRUPTCIES, CONTRACT,
                     DASHBOARD_PATH, DEADLINE, KEY_EVENTS, MARKET_URL,
                     SP500_TICKER, drawdown_leaves)
from . import db
from .tracker import compute_series

TEMPLATE_PATH = DASHBOARD_PATH.parent / "oracle" / "dashboard_template.html"

# Days of data kept before CHART_START so a 90-calendar-day trailing window is
# already accurate on the first displayed day.
BUFFER_DAYS = 110


def _calendar_spine():
    """Daily calendar dates from the buffer start through today (UTC).

    Every graph — equities, H100, Polymarket — shares this one axis, so their
    time scales line up. Equity closes forward-fill across weekends; sparse
    series (H100, Polymarket) are null before their first reading.
    """
    d = date.fromisoformat(CHART_START) - timedelta(days=BUFFER_DAYS)
    today = datetime.now(timezone.utc).date()
    out = []
    while d <= today:
        out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _align_series(pairs, master):
    """Align sorted (date, value) pairs onto the master axis: null before the
    first reading, forward-filled (last known value) afterward."""
    out, j, cur, started = [], 0, None, False
    for d in master:
        while j < len(pairs) and pairs[j][0] <= d:
            cur, started = pairs[j][1], True
            j += 1
        out.append(cur if started else None)
    return out


def _leaf_records(conn, leaf):
    """Return ({date: record}, {basis: last_instant_met_date}) for one leaf.

    record = {"px": close, "close": (ath, trigger, met), "intraday": (...)}.
    Only dates on/after the buffer start are emitted; ATHs still accumulate
    over full history. last-instant-met is computed over full history.
    """
    rows = db.load_prices(conn, leaf["ticker"])
    buf_start = (date.fromisoformat(CHART_START) - timedelta(days=BUFFER_DAYS)).isoformat()
    threshold = leaf["threshold"]
    recs = {}
    last_inst = {}
    for basis in BASES:
        last = None
        for day in compute_series(rows, basis):
            met = 1 if day["drawdown"] >= threshold else 0
            if met:
                last = day["date"]
            if day["date"] < buf_start:
                continue
            r = recs.setdefault(day["date"], {})
            r["px"] = round(day["close"], 2)
            r[basis] = (round(day["ath"], 2), round(day["ath"] * (1 - threshold), 2), met)
        last_inst[basis] = last
    return recs, last_inst


def _rental_type_series(rows, node, master):
    """Build the master-aligned value line + met bitstring for one index tier."""
    dates = [r["date"] for r in rows]
    values = [r["usd_hr"] for r in rows]
    sources = [r["source"] for r in rows]

    # "<= threshold for `days` consecutive readings" — run length over the series.
    run, met_native = 0, []
    for v in values:
        run = run + 1 if v <= node["threshold"] else 0
        met_native.append(1 if run >= node["days"] else 0)

    # Align the met flag onto the master axis (forward-fill; 0 before first read).
    inst, j, cur = [], 0, 0
    for d in master:
        while j < len(dates) and dates[j] <= d:
            cur = met_native[j]
            j += 1
        inst.append(cur)

    last_met = next((dates[i] for i in range(len(met_native) - 1, -1, -1) if met_native[i]), None)
    return {
        "values": _align_series(list(zip(dates, values)), master),   # null before first reading
        "current": values[-1], "currentDate": dates[-1], "source": sources[-1],
        "inst": "".join(str(x) for x in inst), "lastMet": last_met,
    }


def _docket_json(conn, node, master, spikes=None):
    """Payload for a bankruptcy-docket condition.

    Ships the buzz-coefficient series (news + litigation + docket floor, with
    slow release), the candidate counts, and a met bitstring that is all-zero
    unless the entity has a human-confirmed filing in CONFIRMED_BANKRUPTCIES —
    neither buzz nor a scan hit ever flips it.
    """
    from .buzz import compute_buzz
    rows = db.load_bankruptcy(conn, node["entity"])
    if not rows:
        return {"key": node["key"], "label": node["label"], "type": "manual",
                "note": node.get("note", "")}
    pairs = [(r["date"], r["candidates"]) for r in rows]
    cand = _align_series(pairs, master)
    confirmed = CONFIRMED_BANKRUPTCIES.get(node["entity"])
    inst = ["1" if (confirmed and d >= confirmed) else "0" for d in master]

    sig = db.load_buzz(conn, node["entity"])
    news_by_date = {r["date"]: r["news_share"] for r in sig if r["news_share"] is not None}
    dockets_pairs = [(r["date"], r["dockets_total"]) for r in sig if r["dockets_total"] is not None]
    buzz = compute_buzz(master, news_by_date, dockets_pairs, dict(pairs), confirmed)
    cur_buzz = next((v for v in reversed(buzz) if v is not None), None)

    # notable spikes for this entity, with their cached news articles
    idx = {d: i for i, d in enumerate(master)}
    arts = {(r["entity"], r["date"]): r for r in db.load_buzz_events(conn)}
    events = []
    for entity, d, share in (spikes or []):
        if entity != node["entity"] or d not in idx:
            continue
        a = arts.get((entity, d))
        events.append({
            "date": d, "i": idx[d], "share": share,
            "title": (a["title"] if a and a["title"] else None),
            "url": (a["url"] if a and a["url"] else None),
            "domain": (a["domain"] if a and a["domain"] else None),
        })

    return {
        "key": node["key"], "label": node["label"], "type": "docket",
        "entity": node["entity"],
        "cand": cand,
        "buzz": buzz, "currentBuzz": cur_buzz,
        "events": events,
        "candidates": pairs[-1][1], "lastChecked": pairs[-1][0],
        "confirmed": confirmed,
        "inst": "".join(inst),
    }


def _market_json(conn, master):
    """The market's own daily YES-probability, aligned to the master axis."""
    rows = db.load_polymarket(conn)
    if not rows:
        return None
    pairs = [(r["date"], round(r["yes_prob"], 4)) for r in rows]
    prob = _align_series(pairs, master)
    current = next((v for v in reversed(prob) if v is not None), None)
    return {
        "key": "market_price", "label": "Polymarket implied probability (YES)",
        "type": "market", "prob": prob, "current": current, "start": pairs[0][0],
        "url": MARKET_URL,
    }


def _rental_json(conn, node, master):
    """Payload for the H100 rental condition, one series per index tier.

    Each tier ships its own sparse chart series plus a met bitstring aligned to
    the master date axis, so whichever tier the dashboard toggle selects slots
    into the contract's count and the 90-day window logic like a drawdown leaf.
    """
    tiers = {}
    for index_type in ("neocloud", "hyperscaler"):
        rows = db.load_h100(conn, index_type)
        if rows:
            tiers[index_type] = _rental_type_series(rows, node, master)
    if not tiers:
        return {"key": node["key"], "label": node["label"], "type": "manual",
                "note": node.get("note", "")}
    return {
        "key": node["key"], "label": node["label"], "type": "rental",
        "threshold": node["threshold"], "days": node["days"], "note": node.get("note", ""),
        "tiers": tiers, "defaultTier": "neocloud",
    }


def _sp500_json(conn, master):
    """S&P 500 closes aligned to the master axis, plus the key-event markers."""
    rows = db.load_prices(conn, SP500_TICKER)
    if not rows:
        return None
    pairs = [(r["date"], round(r["close"], 2)) for r in rows]
    close = _align_series(pairs, master)
    idx = {d: i for i, d in enumerate(master)}
    events = [{"date": d, "label": lbl, "i": idx[d]}
              for d, lbl in KEY_EVENTS if d in idx]
    current = next((v for v in reversed(close) if v is not None), None)
    return {"close": close, "events": events, "current": current}


def build_payload(conn):
    from .buzz import find_notable_spikes
    spikes, _ = find_notable_spikes(conn)

    leaves = drawdown_leaves()
    leaf_recs = {}
    for leaf in leaves:
        recs, last_inst = _leaf_records(conn, leaf)
        leaf_recs[leaf["key"]] = (recs, last_inst)

    master = _calendar_spine()
    display_start = next((i for i, d in enumerate(master) if d >= CHART_START), 0)

    # Align each leaf onto the master axis, forward-filling gaps.
    aligned = {}
    for key, (recs, last_inst) in leaf_recs.items():
        px, ath, trig, inst = [], {b: [] for b in BASES}, {b: [] for b in BASES}, {b: [] for b in BASES}
        cur_px = None
        cur = {b: (None, None, 0) for b in BASES}
        for d in master:
            r = recs.get(d)
            if r:
                cur_px = r.get("px", cur_px)
                for b in BASES:
                    if b in r:
                        cur[b] = r[b]
            px.append(cur_px)
            for b in BASES:
                a, t, m = cur[b]
                ath[b].append(a)
                trig[b].append(t)
                inst[b].append(m)
        aligned[key] = {"px": px, "ath": ath, "trigger": trig, "inst": inst, "last_inst": last_inst}

    def node_json(node):
        if node["type"] == "drawdown":
            a = aligned[node["key"]]
            return {
                "key": node["key"], "label": node["label"], "type": "drawdown",
                "ticker": node["ticker"], "threshold": node["threshold"],
                "px": a["px"],
                "bases": {b: {
                    "ath": a["ath"][b],
                    "trigger": a["trigger"][b],
                    "inst": "".join(str(x) for x in a["inst"][b]),
                } for b in BASES},
                "lastInst": a["last_inst"],
            }
        if node["type"] == "count":
            return {
                "key": node["key"], "label": node["label"], "type": "count",
                "minMet": node["min_met"], "children": [node_json(c) for c in node["children"]],
            }
        if node["type"] == "rental":
            return _rental_json(conn, node, master)
        if node["type"] == "docket":
            return _docket_json(conn, node, master, spikes)
        return {"key": node["key"], "label": node["label"], "type": "manual",
                "note": node.get("note", "")}

    return {
        "updated": db.get_meta(conn, "last_update"),
        "note": CONTRACT.get("note", ""),
        "deadline": DEADLINE,
        "windowDays": 90,
        "dateAxis": master,
        "displayStart": display_start,
        "marketUrl": MARKET_URL,
        "market": _market_json(conn, master),
        "sp500": _sp500_json(conn, master),
        "tree": node_json(CONTRACT),
    }


def write_dashboard(conn, path=DASHBOARD_PATH):
    payload = json.dumps(build_payload(conn), separators=(",", ":"))
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    path.write_text(template.replace("__DATA__", payload), encoding="utf-8")
    return path
