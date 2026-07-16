"""Projection-stability backtester + ledger.

The question this module answers: as each day passes and we walk further along
the AI-era curve, does a metric keep projecting the same peak date, or does the
date wander? A metric that re-dates the peak with every data print is less
useful than one that holds a consistent target.

Mechanics: for an as-of date D, rebuild the engine's tree with the AI grid
ending at D (the dot-com reference is static), then evaluate the projection for
all four option permutations — smoothing window (90d default / 30d) x ramp
matching (dominant climb leg default / first crossing). One engine build per
day covers every node and both windows; only the cheap evaluate step runs 4x.

The ledger (data/projection_history.csv) is append-only history, one row per
(as_of, node). Rows written by `python main.py backtest` carry source=backfill:
reconstructed from FINAL data (post-revision; no publication-lag simulation),
which measures curve-walk stability, not what-was-known-when. Rows written by
the nightly update carry source=live and are genuinely point-in-time from their
own day forward.

Semantics mirrored from the site: `valid` is the default-window (90d) verdict —
the page keeps that verdict when the smoothing toggle flips; roll-ups blend the
30d curves of the same conforming-children set the default verdict chose.
"""

import csv
import time
from datetime import timedelta

from .config import PROJECT_DIR
from . import thennow as tn

LEDGER_PATH = PROJECT_DIR / "data" / "projection_history.csv"
BACKTEST_START = "2025-01-01"

PERM_KEYS = ("90_dominant", "90_first", "30_dominant", "30_first")
_COLS = ["as_of", "node", "source", "valid",
         "proj_90_dominant", "proj_90_first", "proj_30_dominant", "proj_30_first",
         "int_90", "int_30"]

_PROVENANCE = """\
# projection_history.csv — the projection ledger: one row per (as_of, node).
# For each day, the projected peak the engine produced with data through as_of,
# under all four option permutations (90/30-day smoothing x dominant-leg/first-
# crossing matching). source=backfill rows are reconstructed from FINAL data
# (post-revision, no publication-lag simulation) by `python main.py backtest`;
# source=live rows were written on their own day by the nightly update and are
# genuinely point-in-time. `valid` is the 90d default-window verdict (the site
# keeps that verdict across the smoothing toggle); int_90/int_30 are the node's
# end-of-day intensity per smoothing window at full float precision (the
# weight optimizer re-blends them). Derived entirely from this repo's own
# committed source data; regenerate with `python main.py backtest`.
"""


def _curves_30(node):
    """A node's 30-day-window intensity curves. Leaves carry them; roll-ups
    blend their children's, over the same conforming set the default-window
    verdict chose (mirrors _build + the page's recomputeTree)."""
    perms = node.get("_perms")
    if perms:
        return perms["30"]["int_dot"], perms["30"]["int_ai"]
    kids = [k for k in node.get("children", [])
            if not (k.get("wip") or k.get("stub"))]
    valid_live = [k for k in kids if k.get("valid", True)]
    use = valid_live or kids
    pairs = [_curves_30(k) for k in use]
    return (tn._blend([d for d, _ in pairs]),
            tn._blend([a for _, a in pairs]))


def snapshot(conn, as_of, source):
    """One engine build with the AI grid ending at as_of; returns ledger rows
    for every computed node (all four permutation projections)."""
    from . import registry
    dot_dates = tn._grid(tn.CLOCK["start"], tn.CLOCK["bottom"])
    ai_dates = tn._grid(tn.CLOCK["aiStart"], as_of.isoformat())
    root = tn._build(conn, registry.build_tree(), dot_dates, ai_dates, as_of)
    rows = []

    def walk(n):
        if not n or n.get("wip") or n.get("stub"):
            return
        dot90, ai90 = n["_intDot"], n["_intAi"]
        dot30, ai30 = _curves_30(n)
        projs = {}
        for win, (dot, ai) in (("90", (dot90, ai90)), ("30", (dot30, ai30))):
            for mode in ("dominant", "first"):
                projs[f"proj_{win}_{mode}"] = tn._evaluate(
                    dot, ai, as_of, mode)["projectedPeakDate"]
        # full float precision: the weight optimizer re-blends these, and a
        # rounded intensity can nudge a projection across a day boundary
        int90, int30 = tn._last_val(ai90), tn._last_val(ai30)
        rows.append({
            "as_of": as_of.isoformat(), "node": n["key"], "source": source,
            "valid": "1" if n.get("valid", True) else "0",
            **projs,
            "int_90": "" if int90 is None else repr(int90),
            "int_30": "" if int30 is None else repr(int30),
        })
        for c in n.get("children", []):
            walk(c)

    walk(root)
    return rows


