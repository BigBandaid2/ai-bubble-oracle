"""Then and Now: the dot-com vs AI-boom analog engine, as a roll-up tree.

The section mirrors the dashboard's contract tree. Every node, leaf or parent,
produces exactly one graph and one conclusion date. A parent is NOT an overlay
of its children: it combines their curves with weights (equal by default,
adjustable) into a single curve, then the same alignment + projection runs on
that combined curve to give the parent's own date. Uniform at every level.

    ai_peak  (root: one date)
    └─ valuation
       ├─ price_appreciation   (Nasdaq indexed, "how far it has run")
       └─ valuation_multiple   (Shiller CAPE, "how expensive")
    market_concentration / capex / speculation   (WIP branches)

The common currency that makes the roll-up work is a unitless 0..1 INTENSITY:
0 = the dot-com era's starting level, 1 = its 2000 peak. Each leaf maps its own
data onto that scale in a metric-appropriate way (price by appreciation from
its own start; CAPE by absolute level on the dot-com range, since a P/E means
the same thing in any era). Parents weight-average children's intensities.

Method, stated plainly so a reader can disagree with the inputs:
  1. Each leaf -> a monthly, smoothed value series per era.
  2. Values -> 0..1 intensity (0 dot-com start, 1 dot-com peak).
  3. Parents -> weighted average of children's intensity curves.
  4. For any node, find the dot-com date whose intensity matches today's AI
     intensity (the equivalent point), read its phase and days-from-peak.
  5. Rate-scale the remaining distance by AI's pace vs dot-com's so far,
     giving a projected peak (burst) date. The root's date is the headline;
     the spread of the leaf dates is the visible uncertainty band.

The date is a deliberate hook over a transparent method, not a forecast.
"""

from datetime import date, datetime, timezone

from . import db

# Both eras are anchored on a single defining launch event, so the origins are
# comparable: Netscape's IPO (1995-08-09) opened the dot-com boom the way
# ChatGPT (2022-11-30) opened the AI boom. The peak is not hard-coded; it is
# read from the data (the month the smoothed Nasdaq tops out), see _peak_month.
DOTCOM = {"start": "1995-08-01", "peak": "2000-03-01", "end": "2002-10-01",
          "startEvent": "Netscape IPO"}
AI = {"start": "2022-11-01", "startEvent": "ChatGPT launch"}
PHASES = ["Early Ramp", "Acceleration", "Late Bubble", "Crash & Bottom", "Recovery"]
# Progress-% band edges, calibrated to the dot-com narrative on the Netscape->peak
# clock: Early Ramp through ~1997 (0-35), Acceleration 1998-99 (35-85), the
# blow-off Late Bubble into the 2000 peak (85-100), Crash & Bottom to the 2002
# low (100-160), Recovery to new highs beyond the window (>=160). Editorial and
# tunable; they set phase labels, not the projected date.
PHASE_BOUNDS = [0, 35, 85, 100, 160]
SMOOTH_MONTHS = 3
NASDAQ = "^IXIC"

# The roll-up tree. Leaves name a data builder; parents combine children.
THENNOW_TREE = {
    "key": "ai_peak", "label": "AI bubble bursts",
    "children": [
        {"key": "valuation", "label": "Valuation", "children": [
            {"key": "price_appreciation", "label": "Price appreciation", "leaf": "price"},
            {"key": "valuation_multiple", "label": "Valuation multiple", "leaf": "cape"},
        ]},
        {"key": "market_concentration", "label": "Market concentration", "wip": True},
        {"key": "capex", "label": "Infrastructure / capex", "wip": True},
        {"key": "speculation", "label": "Speculative activity", "wip": True},
    ],
}


# ---------------------------------------------------------------- date helpers
def _today():
    return datetime.now(timezone.utc).date()


def _d(s):
    return date.fromisoformat(s)


def _days(a, b):
    return (_d(b) - _d(a)).days


def _add_days(iso, n):
    return (_d(iso).toordinal() + n)


def _month_starts(start, end):
    """First-of-month iso dates from the start month through the end month."""
    y, m = int(start[:4]), int(start[5:7])
    ey, em = int(end[:4]), int(end[5:7])
    out = []
    while (y, m) <= (ey, em):
        out.append(f"{y:04d}-{m:02d}-01")
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


# -------------------------------------------------------------- series helpers
def _slice(pairs, start, end):
    return [(d, v) for d, v in pairs if start <= d <= end]


