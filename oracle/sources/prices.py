"""The equity-prices source: split-adjusted daily closes from Yahoo Finance.

The actual fetch loop lives in main.py's cmd_update: the ticker set unions the
condition tickers, the S&P context series, and every ticker the active metric
registry requires, and one paced loop is the polite way to hit Yahoo. This
module contributes the SOURCE spec so metric declarations can reference kind
"prices", plus the loader the engine reads through.

Yahoo's data is unofficial and not redistributable, so nothing is committed:
redistributable=False, csv=None. The db is rebuilt by fetching on each run
(full history on first run, a 90-day top-up after).
"""

from .. import db

SOURCE = {
    "kind": "prices", "label": "Yahoo Finance daily closes",
    "requires": [], "redistributable": False, "csv": None,
    "ddl": None, "order": 10, "date_col": "date", "value_col": "close",
    "update": None,   # fetched by main.py's paced ticker loop
    "load": lambda conn, arg: db.load_prices(conn, arg),
}