# ------------------------------------------------------------------- ledger IO
def load_ledger():
    """{(as_of, node): row} from the committed CSV ('#' provenance skipped)."""
    if not LEDGER_PATH.exists():
        return {}
    with open(LEDGER_PATH, encoding="utf-8") as f:
        rows = csv.DictReader(line for line in f if not line.startswith("#"))
        return {(r["as_of"], r["node"]): r for r in rows}


def write_ledger(by_key):
    with open(LEDGER_PATH, "w", newline="", encoding="utf-8") as f:
        f.write(_PROVENANCE)
        w = csv.DictWriter(f, fieldnames=_COLS)
        w.writeheader()
        for key in sorted(by_key):
            w.writerow(by_key[key])


# ------------------------------------------------------------------- commands
def backfill(conn, start_iso=BACKTEST_START, verbose=True):
    """Fill the ledger from start_iso through today. Days that already have
    rows (either source) are left untouched, so the backfill never overwrites
    genuinely-live history and reruns are cheap."""
    ledger = load_ledger()
    have_days = {k[0] for k in ledger}
    today = tn._today()
    day, todo = tn._d(start_iso), []
    while day <= today:
        if day.isoformat() not in have_days:
            todo.append(day)
        day += timedelta(days=1)
    if verbose:
        print(f"backtest: {len(todo)} day(s) to compute "
              f"({start_iso}..{today.isoformat()}, {len(have_days)} already present)")
    t0, wrote = time.time(), 0
    for i, d in enumerate(todo):
        for row in snapshot(conn, d, "backfill"):
            ledger[(row["as_of"], row["node"])] = row
            wrote += 1
        if verbose and (i + 1) % 50 == 0:
            rate = (time.time() - t0) / (i + 1)
            print(f"  {i + 1}/{len(todo)} days ({rate:.2f}s/day, "
                  f"~{rate * (len(todo) - i - 1):.0f}s left)")
    if todo:
        write_ledger(ledger)
    if verbose:
        print(f"backtest: wrote {wrote} row(s) in {time.time() - t0:.0f}s "
              f"-> {LEDGER_PATH.name} ({len(ledger)} total)")
    return wrote


def append_today(conn):
    """Record today's projections as genuine point-in-time history (nightly).
    Replaces any same-day rows so a rerun is idempotent."""
    today = tn._today()
    rows = snapshot(conn, today, "live")
    ledger = load_ledger()
    for row in rows:
        ledger[(row["as_of"], row["node"])] = row
    write_ledger(ledger)
    return len(rows)


# ---------------------------------------------------------------------- stats
# Per-node, per-permutation summaries of the ledger for the thennow payload.
# The trend is deliberately split into two numbers: DRIFT (a robust Theil-Sen
# slope, days of projection movement per month of real time; +30 d/mo means the
# projection recedes one day per day and never converges) and the DETRENDED
# spread (how much the projection wanders around that trend). A steadily
# receding metric and an erratic one have similar raw spreads but opposite
# characters; separating the two keeps the panel honest.

def _median(vals):
    s = sorted(vals)
    n = len(s)
    if not n:
        return 0.0
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def _iso(ordinal):
    from datetime import date
    return date.fromordinal(int(round(ordinal))).isoformat()


