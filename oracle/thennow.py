"""Then and Now analog engine.

Phase 1 foundation of the universal pipeline (see design/PIPELINE-PLAN.md):

  - a DECLARED Nasdaq cycle clock (start / peak / bottom / ai-start), shared by
    every metric so the parent blend stays coherent;
  - a metric REGISTRY where each leaf declares source + columns + a formula +
    type/direction/unit, so adding a metric is a declaration, not new code;
  - DAILY compute (raw forward-filled to a gap-free daily grid, the metric
    formula applied, a CENTERED N-day mean anchored so intensity=100% lands on
    the declared peak), then per-type normalization to a 0-1 intensity;
  - exact DAILY scalars (today's intensity, the equivalent dot-com date, the
    projected peak) plus a WEEKLY-downsampled series for the plot, carrying the
    metric's NATIVE value all the way down for look-through on hover/CSV.

The projected date is a transparent analog, not a forecast.
"""

import hashlib
import json
from datetime import date, datetime, timedelta, timezone

from . import db
from .config import PROJECT_DIR

OBS_PATH = PROJECT_DIR / "data" / "thennow_observations.json"

# ---------------------------------------------------------------- declared clock
CLOCK = {
    "start": "1995-08-09", "startEvent": "Netscape IPO",
    "peak": "2000-03-10",                                   # Nasdaq intraday top
    "bottom": "2002-10-09",                                 # dot-com low
    "aiStart": "2022-11-30", "aiStartEvent": "ChatGPT launch",
}
PHASES = ["Early Ramp", "Acceleration", "Late Bubble", "Crash & Bottom", "Recovery"]
PHASE_BOUNDS = [0, 35, 85, 100, 160]
SMOOTH_DAYS = 90          # centered window, default "3-month" (Phase 4 adds 30-day)


def _d(s):
    return date.fromisoformat(s)


def _days(a, b):
    return (_d(b) - _d(a)).days


def _today():
    return datetime.now(timezone.utc).date()


RAMP = _days(CLOCK["start"], CLOCK["peak"])   # days from cycle start to the peak


# ---------------------------------------------------------------- metric registry
# formula: maps a raw row (the declared columns) to the metric's input value; it
# MAY combine fields (a ratio, a spread). `type` then governs normalization.
PRICE = {
    "kind": "price", "source": ("prices", "^IXIC"), "columns": ["close"],
    "formula": lambda r: r["close"], "cadence": "daily",
    "type": "ratio_from_start", "direction": "up", "unit": "nasdaq_close",
    "unitLabel": "Nasdaq",
}
SP500 = {
    "kind": "sp500", "source": ("prices", "^GSPC"), "columns": ["close"],
    "formula": lambda r: r["close"], "cadence": "daily",
    "type": "ratio_from_start", "direction": "up", "unit": "sp500_close",
    "unitLabel": "S&P 500",
}
CAPE = {
    "kind": "cape", "source": ("cape", None), "columns": ["cape"],
    "formula": lambda r: r["cape"], "cadence": "monthly",
    "type": "absolute_level", "direction": "up", "unit": "shiller_cape",
    "unitLabel": "CAPE",
}

THENNOW_TREE = {
    "key": "ai_peak", "label": "AI bubble bursts", "children": [
        {"key": "valuation", "label": "Valuation", "children": [
            # Price appreciation is now a sub-blend of two indices (Phase 3), so no
            # single index carries the whole "price" argument on its own.
            {"key": "price_appreciation", "label": "Price appreciation", "children": [
                {"key": "nasdaq", "label": "Nasdaq", "metric": PRICE},
                {"key": "sp500", "label": "S&P 500", "metric": SP500},
            ]},
            {"key": "valuation_multiple", "label": "Valuation multiple", "metric": CAPE},
        ]},
        {"key": "market_concentration", "label": "Market concentration", "wip": True},
        {"key": "capex", "label": "Infrastructure / capex", "wip": True},
        {"key": "speculation", "label": "Speculative activity", "wip": True},
    ],
}


# ------------------------------------------------------------------ grid + fills
def _grid(start_iso, end_iso):
    """Contiguous calendar-daily ISO dates from start through end inclusive."""
    d0, d1 = _d(start_iso), _d(end_iso)
    return [(d0 + timedelta(days=i)).isoformat() for i in range((d1 - d0).days + 1)]


