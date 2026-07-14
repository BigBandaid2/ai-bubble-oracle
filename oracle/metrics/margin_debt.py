"""Margin debt: the leverage behind the trade. Broker-dealer margin loans
(Z.1). Nominal dollars, so each era is indexed to its own start (ratio) rather
than compared raw across 30 years of inflation."""

METRIC = {
    "key": "margin_debt", "label": "Margin debt", "parent": "speculation", "order": 10,
    "kind": "margin", "source": ("fred", "BOGZ1FL663067003Q"),
    "formula": lambda r: r["value"] / 1000.0, "cadence": "quarterly",
    "type": "ratio_from_start", "direction": "up", "unit": "usd_bn",
    "unitLabel": "Margin loans $bn",
}
