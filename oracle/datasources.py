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
import math
import re
from decimal import Decimal, ROUND_FLOOR

from .config import DASHBOARD_PATH
from . import db
from .thennow import compute_thennow
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


def _thennow_example(conn):
    """Real scalars from the Then-and-Now roll-up tree so the per-graph IR
    example rows are authentic (mirrors how _example traces SMCI)."""
    t = compute_thennow(conn)
    if not t:
        return None

    def find(node, key):
        if node.get("key") == key:
            return node
        for c in node.get("children", []):
            hit = find(c, key)
            if hit:
                return hit
        return {}

    root, pk = t["tree"], t["peakIdx"]
    # price = the Nasdaq leaf (feeds tn_price); sp = the S&P leaf (tn_sp500);
    # pa = the Price-appreciation sub-blend of the two; val = the Valuation roll-up.
    price, sp = find(root, "nasdaq"), find(root, "sp500")
    cape, pa, val = (find(root, "valuation_multiple"),
                     find(root, "price_appreciation"), find(root, "valuation"))

    def last(a):
        return a[-1] if a else None

    def at(a, i):
        return a[i] if a and 0 <= i < len(a) else None

    return {
        "headlineDate": t["headlineDate"], "bandLow": t["bandLow"],
        "bandHigh": t["bandHigh"], "asOf": t["asOf"],
        "dotWk": len(t["progDot"]), "aiWk": len(t["progAi"]),
        # price leaf: native look-through (Nasdaq) at each step + scalars
        "priceRawNow": last(price.get("rawAi")), "priceSmNow": last(price.get("smoothedAi")),
        "pricePeak": at(price.get("smoothedDot"), pk), "priceStart": at(price.get("smoothedAi"), 0),
        "priceIntensity": price.get("intensityNow"), "priceEquiv": price.get("equivalentDotcomDate"),
        "priceProj": price.get("projectedPeakDate"), "priceDisplay": price.get("display"),
        "priceDaysFromPeak": price.get("daysFromPeak"), "priceCompression": price.get("compression"),
        # cape leaf
        "capeRawNow": last(cape.get("rawAi")), "capeSmNow": last(cape.get("smoothedAi")),
        "capePeak": at(cape.get("smoothedDot"), pk),
        "capeIntensity": cape.get("intensityNow"), "capeEquiv": cape.get("equivalentDotcomDate"),
        "capeProj": cape.get("projectedPeakDate"), "capeDisplay": cape.get("display"),
        "capeDaysFromPeak": cape.get("daysFromPeak"), "capeCompression": cape.get("compression"),
        # valuation roll-up
        "valIntensity": val.get("intensityNow"), "valEquiv": val.get("equivalentDotcomDate"),
        "valProj": val.get("projectedPeakDate"), "valPhase": val.get("phase"),
        # S&P 500 leaf (Phase 3): native look-through + scalars, its own pipeline
        "sp500RawNow": last(sp.get("rawAi")), "sp500SmNow": last(sp.get("smoothedAi")),
        "sp500Peak": at(sp.get("smoothedDot"), pk), "sp500Intensity": sp.get("intensityNow"),
        "sp500Equiv": sp.get("equivalentDotcomDate"), "sp500Proj": sp.get("projectedPeakDate"),
        "sp500Display": sp.get("display"), "sp500DaysFromPeak": sp.get("daysFromPeak"),
        # Price-appreciation sub-blend (Nasdaq + S&P)
        "prApprIntensity": pa.get("intensityNow"), "prApprProj": pa.get("projectedPeakDate"),
        "prApprEquiv": pa.get("equivalentDotcomDate"), "prApprPhase": pa.get("phase"),
        # validator verdicts + checks + cached observation, per metric
        "priceValid": price.get("valid"), "capeValid": cape.get("valid"), "valValid": val.get("valid"),
        "sp500Valid": sp.get("valid"), "prApprValid": pa.get("valid"),
        "priceChecks": (price.get("validation") or {}).get("checks", []),
        "capeChecks": (cape.get("validation") or {}).get("checks", []),
        "sp500Checks": (sp.get("validation") or {}).get("checks", []),
        "priceObs": price.get("observations"), "capeObs": cape.get("observations"),
        "sp500Obs": sp.get("observations"), "prApprObs": pa.get("observations"),
        "valObs": val.get("observations"),
        # per-node scalar map for the big-bang chains (every leaf + roll-up):
        # native now / smoothed now / value at the declared peak / intensity /
        # match + projection / verdict + check tally / cached observation.
        "nodes": _node_examples(t, pk),
    }


