"""Consumer sentiment: the Main Street euphoria check. Michigan sentiment hit
all-time highs into the 2000 peak; today it sits near record lows. Expected
counter-argument. minRange relaxes the dynamic-range gate: a bounded survey
index moves less than a price, and the check detail prints the actual %."""

METRIC = {
    "key": "sentiment", "label": "Consumer sentiment", "parent": "monetary", "order": 20,
    "kind": "sentiment", "source": ("fred", "UMCSENT"),
    "formula": lambda r: r["value"], "cadence": "monthly",
    "type": "absolute_level", "direction": "up", "unit": "umich_index",
    "unitLabel": "UMich sentiment", "minRange": 0.08,
}
