from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_DIR / "oracle.db"
DASHBOARD_PATH = PROJECT_DIR / "dashboard.html"

# Charts embed daily data from this date on (ATHs are still computed over the
# full listed history).
CHART_START = "2022-01-01"

# Market deadline, used by the "deadline-anchored" 90-day window interpretation.
DEADLINE = "2026-12-31"

# The contract as a condition tree, from the Polymarket "AI bubble burst in
# 2026?" market (condition id 0x857398c4...). Node types:
#   drawdown — met while `ticker` closes at least `threshold` below its
#              running all-time closing high
#   count    — met while at least `min_met` of its children are met
#   manual   — no automated data source yet (Phase 3/4); status is unknown
# Any node may nest count-parents to arbitrary depth.
CONTRACT = {
    "key": "ai_bubble_2026",
    "label": "AI bubble burst in 2026?",
    "type": "count",
    "min_met": 3,
    "note": "Market resolves YES if 3 of the 6 conditions occur within a single 90-day window "
            "ending no later than the Dec 31, 2026 deadline (clarified Nov 20, 2025).",
    "children": [
        {
            "key": "nvda_down_50",
            "label": "NVIDIA down 50% from all-time high",
            "type": "drawdown", "ticker": "NVDA", "threshold": 0.50,
        },
        {
            "key": "soxx_down_40",
            "label": "SOXX ETF down 40% from all-time high",
            "type": "drawdown", "ticker": "SOXX", "threshold": 0.40,
        },
        {
            "key": "ai_lab_bankruptcy",
            "label": "OpenAI or Anthropic bankruptcy",
            "type": "count", "min_met": 1,
            "children": [
                {"key": "openai_bankruptcy", "label": "OpenAI declares bankruptcy", "type": "manual"},
                {"key": "anthropic_bankruptcy", "label": "Anthropic declares bankruptcy", "type": "manual"},
            ],
        },
        {
            "key": "openai_acquisition",
            "label": "OpenAI is acquired",
            "type": "manual",
        },
        {
            "key": "h100_rental_dollar",
            "label": "H100 rental at or below $1.00/hr for 5 straight days",
            "type": "rental",
            "threshold": 1.00,   # met while the index is at or below this ($/GPU/hr)
            "days": 5,           # ... for this many consecutive readings
            "note": "Proxy: Vast.ai verified on-demand H100 SXM median. Authoritative "
                    "index (SiliconData SDH100RT) is Bloomberg/enterprise — future plan.",
        },
        {
            "key": "supplier_down_50",
            "label": "Major AI hardware supplier down 50% from all-time high",
            "type": "count", "min_met": 1,
            "children": [
                {"key": "tsm_down_50", "label": "TSMC (TSM) down 50% from ATH", "type": "drawdown", "ticker": "TSM", "threshold": 0.50},
                {"key": "asml_down_50", "label": "ASML down 50% from ATH", "type": "drawdown", "ticker": "ASML", "threshold": 0.50},
                {"key": "avgo_down_50", "label": "Broadcom (AVGO) down 50% from ATH", "type": "drawdown", "ticker": "AVGO", "threshold": 0.50},
                {"key": "anet_down_50", "label": "Arista (ANET) down 50% from ATH", "type": "drawdown", "ticker": "ANET", "threshold": 0.50},
                {"key": "smci_down_50", "label": "Supermicro (SMCI) down 50% from ATH", "type": "drawdown", "ticker": "SMCI", "threshold": 0.50},
            ],
        },
    ],
}


def walk(node=None):
    """Yield every node in the tree, preorder."""
    node = node or CONTRACT
    yield node
    for child in node.get("children", []):
        yield from walk(child)


def drawdown_leaves():
    return [n for n in walk() if n["type"] == "drawdown"]


TICKERS = list(dict.fromkeys(n["ticker"] for n in drawdown_leaves()))

# Both interpretations of "all-time high" (see README). The dashboard and
# met/not-met status use the `close` basis; events are recorded for both.
BASES = ["close", "intraday"]