def _node_examples(t, pk):
    out = {}

    def walk(n):
        if n.get("wip") or n.get("stub"):
            return
        checks = (n.get("validation") or {}).get("checks", [])
        e = {
            "intensity": n.get("intensityNow"), "equiv": n.get("equivalentDotcomDate"),
            "proj": n.get("projectedPeakDate"), "daysFromPeak": n.get("daysFromPeak"),
            "phase": n.get("phase"), "valid": n.get("valid"),
            "checksPass": sum(1 for c in checks if c["pass"]), "checksN": len(checks),
            "obs": n.get("observations"), "display": n.get("display"),
        }
        if n.get("leaf"):
            raw_ai, sm_ai, sm_dot = n.get("rawAi"), n.get("smoothedAi"), n.get("smoothedDot")
            e["rawNow"] = raw_ai[-1] if raw_ai else None
            e["smNow"] = sm_ai[-1] if sm_ai else None
            e["peak"] = sm_dot[pk] if sm_dot and 0 <= pk < len(sm_dot) else None
            e["unitLabel"] = n.get("unitLabel")
        out[n["key"]] = e
        for c in n.get("children", []):
            walk(c)

    walk(t["tree"])
    return out


# ------------------------------------------------------------------ thennow IR
# The Then-and-Now section of the Data Sources page is generated from the
# metric modules' `ir` declarations (see oracle/metrics/*.py). These are
# Python ports of the page's old JS chain factories (tnLeafChain / tnRollup /
# tnVChain / tnJoin); they must reproduce the JS output exactly, including how
# a JS template literal prints numbers, so the strings below are deliberate.

_IR_TOKEN = re.compile(r"\{\{(\w+)\}\}")


def _js_num(v):
    """A value exactly as a JS template literal would print it (188.0 → '188')."""
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        if v == int(v) and abs(v) < 1e16:
            return str(int(v))
        if 0 < abs(v) < 1e-4:                      # JS stays positional to 1e-6
            return format(Decimal(repr(v)), "f")
        return repr(v)
    return str(v)


def _s(v):
    """A string exactly as `${v}` prints it (None → 'null')."""
    return "null" if v is None else str(v)


def _to_fixed(v, digits):
    """JS Number.toFixed: round half toward +infinity on the exact binary value."""
    d = Decimal(v).scaleb(digits)
    n = int((d + Decimal("0.5")).to_integral_value(rounding=ROUND_FLOOR))
    s = str(abs(n)).rjust(digits + 1, "0")
    out = s[:-digits] + "." + s[-digits:] if digits else s
    return ("-" if n < 0 or (n == 0 and v < 0) else "") + out


def _tn_f(v):
    """The page's tnF display formatter (en-US thousands separators)."""
    if v is None:
        return "-"
    v = float(v)
    if abs(v) >= 100:
        return f"{math.floor(v + 0.5):,}"          # JS Math.round + toLocaleString
    return _to_fixed(v, 1 if abs(v) >= 10 else 2)


def _ir_ctx(tn, n):
    """String values for every {{token}} an ir block may embed."""
    proj, valid = n.get("proj"), n.get("valid")
    return {
        "asOf": tn["asOf"], "dotWk": str(tn["dotWk"]), "aiWk": str(tn["aiWk"]),
        "rawNow": _js_num(n.get("rawNow")), "smNow": _js_num(n.get("smNow")),
        "peak": _js_num(n.get("peak")), "intensity": _js_num(n.get("intensity")),
        "daysFromPeak": _js_num(n.get("daysFromPeak")),
        "equiv": _s(n.get("equiv")), "proj": _s(proj),
        "phase": _s(n.get("phase")), "display": _s(n.get("display")),
        "obs": _s(n.get("obs")),
        "checksPass": str(n.get("checksPass", 0)), "checksN": str(n.get("checksN", 0)),
        "verdictWord": "conforms" if valid else "suppressed",
        "verdictLong": "conforms, projection drawn" if valid else "suppressed",
        "intensityPct": _tn_f((n.get("intensity") or 0) * 100),
        "rawNowF": _tn_f(n.get("rawNow")),
        "projDash": proj or "-",
    }


