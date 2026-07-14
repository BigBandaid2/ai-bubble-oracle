"""Semiconductor production: the picks-and-shovels output index (chips carried
both booms: fabs then, GPUs now). NOTE: quality-adjusted chip VOLUME grew
straight through the 2001 bust (the crash was in dollars), so this leaf is
expected to render as an honest counter-argument."""

METRIC = {
    "key": "semis", "label": "Semiconductor production", "parent": "capex", "order": 30,
    "kind": "semis", "source": ("fred", "IPG3344S"),
    "formula": lambda r: r["value"], "cadence": "monthly",
    "type": "ratio_from_start", "direction": "up", "unit": "ip_index",
    "unitLabel": "Semis production",
}
