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

-- Daily YES-probability of the Polymarket market itself (the contract's own
-- implied chance of resolving YES), one row per UTC date.
CREATE TABLE IF NOT EXISTS polymarket_prices (
    date     TEXT PRIMARY KEY,
    yes_prob REAL NOT NULL
);

-- Daily CourtListener bankruptcy-docket scans, one row per (date, entity).
-- candidates = Chapter 7/11 dockets whose case name contains the entity name;
-- a candidate only makes the condition met after human confirmation (config).
CREATE TABLE IF NOT EXISTS bankruptcy_checks (
    date       TEXT NOT NULL,
    entity     TEXT NOT NULL,
    candidates INTEGER NOT NULL,
    PRIMARY KEY (date, entity)
);

-- Raw inputs for the bankruptcy-buzz coefficient, one row per (date, entity).
-- news_share: GDELT daily volume share (% of global coverage) for
--             "<entity>" + bankruptcy-flavored keywords (backfillable).
-- dockets_total: total federal dockets naming the entity (litigation pulse;
--                accumulates from the first scan; NULL for backfilled days).
CREATE TABLE IF NOT EXISTS buzz_signals (
    date          TEXT NOT NULL,
    entity        TEXT NOT NULL,
    news_share    REAL,
    dockets_total INTEGER,
    PRIMARY KEY (date, entity)
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


def upsert_polymarket(conn, rows):
    conn.executemany(
        "INSERT OR REPLACE INTO polymarket_prices (date, yes_prob) VALUES (?, ?)", rows
    )
    conn.commit()


def load_polymarket(conn):
    return conn.execute(
        "SELECT date, yes_prob FROM polymarket_prices ORDER BY date"
    ).fetchall()


def upsert_bankruptcy(conn, date, entity, candidates):
    conn.execute(
        "INSERT OR REPLACE INTO bankruptcy_checks (date, entity, candidates) VALUES (?, ?, ?)",
        (date, entity, candidates),
    )
    conn.commit()


def load_bankruptcy(conn, entity=None):
    if entity is None:
        return conn.execute(
            "SELECT date, entity, candidates FROM bankruptcy_checks ORDER BY date"
        ).fetchall()
    return conn.execute(
        "SELECT date, entity, candidates FROM bankruptcy_checks WHERE entity = ? ORDER BY date",
        (entity,),
    ).fetchall()


def upsert_buzz_news(conn, entity, pairs):
    """Upsert (date, news_share) rows, preserving any dockets_total already set."""
    conn.executemany(
        "INSERT INTO buzz_signals (date, entity, news_share) VALUES (?, ?, ?)"
        " ON CONFLICT(date, entity) DO UPDATE SET news_share = excluded.news_share",
        [(d, entity, v) for d, v in pairs],
    )
    conn.commit()


def upsert_buzz_dockets(conn, date, entity, total):
    conn.execute(
        "INSERT INTO buzz_signals (date, entity, dockets_total) VALUES (?, ?, ?)"
        " ON CONFLICT(date, entity) DO UPDATE SET dockets_total = excluded.dockets_total",
        (date, entity, total),
    )
    conn.commit()


def load_buzz(conn, entity):
    return conn.execute(
        "SELECT date, news_share, dockets_total FROM buzz_signals WHERE entity = ? ORDER BY date",
        (entity,),
    ).fetchall()


def set_meta(conn, key, value):
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))
    conn.commit()


def get_meta(conn, key):
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None
