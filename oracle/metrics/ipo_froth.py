"""IPO froth: the average first-day pop, Ritter's classic speculation gauge
(1999 months ran 60-120%). Zero-IPO months carry no reading (forward-filled)."""

METRIC = {
    "key": "ipo_froth", "label": "IPO froth", "parent": "speculation", "order": 20,
    "kind": "ipo", "source": ("ipo", None),
    "formula": lambda r: r["avg_first_day_return"], "cadence": "monthly",
    "type": "absolute_level", "direction": "up", "unit": "pct",
    "unitLabel": "IPO first-day %",
}
