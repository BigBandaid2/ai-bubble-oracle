import sqlite3

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS prices (
    ticker TEXT NOT NULL,
    date   TEXT NOT NULL,
    open   REAL,
    high   REAL,
    low    REAL,
    close  REAL NOT NULL,
    PRIMARY KEY (ticker, date)
);

-- Threshold-crossing events, derived deterministically from prices and
-- rebuilt on every update. kind: 'triggered' (drawdown crossed the
-- threshold) or 'recovered' (came back above it).
CREATE TABLE IF NOT EXISTS events (
    condition_key TEXT NOT NULL,
    ticker        TEXT NOT NULL,
    basis         TEXT NOT NULL,
    date          TEXT NOT NULL,
    kind          TEXT NOT NULL,
    drawdown      REAL NOT NULL,
    price         REAL NOT NULL,
    ath           REAL NOT NULL,
    PRIMARY KEY (condition_key, ticker, basis, date, kind)
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- H100 rental price readings, one row per (date, index_type).
-- index_type: 'neocloud' (spot-like marketplace, the SDH100RT tier; live Vast.ai
--             proxy) or 'hyperscaler' (reserved/committed tier, ~3x pricier).
-- source: 'vast_proxy' (Vast.ai on-demand median) or 'silicondata_published'
--         (index values quoted in public SiliconData posts).
CREATE TABLE IF NOT EXISTS h100_prices (
    date       TEXT NOT NULL,
    index_type TEXT NOT NULL,
    source     TEXT NOT NULL,
    usd_hr     REAL NOT NULL,
    low        REAL,
    n          INTEGER,
    PRIMARY KEY (date, index_type)
);
"""


def _migrate(conn):
    # h100_prices gained an index_type column + composite PK. Old rows are
    # fully regenerable (seeds + proxy), so drop and let SCHEMA recreate.
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(h100_prices)").fetchall()]
    if cols and "index_type" not in cols:
        conn.execute("DROP TABLE h100_prices")
        conn.executescript(SCHEMA)
        conn.commit()


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def upsert_prices(conn, ticker, bars):
    conn.executemany(
        "INSERT OR REPLACE INTO prices (ticker, date, open, high, low, close) VALUES (?, ?, ?, ?, ?, ?)",
        [(ticker, b["date"], b["open"], b["high"], b["low"], b["close"]) for b in bars],
    )
    conn.commit()


def load_prices(conn, ticker):
    return conn.execute(
        "SELECT date, open, high, low, close FROM prices WHERE ticker = ? ORDER BY date",
        (ticker,),
    ).fetchall()


def has_prices(conn, ticker):
    row = conn.execute("SELECT 1 FROM prices WHERE ticker = ? LIMIT 1", (ticker,)).fetchone()
    return row is not None


def replace_events(conn, events):
    conn.execute("DELETE FROM events")
    conn.executemany(
        "INSERT OR REPLACE INTO events (condition_key, ticker, basis, date, kind, drawdown, price, ath)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        events,
    )
    conn.commit()


def upsert_h100(conn, date, index_type, source, usd_hr, low=None, n=None):
    conn.execute(
        "INSERT OR REPLACE INTO h100_prices (date, index_type, source, usd_hr, low, n)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (date, index_type, source, usd_hr, low, n),
    )
    conn.commit()


def load_h100(conn, index_type=None):
    if index_type is None:
        return conn.execute(
            "SELECT date, index_type, source, usd_hr, low, n FROM h100_prices ORDER BY date"
        ).fetchall()
    return conn.execute(
        "SELECT date, index_type, source, usd_hr, low, n FROM h100_prices"
        " WHERE index_type = ? ORDER BY date",
        (index_type,),
    ).fetchall()


def set_meta(conn, key, value):
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))
    conn.commit()


def get_meta(conn, key):
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None
