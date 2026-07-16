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

from oracle import db, registry
from oracle.config import SP500_TICKER, TICKERS
from oracle.dashboard import write_dashboard
from oracle.datasources import write_datasources
from oracle.observe import refresh_observations
from oracle.report import status_report
from oracle.sources.buzz import record_gdelt_health
from oracle.thennow_page import write_thennow_page
from oracle.tracker import rebuild_events
from oracle.yahoo import fetch_history, YahooError


def cmd_update(conn):
    registry.report()
    # Condition tickers, the S&P 500 context series, and every ticker the
    # ACTIVE metric registry reads (kind "prices"). dict.fromkeys dedupes.
    for ticker in dict.fromkeys(TICKERS + [SP500_TICKER] + registry.required_tickers()):
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

    # Every other data source is a module in oracle/sources/ exporting a SOURCE
    # spec; run each active one's update() in declared order. A source whose
    # required credentials are absent is skipped loudly, never fatally — the
    # public build must stay public-data-only and never blank on a missing key.
    registry.ensure_schema(conn)
    active, skipped = registry.ordered_sources()
    for src_spec in active:
        src_spec["update"](conn)
    for src_spec, miss in skipped:
        print(f"SKIPPED source {src_spec['kind']}: missing {', '.join(miss)}")

    # Record GDELT health so the workflow can alert on a *sustained* throttle
    # (a tripped breaker is a green run, so GitHub's failure email won't fire).
    streak = record_gdelt_health()
    print(f"GDELT health: {'THROTTLED' if streak else 'ok'}"
          + (f" — {streak} consecutive throttled run(s)" if streak else ""))

    # Then-and-Now LLM observations: hash-gated, so this only calls Haiku for a
    # node whose analogy state actually shifted since the last run (usually none).
    obs_changed = refresh_observations(conn)
    print(f"thennow observations: {obs_changed} regenerated"
          if obs_changed else "thennow observations: unchanged")

    # Projection ledger: record today's projections (all option permutations)
    # as genuine point-in-time history for the stability panel.
    from oracle import stability
    print(f"projection ledger: {stability.append_today(conn)} node(s) recorded for today")

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


def cmd_payload(conn, out_dir=None):
    """Dump the two engine payloads as stable (sorted, indented) JSON, for
    payload-equality diffs across refactors. CI and the contributor dev loop
    both rely on this staying deterministic for a fixed oracle.db."""
    import json
    from oracle.thennow import compute_thennow
    from oracle.datasources import build_payload
    payloads = {
        "thennow": compute_thennow(conn),
        "datasources": build_payload(conn),
    }
    text = json.dumps(payloads, indent=1, sort_keys=True, default=str)
    if out_dir:
        from pathlib import Path
        p = Path(out_dir) / "payload.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        print(f"payload written: {p}")
    else:
        print(text)


def cmd_check():
    """The contributor-contract spec lint (no network, no credentials, no db):
    validates every discovered metric/source module, the _template.py fixture,
    the data-licensing rule, the workflow guard, and the template sentinels."""
    errs = registry.check()
    if errs:
        for e in errs:
            print(f"FAIL {e}")
        print(f"\ncheck: {len(errs)} problem(s)")
        sys.exit(1)
    registry.report()
    print("check: all module specs green")


def cmd_verify_pages():
    """Template <-> generated parity, no db needed: each generated page must be
    its template with the single __DATA__ sentinel replaced by a JSON payload.
    Catches 'edited the template but forgot to regenerate' (and vice versa)."""
    import json
    from oracle.config import PROJECT_DIR
    pairs = [
        ("oracle/thennow_template.html", "thennow.html"),
        ("oracle/dashboard_template.html", "dashboard.html"),
        ("oracle/datasources_template.html", "datasources.html"),
    ]
    failed = False
    for tmpl_rel, gen_rel in pairs:
        tmpl = (PROJECT_DIR / tmpl_rel).read_text(encoding="utf-8")
        gen = (PROJECT_DIR / gen_rel).read_text(encoding="utf-8")
        if tmpl.count("__DATA__") != 1:
            print(f"FAIL {tmpl_rel}: expected exactly one __DATA__ sentinel")
            failed = True
            continue
        prefix, suffix = tmpl.split("__DATA__")
        ok = gen.startswith(prefix) and gen.endswith(suffix)
        span = gen[len(prefix):len(gen) - len(suffix)] if ok else ""
        if ok:
            try:
                json.loads(span)
            except ValueError:
                ok = False
        print(f"{'ok  ' if ok else 'FAIL'} {gen_rel} matches {tmpl_rel}"
              + ("" if ok else " (regenerate with `python main.py html`)"))
        failed = failed or not ok
    if failed:
        sys.exit(1)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", nargs="?", default="status",
                   choices=["update", "status", "events", "html", "datasources", "thennow",
                            "payload", "verify-pages", "check", "backtest"])
    p.add_argument("--out", help="directory for `payload` output (default: stdout)")
    args = p.parse_args()

    if args.command == "verify-pages":
        cmd_verify_pages()
        return
    if args.command == "check":
        cmd_check()
        return

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
            registry.report()
            print(f"dashboard written:   {write_dashboard(conn)}")
            print(f"datasources written: {write_datasources(conn)}")
            print(f"thennow written:     {write_thennow_page(conn)}")
        elif args.command == "datasources":
            print(f"datasources written: {write_datasources(conn)}")
        elif args.command == "thennow":
            print(f"thennow written:     {write_thennow_page(conn)}")
        elif args.command == "payload":
            cmd_payload(conn, args.out)
        elif args.command == "backtest":
            from oracle import stability
            stability.backfill(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