def _ir_fill(v, ctx, node):
    """Materialize an ir fragment: {{token}} substitution in strings, and
    {"live": "<field>", "scale": k} dicts to typed example values. An unknown
    token raises KeyError so a module typo fails the build loudly."""
    if isinstance(v, str):
        return _IR_TOKEN.sub(lambda m: ctx[m.group(1)], v)
    if isinstance(v, dict):
        if "live" in v and not (set(v) - {"live", "scale"}):
            val = node.get(v["live"])
            return val * v["scale"] if ("scale" in v and val is not None) else val
        return {k: _ir_fill(x, ctx, node) for k, x in v.items()}
    if isinstance(v, list):
        return [_ir_fill(x, ctx, node) for x in v]
    return v


def _tn_leaf_chain(cfg, spec, gid, tn, n):
    """Port of the page's tnLeafChain(cfg): the standard 8-asset leaf pipeline
    (source → raw → staging → metric → smoothed → intensity → validated →
    graph) with authored prose from the module's compact cfg."""
    P, tree_key, cadence = cfg["p"], spec["key"], cfg["cadence"]
    ratio = spec["type"] == "ratio_from_start"
    valid = bool(n.get("valid"))
    chain = []
    src = cfg.get("src")
    if src:
        chain.append({
            "id": src["id"], "group": gid, "layer": "source", "status": "live",
            "name": src["id"], "mat": src.get("mat") or "API response (CSV)",
            "cadence": src.get("cadence") or "on update",
            "dagster": "thennow/" + re.sub(r"^(raw|seed)\.", "", src["id"]), "dbt": src["dbt"],
            "grain": src["grain"], "why": src["why"], "desc": src["desc"], "upstream": [],
            "transforms": [{"tag": "seed" if src.get("seed") else "extract", "text": src["tx"]}],
            "cardinality": src["card"],
        })
    raw = cfg.get("raw")
    if raw:
        chain.append({
            "id": raw["id"], "group": gid, "layer": "raw", "status": "live",
            "name": raw["id"], "mat": raw.get("mat") or "table (fred_series slice)",
            "cadence": raw.get("cadence") or "on update",
            "dagster": "thennow/" + raw["id"], "dbt": raw["id"],
            "grain": raw["grain"], "why": raw["why"], "desc": raw["desc"],
            "upstream": [src["id"]] if src else [],
            "schema": raw["schema"],
            "transforms": [{"tag": "incremental", "text": raw.get("tx") or "upsert on (series_id, date)"}],
            "tests": ["unique: date", "not_null: " + (raw.get("valCol") or "value")],
            "cardinality": raw["card"],
        })
    chain.append({
        "id": f"stg_{P}_filled", "group": gid, "layer": "staging", "status": "live",
        "name": f"stg_{P}_filled", "mat": "table", "cadence": "on generate",
        "dagster": f"thennow/stg_{P}_filled", "dbt": f"stg_{P}_filled",
        "grain": "one row per calendar day, per era window",
        "why": "A gap-free daily grid so the smoother sees every day; slower cadences step-hold.",
        "desc": cfg.get("stgDesc") or ("Trims to the two declared era windows and forward-fills each published "
                                       + cadence + " value across its days (a step-hold, not interpolation). _grid + _fill."),
        "upstream": cfg.get("stgUpstream") or [raw["id"]],
        "schema": [
            {"col": "era", "type": "STRING", "kind": "key", "ex": "ai", "note": "dotcom | ai"},
            {"col": "date", "type": "DATE", "kind": "key", "ex": tn["asOf"]},
            {"col": "value", "type": "NUMERIC", "kind": "derived", "ex": n.get("rawNow"), "note": "forward-filled"},
        ],
        "transforms": [
            {"tag": "trim", "text": "to the declared era windows"},
            {"tag": "forward-fill", "text": "hold each " + cadence + " value across its days"},
        ],
        "cardinality": f"daily; {tn['dotWk']}+{tn['aiWk']} weekly points shipped.",
    })
    chain.append({
        "id": f"int_{P}_metric", "group": gid, "layer": "intermediate", "status": "live",
        "name": f"int_{P}_metric", "mat": "table", "cadence": "on generate",
        "dagster": f"thennow/int_{P}_metric", "dbt": f"int_{P}_metric",
        "grain": "one row per (era, day)",
        "why": cfg.get("metricWhy") or "Applies the declared formula from the metric registry.",
        "desc": cfg["metricDesc"],
        "upstream": [f"stg_{P}_filled"],
        "schema": [
            {"col": "date", "type": "DATE", "kind": "key", "ex": tn["asOf"]},
            {"col": "value", "type": "NUMERIC", "kind": "derived", "ex": n.get("rawNow"), "note": cfg["metricNote"]},
        ],
        "transforms": [{"tag": "formula", "text": cfg["metricTx"]}],
        "cardinality": "1:1 with the daily grid.",
    })
    chain.append({
        "id": f"int_{P}_smoothed", "group": gid, "layer": "intermediate", "status": "live",
        "name": f"int_{P}_smoothed", "mat": "table", "cadence": "on generate",
        "dagster": f"thennow/int_{P}_smoothed", "dbt": f"int_{P}_smoothed",
        "grain": "one row per (era, day)",
        "why": "A centered mean so the equivalent point reads cleanly, anchored so intensity=100% lands on the declared peak.",
        "desc": "Centered moving average, edge-truncated at today, materialized at both the 90-day '3-month' (default) "
                "and 30-day '1-month' windows; the page's Options drawer toggles which one is read. _smooth_centered.",
        "upstream": [f"int_{P}_metric"],
        "schema": [
            {"col": "date", "type": "DATE", "kind": "key", "ex": tn["asOf"]},
            {"col": "smoothed", "type": "NUMERIC", "kind": "derived", "ex": n.get("smNow"),
             "note": f"now; at the declared peak ≈ {_tn_f(n.get('peak'))}"},
        ],
        "transforms": [{"tag": "smooth", "text": "centered 90-day mean (min-periods at the edge)"}],
        "tests": ["not_null: smoothed"],
        "cardinality": "1:1 with the daily grid.",
    })
    chain.append({
        "id": f"int_{P}_intensity", "group": gid, "layer": "intermediate", "status": "live",
        "name": f"int_{P}_intensity", "mat": "table", "cadence": "on generate",
        "dagster": f"thennow/int_{P}_intensity", "dbt": f"int_{P}_intensity",
        "grain": "one row per (era, day)",
        "why": "The shared 0-1 intensity: 0 at the dot-com starting level, 1 at the declared peak.",
        "desc": ("ratio_from_start: index each era to its own start, then map onto the dot-com range, "
                 "so inflation and scale drift are normalized away. _normalize."
                 if ratio else
                 "absolute_level: compare levels directly on the dot-com anchors (this measure means the same "
                 "thing in any era), so a reading past the 2000 level shows as intensity above 1. _normalize."),
        "upstream": [f"int_{P}_smoothed"],
        "schema": [
            {"col": "date", "type": "DATE", "kind": "key", "ex": tn["asOf"]},
            {"col": "progress", "type": "NUMERIC", "kind": "derived", "ex": "days ÷ ramp × 100"},
            {"col": "intensity", "type": "NUMERIC", "kind": "derived", "ex": n.get("intensity"), "note": "0 start, 1 peak"},
        ],
        "transforms": [{"tag": "normalize",
                        "text": "growth-since-start over the dot-com range" if ratio
                                else "absolute level on the dot-com range"}],
        "cardinality": "1:1; weekly-downsampled for the page.",
    })
    chain.append({
        "id": f"int_{P}_validated", "group": gid, "layer": "intermediate", "status": "live",
        "name": f"int_{P}_validated", "mat": "table", "cadence": "on generate",
        "dagster": f"thennow/int_{P}_validated", "dbt": f"int_{P}_validated",
        "grain": "one verdict per metric (+ one row per check)",
        "why": "The gate every metric passes through. Only a series that rises, peaks, and falls like the dot-com "
               "reference, with AI below that peak and moving toward it, earns a projection; a non-conforming "
               "metric is shown as a labeled counter-argument instead.",
        "desc": "Two passes over the daily curves: candidacy (covers both eras, real dynamic range) then shape. "
                "Emits {valid, checks[], observations}; the verdict and numbers are computed, a cached hash-gated "
                "Haiku call writes the prose (deterministic fallback). _validate + observe.refresh_observations.",
        "upstream": [f"int_{P}_intensity"],
        "schema": [
            {"col": "check", "type": "TEXT", "kind": "key", "ex": "rise, peak, fall"},
            {"col": "pass", "type": "BOOLEAN", "kind": "derived", "ex": n.get("valid"),
             "note": f"{n.get('checksPass', 0)}/{n.get('checksN', 0)} checks pass → "
                     + ("conforms" if valid else "projection suppressed")},
            {"col": "observations", "type": "TEXT", "kind": "derived", "ex": "Haiku · cached", "note": n.get("obs")},
        ],
        "transforms": [
            {"tag": "validate", "text": "candidacy + shape checks → verdict"},
            {"tag": "observe", "text": "cached, hash-gated Haiku prose (deterministic fallback)"},
        ],
        "tests": ["not_null: valid", "accepted_values: valid in (true, false)"],
        "cardinality": "1 verdict per metric; gates the projection downstream.",
    })
    if valid:
        g_json = ('{ "intensityNow": ' + _js_num(n.get("intensity"))
                  + ', "equivalentDotcomDate": "' + _s(n.get("equiv"))
                  + '",\n  "daysFromPeak": ' + _js_num(n.get("daysFromPeak"))
                  + ', "projectedPeakDate": "' + _s(n.get("proj"))
                  + '",\n  "display": "' + _s(n.get("display")) + '" }')
    else:
        g_json = ('{ "intensityNow": ' + _js_num(n.get("intensity"))
                  + ', "valid": false,\n  "display": "' + _s(n.get("display"))
                  + '", "projectedPeakDate": null }')
    chain.append({
        "id": "graph." + tree_key, "group": gid, "layer": "serve", "status": "live",
        "name": "graph: " + tree_key, "mat": "exposure (JSON)", "cadence": "on generate",
        "dagster": "thennow (exposure)", "dbt": "exposure: " + tree_key,
        "grain": "one leaf block on thennow.html",
        "why": cfg["graphWhy"],
        "desc": (cfg.get("graphDesc") or "Match today's intensity on the dot-com ramp, rate-scale the remainder, "
                                         "ship exact daily scalars plus a weekly series carrying the native value "
                                         "for hover/CSV. _evaluate + _emit.")
                + ("" if valid else " Currently NON-CONFORMING: the date is suppressed and the leaf renders as a counter-argument."),
        "upstream": [f"int_{P}_validated"],
        "json": g_json,
        "transforms": [
            {"tag": "lookup", "text": "value-match on the dot-com ramp → equivalent date"},
            {"tag": "rate-scale", "text": "remaining distance × AI pace → projected top"},
            {"tag": "gate", "text": "projection drawn only if the validator conforms"},
        ],
        "cardinality": "one leaf node on the Then-and-Now page.",
    })
    return chain


