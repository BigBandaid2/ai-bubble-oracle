"""Price appreciation: how far each index has run since its era's start.

The exemplar of a one-module, multi-leaf contribution: this file declares a
sub-branch (the Price appreciation blend) plus its two leaves. No single index
carries the whole price argument on its own.
"""

BRANCH = {
    "key": "price_appreciation", "label": "Price appreciation",
    "parent": "valuation", "order": 10,
}

NASDAQ = {
    "key": "nasdaq", "label": "Nasdaq", "parent": "price_appreciation", "order": 10,
    "kind": "price", "source": ("prices", "^IXIC"),
    "formula": lambda r: r["close"], "cadence": "daily",
    "type": "ratio_from_start", "direction": "up", "unit": "nasdaq_close",
    "unitLabel": "Nasdaq",
}

SP500 = {
    "key": "sp500", "label": "S&P 500", "parent": "price_appreciation", "order": 20,
    "kind": "sp500", "source": ("prices", "^GSPC"),
    "formula": lambda r: r["close"], "cadence": "daily",
    "type": "ratio_from_start", "direction": "up", "unit": "sp500_close",
    "unitLabel": "S&P 500",
}

METRICS = [NASDAQ, SP500]
