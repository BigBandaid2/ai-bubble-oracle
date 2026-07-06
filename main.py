"""AI Bubble Oracle — Phase 1: stock drawdown tracker.

Tracks the equity-based conditions of the Polymarket "AI bubble burst in 2026?"
market. See README.md for the full roadmap.

Usage:
    python main.py update    # fetch prices (full history on first run), rebuild events
    python main.py status    # print the current condition report
    python main.py events    # list threshold-crossing events
    python main.py html      # generate dashboard.html + datasources.html (self-contained)
"""

import argparse
import sys
import time
from datetime import datetime, timezone

from oracle import db
from oracle.cape import fetch_cape, import_cape_csv, export_cape_csv
from oracle.config import SP500_TICKER, THENNOW_TICKERS, TICKERS
from oracle.dashboard import write_dashboard
from oracle.datasources import write_datasources
from oracle.h100 import fetch_h100_proxy, SEED_POINTS, import_h100_csv, export_h100_csv
from oracle.polymarket import fetch_market_history, import_polymarket_csv, export_polymarket_csv
from oracle.bankruptcy import scan_all, import_bankruptcy_csv, export_bankruptcy_csv
from oracle.buzz import (update_signals, import_buzz_csv, export_buzz_csv,
                         update_buzz_events, import_buzz_events_csv, export_buzz_events_csv,
                         record_gdelt_health)
from oracle.report import status_report
from oracle.thennow_page import write_thennow_page
from oracle.tracker import rebuild_events
from oracle.yahoo import fetch_history, YahooError