def _tn_rollup(cfg, spec, gid, tn, n):
    """Port of the page's tnRollup(cfg): dimmed foreign inputs → weighted
    blend → graph, for a branch roll-up group."""
    blend_id, tree_key = cfg["blendId"], spec["key"]
    valid = bool(n.get("valid"))
    proj_json = ('"' + _s(n.get("proj")) + '"') if valid else "null"
    return [{
        "id": blend_id, "group": gid, "layer": "intermediate", "status": "live",
        "name": blend_id, "mat": "table", "cadence": "on generate",
        "dagster": "thennow/" + blend_id, "dbt": blend_id,
        "grain": "one row per (era, day)",
        "why": cfg["blendWhy"],
        "desc": cfg["blendDesc"] + " Only CONFORMING inputs are blended; a non-conforming leaf is shown but never "
                                   "drags the roll-up. Its inputs live in their own pipelines and are shown dimmed here. _blend.",
        "upstream": cfg["inputs"],
        "schema": [
            {"col": "date", "type": "DATE", "kind": "key", "ex": tn["asOf"]},
            {"col": "intensity", "type": "NUMERIC", "kind": "derived", "ex": n.get("intensity"),
             "note": "weighted mean of conforming children"},
        ],
        "transforms": [{"tag": "combine", "text": "equal-weight mean of the conforming child intensities"}],
        "tests": ["not_null: intensity"],
        "cardinality": "1:1 on the shared daily grid.",
    }, {
        "id": "graph." + tree_key, "group": gid, "layer": "serve", "status": "live",
        "name": "graph: " + tree_key, "mat": "exposure (JSON)", "cadence": "on generate",
        "dagster": "thennow (exposure)", "dbt": "exposure: " + tree_key,
        "grain": "one roll-up block on thennow.html",
        "why": cfg["graphWhy"],
        "desc": "The same alignment + projection as a leaf, run on the blended curve."
                + ("" if valid else " Currently NO conforming inputs, so the branch renders as context with its projection suppressed."),
        "upstream": [blend_id],
        "json": ('{ "intensityNow": ' + _js_num(n.get("intensity")) + ', "valid": ' + _js_num(valid)
                 + ',\n  "projectedPeakDate": ' + proj_json + ', "phase": "' + _s(n.get("phase")) + '" }'),
        "transforms": [
            {"tag": "lookup", "text": "value-match on the blended curve"},
            {"tag": "rate-scale", "text": "→ branch projected top (suppressed if no inputs conform)"},
        ],
        "cardinality": "one roll-up node; feeds the root headline.",
    }]


