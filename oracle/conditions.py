"""Generic condition-tree evaluation.

Evaluates the CONTRACT tree bottom-up into per-node results carrying:
  status      — 'met' | 'not_met' | 'unknown'
  last_met    — most recent date the condition was met (None if never/unknown)
  met_series  — (dates, bools) daily met-state over full history, used by
                count-parents; None for nodes with no data
  chart       — display payload for the dashboard, sliced from CHART_START:
                  drawdown leaf -> price/ath/trigger series
                  count parent  -> children-met count series + threshold
                  manual leaf   -> none

Count parents forward-fill each child's met state onto the union of all
child dates, so children with different trading calendars (or nested
parents) merge correctly. Children with no data (manual) contribute 0 to
the count and are surfaced via chart.unknown.
"""

import bisect

from .config import CONTRACT, CHART_START
from .tracker import compute_series
from . import db


def _slice_from(dates, start):
    i = bisect.bisect_left(dates, start)
    return i


def _eval_drawdown(node, conn):
    rows = db.load_prices(conn, node["ticker"])
    if not rows:
        return _no_data(node)
    dates, close, ath, trigger, met = [], [], [], [], []
    for day in compute_series(rows, "close"):
        dates.append(day["date"])
        close.append(round(day["close"], 2))
        ath.append(round(day["ath"], 2))
        trigger.append(round(day["ath"] * (1.0 - node["threshold"]), 2))
        met.append(day["drawdown"] >= node["threshold"])
    last_met = None
    for i in range(len(met) - 1, -1, -1):
        if met[i]:
            last_met = dates[i]
            break
    i0 = _slice_from(dates, CHART_START)
    return {
        "key": node["key"],
        "label": node["label"],
        "type": "drawdown",
        "ticker": node["ticker"],
        "threshold": node["threshold"],
        "status": "met" if met[-1] else "not_met",
        "last_met": last_met,
        "met_series": (dates, met),
        "chart": {
            "kind": "price",
            "dates": dates[i0:],
            "close": close[i0:],
            "ath": ath[i0:],
            "trigger": trigger[i0:],
            "met": met[i0:],
        },
        "stats": {
            "date": dates[-1],
            "close": close[-1],
            "ath": ath[-1],
            "trigger": trigger[-1],
            "drawdown": round(1.0 - close[-1] / ath[-1], 4),
        },
        "children": [],
    }


def _eval_rental(node, conn):
    # The CLI uses the neocloud tier — the SDH100RT the market rules name.
    rows = db.load_h100(conn, "neocloud")
    if not rows:
        return _no_data(node)
    dates = [r["date"] for r in rows]
    values = [r["usd_hr"] for r in rows]
    run, met = 0, []
    for v in values:
        run = run + 1 if v <= node["threshold"] else 0
        met.append(run >= node["days"])
    last_met = next((dates[i] for i in range(len(met) - 1, -1, -1) if met[i]), None)
    return {
        "key": node["key"], "label": node["label"], "type": "rental",
        "threshold": node["threshold"],
        "status": "met" if met[-1] else "not_met",
        "last_met": last_met,
        "met_series": (dates, met),
        "chart": {"kind": "none"},
        "stats": {"date": dates[-1], "usd_hr": values[-1], "source": rows[-1]["source"],
                  "days": node["days"], "threshold": node["threshold"], "tier": "neocloud"},
        "children": [],
    }


def _no_data(node, children=None):
    return {
        "key": node["key"],
        "label": node["label"],
        "type": node["type"],
        "status": "unknown",
        "last_met": None,
        "met_series": None,
        "chart": {"kind": "none", "reason": node.get("note", "No automated data source connected yet.")},
        "stats": None,
        "children": children or [],
    }


def _eval_count(node, conn):
    children = [eval_node(c, conn) for c in node["children"]]
    with_data = [c for c in children if c["met_series"] is not None]
    unknown = len(children) - len(with_data)
    if not with_data:
        return _no_data(node, children)

    # Union of all child dates; forward-fill each child's met state onto it.
    all_dates = sorted({d for c in with_data for d in c["met_series"][0]})
    counts = [0] * len(all_dates)
    for c in with_data:
        cd, cm = c["met_series"]
        state, j = False, 0
        for i, date in enumerate(all_dates):
            while j < len(cd) and cd[j] <= date:
                state = cm[j]
                j += 1
            counts[i] += 1 if state else 0

    min_met = node["min_met"]
    met = [n >= min_met for n in counts]
    last_met = None
    for i in range(len(met) - 1, -1, -1):
        if met[i]:
            last_met = all_dates[i]
            break
    i0 = _slice_from(all_dates, CHART_START)
    return {
        "key": node["key"],
        "label": node["label"],
        "type": "count",
        "min_met": min_met,
        "status": "met" if met[-1] else "not_met",
        "last_met": last_met,
        "met_series": (all_dates, met),
        "chart": {
            "kind": "count",
            "dates": all_dates[i0:],
            "count": counts[i0:],
            "threshold": min_met,
            "total": len(children),
            "unknown": unknown,
        },
        "stats": {
            "date": all_dates[-1],
            "count": counts[-1],
            "needed": min_met,
            "total": len(children),
            "unknown": unknown,
        },
        "children": children,
    }


def eval_node(node, conn):
    if node["type"] == "drawdown":
        return _eval_drawdown(node, conn)
    if node["type"] == "rental":
        return _eval_rental(node, conn)
    if node["type"] == "manual":
        return _no_data(node)
    if node["type"] == "count":
        return _eval_count(node, conn)
    raise ValueError(f"unknown node type: {node['type']}")


def evaluate(conn):
    """Evaluate the whole contract tree. Returns the root result (nested)."""
    return eval_node(CONTRACT, conn)


def strip_met_series(result):
    """Drop the bulky full-history met_series before JSON serialization."""
    result = dict(result)
    result.pop("met_series", None)
    result["children"] = [strip_met_series(c) for c in result["children"]]
    return result