def cmd_update(conn):
    # Condition tickers, the S&P 500 context series, and the long-history
    # Then-and-Now series (^IXIC etc). dict.fromkeys dedupes if any overlap.
    for ticker in dict.fromkeys(TICKERS + [SP500_TICKER] + THENNOW_TICKERS):
        days = 90 if db.has_prices(conn, ticker) else None
        try:
            bars = fetch_history(ticker, days)
        except YahooError as e:
            print(f"ERROR fetching {ticker}: {e}", file=sys.stderr)
            continue
        db.upsert_prices(conn, ticker, bars)
        first, last = bars[0]["date"], bars[-1]["date"]
        span = "full history" if days is None else f"last {days}d"
        print(f"{ticker}: {len(bars)} bars ({span}) {first} .. {last}")
        time.sleep(1)  # be polite to Yahoo
    events = rebuild_events(conn)
    print(f"events rebuilt: {len(events)} crossings in history")

    # Shiller CAPE valuation multiple (Then-and-Now valuation leaf). Re-fetchable;
    # the committed CSV is a fallback so a stalled fetch doesn't blank the leaf.
    cape_restored = import_cape_csv(conn)
    cape_rows = fetch_cape()
    if cape_rows:
        db.upsert_cape(conn, cape_rows)
        print(f"CAPE: fetched {len(cape_rows)} monthly points "
              f"({cape_rows[0][0]}..{cape_rows[-1][0]}, latest {cape_rows[-1][1]})")
    else:
        print(f"CAPE: fetch failed (kept {cape_restored} cached points)")
    cape_kept = export_cape_csv(conn)
    print(f"CAPE history: {cape_kept} points in data/cape_history.csv")

    # H100 rental proxy (condition 5). Restore accumulated readings from the
    # committed CSV, seed the published index points (both tiers), append
    # today's live Vast.ai proxy reading, then persist back to the CSV.
    restored = import_h100_csv(conn)
    for d, index_type, src, val in SEED_POINTS:
        db.upsert_h100(conn, d, index_type, src, val)
    proxy = fetch_h100_proxy()
    if proxy:
        today = datetime.now(timezone.utc).date().isoformat()
        db.upsert_h100(conn, today, "neocloud", "vast_proxy", proxy["usd_hr"], proxy["low"], proxy["n"])
        print(f"H100 neocloud proxy: median ${proxy['usd_hr']}/hr (low ${proxy['low']}, n={proxy['n']})")
    else:
        print("H100 proxy: fetch failed (kept prior readings)")
    kept = export_h100_csv(conn)
    print(f"H100 history: restored {restored}, now {kept} readings in data/h100_history.csv")

    # Polymarket's own implied YES-probability over time. Full history is
    # re-fetchable; the CSV is a fallback so a stalled API doesn't blank the chart.
    pm_restored = import_polymarket_csv(conn)
    pm_hist = fetch_market_history()
    if pm_hist:
        db.upsert_polymarket(conn, pm_hist)
        print(f"Polymarket: fetched {len(pm_hist)} daily points "
              f"({pm_hist[0][0]}..{pm_hist[-1][0]}, latest {pm_hist[-1][1] * 100:.0f}% YES)")
    else:
        print(f"Polymarket: fetch failed (kept {pm_restored} cached points)")
    pm_kept = export_polymarket_csv(conn)
    print(f"Polymarket history: {pm_kept} points in data/polymarket_history.csv")

    # Bankruptcy conditions: daily CourtListener docket scan (candidates only
    # count after human confirmation in config.CONFIRMED_BANKRUPTCIES).
    import_bankruptcy_csv(conn)
    scans = scan_all(conn)
    for entity, r in scans.items():
        print(f"Bankruptcy scan ({entity}): {r['candidates']} candidate Ch.7/11 filings")
    bk_kept = export_bankruptcy_csv(conn)
    print(f"Bankruptcy history: {bk_kept} scan rows in data/bankruptcy_history.csv")

    # Bankruptcy-buzz signals (GDELT news volume + litigation pulse). The
    # coefficient itself is computed at page-generation time.
    import_buzz_csv(conn)
    did_backfill = update_signals(conn)
    bz_kept = export_buzz_csv(conn)
    print(f"Buzz history: {bz_kept} signal rows in data/buzz_history.csv")

    # Notable buzz spikes: pick the news item behind each. Skip on backfill runs
    # so the heavy GDELT timeline call and the article calls don't stack up.
    import_buzz_events_csv(conn)
    if did_backfill:
        print("Buzz events: skipped this run (news backfill ran; GDELT cooldown)")
    else:
        update_buzz_events(conn)
    ev_kept = export_buzz_events_csv(conn)
    print(f"Buzz events: {ev_kept} cached articles in data/buzz_events.csv")

    # Record GDELT health so the workflow can alert on a *sustained* throttle
    # (a tripped breaker is a green run, so GitHub's failure email won't fire).
    streak = record_gdelt_health()
    print(f"GDELT health: {'THROTTLED' if streak else 'ok'}"
          + (f" — {streak} consecutive throttled run(s)" if streak else ""))

    db.set_meta(conn, "last_update", datetime.now(timezone.utc).isoformat(timespec="seconds"))


def cmd_events(conn):
    rows = conn.execute(
        "SELECT date, ticker, basis, kind, drawdown, price, ath, condition_key"
        " FROM events ORDER BY date"
    ).fetchall()
    if not rows:
        print("no events (run `python main.py update` first)")
        return
    for e in rows:
        print(f"{e['date']}  {e['ticker']:5s} {e['kind']:9s} ({e['basis']})"
              f"  dd {e['drawdown']*100:.1f}%  px {e['price']:.2f} / ath {e['ath']:.2f}"
              f"  [{e['condition_key']}]")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=["update", "status", "events", "html", "datasources", "thennow"], nargs="?", default="status")
    args = p.parse_args()

    conn = db.connect()
    try:
        if args.command == "update":
            cmd_update(conn)
            print(f"\ndashboard written:   {write_dashboard(conn)}")
            print(f"datasources written: {write_datasources(conn)}")
            print(f"thennow written:     {write_thennow_page(conn)}\n")
            print(status_report(conn))
        elif args.command == "status":
            print(status_report(conn))
        elif args.command == "events":
            cmd_events(conn)
        elif args.command == "html":
            print(f"dashboard written:   {write_dashboard(conn)}")
            print(f"datasources written: {write_datasources(conn)}")
            print(f"thennow written:     {write_thennow_page(conn)}")
        elif args.command == "datasources":
            print(f"datasources written: {write_datasources(conn)}")
        elif args.command == "thennow":
            print(f"thennow written:     {write_thennow_page(conn)}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
