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
# intensityNow per smoothing window. Derived entirely from this repo's own
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
        int30 = tn._last_val(ai30)
        rows.append({
            "as_of": as_of.isoformat(), "node": n["key"], "source": source,
            "valid": "1" if n.get("valid", True) else "0",
            **projs,
            "int_90": f"{n['intensityNow']:.4f}",
            "int_30": "" if int30 is None else f"{int30:.4f}",
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
