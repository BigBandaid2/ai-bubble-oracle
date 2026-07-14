"""Yield curve: the late-cycle monetary tell. The 10Y-3M spread inverts near
tops; direction DOWN (falling spread = later cycle). The AI era already
inverted deeper than 2000 and has re-steepened, so this is expected to render
as a counter-argument."""

METRIC = {
    "key": "yield_curve", "label": "Yield curve", "parent": "monetary", "order": 10,
    "kind": "curve", "source": ("fred", "T10Y3M"),
    "formula": lambda r: r["value"], "cadence": "daily",
    "type": "absolute_level", "direction": "down", "unit": "pct_spread",
    "unitLabel": "10Y-3M spread",
    "ir": {
        "group": "tn_curve", "group_name": "Yield curve (WIP)", "foreign_from": "CURVE",
        "leaf_chain": {
            "p": "curve", "cadence": "daily",
            "src": {
                "id": "raw.fred_t10y3m", "dbt": "source('fred','T10Y3M')",
                "grain": "one CSV document (daily spread series)",
                "why": "The late-cycle monetary tell: the 10Y minus 3M treasury spread inverts near tops.",
                "desc": "FRED fredgraph.csv for T10Y3M (percent, daily since 1982), keyless, public domain. oracle/sources/fred.py.",
                "tx": "HTTP GET fredgraph.csv?id=T10Y3M", "card": "one document, daily since 1982.",
            },
            "raw": {
                "id": "fred_curve", "grain": "one row per business day",
                "why": "The landed daily spread.",
                "desc": "The T10Y3M slice of fred_series in oracle.db, kept from 1990 on with the committed CSV as outage fallback.",
                "schema": [
                    {"col": "date", "type": "TEXT", "kind": "key", "ex": "{{asOf}}"},
                    {"col": "value", "type": "REAL", "kind": "pass", "ex": {"live": "rawNow"}, "note": "percentage points"},
                ],
                "card": "daily since 1990 (committed CSV fallback).",
            },
            "metricWhy": "Applies the declared formula: the spread itself, direction DOWN.",
            "metricDesc": "Registry: formula = value, type = absolute_level, direction = down: a falling spread means later cycle, so the intensity scale maps inversion toward 1.",
            "metricTx": "value = 10Y minus 3M spread", "metricNote": "pct points",
            "graphWhy": "A deliberate counter-argument: the curve inverted at the 2000 peak, but the AI era already inverted DEEPER in 2023 and has re-steepened, so on this tell the late-cycle moment may have passed. Projection suppressed.",
        },
        "graph": {"vchain": {
            "ids": ["raw.fred_t10y3m", "fred_curve", "stg_curve_filled", "int_curve_metric",
                    "int_curve_smoothed", "int_curve_intensity", "int_curve_validated", "graph.yield_curve"],
            "shorts": {"raw.fred_t10y3m": "raw: fred T10Y3M", "graph.yield_curve": "graph: yield curve"},
        }},
        "source_info": {
            "blurb": "Yield curve (WIP): a Monetary & sentiment leaf, direction DOWN (a falling 10Y-3M spread means later cycle). The curve inverted at the 2000 peak and steepened after. The AI era already inverted DEEPER in 2023 and has re-steepened, so on this tell the late-cycle moment may have passed; the validator suppresses the projection and shows it as a counter-argument.",
            "options": [
                {"t": "10Y-3M vs 10Y-2Y", "d": "T10Y3M is the recession-literature standard and reaches 1982; T10Y2Y exists back to 1976 if a second read is ever wanted."},
            ],
            "ambiguities": [
                {"t": "Which inversion counts", "d": "The 2022-24 inversion was the deepest since 1981 and un-inverted without (so far) a crash, which is exactly why this leaf argues against the analogy rather than for it."},
            ],
            "caveats": [
                {"t": "Daily, business days", "d": "Holidays carry '.' in the raw CSV and are dropped, then forward-filled on the grid."},
            ],
            "cardinality": [
                {"asset": "fred_curve", "count": "daily", "meaning": "Latest {{rawNowF}} pct pts."},
                {"asset": "int_curve_validated", "count": "1 verdict", "meaning": "{{checksPass}}/{{checksN}} checks pass → projection suppressed (moving away from the peak state)."},
                {"asset": "graph.yield_curve", "count": "1 leaf", "meaning": "The monetary counter-argument, kept out of the headline math."},
            ],
        },
    },
}
