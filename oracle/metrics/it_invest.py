"""IT investment share: private fixed investment in information processing
equipment + software as a share of GDP. Indexed to each era's own start
(ratio_from_start): how much the share has grown since ChatGPT versus its
dot-com run-up, not the absolute level."""

METRIC = {
    "key": "it_invest", "label": "IT investment share", "parent": "capex", "order": 10,
    "kind": "it_invest",
    "series": {"it": ("fred", "A679RC1Q027SBEA"), "gdp": ("fred", "GDP")},
    "formula": lambda r: r["it"] / r["gdp"] * 100.0, "cadence": "quarterly",
    "type": "ratio_from_start", "direction": "up", "unit": "pct_gdp",
    "unitLabel": "% of GDP",
    "ir": {
        "group": "tn_it_invest", "group_name": "IT investment share (WIP)", "foreign_from": "IT INVEST",
        "leaf_chain": {
            "p": "it", "cadence": "quarterly",
            "src": {
                "id": "raw.fred_a679", "dbt": "source('fred','A679RC1Q027SBEA')",
                "grain": "one CSV document (quarterly NIPA series)",
                "why": "The economy-wide capex commitment to the boom's tooling: private fixed investment in information processing equipment and software.",
                "desc": "FRED fredgraph.csv for A679RC1Q027SBEA ($bn SAAR), keyless, public domain, quarterly since 1947. oracle/sources/fred.py.",
                "tx": "HTTP GET fredgraph.csv?id=A679RC1Q027SBEA", "card": "one document, quarterly since 1947.",
            },
            "raw": {
                "id": "fred_gdp", "grain": "one row per quarter",
                "why": "The denominator, homed in this pipeline and reused (dimmed) by the Buffett leaf.",
                "desc": "Nominal GDP ($bn SAAR) from fredgraph.csv?id=GDP, the same keyless tap. Landed in fred_series beside every other series.",
                "schema": [
                    {"col": "date", "type": "TEXT", "kind": "key", "ex": "2026-01-01"},
                    {"col": "value", "type": "REAL", "kind": "pass", "ex": 31865.7, "note": "nominal GDP $bn SAAR"},
                ],
                "card": "quarterly since 1990 (committed CSV fallback).",
            },
            "stgUpstream": ["raw.fred_a679", "fred_gdp"],
            "metricWhy": "The declared composite formula: IT investment as a share of GDP.",
            "metricDesc": "Registry: series {it: A679RC1Q027SBEA, gdp: GDP}, formula = it ÷ gdp × 100, inner-joined on the shared quarterly dates. type = ratio_from_start: each era is indexed to its own starting share, so this reads how much the IT-investment share has grown since ChatGPT versus its dot-com run-up.",
            "metricTx": "value = IT investment ÷ GDP × 100", "metricNote": "% of GDP",
            "graphWhy": "The capex pillar's share-of-economy read. Indexed to each era's own start, the AI-era run-up in IT-investment share tracks a similar mid-cycle point to the dot-com build-out.",
        },
        "graph": {"join": {
            "tops": [{"id": "raw.fred_a679"}, {"id": "fred_gdp"}],
            "ids": ["stg_it_filled", "int_it_metric", "int_it_smoothed",
                    "int_it_intensity", "int_it_validated", "graph.it_invest"],
            "shorts": {"raw.fred_a679": "raw: fred A679 (IT invest)", "graph.it_invest": "graph: IT invest share"},
        }},
        "source_info": {
            "blurb": "IT investment share (WIP): a Capex leaf. Private fixed investment in information processing equipment and software as a share of nominal GDP (both BEA series via FRED). Indexed to each era's own start, so it reads how much the share has GROWN since ChatGPT versus its dot-com run-up rather than the absolute level. On that framing it conforms, mid-cycle.",
            "options": [
                {"t": "Share, not dollars", "d": "Nominal dollars across 30 years mean nothing; the share of GDP is the honest cross-era normalization, declared as absolute_level."},
            ],
            "ambiguities": [
                {"t": "Software got bigger", "d": "The category mixes hardware and software; software's secular growth lifts the baseline share independent of any bubble, which is one reason the absolute level is misleading and the run-up-since-start framing is used instead."},
            ],
            "caveats": [
                {"t": "Quarterly NIPA revisions", "d": "BEA revises; the edge quarters can move after the fact."},
                {"t": "GDP homed here", "d": "The GDP slice lives in this pipeline and is reused (dimmed) by the Buffett leaf."},
            ],
            "cardinality": [
                {"asset": "fred_gdp", "count": "quarterly", "meaning": "Nominal GDP, the shared denominator."},
                {"asset": "int_it_intensity", "count": "1:1", "meaning": "Intensity {{intensityPct}}% of the dot-com run-up (0 = its own start, 1 = the 2000 peak)."},
                {"asset": "int_it_validated", "count": "1 verdict", "meaning": "{{checksPass}}/{{checksN}} checks pass → {{verdictLong}}."},
                {"asset": "graph.it_invest", "count": "1 leaf", "meaning": "The IT-share run-up leaf; projected top {{projDash}}."},
            ],
        },
    },
}
