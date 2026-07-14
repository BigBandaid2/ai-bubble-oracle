"""Semiconductor production: the picks-and-shovels output index (chips carried
both booms: fabs then, GPUs now). NOTE: quality-adjusted chip VOLUME grew
straight through the 2001 bust (the crash was in dollars), so this leaf is
expected to render as an honest counter-argument."""

METRIC = {
    "key": "semis", "label": "Semiconductor production", "parent": "capex", "order": 30,
    "kind": "semis", "source": ("fred", "IPG3344S"),
    "formula": lambda r: r["value"], "cadence": "monthly",
    "type": "ratio_from_start", "direction": "up", "unit": "ip_index",
    "unitLabel": "Semis production",
    "ir": {
        "group": "tn_semis", "group_name": "Semiconductor production (WIP)", "foreign_from": "SEMIS",
        "leaf_chain": {
            "p": "semis", "cadence": "monthly",
            "src": {
                "id": "raw.fred_ipg3344s", "dbt": "source('fred','IPG3344S')",
                "grain": "one CSV document (monthly industrial production series)",
                "why": "The picks-and-shovels output index: chips carried both booms (fabs then, GPUs now).",
                "desc": "FRED fredgraph.csv for IPG3344S (industrial production, semiconductors and other electronic components, index), keyless, public domain, monthly since 1972. oracle/sources/fred.py.",
                "tx": "HTTP GET fredgraph.csv?id=IPG3344S", "card": "one document, monthly since 1972.",
            },
            "raw": {
                "id": "fred_semis", "grain": "one row per month",
                "why": "The landed production index.",
                "desc": "The IPG3344S slice of fred_series in oracle.db, kept from 1990 on with the committed CSV as outage fallback.",
                "schema": [
                    {"col": "date", "type": "TEXT", "kind": "key", "ex": "2026-05-01"},
                    {"col": "value", "type": "REAL", "kind": "pass", "ex": {"live": "rawNow"}, "note": "index, 2017=100"},
                ],
                "card": "monthly since 1990 (committed CSV fallback).",
            },
            "metricWhy": "Applies the declared formula: the index itself.",
            "metricDesc": "Registry: formula = value, type = ratio_from_start: a volume index, so each era is measured by its own growth.",
            "metricTx": "value = production index", "metricNote": "2017=100",
            "graphWhy": "An honest counter-argument by design: quality-adjusted chip VOLUME grew straight through the 2001 bust (the crash was in dollars), so this series never had the rise-peak-fall shape and its projection is suppressed. The dollar cycle lives in the tech-orders leaf.",
        },
        "graph": {"vchain": {
            "ids": ["raw.fred_ipg3344s", "fred_semis", "stg_semis_filled", "int_semis_metric",
                    "int_semis_smoothed", "int_semis_intensity", "int_semis_validated", "graph.semis"],
            "shorts": {"raw.fred_ipg3344s": "raw: fred IPG3344S", "graph.semis": "graph: semis production"},
        }},
        "source_info": {
            "blurb": "Semiconductor production (WIP): a Capex leaf kept as an honest counter-argument. Industrial production of semiconductors and components (Fed, monthly since 1972). Quality-adjusted chip VOLUME grew straight through the 2001 bust (the crash was in dollars), so the series never had a rise-peak-fall shape and its projection is suppressed. That is a finding, not a failure.",
            "options": [
                {"t": "Volume vs dollars", "d": "WSTS publishes dollar billings (monthly, 1986+) that DID crash 32% in 2001, but its file prohibits reproduction and the URL rotates monthly, so the public-domain volume index is wired and WSTS is cited here instead."},
            ],
            "ambiguities": [
                {"t": "What counts as the chip cycle", "d": "Volume says the buildout never stopped; dollars say it crashed. Both are true. The dollar cycle lives in the tech-orders leaf; this leaf shows the volume truth."},
            ],
            "caveats": [
                {"t": "Index, not dollars", "d": "2017=100, quality-adjusted; Moore's law makes long spans grow relentlessly."},
            ],
            "cardinality": [
                {"asset": "fred_semis", "count": "monthly", "meaning": "Latest index {{rawNowF}}."},
                {"asset": "int_semis_validated", "count": "1 verdict", "meaning": "{{checksPass}}/{{checksN}} checks pass → projection suppressed (no interior peak in the reference era)."},
                {"asset": "graph.semis", "count": "1 leaf", "meaning": "Shown for context beside the conforming orders leaf."},
            ],
        },
    },
}
