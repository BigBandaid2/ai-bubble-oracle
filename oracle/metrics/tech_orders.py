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
}
