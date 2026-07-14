"""Yield curve: the late-cycle monetary tell. The 10Y-3M spread inverts near
tops; direction DOWN (falling spread = later cycle). The AI era already
inverted deeper than 2000 and has re-steepened, so this is expected to render
as a counter-argument."""

METRIC = {
    "key": "yield_curve", "label": "Yield curve", "parent": "monetary", "order": 10,
    "kind": "curve", "source": ("fred", "T10Y3M"),
    "formula": lambda r: r["value"], "cadence": "daily",
    "type": "absolute_level", "direction": "down", "unit": "pct_spread",
    "unitLabel": "10Y-3M spread",
}