def _load_metric(conn, metric):
    """Return sorted [(date_iso, value)] with the metric's formula applied."""
    src, arg = metric["source"]
    if src == "prices":
        rows = db.load_prices(conn, arg)
    elif src == "cape":
        rows = db.load_cape(conn)
    else:
        return []
    f = metric["formula"]
    out = []
    for r in rows:
        try:
            v = f(r)
        except (KeyError, TypeError, ZeroDivisionError):
            v = None
        if v is not None:
            out.append((r["date"], float(v)))
    out.sort()
    return out


def _fill(pairs, grid_dates):
    """Forward-fill values onto a daily grid: markets don't move on weekends /
    holidays, so the last known value persists (no invented intra-gap motion).
    Leading days before the first observation carry the earliest prior value, or
    None if the series does not reach the grid start."""
    bym = {dt: v for dt, v in pairs}
    g0 = grid_dates[0]
    prior = [v for dt, v in pairs if dt <= g0]
    cur = prior[-1] if prior else None
    out = []
    for iso in grid_dates:
        if iso in bym:
            cur = bym[iso]
        out.append(cur)
    return out


def _smooth_centered(vals, window_days):
    """Centered simple moving average with edge truncation (min-periods): interior
    points are centered; the leading edge (today) necessarily uses only trailing
    data, since there is no future to average in."""
    half = window_days // 2
    n = len(vals)
    out = []
    for i in range(n):
        seg = [v for v in vals[max(0, i - half):min(n, i + half + 1)] if v is not None]
        out.append(sum(seg) / len(seg) if seg else None)
    return out


# ---------------------------------------------------------------- normalization
def _normalize(sm_dot, sm_ai, type_):
    """Map smoothed native values to 0-1 intensity over the dot-com range, with
    intensity = 1 anchored to the value AT the declared peak (so the reference
    line crests on the peak marker). ratio_from_start indexes each era to its own
    start; absolute_level compares levels on the dot-com anchors."""
    start_dot = sm_dot[0]
    peak_dot = sm_dot[RAMP]                              # value at the declared peak date
    if type_ == "ratio_from_start":
        peak_mult = peak_dot / start_dot
        denom = (peak_mult - 1) or 1e-9
        int_dot = [((v / start_dot) - 1) / denom if v is not None else None for v in sm_dot]
        start_ai = sm_ai[0]
        int_ai = [((v / start_ai) - 1) / denom if v is not None else None for v in sm_ai]
    else:  # absolute_level
        denom = (peak_dot - start_dot) or 1e-9
        int_dot = [(v - start_dot) / denom if v is not None else None for v in sm_dot]
        int_ai = [(v - start_dot) / denom if v is not None else None for v in sm_ai]
    return int_dot, int_ai


# --------------------------------------------------------------- match + project
def _phase_of(progress):
    label = PHASES[0]
    for i, edge in enumerate(PHASE_BOUNDS):
        if progress >= edge:
            label = PHASES[i]
    return label


def _match(target, int_dot):
    """First upward crossing of `target` on the dot-com ramp (progress<=100),
    returned as a progress %. Earliest crossing wins if the ramp is non-monotone."""
    lim = min(len(int_dot) - 1, RAMP)
    if target <= (int_dot[0] or 0):
        return 0.0
    for i in range(1, lim + 1):
        v0, v1 = int_dot[i - 1], int_dot[i]
        if v0 is None or v1 is None or v1 == v0:
            continue
        if (v0 - target) * (v1 - target) <= 0:
            f = (target - v0) / (v1 - v0)
            return (i - 1 + f) / RAMP * 100.0
    return lim / RAMP * 100.0


def _evaluate(int_dot, int_ai, today):
    """Analog + projection on a node's daily curves (scalars, exact daily)."""
    ai_now = next((v for v in reversed(int_ai) if v is not None), 0.0)
    eq = _match(ai_now, int_dot)
    equiv_date = date.fromordinal(_d(CLOCK["start"]).toordinal() + round(eq / 100 * RAMP))
    ai_elapsed = _days(CLOCK["aiStart"], today.isoformat())
    dot_done = max(eq, 0.0) / 100 * RAMP
    ratio = ai_elapsed / dot_done if dot_done > 0 else 1.0
    dot_left = max(100.0 - eq, 0.0) / 100 * RAMP
    proj = date.fromordinal(today.toordinal() + round(ratio * dot_left))
    ramp_max = max((v for v in int_dot[:min(len(int_dot), RAMP + 1)] if v is not None), default=1.0)
    return {
        "intensityNow": round(ai_now, 4),
        "equiv": {"progress": round(eq, 2), "intensity": round(ai_now, 4)},
        "equivalentDotcomDate": equiv_date.isoformat(),
        "daysFromPeak": (equiv_date - _d(CLOCK["peak"])).days,
        "compression": round(ratio, 2),
        "projectedPeakDate": proj.isoformat(),
        "phase": _phase_of(eq),
        "beyondDotcomPeak": ai_now > ramp_max,
    }


