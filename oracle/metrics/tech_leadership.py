"""Tech leadership: how far the tech-heavy index outruns the broad market.
The concentration / narrow-leadership proxy, computable daily back to the
1970s from data already in the warehouse."""

METRIC = {
    "key": "tech_leadership", "label": "Tech leadership", "parent": "market_concentration", "order": 10,
    "kind": "tech_leadership",
    "series": {"ixic": ("prices", "^IXIC"), "gspc": ("prices", "^GSPC")},
    "formula": lambda r: r["ixic"] / r["gspc"], "cadence": "daily",
    "type": "ratio_from_start", "direction": "up", "unit": "ixic_gspc_ratio",
    "unitLabel": "Nasdaq/S&P ratio",
    "ir": {
        "group": "tn_tech_leadership", "group_name": "Tech leadership (WIP)", "foreign_from": "TECH LEAD",
        "leaf_chain": {
            "p": "ratio", "cadence": "daily",
            "src": None, "raw": None,
            "stgUpstream": ["ixic_prices", "gspc_prices"],
            "stgDesc": "Joins the two index closes (both already landed by their own pipelines, shown dimmed here), trims to the era windows, and forward-fills non-trading days. _grid + _fill.",
            "metricWhy": "The declared composite formula: how far the tech-heavy index outruns the broad market.",
            "metricDesc": "Registry: series {ixic: ^IXIC, gspc: ^GSPC}, formula = ixic ÷ gspc, inner-joined on trading days. type = ratio_from_start: each era is indexed to its own starting ratio, so this reads pure narrowing of leadership.",
            "metricTx": "value = ^IXIC close ÷ ^GSPC close", "metricNote": "index ratio",
            "graphWhy": "The concentration pillar's live leaf: narrow leadership is the hallmark of both booms, and this ratio is computable daily back to the 1970s from data already in the warehouse.",
        },
        "graph": {"join": {
            "tops": [{"id": "ixic_prices", "foreign": True}, {"id": "gspc_prices", "foreign": True}],
            "ids": ["stg_ratio_filled", "int_ratio_metric", "int_ratio_smoothed",
                    "int_ratio_intensity", "int_ratio_validated", "graph.tech_leadership"],
            "shorts": {"graph.tech_leadership": "graph: tech leadership"},
        }},
        "source_info": {
            "blurb": "Tech leadership (WIP): the Market-concentration leaf. The Nasdaq Composite divided by the S&P 500, each era indexed to its own starting ratio, so it reads pure narrowing of leadership: how far the tech-heavy index outruns the broad market. Both inputs are already in the warehouse, so this pipeline adds no new source.",
            "options": [
                {"t": "Proxy choice", "d": "Index-ratio leadership rather than literal top-10 cap-weight share: cap-weight history for 1995-2002 is not openly available, and the ratio is computable daily from open data. The direction of the story is the same."},
            ],
            "ambiguities": [
                {"t": "Composition drift", "d": "Both indexes rebalance over decades; the ratio measures the tech tilt of the market as traded, not a fixed basket."},
            ],
            "caveats": [
                {"t": "Inputs shown dimmed", "d": "^IXIC and ^GSPC closes come from the Nasdaq and S&P pipelines; this chain starts at the join."},
            ],
            "cardinality": [
                {"asset": "stg_ratio_filled", "count": "{{dotWk}}+{{aiWk}}", "meaning": "Daily joined ratio, weekly points shipped."},
                {"asset": "int_ratio_intensity", "count": "1:1", "meaning": "Intensity {{intensityPct}}% of the way to the dot-com peak narrowing."},
                {"asset": "int_ratio_validated", "count": "1 verdict", "meaning": "{{checksPass}}/{{checksN}} checks pass → conforms."},
                {"asset": "graph.tech_leadership", "count": "1 leaf", "meaning": "Projected top {{projDash}}; feeds the Concentration roll-up."},
            ],
        },
    },
}