def _by_month(pairs):
    """Last observation per calendar month, keyed 'YYYY-MM'."""
    out = {}
    for d, v in pairs:
        out[d[:7]] = v
    return out


def _on_months(pairs, months):
    """Sample a (date,value) series onto a list of month-start dates, linearly
    interpolating gaps and clipping at the ends. Returns [value] aligned to
    `months` (None only if the series is empty)."""
    bm = _by_month(pairs)
    keys = sorted(bm)
    if not keys:
        return [None] * len(months)
    kv = [(k, bm[k]) for k in keys]
    out = []
    for mo in months:
        key = mo[:7]
        if key in bm:
            out.append(bm[key])
            continue
        # interpolate/clip against the surrounding known months
        before = [x for x in kv if x[0] <= key]
        after = [x for x in kv if x[0] >= key]
        if not before:
            out.append(after[0][1])
        elif not after:
            out.append(before[-1][1])
        else:
            (k0, v0), (k1, v1) = before[-1], after[0]
            if k0 == k1:
                out.append(v0)
            else:
                f = (_ym_ord(key) - _ym_ord(k0)) / (_ym_ord(k1) - _ym_ord(k0))
                out.append(v0 + f * (v1 - v0))
    return out


def _ym_ord(ym):
    return int(ym[:4]) * 12 + int(ym[5:7])


def _smooth(values, window):
    if window <= 1:
        return list(values)
    half = window // 2
    out = []
    for i in range(len(values)):
        seg = [v for v in values[max(0, i - half):i + half + 1] if v is not None]
        out.append(sum(seg) / len(seg) if seg else None)
    return out


def _phase_of(progress):
    label = PHASES[0]
    for i, edge in enumerate(PHASE_BOUNDS):
        if progress >= edge:
            label = PHASES[i]
    return label


# ---------------------------------------------------------------- axes (shared)
def _peak_month(conn):
    """The cycle peak = the month the smoothed Nasdaq tops out. Reading it from
    the data (not hard-coding 2000-03) means the grey line's high sits exactly
    at progress 100, where the peak marker is drawn."""
    rows = db.load_prices(conn, NASDAQ)
    pairs = sorted((r["date"], r["close"]) for r in rows if r["close"] is not None)
    months = _month_starts(DOTCOM["start"], DOTCOM["end"])
    vals = _smooth(_on_months(pairs, months), SMOOTH_MONTHS)
    best = max(range(len(vals)), key=lambda i: (vals[i] if vals[i] is not None else float("-inf")))
    return months[best]


def _axes(today, peak):
    """Shared canonical month lists + progress arrays for both eras. Every leaf
    and every combined node lives on these, so weighting is a pointwise average.
    progress = days since the era start / days(start -> peak) * 100."""
    ramp = _days(DOTCOM["start"], peak)
    dot_months = _month_starts(DOTCOM["start"], DOTCOM["end"])
    ai_months = _month_starts(AI["start"], today.isoformat())
    prog_dot = [round(_days(DOTCOM["start"], m) / ramp * 100.0, 2) for m in dot_months]
    prog_ai = [round(_days(AI["start"], m) / ramp * 100.0, 2) for m in ai_months]
    return {"dotMonths": dot_months, "aiMonths": ai_months, "peakDate": peak,
            "progDot": prog_dot, "progAi": prog_ai,
            "peakIdx": dot_months.index(peak), "ramp": ramp}


# ------------------------------------------------------------------ leaf curves
def _leaf_raw(conn, kind, ax):
    """Return raw (monthly) and smoothed value series for both eras, aligned to
    the canonical months. `unit` names what the raw number is."""
    if kind == "price":
        rows = db.load_prices(conn, NASDAQ)
        pairs = sorted((r["date"], r["close"]) for r in rows if r["close"] is not None)
        unit = "nasdaq_close"
    elif kind == "cape":
        rows = db.load_cape(conn)
        pairs = sorted((r["date"], r["cape"]) for r in rows)
        unit = "shiller_cape"
    else:
        return None
    if not pairs:
        return None
    raw_dot = _on_months(pairs, ax["dotMonths"])
    raw_ai = _on_months(pairs, ax["aiMonths"])
    return {"unit": unit, "rawDot": raw_dot, "smoothedDot": _smooth(raw_dot, SMOOTH_MONTHS),
            "rawAi": raw_ai, "smoothedAi": _smooth(raw_ai, SMOOTH_MONTHS)}


def _r2(seq):
    return [round(v, 2) if v is not None else None for v in seq]