# ------------------------------------------------------------------- validation
# Two passes over a leaf's daily curves. CANDIDACY: does the metric even span both
# eras with real dynamic range? SHAPE: does the reference era actually rise, peak,
# and fall, and is AI below that peak and moving toward it? The verdict and numbers
# are computed here and are authoritative; observations layer cached prose on top.
def _first(a):
    return next((v for v in a if v is not None), None)


def _last_val(a):
    return next((v for v in reversed(a) if v is not None), None)


def _validate(sm_dot, sm_ai, int_dot, int_ai, direction):
    up = direction != "down"
    checks = []

    def add(name, ok, detail):
        checks.append({"name": name, "pass": bool(ok), "detail": detail})

    start_dot, peak_dot = sm_dot[0], sm_dot[RAMP]
    # pass 1 — candidacy
    covers = _first(sm_dot) is not None and _first(sm_ai) is not None
    add("covers both eras", covers,
        "real data at both era starts" if covers else "missing one era's start")
    rng = abs(peak_dot - start_dot) / abs(start_dot) if start_dot else 0.0
    add("dynamic range", rng >= 0.2, f"dot-com moved {rng * 100:.0f}% from start to peak")

    # pass 2 — shape (after smoothing)
    seq = [v for v in sm_dot if v is not None]
    n = len(seq)
    ext_i = (max(range(n), key=lambda i: seq[i]) if up
             else min(range(n), key=lambda i: seq[i])) if n else 0
    interior = bool(n) and 0.15 * n < ext_i < 0.9 * n
    reverses = bool(n) and ((seq[-1] < seq[ext_i] * 0.92) if up else (seq[-1] > seq[ext_i] * 1.08))
    add("rise, peak, fall", interior and reverses,
        f"peaks near {ext_i / RAMP * 100:.0f}% then reverses" if interior and reverses
        else "no clear interior peak in the reference era")
    ai_now = _last_val(int_ai) or 0.0
    add("AI below the peak", ai_now < 1.02, f"AI at {ai_now * 100:.0f}% of the dot-com peak")
    ai_start = _first(int_ai) or 0.0
    rising = (ai_now > ai_start) if up else (ai_now < ai_start)
    add("AI moving toward the peak", rising,
        "AI has risen over its era" if rising else "AI is flat or moving away from the peak")

    # AI's current level crossed on the dot-com ramp (informational, not gating)
    lim = min(len(int_dot) - 1, RAMP)
    crossings = 0
    for i in range(1, lim + 1):
        v0, v1 = int_dot[i - 1], int_dot[i]
        if v0 is None or v1 is None:
            continue
        if (v0 - ai_now) * (v1 - ai_now) < 0:
            crossings += 1
    return {"valid": all(c["pass"] for c in checks), "checks": checks, "crossings": crossings}


