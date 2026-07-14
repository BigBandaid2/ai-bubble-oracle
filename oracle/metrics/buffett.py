"""Market cap to GDP (the Buffett indicator): nonfinancial corporate equities
(Z.1, $mn) over nominal GDP ($bn). Indexed to each era's own start
(ratio_from_start), so it measures how much the ratio has RUN UP since ChatGPT
versus its dot-com run-up, rather than comparing absolute levels across eras
(which structural shifts make less comparable)."""

METRIC = {
    "key": "buffett", "label": "Market cap to GDP", "parent": "valuation", "order": 30,
    "kind": "buffett",
    "series": {"eq": ("fred", "NCBEILQ027S"), "gdp": ("fred", "GDP")},
    "formula": lambda r: (r["eq"] / 1000.0) / r["gdp"], "cadence": "quarterly",
    "type": "ratio_from_start", "direction": "up", "unit": "mktcap_gdp",
    "unitLabel": "x GDP",
    "ir": {
        "group": "tn_buffett", "group_name": "Market cap to GDP (WIP)", "foreign_from": "BUFFETT",
        "leaf_chain": {
            "p": "bf", "cadence": "quarterly",
            "src": {
                "id": "raw.fred_ncbeilq", "dbt": "source('fred','NCBEILQ027S')",
                "grain": "one CSV document (quarterly Z.1 series)",
                "why": "The Buffett-indicator numerator: nonfinancial corporate equities at market value, from the Fed's Z.1 financial accounts.",
                "desc": "FRED fredgraph.csv for NCBEILQ027S, keyless, public domain. Quarterly since 1945; ~1 quarter of Z.1 publication lag. oracle/sources/fred.py.",
                "tx": "HTTP GET fredgraph.csv?id=NCBEILQ027S", "card": "one document, quarterly since 1945.",
            },
            "raw": {
                "id": "fred_equities", "grain": "one row per quarter",
                "why": "The landed numerator; the GDP denominator lives in the IT-investment pipeline and is shown dimmed in this graph.",
                "desc": "The NCBEILQ027S slice of fred_series ($mn, quarter end), joined at metric time with the GDP slice ($bn) fetched by the same tap.",
                "schema": [
                    {"col": "date", "type": "TEXT", "kind": "key", "ex": "2026-01-01", "note": "quarter start stamp"},
                    {"col": "value", "type": "REAL", "kind": "pass", "ex": 69511628, "note": "equities market value $mn"},
                ],
                "card": "quarterly since 1990 (committed CSV fallback).",
            },
            "stgUpstream": ["fred_equities", "fred_gdp"],
            "metricWhy": "The declared composite formula: equities market value over GDP.",
            "metricDesc": "Registry: series {eq: NCBEILQ027S, gdp: GDP}, formula = (eq ÷ 1000) ÷ gdp, inner-joined on the shared quarterly dates. type = ratio_from_start: each era is indexed to its own starting ratio, so this reads how far market-cap-to-GDP has run up since ChatGPT versus its dot-com run-up.",
            "metricTx": "value = (equities $mn ÷ 1000) ÷ GDP $bn", "metricNote": "x GDP",
            "graphWhy": "The most famous single bubble gauge. Indexed to each era's own start, its run-up since ChatGPT is a fraction of the dot-com blow-off, so on this framing the valuation cycle still reads early.",
        },
        "graph": {"join": {
            "tops": [{"id": "raw.fred_ncbeilq"}, {"id": "fred_gdp", "foreign": True}],
            "ids": ["fred_equities", "stg_bf_filled", "int_bf_metric", "int_bf_smoothed",
                    "int_bf_intensity", "int_bf_validated", "graph.buffett"],
            "shorts": {"raw.fred_ncbeilq": "raw: fred NCBEILQ", "graph.buffett": "graph: mkt cap to GDP"},
        }},
        "source_info": {
            "blurb": "Market cap to GDP (WIP): the Buffett indicator as a Valuation leaf. Nonfinancial corporate equities (Fed Z.1) over nominal GDP, indexed to each era's own start so it reads the RUN-UP since ChatGPT versus the dot-com run-up rather than the absolute level. On that framing it conforms and reads early: the AI-era valuation cycle has run up far less than 1995-2000 did.",
            "options": [
                {"t": "Numerator choice", "d": "Nonfinancial corporate equities (NCBEILQ027S), the classic Buffett numerator. The all-sectors Z.1 series exists too and reads even higher; using the narrower one is the conservative pick."},
            ],
            "ambiguities": [
                {"t": "Beyond the peak means what?", "d": "Reading above the 2000 level can argue 'crash overdue' or 'structurally different economy' (more intangibles, more foreign revenue). The page shows the number and the suppressed projection; the reader picks the story."},
            ],
            "caveats": [
                {"t": "Quarterly with a lag", "d": "Z.1 publishes about one quarter behind, so the AI-era edge is the latest published quarter, forward-filled."},
                {"t": "Public domain", "d": "Both series are US-government data via FRED's keyless CSV endpoint; the committed fallback CSV is redistribution-safe."},
            ],
            "cardinality": [
                {"asset": "fred_equities", "count": "quarterly", "meaning": "Equities market value, $mn (2026Q1 about $69.5T)."},
                {"asset": "int_bf_intensity", "count": "1:1", "meaning": "Intensity {{intensityPct}}% of the dot-com run-up (0 = its own start, 1 = the 2000 peak)."},
                {"asset": "int_bf_validated", "count": "1 verdict", "meaning": "{{checksPass}}/{{checksN}} checks pass → {{verdictLong}}."},
                {"asset": "graph.buffett", "count": "1 leaf", "meaning": "The valuation-vs-GDP run-up leaf; projected top {{projDash}}, feeding the Valuation blend."},
            ],
        },
    },
}
