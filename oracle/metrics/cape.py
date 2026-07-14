"""Valuation multiple: the Shiller CAPE, comparable in absolute terms across
eras, so it reads "how expensive" beside price appreciation's "how far"."""

METRIC = {
    "key": "valuation_multiple", "label": "Valuation multiple", "parent": "valuation", "order": 20,
    "kind": "cape", "source": ("cape", None),
    "formula": lambda r: r["cape"], "cadence": "monthly",
    "type": "absolute_level", "direction": "up", "unit": "shiller_cape",
    "unitLabel": "CAPE",
}