_GRAPH_MX = 220     # the page's MX: main-spine x centre


def _tn_vchain(cfg):
    """Port of tnVChain(ids, shorts): a straight top-to-bottom chain layout."""
    ids, shorts = cfg["ids"], cfg.get("shorts") or {}
    nodes = []
    for i, aid in enumerate(ids):
        node = {"id": aid, "cx": _GRAPH_MX, "cy": 30 + i * 60 + (20 if i == len(ids) - 1 else 0)}
        if aid in shorts:
            node["short"] = shorts[aid]
        nodes.append(node)
    return {
        "viewBox": f"0 0 460 {30 + (len(ids) - 1) * 60 + 62}",
        "nodes": nodes,
        "spine": [[ids[i], ids[i + 1]] for i in range(len(ids) - 1)],
        "curves": [],
    }


def _tn_join(cfg):
    """Port of tnJoin(top, ids, shorts): two inputs at the top feeding a chain."""
    tops, ids, shorts = cfg["tops"], cfg["ids"], cfg.get("shorts") or {}
    nodes = [
        {"id": tops[0]["id"], "cx": 170, "cy": 44, "w": 210, "foreign": bool(tops[0].get("foreign"))},
        {"id": tops[1]["id"], "cx": 490, "cy": 44, "w": 210, "foreign": bool(tops[1].get("foreign"))},
    ]
    for i, aid in enumerate(ids):
        node = {"id": aid, "cx": 330, "cy": 130 + i * 60 + (20 if i == len(ids) - 1 else 0)}
        if aid in shorts:
            node["short"] = shorts[aid]
        nodes.append(node)
    return {
        "viewBox": f"0 0 660 {130 + (len(ids) - 1) * 60 + 62}",
        "nodes": nodes,
        "spine": [[ids[i], ids[i + 1]] for i in range(len(ids) - 1)],
        "curves": ["M170,67 C 170,95 285,100 306,107", "M490,67 C 490,95 375,100 354,107"],
    }


