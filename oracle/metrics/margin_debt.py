"""Margin debt: the leverage behind the trade. Broker-dealer margin loans
(Z.1). Nominal dollars, so each era is indexed to its own start (ratio) rather
than compared raw across 30 years of inflation."""

METRIC = {
    "key": "margin_debt", "label": "Margin debt", "parent": "speculation", "order": 10,
    "kind": "margin", "source": ("fred", "BOGZ1FL663067003Q"),
    "formula": lambda r: r["value"] / 1000.0, "cadence": "quarterly",
    "type": "ratio_from_start", "direction": "up", "unit": "usd_bn",
    "unitLabel": "Margin loans $bn",
    "ir": {
        "group": "tn_margin", "group_name": "Margin debt (WIP)", "foreign_from": "MARGIN",
        "leaf_chain": {
            "p": "margin", "cadence": "quarterly",
            "src": {
                "id": "raw.fred_z1margin", "dbt": "source('fred','BOGZ1FL663067003Q')",
                "grain": "one CSV document (quarterly Z.1 series)",
                "why": "The leverage behind the trade: broker-dealer margin loans from the Fed's Z.1 accounts, the only open margin series that reaches 1995.",
                "desc": "FRED fredgraph.csv for BOGZ1FL663067003Q (security brokers and dealers, margin loans and other receivables, $mn), keyless, public domain, quarterly since 1945. FINRA's monthly series is the cross-check but starts 1997-01 and its terms bar committing a copy. oracle/sources/fred.py.",
                "tx": "HTTP GET fredgraph.csv?id=BOGZ1FL663067003Q", "card": "one document, quarterly since 1945.",
            },
            "raw": {
                "id": "fred_margin", "grain": "one row per quarter",
                "why": "The landed margin-loans series.",
                "desc": "The Z.1 slice of fred_series in oracle.db. Caveat carried honestly: the line includes 'other receivables', so it is a proxy for pure margin debt.",
                "schema": [
                    {"col": "date", "type": "TEXT", "kind": "key", "ex": "2026-01-01"},
                    {"col": "value", "type": "REAL", "kind": "pass", "ex": {"live": "rawNow", "scale": 1000}, "note": "$mn, quarter end"},
                ],
                "card": "quarterly since 1990 (committed CSV fallback).",
            },
            "metricWhy": "Applies the declared formula: loans scaled to billions.",
            "metricDesc": "Registry: formula = value ÷ 1000 ($bn), type = ratio_from_start: nominal dollars, so each era is indexed to its own start rather than compared raw across 30 years of inflation.",
            "metricTx": "value = margin loans $mn ÷ 1000", "metricNote": "$bn",
            "graphWhy": "The speculation pillar's leverage leaf: margin balances tripled into the exact 2000 top. The AI era is up about 1.6x, mid-cycle on this measure.",
        },
        "graph": {"vchain": {
            "ids": ["raw.fred_z1margin", "fred_margin", "stg_margin_filled", "int_margin_metric",
                    "int_margin_smoothed", "int_margin_intensity", "int_margin_validated", "graph.margin_debt"],
            "shorts": {"raw.fred_z1margin": "raw: fred Z.1 margin", "graph.margin_debt": "graph: margin debt"},
        }},
        "source_info": {
            "blurb": "Margin debt (WIP): the Speculation branch's leverage leaf. Broker-dealer margin loans from the Fed's Z.1 accounts, quarterly back to 1945, the only open margin series that reaches the 1995 era start. Balances tripled into the exact 2000 top; the AI era is up about 1.6x, mid-cycle on this measure.",
            "options": [
                {"t": "Z.1 vs FINRA", "d": "FINRA publishes monthly margin statistics, but the series starts 1997-01 (after the declared era start) and FINRA's terms bar committing a copy, so the Z.1 series is wired and FINRA remains the monthly cross-check."},
            ],
            "ambiguities": [
                {"t": "Proxy width", "d": "The Z.1 line includes 'other receivables' beside pure margin loans; treat levels as a proxy, trends as the signal."},
            ],
            "caveats": [
                {"t": "Quarterly lag", "d": "About one quarter behind; the AI edge forward-fills the latest published quarter."},
            ],
            "cardinality": [
                {"asset": "fred_margin", "count": "quarterly", "meaning": "Latest ~${{rawNowF}}bn."},
                {"asset": "int_margin_intensity", "count": "1:1", "meaning": "Intensity {{intensityPct}}% of the dot-com leverage run."},
                {"asset": "int_margin_validated", "count": "1 verdict", "meaning": "{{checksPass}}/{{checksN}} checks pass → conforms."},
                {"asset": "graph.margin_debt", "count": "1 leaf", "meaning": "Projected top {{projDash}}; reads early, which drags the branch date late."},
            ],
        },
    },
}
