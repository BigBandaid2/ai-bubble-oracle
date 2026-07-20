"""Then and Now analogy engine.

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

The projected date is a transparent analogy, not a forecast.
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
SMOOTH_WINDOWS = {"90": 90, "30": 30}   # centered-mean windows, materialized as permutations
DEFAULT_SMOOTH = "90"                   # the "3-month" default; "30" is the "1-month" alternative
SMOOTH_DAYS = SMOOTH_WINDOWS[DEFAULT_SMOOTH]


def _d(s):
    return date.fromisoformat(s)


def _days(a, b):
    return (_d(b) - _d(a)).days


def _today():
    return datetime.now(timezone.utc).date()


RAMP = _days(CLOCK["start"], CLOCK["peak"])   # days from cycle start to the peak
# The declared 2002 low as a progress % (past 100%), a pure clock constant. It places
# the projected-bottom marker and scales each metric's projected bottom by its pace.
BOTTOM_PROG = _days(CLOCK["start"], CLOCK["bottom"]) / RAMP * 100.0

# The dot-com start anchor is the model's single biggest assumption. Two declared
# choices: the Netscape IPO (default; the popular "birth of the dot-com era") and
# Greenspan's "irrational exuberance" speech 16 months later, the first time a
# sitting Fed chair called the market overvalued. The later anchor shortens the
# reference climb (~1675d -> ~1191d), which lifts AI's normalized intensity against
# a shorter yardstick and (net) tightens the projection band, pulling the far-future
# speculative tail in. It re-baselines and re-domains the DOT-COM reference only;
# the AI-era start (aiStart) is a separate knob, unchanged by this choice.
START_ANCHORS = [
    {"key": "netscape", "start": CLOCK["start"], "event": CLOCK["startEvent"], "default": True},
    {"key": "exuberance", "start": "1996-12-05", "event": "Irrational Exuberance speech"},
]
DEFAULT_START = "netscape"
ALT_START = next(a["key"] for a in START_ANCHORS if not a.get("default"))

# The AI-era start is the mirror assumption. ChatGPT's launch is the default (the
# popular "start of the AI era", the launch analogue of Netscape). Sundar Pichai's
# 2025-11-18 BBC interview -- "there are elements of irrationality through a moment
# like this" -- is the AI analogue of Greenspan's speech: the moment an insider with
# authority named the excess. Pairing it with the Exuberance dot-com anchor is the
# conceptually matched read (warning-to-warning); the other crossings are computed
# too. It re-baselines the AI era only: with barely a year of data behind it the
# measured pace is thin, so its projections are far less stable (see MAX_HORIZON).
AI_ANCHORS = [
    {"key": "chatgpt", "start": CLOCK["aiStart"], "event": CLOCK["aiStartEvent"],
     "short": "ChatGPT", "default": True},
    {"key": "pichai", "start": "2025-11-18", "event": "Elements of irrationality",
     "short": "the Pichai warning"},
]
DEFAULT_AI = "chatgpt"
ALT_AI = next(a["key"] for a in AI_ANCHORS if not a.get("default"))

# A projection further out than this is not a meaningful reading of the analogy --
# it means the measured pace is so slow (or the base so short) that the remaining
# dot-com shape stretches past any useful horizon. Such dates are computed and kept
# in the ledger, but SUPPRESSED for display, like a non-conforming metric. Nothing
# on the default clock comes close (the furthest is ~5 years out); it exists for the
# short-base anchors.
MAX_HORIZON_DAYS = 3653          # ~10 years

# every (dot-anchor, ai-anchor, smoothing-window) permutation materialized per node
PERM_KEYS = [(d["key"], a["key"], w)
             for d in START_ANCHORS for a in AI_ANCHORS for w in SMOOTH_WINDOWS]


def _ramp_of(start_iso):
    return _days(start_iso, CLOCK["peak"])


def _bottom_prog_of(start_iso, ramp):
    return _days(start_iso, CLOCK["bottom"]) / ramp * 100.0


# ---------------------------------------------------------------- metric registry
# Metric declarations live as one module each under oracle/metrics/ (see
# oracle/registry.py for the spec and docs/ADDING-A-METRIC.md for the
# walkthrough). Each declares: key/label/parent/order (tree placement), a
# formula over a single `source` or a multi-`series` composite, cadence,
# type (ratio_from_start | absolute_level), direction, unit/unitLabel, and an
# optional minRange for the validator's dynamic-range gate. The tree below is
# assembled at build time; inactive (credential-gated) metrics appear as stubs.


# ------------------------------------------------------------------ grid + fills
def _grid(start_iso, end_iso):
    """Contiguous calendar-daily ISO dates from start through end inclusive."""
    d0, d1 = _d(start_iso), _d(end_iso)
    return [(d0 + timedelta(days=i)).isoformat() for i in range((d1 - d0).days + 1)]


# Per-source loading goes through the registry: every source module in
# oracle/sources/ declares its loader plus the date/value columns the engine
# reads through, so adding a source never touches this file.
def _source(kind):
    from . import registry
    try:
        return registry.sources()[kind]
    except KeyError:
        raise RuntimeError(f"metric references unknown source kind {kind!r}") from None


def _load_rows(conn, src, arg):
    loader = _source(src).get("load")
    return loader(conn, arg) if loader else []


def _load_metric(conn, metric):
    """Return sorted [(date_iso, value)] with the metric's formula applied.

    Single `source`: the formula receives each raw row. Multi-`series` composite
    (a ratio, a share-of-GDP): each alias's scalar column is inner-joined on
    date, and the formula receives {alias: value}. Every composite in the
    registry joins same-cadence series, so an inner join loses nothing."""
    f = metric["formula"]
    if "series" in metric:
        maps = {}
        for alias, (src, arg) in metric["series"].items():
            spec = _source(src)
            dcol, scol = spec["date_col"], spec["value_col"]
            maps[alias] = {r[dcol]: r[scol] for r in _load_rows(conn, src, arg)
                           if r[scol] is not None}
        if not maps or any(not m for m in maps.values()):
            return []
        common = set.intersection(*(set(m) for m in maps.values()))
        out = []
        for d in common:
            try:
                v = f({a: m[d] for a, m in maps.items()})
            except (KeyError, TypeError, ZeroDivisionError):
                v = None
            if v is not None:
                out.append((d, float(v)))
        out.sort()
        return out
    src, arg = metric["source"]
    rows = _load_rows(conn, src, arg)
    dcol = _source(src)["date_col"]
    out = []
    for r in rows:
        try:
            v = f(r)
        except (KeyError, TypeError, ZeroDivisionError):
            v = None
        if v is not None:
            out.append((r[dcol], float(v)))
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
def _normalize(sm_dot, sm_ai, type_, ramp=RAMP):
    """Map smoothed native values to 0-1 intensity over the dot-com range, with
    intensity = 1 anchored to the value AT the declared peak (so the reference
    line crests on the peak marker). ratio_from_start indexes each era to its own
    start; absolute_level compares levels on the dot-com anchors. `ramp` selects
    the start anchor: sm_dot is built on that anchor's grid, so sm_dot[0] is the
    value at the start and sm_dot[ramp] the value at the (fixed) peak."""
    start_dot = sm_dot[0]
    peak_dot = sm_dot[ramp]                              # value at the declared peak date
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


def _match(target, int_dot, mode="dominant", ramp=RAMP):
    """Where `target` sits on the dot-com ramp (progress<=100), as a progress %.

    The ramp is not monotone (the 1998 crisis pulls it back below levels it had
    already reached), so a level can be crossed more than once. Two readings:
      - "dominant": the LAST upward crossing, i.e. the final time the dot-com rose
        through this level on its sustained approach to the peak. This is the
        dominant climb leg, and it is the default: an early touch that a later
        correction undid does not represent how far along the cycle we are.
      - "first": the EARLIEST crossing (the first date the level was reached).

    `ramp` is the active start anchor's days-to-peak (int_dot is on that grid)."""
    lim = min(len(int_dot) - 1, ramp)
    if target <= (int_dot[0] or 0):
        return 0.0
    crossings = []  # (progress, is_upward)
    for i in range(1, lim + 1):
        v0, v1 = int_dot[i - 1], int_dot[i]
        if v0 is None or v1 is None or v1 == v0:
            continue
        if (v0 - target) * (v1 - target) <= 0:
            f = (target - v0) / (v1 - v0)
            crossings.append(((i - 1 + f) / ramp * 100.0, v1 > v0))
    if not crossings:
        return lim / ramp * 100.0
    if mode == "dominant":
        ups = [p for p, up in crossings if up]
        return ups[-1] if ups else crossings[-1][0]
    return crossings[0][0]