def _perm_stats(days, base_ord):
    """days: [(as_of_ord, proj_ord, valid_bool)] sorted by as_of."""
    valid = [(a, p) for a, p, ok in days if ok]
    block = {"runs": len(days), "validDays": len(valid)}
    # weekly trend series (always shipped, even if never valid): proj as
    # day-offsets from the backtest start, null where the projection was
    # suppressed, so the chart shows gaps honestly.
    sampled = days[::7]
    if days and (not sampled or sampled[-1][0] != days[-1][0]):
        sampled.append(days[-1])
    block["series"] = [[a - base_ord, (p - base_ord) if ok else None]
                      for a, p, ok in sampled]
    if not valid:
        return block
    projs = sorted(p for _, p in valid)
    n = len(projs)
    p10, p90 = projs[int(n * .1)], projs[min(n - 1, int(n * .9))]
    # drift: Theil-Sen over weekly-subsampled valid points (robust to jumps)
    wk = valid[::7] if len(valid) > 14 else valid
    slopes = [(wk[j][1] - wk[i][1]) / (wk[j][0] - wk[i][0])
              for i in range(len(wk)) for j in range(i + 1, len(wk))
              if wk[j][0] > wk[i][0]]
    drift = _median(slopes)
    # residual spread around the Theil-Sen line through the median point
    ma, mp = _median([a for a, _ in valid]), _median([p for _, p in valid])
    resid = sorted(p - (mp + drift * (a - ma)) for a, p in valid)
    rn = len(resid)
    d10, d90 = resid[int(rn * .1)], resid[min(rn - 1, int(rn * .9))]
    # jumps: >60d moves between adjacent valid days (a re-validation after a
    # suppression gap is not a "jump", hence the 3-day adjacency guard)
    jumps = sum(1 for i in range(1, len(valid))
                if valid[i][0] - valid[i - 1][0] <= 3
                and abs(valid[i][1] - valid[i - 1][1]) > 60)
    bins = {}
    for _, p in valid:
        from datetime import date
        d = date.fromordinal(p)
        q_start = date(d.year, ((d.month - 1) // 3) * 3 + 1, 1)
        bins[q_start.toordinal()] = bins.get(q_start.toordinal(), 0) + 1
    block.update({
        "median": _iso(_median(projs)), "p10": _iso(p10), "p90": _iso(p90),
        "spread80": int(p90 - p10),
        "driftDpm": round(drift * 30, 1),
        "detrended80": int(d90 - d10),
        "jumps": jumps,
        "latest": _iso(valid[-1][1]), "latestAsOf": _iso(valid[-1][0]),
        "bins": [[_iso(k), c] for k, c in sorted(bins.items())],
    })
    return block


# ------------------------------------------------------- weight optimization
# For each roll-up: which child weighting would have made its projection most
# STABLE over the backtest window? The replay is exact: a roll-up's blended
# aiNow on day D is the weighted mean of its direct children's ledger
# intensities (each already reflecting that day's engine state), and its
# dot-com reference curve is rebuilt bottom-up from the STATIC leaf dot curves
# using each descendant's ledger validity ON THAT DAY (composition changes
# when a child flips conformance -- the first replay attempt missed this and
# the gate caught it). The engine's own _match arithmetic is reused verbatim,
# so the equal-weight replay must reproduce the ledger's roll-up projections
# exactly -- that is the gate, and it aborts the run on any mismatch.
#
# Honesty rails: optimization runs IN-SAMPLE on days <= OOS_SPLIT and is
# judged OUT-OF-SAMPLE on the rest; a 10% floor per child prevents the
# degenerate collapse onto one child; ties within 5% of the best loss go to
# the most diversified (max entropy) weighting; and this optimizes
# CONSISTENCY, the only thing measurable before the real peak -- a stable
# blend can be stably wrong.

OOS_SPLIT = "2025-09-30"
WEIGHTS_PATH = PROJECT_DIR / "data" / "weight_stability.json"
_LOSS_DRIFT_K = 10.0     # loss = detrended80 + 10*|drift d/mo| + 0.5*jitter d/mo
_LOSS_JITTER_K = 0.5
_FLOOR = 0.10


def _structure(conn):
    """Tree shape + static per-LEAF dot curves from one engine build: children
    per roll-up, subtree key lists (for per-day composition signatures), and
    display labels. Only leaf dot curves are time-invariant, so roll-up dot
    curves are reconstructed per day from these."""
    from . import registry
    today = tn._today()
    dot_dates = tn._grid(tn.CLOCK["start"], tn.CLOCK["bottom"])
    ai_dates = tn._grid(tn.CLOCK["aiStart"], today.isoformat())
    root = tn._build(conn, registry.build_tree(), dot_dates, ai_dates, today)
    st = {"children": {}, "labels": {}, "leaf_dot": {}, "subtree": {}}

    def walk(n):
        if not n or n.get("wip") or n.get("stub"):
            return []
        st["labels"][n["key"]] = n["label"]
        kids = [k for k in n.get("children", [])
                if not (k.get("wip") or k.get("stub"))]
        if kids:
            st["children"][n["key"]] = [k["key"] for k in kids]
            sub = [n["key"]]
            for k in kids:
                sub += walk(k)
            st["subtree"][n["key"]] = sub
            return sub
        st["leaf_dot"][n["key"]] = n["_intDot"]
        st["subtree"][n["key"]] = [n["key"]]
        return [n["key"]]

    walk(root)
    return st


def _wblend(curve_weight_pairs):
    """Weighted pointwise mean over the values present at each index -- the
    weighted generalization of the engine's _blend (equal weights reduce to it
    exactly)."""
    n = len(curve_weight_pairs[0][0])
    out = []
    for i in range(n):
        s = wsum = 0.0
        for c, w in curve_weight_pairs:
            v = c[i]
            if v is not None:
                s += v * w
                wsum += w
        out.append(s / wsum if wsum else None)
    return out


def _node_dot(key, rows, st, cache):
    """A node's dot-com intensity curve AS COMPOSED on this day: leaves are
    static; a roll-up blends the children conforming that day (falling back to
    all, mirroring _build). Cached by the subtree's validity signature."""
    leaf = st["leaf_dot"].get(key)
    if leaf is not None:
        return leaf
    sig = (key,) + tuple(rows[d]["valid"] for d in st["subtree"][key])
    hit = cache.get(sig)
    if hit is not None:
        return hit
    kids = st["children"][key]
    use = [k for k in kids if rows[k]["valid"] == "1"] or kids
    cur = _wblend([(_node_dot(k, rows, st, cache), 1.0) for k in use])
    cache[sig] = cur
    return cur


def _replay(rollup_key, weights, day_list, by_day, st, dot_cache):
    """Daily projections for a roll-up under direct-child weights `weights`
    (equal weights below it, as shipped). Returns [(as_of_ord, proj_ord)] over
    the days the blend conforms; matching/projection arithmetic mirrors
    _match/_evaluate exactly."""
    ai_start = tn._d(tn.CLOCK["aiStart"]).toordinal()
    ramp = tn.RAMP
    kids = st["children"][rollup_key]
    top_cache = {}
    out = []
    for as_ord, as_of in day_list:
        rows = by_day[as_of]
        valid = [k for k in kids if rows[k]["valid"] == "1"]
        if not valid:
            continue
        wsum = sum(weights[k] for k in valid)
        ai_now = sum(float(rows[k]["int_90"]) * weights[k] for k in valid) / wsum
        sig = tuple(rows[d]["valid"] for d in st["subtree"][rollup_key])
        curve = top_cache.get(sig)
        if curve is None:
            curve = _wblend([(_node_dot(k, rows, st, dot_cache), weights[k])
                             for k in valid])
            top_cache[sig] = curve
        eq = tn._match(ai_now, curve, "dominant")
        dot_done = max(eq, 0.0) / 100 * ramp
        ratio = (as_ord - ai_start) / dot_done if dot_done > 0 else 1.0
        proj = as_ord + round(ratio * max(100.0 - eq, 0.0) / 100 * ramp)
        out.append((as_ord, proj))
    return out


def _loss(series, max_gap=3):
    """Stability loss on [(as_of_ord, proj_ord)]: detrended 80% spread plus
    penalized |drift| and step jitter (both in days/month). max_gap widens for
    subsampled series so adjacent steps still count."""
    if len(series) < 20:
        return None
    wk = series[::7] if len(series) > 60 else series
    slopes = [(wk[j][1] - wk[i][1]) / (wk[j][0] - wk[i][0])
              for i in range(len(wk)) for j in range(i + 1, len(wk))
              if wk[j][0] > wk[i][0]]
    drift = _median(slopes)
    ma, mp = _median([a for a, _ in series]), _median([p for _, p in series])
    resid = sorted(p - (mp + drift * (a - ma)) for a, p in series)
    n = len(resid)
    detr = resid[min(n - 1, int(n * .9))] - resid[int(n * .1)]
    steps = [abs(series[i][1] - series[i - 1][1]) / (series[i][0] - series[i - 1][0])
             for i in range(1, len(series))
             if series[i][0] - series[i - 1][0] <= max_gap]
    jitter = _median(steps) * 30 if steps else 0.0
    return {"loss": round(detr + _LOSS_DRIFT_K * abs(drift * 30) + _LOSS_JITTER_K * jitter, 1),
            "detrended80": int(detr), "driftDpm": round(drift * 30, 1),
            "jitterDpm": round(jitter, 1), "days": len(series)}


def _weight_grid(keys, step):
    """All floor-respecting weight vectors on the simplex at `step` spacing."""
    k = len(keys)
    free = int(round((1.0 - k * _FLOOR) / step))
    out = []

    def rec(i, left, acc):
        if i == k - 1:
            out.append(acc + [left])
            return
        for units in range(left + 1):
            rec(i + 1, left - units, acc + [units])

    rec(0, free, [])
    return [{key: _FLOOR + u * step for key, u in zip(keys, units)}
            for units in out]


def _entropy(w):
    import math
    return -sum(v * math.log(v) for v in w.values() if v > 0)


def optimize_weights(conn, verbose=True):
    """Grid-search stability-optimal child weights per roll-up (in-sample,
    weekly-subsampled for speed), judge daily out-of-sample, compare with
    equal and inverse-variance weighting, and write data/weight_stability.json
    for the panel. Site defaults stay equal-weight. Prints its work."""
    import json
    ledger = load_ledger()
    if not ledger:
        raise RuntimeError("no projection ledger; run `python main.py backtest` first")
    st = _structure(conn)
    split_ord = tn._d(OOS_SPLIT).toordinal()
    by_day = {}
    for (as_of, node), r in ledger.items():
        by_day.setdefault(as_of, {})[node] = r
    all_days = [(tn._d(a).toordinal(), a) for a in sorted(by_day)]
    dot_cache = {}

    result = {"split": OOS_SPLIT, "lossFormula":
              f"detrended80 + {_LOSS_DRIFT_K:g}*|drift d/mo| + {_LOSS_JITTER_K:g}*jitter d/mo",
              "rollups": {}}
    for key in st["children"]:
        kids = st["children"][key]
        days = [(o, a) for o, a in all_days
                if all(k in by_day[a] for k in kids + [key])]
        equal = {k: 1.0 / len(kids) for k in kids}

        # gate: the equal-weight replay must reproduce the ledger exactly
        replayed = dict(_replay(key, equal, days, by_day, st, dot_cache))
        mism = [a for o, a in days
                if by_day[a][key]["valid"] == "1" and o in replayed
                and _iso(replayed[o]) != by_day[a][key]["proj_90_dominant"]]
        if verbose:
            print(f"{key}: equal-weight replay vs ledger -- {len(mism)} mismatch(es)")
        if mism:
            raise RuntimeError(f"{key}: replay does not reproduce the ledger "
                               f"(first: {mism[0]}); aborting")
        if len(kids) < 2:
            continue

        is_days = [d for d in days if d[0] <= split_ord]
        oos_days = [d for d in days if d[0] > split_ord]
        is_weekly = is_days[::7]

        step = 0.10 if len(kids) >= 4 else 0.05
        scored = []
        for w in _weight_grid(kids, step):
            li = _loss(_replay(key, w, is_weekly, by_day, st, dot_cache), max_gap=8)
            if li:
                scored.append((li["loss"], w))
        if not scored:
            # too few conforming in-sample days to judge any weighting (e.g.
            # the monetary branch, valid on a handful of days): record the
            # equal-weight stats only, honestly unoptimized
            result["rollups"][key] = {
                "children": [{"key": k, "label": st["labels"][k]} for k in kids],
                "equal": {"w": {k: round(1.0 / len(kids), 3) for k in kids},
                          "insample": _loss(_replay(key, equal, is_days, by_day, st, dot_cache)),
                          "oos": _loss(_replay(key, equal, oos_days, by_day, st, dot_cache))},
                "note": "too few conforming days in-sample to optimize",
            }
            if verbose:
                print(f"  {key}: skipped (too few conforming in-sample days)")
            continue
        scored.sort(key=lambda t: t[0])
        best = scored[0][0]
        opt = max((w for l, w in scored if l <= best * 1.05), key=_entropy)

        # inverse-variance baseline from each child's own IS-window projections
        ivw_raw = {}
        for k in kids:
            projs = sorted(tn._d(by_day[a][k]["proj_90_dominant"]).toordinal()
                           for _, a in is_days if by_day[a][k]["valid"] == "1")
            if len(projs) >= 20:
                sp = projs[min(len(projs) - 1, int(len(projs) * .9))] - projs[int(len(projs) * .1)]
                ivw_raw[k] = 1.0 / max(sp, 30) ** 2
            else:
                ivw_raw[k] = 0.0
        if any(v > 0 for v in ivw_raw.values()):
            tot = sum(ivw_raw.values())
            ivw = {k: max(_FLOOR, v / tot) for k, v in ivw_raw.items()}
            tot2 = sum(ivw.values())
            ivw = {k: v / tot2 for k, v in ivw.items()}
        else:
            ivw = dict(equal)

        entry = {"children": [{"key": k, "label": st["labels"][k]} for k in kids]}
        for name, w in (("equal", equal), ("opt", opt), ("ivw", ivw)):
            entry[name] = {"w": {k: round(v, 3) for k, v in w.items()},
                           "insample": _loss(_replay(key, w, is_days, by_day, st, dot_cache)),
                           "oos": _loss(_replay(key, w, oos_days, by_day, st, dot_cache))}
        result["rollups"][key] = entry
        if verbose:
            def fmt(nm):
                e = entry[nm]
                ins = e["insample"]["loss"] if e["insample"] else "-"
                oo = e["oos"]["loss"] if e["oos"] else "-"
                pct = "/".join(str(round(v * 100)) for v in e["w"].values())
                return f"{nm} {pct} IS={ins} OOS={oo}"
            print(f"  {key}: {fmt('equal')} | {fmt('opt')} | {fmt('ivw')}")

    WEIGHTS_PATH.write_text(json.dumps(result, indent=1, sort_keys=True),
                            encoding="utf-8")
    if verbose:
        print(f"wrote {WEIGHTS_PATH.name}")
    return result


def weight_blocks():
    """The thennow payload's `weightStability` member (None until generated)."""
    import json
    try:
        return json.loads(WEIGHTS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def payload_blocks():
    """The thennow payload's `stability` member: backtest summaries per node
    per option permutation, or None when no ledger exists yet."""
    ledger = load_ledger()
    if not ledger:
        return None
    base_ord = tn._d(BACKTEST_START).toordinal()
    by_node = {}
    for (as_of, node) in sorted(ledger):
        by_node.setdefault(node, []).append(ledger[(as_of, node)])
    nodes = {}
    for node, rows in by_node.items():
        entry = {}
        for perm in PERM_KEYS:
            days = [(tn._d(r["as_of"]).toordinal(),
                     tn._d(r["proj_" + perm]).toordinal(),
                     r["valid"] == "1") for r in rows]
            entry[perm] = _perm_stats(days, base_ord)
        nodes[node] = entry
    return {"base": BACKTEST_START, "asOf": max(k[0] for k in ledger),
            "nodes": nodes}
