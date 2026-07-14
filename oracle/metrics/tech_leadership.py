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
}