# ------------------------------------------------------------------- observations
def _load_obs_cache():
    try:
        return json.loads(OBS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def obs_hash(node):
    """Stable signature of a node's qualitative state: verdict, phase, intensity
    bucketed to 5%, and the check pass/fail pattern. Daily wiggles don't move it, so
    the cached Haiku prose regenerates only on a real shift (rare, hence committable)."""
    checks = "".join("1" if c["pass"] else "0"
                     for c in (node.get("validation") or {}).get("checks", []))
    sig = (f"{node.get('valid')}|{node.get('phase')}|"
           f"{round((node.get('intensityNow') or 0) * 20)}|{checks}")
    return hashlib.md5(sig.encode()).hexdigest()[:12]


def obs_fallback(node):
    """Deterministic observation from the computed checks, used when no cached LLM
    prose matches (no API key, or the state shifted since the last refresh)."""
    v = node.get("validation") or {}
    eqp = (node.get("equiv") or {}).get("progress", 0) or 0
    if node.get("valid"):
        if node.get("children"):
            n = sum(1 for c in node["children"] if not c.get("wip") and c.get("valid", True))
            head = f"{node['label']} blends {n} conforming input{'s' if n != 1 else ''}"
        else:
            head = f"{node['label']}: {node.get('display', '')}"
        return (f"{head}, matching the dot-com path near {eqp:.0f}% of the way to the peak "
                f"({node.get('phase', '')}); it projects a top around {node.get('projectedPeakDate', '')}.")
    fail = next((c for c in v.get("checks", []) if not c["pass"]), None)
    tail = f" ({fail['detail']})" if fail else ""
    return (f"{node['label']} does not fit the rise-peak-fall analog{tail}; "
            "it is shown for context and its projection is suppressed.")


def _attach_observations(node, cache):
    if not node.get("wip"):
        h = obs_hash(node)
        node["obsHash"] = h
        entry = cache.get(node["key"])
        node["observations"] = (entry["text"] if entry and entry.get("hash") == h
                                else obs_fallback(node))
    for c in node.get("children", []):
        _attach_observations(c, cache)


def _blend(arrays):
    """Equal-weight pointwise mean of daily intensity curves."""
    n = len(arrays[0])
    out = []
    for i in range(n):
        vals = [a[i] for a in arrays if i < len(a) and a[i] is not None]
        out.append(sum(vals) / len(vals) if vals else None)
    return out


# ------------------------------------------------------------------- build tree
def _build_leaf(conn, node, dot_dates, ai_dates, today):
    m = node["metric"]
    pairs = _load_metric(conn, m)
    if not pairs:
        return None
    raw_dot = _fill(pairs, dot_dates)
    raw_ai = _fill(pairs, ai_dates)
    if raw_dot[0] is None or raw_ai[0] is None:
        return None                                   # no coverage (validator refines later)
    sm_dot = _smooth_centered(raw_dot, SMOOTH_DAYS)
    sm_ai = _smooth_centered(raw_ai, SMOOTH_DAYS)
    int_dot, int_ai = _normalize(sm_dot, sm_ai, m["type"])
    result = _evaluate(int_dot, int_ai, today)
    validation = _validate(sm_dot, sm_ai, int_dot, int_ai, m["direction"])

    if m["type"] == "ratio_from_start":
        ai_mult = sm_ai[-1] / sm_ai[0]
        peak_mult = sm_dot[RAMP] / sm_dot[0]
        name = node["label"]
        display = f"up {ai_mult:.1f}x since ChatGPT"
        different = (f"{name} is up about {ai_mult:.1f}x since ChatGPT against roughly "
                     f"{peak_mult:.1f}x for the same index into 2000, so on price alone it "
                     "reads earlier and less stretched than the dot-com run.")
    else:
        display = f"CAPE {sm_ai[-1]:.0f}"
        different = (f"CAPE is about {sm_ai[-1]:.0f} now against roughly {sm_dot[RAMP]:.0f} at "
                     "the 2000 peak, so on valuation multiple AI is already close to dot-com's top.")

    return {"key": node["key"], "label": node["label"], "leaf": m["kind"], "unit": m["unit"],
            "unitLabel": m["unitLabel"], "type": m["type"], "display": display, "different": different,
            "valid": validation["valid"], "validation": validation,
            "_intDot": int_dot, "_intAi": int_ai, "_smDot": sm_dot, "_smAi": sm_ai,
            "_rawDot": raw_dot, "_rawAi": raw_ai, **result}


def _build(conn, node, dot_dates, ai_dates, today):
    if node.get("wip"):
        return {"key": node["key"], "label": node["label"], "wip": True}
    if "metric" in node:
        return _build_leaf(conn, node, dot_dates, ai_dates, today)
    kids = [_build(conn, c, dot_dates, ai_dates, today) for c in node["children"]]
    live = [k for k in kids if k and not k.get("wip")]
    placeholders = [k for k in kids if k and k.get("wip")]
    if not live:
        return None
    # A parent blends only its CONFORMING inputs, so a non-conforming child is shown
    # but never drags the roll-up's projection. If none conform, fall back to the
    # full set for a curve but mark the parent invalid (projection suppressed too).
    valid_live = [k for k in live if k.get("valid", True)]
    use = valid_live or live
    int_dot = _blend([k["_intDot"] for k in use])
    int_ai = _blend([k["_intAi"] for k in use])
    result = _evaluate(int_dot, int_ai, today)
    valid = len(valid_live) > 0
    validation = {"valid": valid, "crossings": 0, "checks": [
        {"name": "conforming inputs", "pass": valid,
         "detail": f"{len(valid_live)} of {len(live)} inputs fit the analog"}]}
    return {"key": node["key"], "label": node["label"], "display": "blended",
            "valid": valid, "validation": validation,
            "children": live + placeholders, "_intDot": int_dot, "_intAi": int_ai, **result}


# ---------------------------------------------------------------- weekly downsample
def _weekly_idx(n):
    idx = list(range(0, n, 7))
    if not idx or idx[-1] != n - 1:
        idx.append(n - 1)
    return idx


def _pick(arr, idx, nd=4):
    return [round(arr[i], nd) if arr[i] is not None else None for i in idx]


def _emit(node, dw, aw):
    """Recursively build the weekly payload node (arrays downsampled to weekly)."""
    if node.get("wip"):
        return {"key": node["key"], "label": node["label"], "wip": True}
    out = {"key": node["key"], "label": node["label"], "display": node["display"],
           "valid": node.get("valid", True), "validation": node.get("validation"),
           "intensityDot": _pick(node["_intDot"], dw), "intensityAi": _pick(node["_intAi"], aw)}
    for k in ("intensityNow", "equiv", "equivalentDotcomDate", "daysFromPeak",
              "compression", "projectedPeakDate", "phase", "beyondDotcomPeak"):
        out[k] = node[k]
    if "leaf" in node:
        out["leaf"] = node["leaf"]; out["unit"] = node["unit"]; out["unitLabel"] = node["unitLabel"]
        out["type"] = node["type"]; out["different"] = node["different"]
        out["smoothedDot"] = _pick(node["_smDot"], dw, 2); out["smoothedAi"] = _pick(node["_smAi"], aw, 2)
        out["rawDot"] = _pick(node["_rawDot"], dw, 2); out["rawAi"] = _pick(node["_rawAi"], aw, 2)
    if "children" in node:
        out["children"] = [_emit(c, dw, aw) for c in node["children"]]
    return out


def _leaf_dates(node, acc):
    # Only conforming leaves contribute to the headline band; a non-conforming
    # metric's projection is suppressed, so it must not widen the range either.
    if node.get("leaf") and node.get("valid", True):
        acc.append(node["projectedPeakDate"])
    for c in node.get("children", []):
        _leaf_dates(c, acc)


# --------------------------------------------------------------------- assemble
def compute_thennow(conn):
    today = _today()
    dot_dates = _grid(CLOCK["start"], CLOCK["bottom"])
    ai_dates = _grid(CLOCK["aiStart"], today.isoformat())
    root = _build(conn, THENNOW_TREE, dot_dates, ai_dates, today)
    if not root:
        return None

    dw, aw = _weekly_idx(len(dot_dates)), _weekly_idx(len(ai_dates))
    prog_dot = [round(i / RAMP * 100, 2) for i in dw]
    prog_ai = [round(i / RAMP * 100, 2) for i in aw]
    peak_idx = min(range(len(dw)), key=lambda k: abs(dw[k] - RAMP))
    tree = _emit(root, dw, aw)
    _attach_observations(tree, _load_obs_cache())

    dates = []
    _leaf_dates(tree, dates)
    dates.sort()

    return {
        "updated": db.get_meta(conn, "last_update"),
        "asOf": today.isoformat(),
        "ramp": RAMP,
        "dotcomStart": CLOCK["start"], "dotcomStartEvent": CLOCK["startEvent"],
        "dotcomPeak": CLOCK["peak"], "aiStart": CLOCK["aiStart"], "aiStartEvent": CLOCK["aiStartEvent"],
        "phases": PHASES, "phaseBounds": PHASE_BOUNDS, "peakIdx": peak_idx,
        "progDot": prog_dot, "progAi": prog_ai,
        "dotMonths": [dot_dates[i] for i in dw], "aiMonths": [ai_dates[i] for i in aw],
        "headlineDate": tree["projectedPeakDate"],
        "bandLow": dates[0] if dates else tree["projectedPeakDate"],
        "bandHigh": dates[-1] if dates else tree["projectedPeakDate"],
        "tree": tree,
    }
