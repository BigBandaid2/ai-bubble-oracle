"""Fetch daily OHLC history from Yahoo Finance's public chart API.

No API key needed; requires a browser-like User-Agent. Prices returned by
the v8 chart endpoint are split-adjusted (the `close` series), which matches
how people normally quote "the stock price" — we deliberately do NOT use
`adjclose` (dividend-adjusted), since drawdown-from-ATH rules are read
against quoted prices.
"""

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
# NOTE: the `range=` form of this endpoint silently downgrades interval to
# monthly for long ranges, so we always pass explicit period1/period2 epochs —
# that form honors interval=1d over the full history.
CHART_URL = ("https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
             "?period1={period1}&period2={period2}&interval=1d")


class YahooError(Exception):
    pass


def _get(url, retries=4):
    last_err = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 429:  # rate limited — back off and retry
                time.sleep(2 * (attempt + 1))
                continue
            raise YahooError(f"HTTP {e.code} for {url}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise YahooError(f"failed after {retries} retries: {last_err}")


def fetch_history(ticker, days=None):
    """Return daily bars: dicts with date (ISO str), open, high, low, close.

    days=None fetches the full listed history; otherwise the last `days` days.
    Rows with missing close are skipped (Yahoo pads holidays/halts with nulls).
    """
    now = int(time.time())
    period1 = 0 if days is None else now - days * 86400
    data = _get(CHART_URL.format(ticker=ticker, period1=period1, period2=now))
    result = data.get("chart", {}).get("result")
    if not result:
        raise YahooError(f"empty chart result for {ticker}: {data.get('chart', {}).get('error')}")
    result = result[0]
    meta = result["meta"]
    gmtoffset = meta.get("gmtoffset", 0)
    timestamps = result.get("timestamp") or []
    quote = result["indicators"]["quote"][0]

    bars = []
    for i, ts in enumerate(timestamps):
        close = quote["close"][i]
        if close is None:
            continue
        # Shift by the exchange's UTC offset so the bar lands on the local trading date.
        date = datetime.fromtimestamp(ts + gmtoffset, tz=timezone.utc).date().isoformat()
        bars.append({
            "date": date,
            "open": quote["open"][i],
            "high": quote["high"][i],
            "low": quote["low"][i],
            "close": close,
        })
    return bars