def _evaluate(int_dot, int_ai, today, mode="dominant",
              start=CLOCK["start"], ramp=RAMP, bottom_prog=BOTTOM_PROG,
              ai_start=CLOCK["aiStart"]):
    """Analogy + projection on a node's daily curves (scalars, exact daily).
    `mode` selects the ramp matching (see _match); the site default is
    "dominant" — the backtester (oracle/stability.py) evaluates both. `start`,
    `ramp`, `bottom_prog` select the dot-com start anchor; `ai_start` selects the
    AI-era anchor, which sets how much elapsed AI time produced the progress so
    far (and hence the pace). Both default to the canonical clock."""
    ai_now = next((v for v in reversed(int_ai) if v is not None), 0.0)
    eq = _match(ai_now, int_dot, mode, ramp)
    equiv_date = date.fromordinal(_d(start).toordinal() + round(eq / 100 * ramp))
    ai_elapsed = _days(ai_start, today.isoformat())
    dot_done = max(eq, 0.0) / 100 * ramp
    ratio = ai_elapsed / dot_done if dot_done > 0 else 1.0
    dot_left = max(100.0 - eq, 0.0) / 100 * ramp
    proj = date.fromordinal(today.toordinal() + round(ratio * dot_left))
    # Projected bottom: the remaining distance to the declared 2002 low, at this
    # node's own measured pace (same rate-scaling as the peak).
    bottom_left = max(bottom_prog - eq, 0.0) / 100 * ramp
    bottom = date.fromordinal(today.toordinal() + round(ratio * bottom_left))
    ramp_max = max((v for v in int_dot[:min(len(int_dot), ramp + 1)] if v is not None), default=1.0)
    return {
        "intensityNow": round(ai_now, 4),
        "equiv": {"progress": round(eq, 2), "intensity": round(ai_now, 4)},
        "equivalentDotcomDate": equiv_date.isoformat(),
        "daysFromPeak": (equiv_date - _d(CLOCK["peak"])).days,
        "compression": round(ratio, 2),
        "projectedPeakDate": proj.isoformat(),
        "projectedBottomDate": bottom.isoformat(),
        "phase": _phase_of(eq),
        "beyondDotcomPeak": ai_now > ramp_max,
        # too far out to be a meaningful reading; kept in the ledger, suppressed
        # for display (see MAX_HORIZON_DAYS)
        "beyondHorizon": (proj.toordinal() - today.toordinal()) > MAX_HORIZON_DAYS,
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


def _validate(sm_dot, sm_ai, int_dot, int_ai, direction, min_range=0.2, ramp=RAMP):
    up = direction != "down"
    checks = []

    def add(name, ok, detail):
        checks.append({"name": name, "pass": bool(ok), "detail": detail})

    start_dot, peak_dot = sm_dot[0], sm_dot[ramp]
    # pass 1 — candidacy
    covers = _first(sm_dot) is not None and _first(sm_ai) is not None
    add("covers both eras", covers,
        "real data at both era starts" if covers else "missing one era's start")
    rng = abs(peak_dot - start_dot) / abs(start_dot) if start_dot else 0.0
    add("dynamic range", rng >= min_range,
        f"dot-com moved {rng * 100:.0f}% from start to peak")

    # pass 2 — shape (after smoothing)
    seq = [v for v in sm_dot if v is not None]
    n = len(seq)
    ext_i = (max(range(n), key=lambda i: seq[i]) if up
             else min(range(n), key=lambda i: seq[i])) if n else 0
    interior = bool(n) and 0.15 * n < ext_i < 0.9 * n
    reverses = bool(n) and ((seq[-1] < seq[ext_i] * 0.92) if up else (seq[-1] > seq[ext_i] * 1.08))
    add("rise, peak, fall", interior and reverses,
        f"peaks near {ext_i / ramp * 100:.0f}% then reverses" if interior and reverses
        else "no clear interior peak in the reference era")
    ai_now = _last_val(int_ai) or 0.0
    add("AI below the peak", ai_now < 1.02, f"AI at {ai_now * 100:.0f}% of the dot-com peak")
    ai_start = _first(int_ai) or 0.0
    # Intensity space is already direction-normalized (1 = the peak state, for
    # up- and down-direction metrics alike), so "toward the peak" is simply
    # rising intensity here; no direction flip.
    rising = ai_now > ai_start
    add("AI moving toward the peak", rising,
        "AI is moving toward the peak state" if rising
        else "AI is flat or moving away from the peak")

    # AI's current level crossed on the dot-com ramp (informational, not gating)
    lim = min(len(int_dot) - 1, ramp)
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
    return (f"{node['label']} does not fit the rise-peak-fall analogy{tail}; "
            "it is shown for context and its projection is suppressed.")


def _attach_observations(node, cache):
    if not (node.get("wip") or node.get("stub")):
        h = obs_hash(node)
        node["obsHash"] = h
        entry = cache.get(node["key"])
        node["observations"] = (entry["text"] if entry and entry.get("hash") == h
                                else obs_fallback(node))
    for c in node.get("children", []):
        _attach_observations(c, cache)


def _blend(arrays, weights=None):
    """Pointwise mean of daily intensity curves over the values present at
    each index — equal-weight by default, or weighted when a branch declares
    default child weights (metrics/_tree.py)."""
    n = len(arrays[0])
    out = []
    if weights is None:
        for i in range(n):
            vals = [a[i] for a in arrays if i < len(a) and a[i] is not None]
            out.append(sum(vals) / len(vals) if vals else None)
        return out
    for i in range(n):
        s = wsum = 0.0
        for a, w in zip(arrays, weights):
            if i < len(a) and a[i] is not None:
                s += a[i] * w
                wsum += w
        out.append(s / wsum if wsum else None)
    return out


# ------------------------------------------------------------------- build tree
def _fmt_level(v):
    """Native-value formatting by magnitude, so a 0.85 spread keeps its decimals
    and a 41.6 CAPE reads as before."""
    return f"{v:,.0f}" if abs(v) >= 100 else f"{v:.1f}" if abs(v) >= 10 else f"{v:.2f}"


def _leaf_copy(m, node, sm_dot, sm_ai, ramp=RAMP, since="ChatGPT"):
    """The 'today' display and the 'vs dot-com' note for a leaf, from a given
    smoothed series (so it can be recomputed per smoothing window / start anchor).
    `ramp` indexes the peak on the active dot anchor's grid; `since` names the
    active AI anchor the ratio is measured from."""
    name = node["label"]
    if m["type"] == "ratio_from_start":
        ai_mult = sm_ai[-1] / sm_ai[0]
        peak_mult = sm_dot[ramp] / sm_dot[0]
        display = f"up {ai_mult:.1f}x since {since}"
        different = (f"{name} is up about {ai_mult:.1f}x since {since} against roughly "
                     f"{peak_mult:.1f}x for the same series into 2000, so on this measure "
                     "the AI era reads earlier than the dot-com run.")
    else:
        now, pk = sm_ai[-1], sm_dot[ramp]
        rel = ("already past" if now > pk else "close to" if now > 0.9 * pk and pk > 0
               else "still below")
        display = f"{m['unitLabel']} {_fmt_level(now)}"
        different = (f"{name} reads {_fmt_level(now)} now against roughly {_fmt_level(pk)} "
                     f"at the 2000 peak, {rel} the dot-com top on this measure.")
    return display, different


def _build_leaf(conn, node, dot_grids, ai_grids, today):
    m = node["metric"]
    pairs = _load_metric(conn, m)
    if not pairs:
        return None

    # AI side, per anchor: raw series + both smoothings. An anchor whose window has
    # not opened yet (a backtest day before it) has an empty grid and is skipped --
    # the alt AI anchor simply has no permutations on those days.
    ai_raw, ai_sm = {}, {}
    for a in AI_ANCHORS:
        grid = ai_grids.get(a["key"]) or []
        raw = _fill(pairs, grid) if grid else []
        if not raw or raw[0] is None:
            if a["key"] == DEFAULT_AI:
                return None                           # metric never reaches the AI era
            continue
        ai_raw[a["key"]] = raw
        for win, wd in SMOOTH_WINDOWS.items():
            ai_sm[(a["key"], win)] = _smooth_centered(raw, wd)

    # Dot side, per anchor: raw series + both smoothings + that anchor's ramp. The alt
    # start is strictly later than the default, so forward-fill guarantees coverage.
    dot_raw, dot_sm, ramps = {}, {}, {}
    for anc in START_ANCHORS:
        raw = _fill(pairs, dot_grids[anc["key"]])
        if raw[0] is None:
            if anc["key"] == DEFAULT_START:
                return None                           # no coverage at the canonical start
            continue
        dot_raw[anc["key"]] = raw
        ramps[anc["key"]] = _ramp_of(anc["start"])
        for win, wd in SMOOTH_WINDOWS.items():
            dot_sm[(anc["key"], win)] = _smooth_centered(raw, wd)

    # Cross them. Normalization couples the two sides (the AI curve is scaled by how
    # far the dot-com reference climbed), so every (dot, ai, window) triple is its own
    # dataset even though the smoothed inputs are shared.
    perms = {}
    for anc in START_ANCHORS:
        dk = anc["key"]
        if dk not in dot_raw:
            continue
        ramp = ramps[dk]
        for a in AI_ANCHORS:
            ak = a["key"]
            if ak not in ai_raw:
                continue
            for win in SMOOTH_WINDOWS:
                sm_dot, sm_ai = dot_sm[(dk, win)], ai_sm[(ak, win)]
                int_dot, int_ai = _normalize(sm_dot, sm_ai, m["type"], ramp)
                disp, _diff = _leaf_copy(m, node, sm_dot, sm_ai, ramp, a["short"])
                perms[(dk, ak, win)] = {
                    "sm_dot": sm_dot, "sm_ai": sm_ai, "int_dot": int_dot, "int_ai": int_ai,
                    "display": disp, "ramp": ramp, "start": anc["start"], "aiStart": a["start"]}

    # scalars, validation, and prose come from the default (Netscape / ChatGPT /
    # 90-day) clock; conformance is judged once here and reused across every anchor
    d = perms[(DEFAULT_START, DEFAULT_AI, DEFAULT_SMOOTH)]
    result = _evaluate(d["int_dot"], d["int_ai"], today)
    validation = _validate(d["sm_dot"], d["sm_ai"], d["int_dot"], d["int_ai"],
                           m["direction"], m.get("minRange", 0.2))
    display, different = _leaf_copy(m, node, d["sm_dot"], d["sm_ai"])

    return {"key": node["key"], "label": node["label"], "leaf": m["kind"], "unit": m["unit"],
            "unitLabel": m["unitLabel"], "type": m["type"], "display": display, "different": different,
            "valid": validation["valid"], "validation": validation,
            "_intDot": d["int_dot"], "_intAi": d["int_ai"], "_smDot": d["sm_dot"], "_smAi": d["sm_ai"],
            "_rawDot": dot_raw.get(DEFAULT_START), "_rawAi": ai_raw[DEFAULT_AI],
            "_altRawDot": dot_raw.get(ALT_START), "_altRawAi": ai_raw.get(ALT_AI),
            "_perms": perms, **result}


def _build(conn, node, dot_grids, ai_grids, today):
    if node.get("wip"):
        return {"key": node["key"], "label": node["label"], "wip": True}
    if node.get("stub"):
        # A discovered-but-inactive metric (credential-gated or disabled): shown
        # in the sidebar tree as available, never computed, never blended.
        return {"key": node["key"], "label": node["label"], "stub": True,
                "requires": node.get("requires", "credentials required")}
    if "metric" in node:
        return _build_leaf(conn, node, dot_grids, ai_grids, today)
    kids = [_build(conn, c, dot_grids, ai_grids, today) for c in node["children"]]
    live = [k for k in kids if k and not (k.get("wip") or k.get("stub"))]
    placeholders = [k for k in kids if k and (k.get("wip") or k.get("stub"))]
    if not live:
        return None
    # A parent blends only its CONFORMING inputs, so a non-conforming child is shown
    # but never drags the roll-up's projection. If none conform, fall back to the
    # full set for a curve but mark the parent invalid (projection suppressed too).
    valid_live = [k for k in live if k.get("valid", True)]
    use = valid_live or live
    declared = node.get("weights")
    weights = [declared.get(k["key"], 1.0) for k in use] if declared else None
    # Blend each (dot, ai, smoothing) permutation independently over the same
    # conforming set + weights, so the roll-up's projection reflows correctly under
    # whichever combination the reader selects. A permutation is only blended where
    # EVERY used child has it (an AI anchor that had not opened yet is absent).
    perms = {}
    for pk in PERM_KEYS:
        if not all(pk in k["_perms"] for k in use):
            continue
        perms[pk] = {"int_dot": _blend([k["_perms"][pk]["int_dot"] for k in use], weights),
                     "int_ai": _blend([k["_perms"][pk]["int_ai"] for k in use], weights)}
    d = perms[(DEFAULT_START, DEFAULT_AI, DEFAULT_SMOOTH)]
    result = _evaluate(d["int_dot"], d["int_ai"], today)
    valid = len(valid_live) > 0
    validation = {"valid": valid, "crossings": 0, "checks": [
        {"name": "conforming inputs", "pass": valid,
         "detail": f"{len(valid_live)} of {len(live)} inputs fit the analogy"}]}
    out = {"key": node["key"], "label": node["label"], "display": "blended",
           "valid": valid, "validation": validation, "children": live + placeholders,
           "_intDot": d["int_dot"], "_intAi": d["int_ai"], "_perms": perms, **result}
    if declared:
        out["weights"] = declared
    return out


# ---------------------------------------------------------------- weekly downsample
def _weekly_idx(n):
    idx = list(range(0, n, 7))
    if not idx or idx[-1] != n - 1:
        idx.append(n - 1)
    return idx


def _pick(arr, idx, nd=4):
    return [round(arr[i], nd) if arr[i] is not None else None for i in idx]


def _emit(node, dw, aw, dw_alt, aw_alt):
    """Recursively build the weekly payload node (arrays downsampled to weekly).
    dw/dw_alt index the default and alt dot grids; aw/aw_alt the default and alt
    AI grids (the alt AI grid is much shorter, opening only at its anchor)."""
    if node.get("wip"):
        return {"key": node["key"], "label": node["label"], "wip": True}
    if node.get("stub"):
        return {"key": node["key"], "label": node["label"], "stub": True,
                "requires": node["requires"]}
    out = {"key": node["key"], "label": node["label"], "display": node["display"],
           "valid": node.get("valid", True), "validation": node.get("validation"),
           "intensityDot": _pick(node["_intDot"], dw), "intensityAi": _pick(node["_intAi"], aw)}
    for k in ("intensityNow", "equiv", "equivalentDotcomDate", "daysFromPeak",
              "compression", "projectedPeakDate", "projectedBottomDate", "phase",
              "beyondDotcomPeak", "beyondHorizon"):
        out[k] = node[k]
    if "leaf" in node:
        out["leaf"] = node["leaf"]; out["unit"] = node["unit"]; out["unitLabel"] = node["unitLabel"]
        out["type"] = node["type"]; out["different"] = node["different"]
        out["smoothedDot"] = _pick(node["_smDot"], dw, 2); out["smoothedAi"] = _pick(node["_smAi"], aw, 2)
        out["rawDot"] = _pick(node["_rawDot"], dw, 2); out["rawAi"] = _pick(node["_rawAi"], aw, 2)
        perms = node.get("_perms", {})
        # the alternate smoothing window (30-day) on the default anchors; the default
        # (90) is the top-level set
        alt = perms.get((DEFAULT_START, DEFAULT_AI, "30"))
        if alt:
            out["alt30"] = {"intensityDot": _pick(alt["int_dot"], dw), "intensityAi": _pick(alt["int_ai"], aw),
                            "smoothedDot": _pick(alt["sm_dot"], dw, 2), "smoothedAi": _pick(alt["sm_ai"], aw, 2),
                            "display": alt["display"]}
        # the alternate DOT-COM start: its own (shorter) dot grid + both windows, so the
        # toggle can swap the whole reference. AI curves re-normalize per dot anchor
        # (the denominator is the dot-com climb, which the anchor changes).
        a90, a30 = (perms.get((ALT_START, DEFAULT_AI, "90")),
                    perms.get((ALT_START, DEFAULT_AI, "30")))
        if a90 and a30 and node.get("_altRawDot") is not None:
            def altw(p):
                return {"intensityDot": _pick(p["int_dot"], dw_alt), "intensityAi": _pick(p["int_ai"], aw),
                        "smoothedDot": _pick(p["sm_dot"], dw_alt, 2), "smoothedAi": _pick(p["sm_ai"], aw, 2),
                        "display": p["display"]}
            out["altStart"] = {"rawDot": _pick(node["_altRawDot"], dw_alt, 2),
                               "90": altw(a90), "30": altw(a30)}
        # the alternate AI-ERA start: ONLY the AI-side arrays (its own short grid),
        # plus the parts that genuinely depend on all three axes (intensityAi, prose)
        # keyed by dot anchor. Dot-side arrays are not duplicated; the client composes
        # them from the blocks above.
        if node.get("_altRawAi") is not None and aw_alt:
            def aiw(win):
                base = perms.get((DEFAULT_START, ALT_AI, win))
                if not base:
                    return None
                blk = {"smoothedAi": _pick(base["sm_ai"], aw_alt, 2),
                       "intensityAi": {}, "display": {}}
                for dkey in (DEFAULT_START, ALT_START):
                    p = perms.get((dkey, ALT_AI, win))
                    if p:
                        blk["intensityAi"][dkey] = _pick(p["int_ai"], aw_alt)
                        blk["display"][dkey] = p["display"]
                return blk
            b90, b30 = aiw("90"), aiw("30")
            if b90 and b30:
                out["altAi"] = {"rawAi": _pick(node["_altRawAi"], aw_alt, 2),
                                "90": b90, "30": b30}
    if "weights" in node:
        out["weights"] = node["weights"]
    if "children" in node:
        out["children"] = [_emit(c, dw, aw, dw_alt, aw_alt) for c in node["children"]]
    return out


def _leaf_dates(node, acc):
    # Only conforming leaves with a meaningful horizon contribute to the headline
    # band; a suppressed projection (non-conforming, or past MAX_HORIZON_DAYS) is
    # not shown, so it must not widen the range either.
    if node.get("leaf") and node.get("valid", True) and not node.get("beyondHorizon"):
        acc.append(node["projectedPeakDate"])
    for c in node.get("children", []):
        _leaf_dates(c, acc)


# --------------------------------------------------------------------- assemble
def _alt_clock_block(alt_grid, ai_dates, aw, dw_alt, root, today):
    """The non-default dot-com start anchor's clock + weekly axes, so the client can
    reflow the whole reference when the reader toggles the start. headlineDate is the
    alt-anchor root projection (a static preview; the client recomputes live)."""
    anchor = next(a for a in START_ANCHORS if a["key"] == ALT_START)
    ramp = _ramp_of(anchor["start"])
    bprog = _bottom_prog_of(anchor["start"], ramp)
    ad = root["_perms"][(ALT_START, DEFAULT_AI, DEFAULT_SMOOTH)]
    head = _evaluate(ad["int_dot"], ad["int_ai"], today, "dominant",
                     anchor["start"], ramp, bprog)["projectedPeakDate"]
    return {
        "key": anchor["key"], "start": anchor["start"], "event": anchor["event"],
        "ramp": ramp, "bottomProgress": round(bprog, 2),
        "peakIdx": min(range(len(dw_alt)), key=lambda k: abs(dw_alt[k] - ramp)),
        "progDot": [round(i / ramp * 100, 2) for i in dw_alt],
        "progAi": [round(i / ramp * 100, 2) for i in aw],
        "dotMonths": [alt_grid[i] for i in dw_alt],
        "headlineDate": head,
    }


def _alt_ai_block(alt_ai_grid, aw_alt, root, today):
    """The non-default AI-era anchor: its own (much shorter) weekly grid, plus the
    root projection under each dot anchor as a static preview. The client derives
    progAi from these months and the active ramp, so no per-pair axis is shipped."""
    anchor = next(a for a in AI_ANCHORS if a["key"] == ALT_AI)
    heads = {}
    for d in START_ANCHORS:
        p = root["_perms"].get((d["key"], ALT_AI, DEFAULT_SMOOTH))
        if not p:
            continue
        ramp = _ramp_of(d["start"])
        heads[d["key"]] = _evaluate(
            p["int_dot"], p["int_ai"], today, "dominant", d["start"], ramp,
            _bottom_prog_of(d["start"], ramp), anchor["start"])["projectedPeakDate"]
    return {
        "key": anchor["key"], "start": anchor["start"], "event": anchor["event"],
        "short": anchor["short"],
        "aiMonths": [alt_ai_grid[i] for i in aw_alt],
        "headlineDate": heads,
    }


def compute_thennow(conn):
    today = _today()
    dot_grids = {a["key"]: _grid(a["start"], CLOCK["bottom"]) for a in START_ANCHORS}
    dot_dates = dot_grids[DEFAULT_START]
    ai_grids = {a["key"]: _grid(a["start"], today.isoformat()) for a in AI_ANCHORS}
    ai_dates = ai_grids[DEFAULT_AI]
    from . import registry
    root = _build(conn, registry.build_tree(), dot_grids, ai_grids, today)
    if not root:
        return None

    dw, aw = _weekly_idx(len(dot_dates)), _weekly_idx(len(ai_dates))
    dw_alt = _weekly_idx(len(dot_grids[ALT_START]))
    alt_ai_grid = ai_grids.get(ALT_AI) or []
    aw_alt = _weekly_idx(len(alt_ai_grid)) if alt_ai_grid else []
    prog_dot = [round(i / RAMP * 100, 2) for i in dw]
    prog_ai = [round(i / RAMP * 100, 2) for i in aw]
    peak_idx = min(range(len(dw)), key=lambda k: abs(dw[k] - RAMP))
    tree = _emit(root, dw, aw, dw_alt, aw_alt)
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
        "bottomProgress": round(BOTTOM_PROG, 2),
        "progDot": prog_dot, "progAi": prog_ai,
        "dotMonths": [dot_dates[i] for i in dw], "aiMonths": [ai_dates[i] for i in aw],
        "headlineDate": tree["projectedPeakDate"],
        "bandLow": dates[0] if dates else tree["projectedPeakDate"],
        "bandHigh": dates[-1] if dates else tree["projectedPeakDate"],
        "tree": tree,
        # selectable dot-com start anchors + the non-default anchor's clock/axes,
        # for the Options "Dot-com start" toggle (default projections above are the
        # canonical Netscape clock; the alt is opt-in and reflows client-side)
        "startAnchors": [{"key": a["key"], "start": a["start"], "event": a["event"],
                          "default": bool(a.get("default"))} for a in START_ANCHORS],
        "altStart": _alt_clock_block(dot_grids[ALT_START], ai_dates, aw, dw_alt, root, today),
        # selectable AI-era start anchors + the non-default anchor's grid. Its window
        # is far shorter, so its projections are much less stable -- the stability
        # panel and the horizon rule below are what keep that honest.
        "aiAnchors": [{"key": a["key"], "start": a["start"], "event": a["event"],
                       "short": a["short"], "default": bool(a.get("default"))}
                      for a in AI_ANCHORS],
        "altAi": _alt_ai_block(alt_ai_grid, aw_alt, root, today) if aw_alt else None,
        "maxHorizonDays": MAX_HORIZON_DAYS,
        # leaf-kind / branch-key → Data Sources group anchor, from the modules'
        # ir declarations (drives the "full method & sources" links)
        "srcGroups": registry.src_groups(),
        # projection-stability backtest summaries per node per option
        # permutation, from the committed ledger (None until backfilled)
        "stability": _stability_blocks(),
        # stability-optimal roll-up weightings (display-only; the site's
        # defaults stay equal-weight), from `python main.py optimize-weights`
        "weightStability": _weight_blocks(),
    }


def _stability_blocks():
    from . import stability
    return stability.payload_blocks()


def _weight_blocks():
    from . import stability
    return stability.weight_blocks()
