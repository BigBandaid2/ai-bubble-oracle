"""Tech equipment orders: the dollar capex cycle that DID rise, peak, and
crash in 2000-2002. Manufacturers' new orders for computers and electronic
products (excludes semiconductor orders, a Census reporting gap; the semis
volume leaf covers chips)."""

METRIC = {
    "key": "tech_orders", "label": "Tech equipment orders", "parent": "capex", "order": 20,
    "kind": "tech_orders", "source": ("fred", "A34SNO"),
    "formula": lambda r: r["value"] / 1000.0, "cadence": "monthly",
    "type": "ratio_from_start", "direction": "up", "unit": "usd_bn",
    "unitLabel": "Tech orders $bn",
    "ir": {
        "group": "tn_tech_orders", "group_name": "Tech equipment orders (WIP)", "foreign_from": "ORDERS",
        "leaf_chain": {
            "p": "orders", "cadence": "monthly",
            "src": {
                "id": "raw.fred_a34sno", "dbt": "source('fred','A34SNO')",
                "grain": "one CSV document (monthly M3 survey series)",
                "why": "The dollar capex cycle that actually rose, peaked, and crashed in 2000-2002: manufacturers' new orders for computers and electronic products.",
                "desc": "FRED fredgraph.csv for A34SNO ($mn SA), keyless, public domain, monthly since 1992. Census notes the M3 survey EXCLUDES semiconductor orders, which is why the semis leaf exists separately. oracle/sources/fred.py.",
                "tx": "HTTP GET fredgraph.csv?id=A34SNO", "card": "one document, monthly since 1992.",
            },
            "raw": {
                "id": "fred_orders", "grain": "one row per month",
                "why": "The landed monthly orders series.",
                "desc": "The A34SNO slice of fred_series in oracle.db, kept from 1990 on with the committed CSV as outage fallback.",
                "schema": [
                    {"col": "date", "type": "TEXT", "kind": "key", "ex": "2000-03-01"},
                    {"col": "value", "type": "REAL", "kind": "pass", "ex": {"live": "rawNow", "scale": 1000}, "note": "orders $mn SA"},
                ],
                "card": "monthly since 1990 (committed CSV fallback).",
            },
            "metricWhy": "Applies the declared formula: orders scaled to billions.",
            "metricDesc": "Registry: formula = value ÷ 1000 ($bn), type = ratio_from_start: nominal dollars, so each era is indexed to its own start.",
            "metricTx": "value = orders $mn ÷ 1000", "metricNote": "$bn",
            "graphWhy": "The conforming capex leaf: tech equipment orders rose about 40% into mid-2000, crashed about 40% by 2002, and are rising again in the AI era.",
        },
        "graph": {"vchain": {
            "ids": ["raw.fred_a34sno", "fred_orders", "stg_orders_filled", "int_orders_metric",
                    "int_orders_smoothed", "int_orders_intensity", "int_orders_validated", "graph.tech_orders"],
            "shorts": {"raw.fred_a34sno": "raw: fred A34SNO", "graph.tech_orders": "graph: tech orders"},
        }},
        "source_info": {
            "blurb": "Tech equipment orders (WIP): the conforming Capex leaf. Manufacturers' new orders for computers and electronic products (Census M3 via FRED): the dollar capex cycle that rose about 40% into mid-2000, crashed about 40% by 2002, and is rising again now. Indexed to each era's start.",
            "options": [
                {"t": "Orders vs shipments", "d": "New orders lead shipments and read intent; the shipments series exists (A34SVS) if the leading edge ever looks too noisy."},
            ],
            "ambiguities": [
                {"t": "Semis excluded", "d": "The M3 survey does not collect semiconductor orders (a Census reporting gap), which is exactly why the semis production leaf exists beside this one."},
            ],
            "caveats": [
                {"t": "Nominal dollars", "d": "ratio_from_start handles the inflation drift by indexing each era to itself."},
            ],
            "cardinality": [
                {"asset": "fred_orders", "count": "monthly", "meaning": "Latest ~${{rawNowF}}bn/mo."},
                {"asset": "int_orders_intensity", "count": "1:1", "meaning": "Intensity {{intensityPct}}% of the dot-com run."},
                {"asset": "int_orders_validated", "count": "1 verdict", "meaning": "{{checksPass}}/{{checksN}} checks pass → conforms."},
                {"asset": "graph.tech_orders", "count": "1 leaf", "meaning": "Projected top {{projDash}}; currently carries the Capex branch date."},
            ],
        },
    },
}