def _leaf_curves(conn, node, ax):
    """Compute a leaf's 0..1 intensity curves, the raw/smoothed series behind
    them (for inspection/download), and a human display of 'now'."""
    kind = node["leaf"]
    mode = "relative" if kind == "price" else "absolute"
    lr = _leaf_raw(conn, kind, ax)
    if not lr or lr["smoothedDot"][0] is None or lr["smoothedAi"][0] is None:
        return None
    dot, ai = lr["smoothedDot"], lr["smoothedAi"]
    dot_start, dot_peak = dot[0], dot[ax["peakIdx"]]
    span = dot_peak - dot_start or 1.0
    dot_int = [round((v - dot_start) / span, 4) if v is not None else None for v in dot]
    if mode == "relative":
        ai_start = ai[0]
        peak_mult = dot_peak / dot_start
        ai_int = [round(((v / ai_start) - 1) / ((peak_mult - 1) or 1), 4)
                  if v is not None else None for v in ai]
        ai_mult = ai[-1] / ai_start
        display = f"up {ai_mult:.1f}x since ChatGPT"
        similar = "Both cycles are led by a single tech-heavy index climbing above trend."
        different = (f"Up about {ai_mult:.1f}x since ChatGPT vs roughly "
                     f"{dot_peak / dot_start:.1f}x for the dot-com Nasdaq into 2000, "
                     "so on price alone AI reads earlier and less stretched.")
    else:
        ai_int = [round((v - dot_start) / span, 4) if v is not None else None for v in ai]
        display = f"CAPE {ai[-1]:.0f}"
        similar = "Rich broad-market valuations in both booms, driven by the tech leaders."
        different = (f"CAPE is about {ai[-1]:.0f} now against roughly {dot_peak:.0f} at the "
                     "2000 peak, so on valuation multiple AI is already close to dot-com's top.")
    return {"intensityDot": dot_int, "intensityAi": ai_int,
            "unit": lr["unit"],
            "rawDot": _r2(lr["rawDot"]), "smoothedDot": _r2(dot),
            "rawAi": _r2(lr["rawAi"]), "smoothedAi": _r2(ai),
            "display": display, "similar": similar, "different": different}


# --------------------------------------------------------------- node evaluate
def _match(target, prog, inten):
    """First point on the ramp (progress<=100) where intensity crosses target;
    returns interpolated progress. Clips below the first / above the peak."""
    ramp = [(p, v) for p, v in zip(prog, inten) if v is not None and p <= 100.0]
    if not ramp:
        return {"progress": 0.0, "beyond": False}
    if target >= ramp[-1][1]:
        return {"progress": ramp[-1][0], "beyond": target > ramp[-1][1]}
    if target <= ramp[0][1]:
        return {"progress": ramp[0][0], "beyond": False}
    for (p0, v0), (p1, v1) in zip(ramp, ramp[1:]):
        if v1 == v0:
            continue
        if (v0 - target) * (v1 - target) <= 0:
            f = (target - v0) / (v1 - v0)
            return {"progress": p0 + f * (p1 - p0), "beyond": False}
    return {"progress": ramp[-1][0], "beyond": False}


def _evaluate(intensity_dot, intensity_ai, ax, today):
    """Run the analog + projection on one node's combined curves."""
    ai_now = next((v for v in reversed(intensity_ai) if v is not None), 0.0)
    m = _match(ai_now, ax["progDot"], intensity_dot)
    equiv_prog = m["progress"]
    ramp = ax["ramp"]
    equiv_date = date.fromordinal(_add_days(DOTCOM["start"], round(equiv_prog / 100.0 * ramp)))
    days_from_peak = (equiv_date - _d(ax["peakDate"])).days
    # rate-scale the remaining distance to the peak
    ai_elapsed = _days(AI["start"], today.isoformat())
    dot_days_done = max(equiv_prog, 0.0) / 100.0 * ramp
    ratio = ai_elapsed / dot_days_done if dot_days_done > 0 else 1.0
    dot_days_left = max(100.0 - equiv_prog, 0.0) / 100.0 * ramp
    proj = date.fromordinal(today.toordinal() + round(ratio * dot_days_left))
    ai_now_prog = ax["progAi"][-1]
    return {
        "intensityNow": round(ai_now, 3),
        "equivalentDotcomDate": equiv_date.isoformat(),
        "phase": _phase_of(equiv_prog),
        "daysFromPeak": days_from_peak,
        "compression": round(ratio, 2),
        "projectedPeakDate": proj.isoformat(),
        "beyondDotcomPeak": m["beyond"],
        "equiv": {"progress": round(equiv_prog, 1), "intensity": round(ai_now, 3),
                  "date": equiv_date.isoformat()},
        "aiNow": {"progress": round(ai_now_prog, 1), "intensity": round(ai_now, 3)},
    }


