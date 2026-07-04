"""Drawdown tracking and threshold-crossing detection.

For each drawdown leaf in the contract tree we maintain a running all-time
high under two bases:
  close    — running max of daily closes, compared against the daily close
  intraday — running max of daily highs, compared against the daily low

Crossing events (triggered/recovered transitions) are recorded with dates so
that the "3 conditions within 90 days" window logic can run over them.
"""

from .config import BASES, drawdown_leaves
from . import db


def compute_series(rows, basis="close"):
    """Given ordered price rows, yield per-day dicts with running ATH and drawdown."""
    ath = None
    ath_date = None
    for r in rows:
        peak_candidate = r["close"] if basis == "close" else (r["high"] or r["close"])
        probe = r["close"] if basis == "close" else (r["low"] or r["close"])
        if ath is None or peak_candidate > ath:
            ath = peak_candidate
            ath_date = r["date"]
        yield {
            "date": r["date"],
            "close": r["close"],
            "probe": probe,
            "ath": ath,
            "ath_date": ath_date,
            # Positive magnitude: fraction below the all-time high (0 at the
            # peak). A condition is met when this reaches `threshold`, so both
            # sides of the comparison share a sign.
            "drawdown": 1.0 - probe / ath,
        }


def detect_events(rows, threshold, basis, condition_key, ticker):
    """Return crossing events [(condition_key, ticker, basis, date, kind, drawdown, price, ath)]."""
    events = []
    triggered = False
    for day in compute_series(rows, basis):
        is_down = day["drawdown"] >= threshold
        if is_down and not triggered:
            events.append((condition_key, ticker, basis, day["date"], "triggered",
                           day["drawdown"], day["probe"], day["ath"]))
            triggered = True
        elif not is_down and triggered:
            events.append((condition_key, ticker, basis, day["date"], "recovered",
                           day["drawdown"], day["probe"], day["ath"]))
            triggered = False
    return events


def rebuild_events(conn):
    """Recompute all crossing events from stored prices (deterministic)."""
    all_events = []
    for leaf in drawdown_leaves():
        rows = db.load_prices(conn, leaf["ticker"])
        for basis in BASES:
            all_events.extend(
                detect_events(rows, leaf["threshold"], basis, leaf["key"], leaf["ticker"])
            )
    db.replace_events(conn, all_events)
    return all_events


def leaf_state(conn, leaf):
    """Latest close-basis snapshot for one drawdown leaf (None if no data)."""
    rows = db.load_prices(conn, leaf["ticker"])
    if not rows:
        return None
    out = {}
    for basis in BASES:
        last = None
        for day in compute_series(rows, basis):
            last = day
        dd_now = 1.0 - last["close"] / last["ath"]
        out[basis] = {
            "date": last["date"],
            "close": last["close"],
            "ath": last["ath"],
            "ath_date": last["ath_date"],
            "drawdown": dd_now,
            "trigger_price": last["ath"] * (1.0 - leaf["threshold"]),
            "triggered_now": dd_now >= leaf["threshold"],
        }
    return out