def _build_ir(tn):
    """DATA.ir: the Then-and-Now section of the Data Sources page (group list,
    asset chains, graph layouts, FROM-tags, and source overviews), generated
    from the metric modules' ir declarations with live example values filled
    in from the engine's per-node scalars. Group order is the tree's
    post-order walk (leaves before their branch), matching the page's
    long-standing hand-authored order."""
    from . import registry
    nodes = tn.get("nodes") or {}
    groups, assets, graphs, foreign, infos = [], [], {}, {}, {}
    for entry in registry.ir_entries():
        spec = entry["spec"]
        ir = spec["ir"]
        gid = ir["group"]
        n = nodes.get(spec["key"]) or {}
        ctx = _ir_ctx(tn, n)
        groups.append({"id": gid, "name": ir["group_name"], "status": "live"})
        if "assets" in ir:
            assets += [_ir_fill(a, ctx, n) for a in ir["assets"]]
        elif "leaf_chain" in ir:
            assets += _tn_leaf_chain(_ir_fill(ir["leaf_chain"], ctx, n), spec, gid, tn, n)
        else:
            assets += _tn_rollup(ir["rollup"], spec, gid, tn, n)
        g = ir.get("graph") or {}
        if "vchain" in g:
            graphs[gid] = _tn_vchain(g["vchain"])
        elif "join" in g:
            graphs[gid] = _tn_join(g["join"])
        else:
            graphs[gid] = g["explicit"]
        if ir.get("foreign_from"):
            foreign[gid] = ir["foreign_from"]
        infos[gid] = _ir_fill(ir["source_info"], ctx, n)
    return {"groups": groups, "assets": assets, "graphs": graphs,
            "foreignFrom": foreign, "sourceInfo": infos}


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

    tn = _thennow_example(conn)
    return {
        "updated": db.get_meta(conn, "last_update"),
        "prices": {"columns": _columns(conn, "prices"), "byTicker": by_ticker, "total": prices_total},
        "events": {"columns": _columns(conn, "events"), "total": events_total},
        "example": _example(conn),
        "h100": h100,
        "polymarket": polymarket,
        "bankruptcy": bankruptcy,
        "thennow": tn,
        "ir": _build_ir(tn) if tn else None,
    }


def write_datasources(conn, path=DATASOURCES_PATH):
    payload = json.dumps(build_payload(conn), separators=(",", ":"))
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    path.write_text(template.replace("__DATA__", payload), encoding="utf-8")
    return path