def _combine(children, weights):
    """Weighted-average the children's intensity curves (pointwise)."""
    def blend(arrays):
        n = len(arrays[0])
        out = []
        for i in range(n):
            num, den = 0.0, 0.0
            for w, arr in zip(weights, arrays):
                if i < len(arr) and arr[i] is not None:
                    num += w * arr[i]
                    den += w
            out.append(round(num / den, 4) if den else None)
        return out
    return (blend([c["intensityDot"] for c in children]),
            blend([c["intensityAi"] for c in children]))


# ------------------------------------------------------------------ build tree
def _build(conn, node, ax, today):
    """Return a fully-evaluated node dict (recursive), or None if it has no data."""
    if node.get("wip"):
        return {"key": node["key"], "label": node["label"], "wip": True}

    if "leaf" in node:
        curves = _leaf_curves(conn, node, ax)
        if not curves:
            return None
        result = _evaluate(curves["intensityDot"], curves["intensityAi"], ax, today)
        return {"key": node["key"], "label": node["label"], "leaf": node["leaf"],
                **curves, **result}

    kids = [_build(conn, c, ax, today) for c in node["children"]]
    live = [k for k in kids if k and not k.get("wip")]
    placeholders = [k for k in kids if k and k.get("wip")]
    if not live:
        return None
    weights = [1.0] * len(live)   # equal by default; the page lets you adjust
    idot, iai = _combine(live, weights)
    result = _evaluate(idot, iai, ax, today)
    return {"key": node["key"], "label": node["label"],
            "intensityDot": idot, "intensityAi": iai,
            "weights": weights, "display": "blended",
            "children": live + placeholders, **result}


def _leaf_dates(node, acc):
    if node.get("wip"):
        return
    if "leaf" in node:
        acc.append(node["projectedPeakDate"])
    for c in node.get("children", []):
        _leaf_dates(c, acc)


# --------------------------------------------------------------------- assemble
def compute_thennow(conn):
    today = _today()
    ax = _axes(today, _peak_month(conn))
    root = _build(conn, THENNOW_TREE, ax, today)
    if not root:
        return None
    leaf_dates = []
    _leaf_dates(root, leaf_dates)
    band_low = min(leaf_dates) if leaf_dates else root["projectedPeakDate"]
    band_high = max(leaf_dates) if leaf_dates else root["projectedPeakDate"]
    return {
        "headlineDate": root["projectedPeakDate"],
        "bandLow": band_low, "bandHigh": band_high,
        "dotcomStart": DOTCOM["start"], "dotcomStartEvent": DOTCOM["startEvent"],
        "dotcomPeak": ax["peakDate"], "aiStart": AI["start"],
        "aiStartEvent": AI["startEvent"], "ramp": ax["ramp"], "asOf": today.isoformat(),
        "phases": PHASES, "phaseBounds": PHASE_BOUNDS,
        "progDot": ax["progDot"], "progAi": ax["progAi"], "peakIdx": ax["peakIdx"],
        "dotMonths": ax["dotMonths"], "aiMonths": ax["aiMonths"],
        "tree": root,
        "assumptions": [
            "The dot-com bubble is a fair analog: an infrastructure-led tech cycle, "
            "narrow leadership, heavy retail speculation, one defining index.",
            "Cycle anchors are chosen: dot-com runs 1995 to its 2000-03 peak to the "
            "2002-10 bottom; the AI cycle starts at the 2022-11 ChatGPT release.",
            "Each metric becomes a 0-1 intensity: 0 at the dot-com starting level, "
            "1 at the 2000 peak. Parents weight-average their children (equal by "
            "default, adjustable).",
        ],
        "limitations": [
            "The date is a bold hook over a transparent method, not a forecast. "
            "Change the weights or anchors and it moves.",
            "Price appreciation and valuation multiple tell different stories on "
            "purpose: price reads early, CAPE reads late. The parent is where they "
            "reconcile.",
            "Small sample: one prior cycle. The band is the spread of the leaf "
            "dates, the honest uncertainty.",
            "Concentration, capex and speculation are not wired yet, so today the "
            "headline reflects Valuation only.",
        ],
    }
