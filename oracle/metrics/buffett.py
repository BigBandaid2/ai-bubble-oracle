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
}
