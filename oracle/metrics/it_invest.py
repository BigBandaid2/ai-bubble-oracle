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
}
