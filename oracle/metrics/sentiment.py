"""Consumer sentiment: the Main Street euphoria check. Michigan sentiment hit
all-time highs into the 2000 peak; today it sits near record lows. Expected
counter-argument. minRange relaxes the dynamic-range gate: a bounded survey
index moves less than a price, and the check detail prints the actual %."""

METRIC = {
    "key": "sentiment", "label": "Consumer sentiment", "parent": "monetary", "order": 20,
    "kind": "sentiment", "source": ("fred", "UMCSENT"),
    "formula": lambda r: r["value"], "cadence": "monthly",
    "type": "absolute_level", "direction": "up", "unit": "umich_index",
    "unitLabel": "UMich sentiment", "minRange": 0.08,
    "ir": {
        "group": "tn_sentiment", "group_name": "Consumer sentiment (WIP)", "foreign_from": "SENTIMENT",
        "leaf_chain": {
            "p": "sent", "cadence": "monthly",
            "src": {
                "id": "raw.fred_umcsent", "dbt": "source('fred','UMCSENT')",
                "grain": "one CSV document (monthly survey index)",
                "why": "The Main Street euphoria check: University of Michigan consumer sentiment.",
                "desc": "FRED fredgraph.csv for UMCSENT (index, monthly since 1952, 1-2 month publication lag), keyless, public domain. oracle/sources/fred.py.",
                "tx": "HTTP GET fredgraph.csv?id=UMCSENT", "card": "one document, monthly since 1952.",
            },
            "raw": {
                "id": "fred_sentiment", "grain": "one row per month",
                "why": "The landed sentiment index.",
                "desc": "The UMCSENT slice of fred_series in oracle.db, kept from 1990 on with the committed CSV as outage fallback.",
                "schema": [
                    {"col": "date", "type": "TEXT", "kind": "key", "ex": "2026-05-01"},
                    {"col": "value", "type": "REAL", "kind": "pass", "ex": {"live": "rawNow"}, "note": "1966Q1 = 100"},
                ],
                "card": "monthly since 1990 (committed CSV fallback).",
            },
            "metricWhy": "Applies the declared formula: the index itself, with a relaxed range gate.",
            "metricDesc": "Registry: formula = value, type = absolute_level, minRange = 0.08: a bounded survey index moves less than a price, and the check detail prints the actual % so nothing hides.",
            "metricTx": "value = sentiment index", "metricNote": "1966Q1 = 100",
            "graphWhy": "The strongest counter-argument on the page: sentiment hit all-time highs into the 2000 peak, but the AI era's readings sit near record LOWS and falling. Whatever this boom is, Main Street euphoria is not part of it. Projection suppressed.",
        },
        "graph": {"vchain": {
            "ids": ["raw.fred_umcsent", "fred_sentiment", "stg_sent_filled", "int_sent_metric",
                    "int_sent_smoothed", "int_sent_intensity", "int_sent_validated", "graph.sentiment"],
            "shorts": {"raw.fred_umcsent": "raw: fred UMCSENT", "graph.sentiment": "graph: sentiment"},
        }},
        "source_info": {
            "blurb": "Consumer sentiment (WIP): a Monetary & sentiment leaf and the strongest counter-argument on the page. Michigan sentiment ran at all-time highs into the 2000 peak; the AI era's readings sit near record LOWS and falling. Whatever this boom is, Main Street euphoria is not part of it. Projection suppressed.",
            "options": [
                {"t": "Relaxed range gate", "d": "A bounded survey index moves less than a price, so this metric declares minRange 0.08 instead of the default 0.2; the check detail prints the actual movement so nothing hides."},
            ],
            "ambiguities": [
                {"t": "Whose euphoria", "d": "The dot-com bubble was a retail mania; the AI boom is, so far, an institutional capex cycle. This leaf is where that difference shows up in data."},
            ],
            "caveats": [
                {"t": "Deep negative intensity", "d": "On dot-com anchors today's sentiment maps far below 0 intensity, which is why its card reads a large negative percent. That is the honest arithmetic, not a glitch."},
            ],
            "cardinality": [
                {"asset": "fred_sentiment", "count": "monthly", "meaning": "Latest {{rawNowF}} (1966Q1=100)."},
                {"asset": "int_sent_validated", "count": "1 verdict", "meaning": "{{checksPass}}/{{checksN}} checks pass → projection suppressed (moving away from the peak state)."},
                {"asset": "graph.sentiment", "count": "1 leaf", "meaning": "The no-euphoria counter-argument."},
            ],
        },
    },
}
