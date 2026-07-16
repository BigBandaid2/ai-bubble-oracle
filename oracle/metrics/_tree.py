"""The Then & Now tree skeleton: the root and the five pillar branches.

Metric modules attach leaves (or sub-branches) to these by declaring a
`parent` key. The declared cycle CLOCK and PHASES live in oracle/thennow.py;
together with this file they are the single place to change if you fork this
project to compare a different pair of cycles.

Each branch carries an `ir` block documenting its roll-up pipeline on the
Data Sources page. Most use the compact `rollup` form (the blend + graph
assets are generated, see datasources._tn_rollup); Valuation authors its two
assets explicitly because its blend prose names each child. Live example
values use {{field}} tokens / {"live": "<field>"} dicts, materialized at
generate time from the branch node's computed scalars.
"""

ROOT = {"key": "ai_peak", "label": "AI bubble bursts"}

BRANCHES = [
    {
        "key": "valuation", "label": "Valuation", "parent": "ai_peak", "order": 10,
        "ir": {
            "group": "tn_valuation", "group_name": "Valuation roll-up (WIP)",
            "assets": [
                {
                    "id": "int_valuation_blend", "group": "tn_valuation", "layer": "intermediate", "status": "live",
                    "name": "int_valuation_blend", "mat": "table", "cadence": "on generate",
                    "dagster": "thennow/int_valuation_blend", "dbt": "int_valuation_blend",
                    "grain": "one row per (era, day)",
                    "why": "The roll-up: the child intensities combined into one Valuation curve by weight.",
                    "desc": "Pointwise weighted average of the CONFORMING children on the shared daily grid (equal by default, adjustable on the page): int_price_blend (Nasdaq + S&P), int_cape_intensity, and int_bf_intensity (Market cap to GDP). Each input lives in its own pipeline, so all three are shown dimmed here. Only conforming inputs are blended. _blend().",
                    "upstream": ["int_price_blend", "int_cape_intensity", "int_bf_intensity"],
                    "schema": [
                        {"col": "date", "type": "DATE", "kind": "key", "ex": "{{asOf}}"},
                        {"col": "intensity", "type": "NUMERIC", "kind": "derived", "ex": {"live": "intensity"}, "note": "weighted mean of children"},
                    ],
                    "transforms": [{"tag": "combine", "text": "equal-weight mean of the child intensities"}],
                    "tests": ["not_null: intensity"],
                    "cardinality": "1:1 with the daily grid.",
                },
                {
                    "id": "graph.valuation", "group": "tn_valuation", "layer": "serve", "status": "live",
                    "name": "graph: valuation", "mat": "exposure (JSON)", "cadence": "on generate",
                    "dagster": "thennow (exposure)", "dbt": "exposure: valuation",
                    "grain": "one parent block on thennow.html",
                    "why": "The Valuation parent: one graph, one date, from the blended curve, exactly like a leaf.",
                    "desc": "The same _evaluate() runs on the combined curve, so the parent is one conclusion date. This node rolls up into the root 'AI bubble bursts' headline.",
                    "upstream": ["int_valuation_blend"],
                    "json": "{ \"intensityNow\": {{intensity}}, \"equivalentDotcomDate\": \"{{equiv}}\",\n  \"phase\": \"{{phase}}\", \"projectedPeakDate\": \"{{proj}}\" }",
                    "transforms": [
                        {"tag": "lookup", "text": "value-match on the combined curve"},
                        {"tag": "rate-scale", "text": "→ parent projected top"},
                    ],
                    "cardinality": "one parent node; feeds the root headline.",
                },
            ],
            "graph": {"explicit": {
                "viewBox": "0 0 660 300",
                "nodes": [
                    {"id": "int_price_blend", "cx": 120, "cy": 44, "w": 200, "foreign": True},
                    {"id": "int_cape_intensity", "cx": 330, "cy": 44, "w": 190, "foreign": True},
                    {"id": "int_bf_intensity", "cx": 540, "cy": 44, "w": 200, "foreign": True},
                    {"id": "int_valuation_blend", "cx": 330, "cy": 150},
                    {"id": "graph.valuation", "cx": 330, "cy": 240, "short": "graph: valuation"},
                ],
                "spine": [
                    ["int_cape_intensity", "int_valuation_blend"],
                    ["int_valuation_blend", "graph.valuation"],
                ],
                "curves": [
                    "M120,67 C 120,112 270,120 296,127",
                    "M540,67 C 540,112 390,120 364,127",
                ],
            }},
            "source_info": {
                "blurb": "Valuation roll-up (WIP): how the children become one parent. The Price-appreciation blend and the CAPE intensity series (shown dimmed, drawn from their own pipelines) are combined by weight into one Valuation curve, then the same alignment + projection gives the parent's one date. Uniform for every roll-up.",
                "options": [
                    {"t": "Weights", "d": "Each child's share of the parent, split evenly by default and adjustable with the sliders on thennow.html. The blended curve, its equivalent date, and the projected top all recompute live."},
                ],
                "ambiguities": [
                    {"t": "Price early, CAPE late", "d": "The two leaves disagree on purpose. The parent is where they reconcile; the weights decide how much each voice counts."},
                ],
                "caveats": [
                    {"t": "WIP prototype", "d": "Method and copy will change. Not linked in the site nav; reachable by direct URL only."},
                    {"t": "Root is Valuation for now", "d": "Concentration, capex and speculation are not wired, so the root 'AI bubble bursts' headline currently equals the Valuation roll-up."},
                ],
                "cardinality": [
                    {"asset": "int_valuation_blend", "count": "1:1", "meaning": "Equal-weight mean of the conforming children: Price appreciation, CAPE, and Market cap to GDP."},
                    {"asset": "graph.valuation", "count": "1 parent", "meaning": "The Valuation date; feeds the root AI-bubble-bursts headline."},
                ],
            },
        },
    },
    {
        "key": "market_concentration", "label": "Market concentration", "parent": "ai_peak", "order": 20,
        "ir": {
            "group": "tn_concentration", "group_name": "Concentration roll-up (WIP)",
            "rollup": {
                "blendId": "int_concentration_blend",
                "inputs": ["int_ratio_intensity"],
                "blendWhy": "The concentration branch roll-up. One conforming leaf today, so the blend passes it through unchanged.",
                "blendDesc": "Weighted mean of the branch's leaf intensities (currently just tech leadership).",
                "graphWhy": "The Market concentration pillar's one date, from narrow-leadership intensity.",
            },
            "graph": {"explicit": {
                "viewBox": "0 0 660 250",
                "nodes": [
                    {"id": "int_ratio_intensity", "cx": 330, "cy": 44, "w": 230, "foreign": True},
                    {"id": "int_concentration_blend", "cx": 330, "cy": 130},
                    {"id": "graph.market_concentration", "cx": 330, "cy": 210, "short": "graph: concentration"},
                ],
                "spine": [["int_ratio_intensity", "int_concentration_blend"], ["int_concentration_blend", "graph.market_concentration"]],
                "curves": [],
            }},
            "source_info": {
                "blurb": "Concentration roll-up (WIP): the Market concentration pillar's one date. One conforming leaf today (tech leadership), so the blend passes it through; more leaves (breadth, cap-weight overlays) can join the branch later without touching the engine.",
                "options": [{"t": "Weights", "d": "Adjustable on thennow.html once the branch has more than one conforming leaf."}],
                "ambiguities": [],
                "caveats": [{"t": "Single-leaf branch", "d": "Branch date equals the leaf date until a second concentration leaf lands."}],
                "cardinality": [
                    {"asset": "int_concentration_blend", "count": "1:1", "meaning": "Pass-through of the tech-leadership intensity (dimmed input from its own pipeline)."},
                    {"asset": "graph.market_concentration", "count": "1 parent", "meaning": "Projected top {{projDash}}; feeds the root headline."},
                ],
            },
        },
    },
    {
        "key": "capex", "label": "Infrastructure / capex", "parent": "ai_peak", "order": 30,
        "ir": {
            "group": "tn_capex", "group_name": "Capex roll-up (WIP)",
            "rollup": {
                "blendId": "int_capex_blend",
                "inputs": ["int_it_intensity", "int_orders_intensity", "int_semis_intensity"],
                "blendWhy": "The capex branch roll-up across three leaves that deliberately disagree.",
                "blendDesc": "Weighted mean of the conforming capex intensities: IT-investment share and tech equipment orders. Semiconductor production is excluded (its quality-adjusted volume never had the bubble shape) and shown beside the blend as a counter-argument.",
                "graphWhy": "The Infrastructure / capex pillar's one date, beside the semiconductor-production counter-argument.",
            },
            "graph": {"explicit": {
                "viewBox": "0 0 660 260",
                "nodes": [
                    {"id": "int_it_intensity", "cx": 120, "cy": 44, "w": 190, "foreign": True},
                    {"id": "int_orders_intensity", "cx": 330, "cy": 44, "w": 190, "foreign": True},
                    {"id": "int_semis_intensity", "cx": 540, "cy": 44, "w": 190, "foreign": True},
                    {"id": "int_capex_blend", "cx": 330, "cy": 140},
                    {"id": "graph.capex", "cx": 330, "cy": 220, "short": "graph: capex"},
                ],
                "spine": [["int_orders_intensity", "int_capex_blend"], ["int_capex_blend", "graph.capex"]],
                "curves": [
                    "M120,67 C 120,100 270,108 298,117",
                    "M540,67 C 540,100 390,108 362,117",
                ],
            }},
            "source_info": {
                "blurb": "Capex roll-up (WIP): the Infrastructure pillar's one date, blended from three leaves. IT-investment share and tech equipment orders conform (both indexed to each era's own start, both mid-cycle); semiconductor production is the counter-argument, its quality-adjusted volume having grown straight through the 2001 bust, shown beside the blend.",
                "options": [{"t": "Weights", "d": "Adjustable on thennow.html; only conforming leaves enter the blend."}],
                "ambiguities": [{"t": "Which capex truth", "d": "Share-of-economy and dollar orders both read mid-cycle once indexed to each era's own start, while quality-adjusted chip volume shows no cycle at all. The branch blends the first two and shows volume beside them."}],
                "caveats": [{"t": "Blend excludes counters", "d": "Non-conforming leaves are shown but never drag the roll-up date."}],
                "cardinality": [
                    {"asset": "int_capex_blend", "count": "1:1", "meaning": "Weighted mean of the conforming capex intensities (currently orders alone)."},
                    {"asset": "graph.capex", "count": "1 parent", "meaning": "Projected top {{projDash}}; feeds the root headline."},
                ],
            },
        },
    },
    {
        "key": "speculation", "label": "Speculative activity", "parent": "ai_peak", "order": 40,
        # Default child weights, adopted 2026-07-16 from the projection-stability
        # backtest (`python main.py optimize-weights`): margin-heavy 90/10 roughly
        # halved the out-of-sample instability vs equal weights (loss 1310 -> 737,
        # optimized on Jan-Sep 2025, judged Oct 2025-Jul 2026), and inverse-variance
        # weighting independently landed at 91/9. IPO froth's validity flapping is
        # what equal weighting kept importing. Re-derivable from the committed
        # ledger; the page's sliders still let readers reweight live.
        "weights": {"margin_debt": 0.9, "ipo_froth": 0.1},
        "ir": {
            "group": "tn_speculation", "group_name": "Speculation roll-up (WIP)",
            "rollup": {
                "blendId": "int_speculation_blend",
                "inputs": ["int_margin_intensity", "int_ipo_intensity"],
                "blendWhy": "The speculation branch roll-up: leverage and IPO froth, equal weight.",
                "blendDesc": "Weighted mean of the margin-debt and IPO-froth intensities.",
                "graphWhy": "The Speculative activity pillar's one date. Both leaves read early, which drags the branch date late; that is the honest read of speculation so far.",
            },
            "graph": {"join": {
                "tops": [{"id": "int_margin_intensity", "foreign": True}, {"id": "int_ipo_intensity", "foreign": True}],
                "ids": ["int_speculation_blend", "graph.speculation"],
                "shorts": {"graph.speculation": "graph: speculation"},
            }},
            "source_info": {
                "blurb": "Speculation roll-up (WIP): leverage and IPO froth, equal weight. Both leaves conform and both read EARLY (margin up 1.6x vs 3x into 2000; IPO pops warming from a cold start), which drags the branch's projected date well past the price-led branches. That gap between price heat and speculation cool is itself the finding.",
                "options": [{"t": "Weights", "d": "Adjustable on thennow.html; the two leaves currently split evenly."}],
                "ambiguities": [{"t": "Where is the mania", "d": "If the bubble argument fails anywhere on classic 1999 terms, it is here: the leverage and issuance manias have not shown up yet."}],
                "caveats": [{"t": "Both inputs lag", "d": "Z.1 is quarterly with a lag; Ritter refreshes annually. The branch edge is the slowest-moving on the page."}],
                "cardinality": [
                    {"asset": "int_speculation_blend", "count": "1:1", "meaning": "Weighted mean of the margin and IPO intensities."},
                    {"asset": "graph.speculation", "count": "1 parent", "meaning": "Projected top {{projDash}}; feeds the root headline."},
                ],
            },
        },
    },
    {
        "key": "monetary", "label": "Monetary & sentiment", "parent": "ai_peak", "order": 50,
        "ir": {
            "group": "tn_monetary", "group_name": "Monetary & sentiment roll-up (WIP)",
            "rollup": {
                "blendId": "int_monetary_blend",
                "inputs": ["int_curve_intensity", "int_sent_intensity"],
                "blendWhy": "The monetary and sentiment branch roll-up, currently the counter-argument branch.",
                "blendDesc": "Weighted mean of the conforming inputs; today NEITHER conforms (the curve already un-inverted, sentiment is at lows), so the branch renders as context with its projection suppressed and is excluded from the root blend.",
                "graphWhy": "The Monetary & sentiment pillar: two tells that argue AGAINST the analogy right now, shown, labeled, and kept out of the headline math.",
            },
            "graph": {"join": {
                "tops": [{"id": "int_curve_intensity", "foreign": True}, {"id": "int_sent_intensity", "foreign": True}],
                "ids": ["int_monetary_blend", "graph.monetary"],
                "shorts": {"graph.monetary": "graph: monetary & sentiment"},
            }},
            "source_info": {
                "blurb": "Monetary & sentiment roll-up (WIP): the counter-argument branch. Today NEITHER leaf conforms (the curve already did its inversion round trip; sentiment is at lows, not highs), so the branch renders as labeled context with its projection suppressed and is excluded from the root blend entirely.",
                "options": [{"t": "Weights", "d": "Dormant until at least one leaf conforms; the sliders need two conforming children."}],
                "ambiguities": [{"t": "Counter or leading", "d": "A re-steepening curve after deep inversion has historically PRECEDED recessions; the validator reads shape, not causality. The observation text carries that nuance."}],
                "caveats": [{"t": "Excluded from the headline", "d": "The root date is blended only from conforming branches, so this branch never moves it; it argues beside it."}],
                "cardinality": [
                    {"asset": "int_monetary_blend", "count": "1:1", "meaning": "Falls back to the full-set mean for the context curve; marked non-conforming."},
                    {"asset": "graph.monetary", "count": "1 parent", "meaning": "Shown for context; projection suppressed."},
                ],
            },
        },
    },
]
