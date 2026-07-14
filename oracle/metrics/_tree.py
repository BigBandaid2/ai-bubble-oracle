"""The Then & Now tree skeleton: the root and the five pillar branches.

Metric modules attach leaves (or sub-branches) to these by declaring a
`parent` key. The declared cycle CLOCK and PHASES live in oracle/thennow.py;
together with this file they are the single place to change if you fork this
project to compare a different pair of cycles.
"""

ROOT = {"key": "ai_peak", "label": "AI bubble bursts"}

BRANCHES = [
    {"key": "valuation", "label": "Valuation", "parent": "ai_peak", "order": 10},
    {"key": "market_concentration", "label": "Market concentration", "parent": "ai_peak", "order": 20},
    {"key": "capex", "label": "Infrastructure / capex", "parent": "ai_peak", "order": 30},
    {"key": "speculation", "label": "Speculative activity", "parent": "ai_peak", "order": 40},
    {"key": "monetary", "label": "Monetary & sentiment", "parent": "ai_peak", "order": 50},
]
