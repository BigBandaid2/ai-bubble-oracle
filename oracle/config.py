from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_DIR / "oracle.db"
DASHBOARD_PATH = PROJECT_DIR / "dashboard.html"

# Charts embed daily data from this date on (ATHs are still computed over the
# full listed history).
CHART_START = "2022-01-01"

# Market deadline, used by the "deadline-anchored" 90-day window interpretation.
DEADLINE = "2026-12-31"

# The Polymarket market page this oracle tracks.
MARKET_URL = "https://polymarket.com/event/ai-bubble-burst-by"

# Human-confirm gate for bankruptcy candidates: a docket found by the daily
# CourtListener scan only makes its condition met once it is confirmed here,
# as {entity: "YYYY-MM-DD"} (the filing date it should count from).
# e.g. CONFIRMED_BANKRUPTCIES = {"OpenAI": "2026-08-14"}
CONFIRMED_BANKRUPTCIES = {}

# Broad-market context series (not a condition): the S&P 500 index.
SP500_TICKER = "^GSPC"

# Then-and-Now tickers are no longer listed here: the metric registry derives
# them from the active metric declarations (oracle/registry.required_tickers).

# Key AI-era / macro events overlaid on the S&P 500 context chart.
# Editable list: (date, short label). Keep labels tight, they render as a
# numbered legend under the chart.
# (date, label, url), url is a hand-curated article link (prefer
# Reuters/Bloomberg/FT/The Register), or None if no solid source. Curated, not
# automated: edit these directly.
KEY_EVENTS = [
    ("2022-11-30", "ChatGPT released",
     "https://www.theregister.com/2022/12/03/in_brief_ai/"),
    ("2023-05-24", "Nvidia blowout AI guidance",
     "https://www.cnbc.com/2023/05/24/nvidia-nvda-earnings-report-q1-2024.html"),
    ("2024-06-05", "Nvidia hits ~$3T, overtakes Apple #2",
     "https://www.cnbc.com/2024/06/05/nvidia-briefly-passes-3-trillion-market-cap-on-back-of-ai-boom.html"),
    ("2024-08-05", "Yen carry-trade unwind sparks selloff",
     "https://www.cnn.com/2024/08/04/investing/japan-nikkei-stock-rout-intl-hnk/index.html"),
    ("2025-01-27", "DeepSeek triggers NVDA −17% record drop",
     "https://www.cnbc.com/2025/01/27/nvidia-sheds-almost-600-billion-in-market-cap-biggest-drop-ever.html"),
    ("2025-04-02", '"Liberation Day" tariffs announced',
     "https://www.cbsnews.com/news/trump-liberation-day-new-tariffs-us/"),
    ("2025-11-04", "SMCI earnings disappoint, analyst downgrade",
     "https://www.cnbc.com/2025/11/04/super-micro-smci-q1-earnings-report-2026.html"),
    ("2026-02-28", "US/Israel strike kills Khamenei",
     "https://www.aljazeera.com/news/2026/2/28/irans-supreme-leader-ali-khamenei-killed-in-us-israeli-attacks-reports"),
    ("2026-05-28", "Anthropic hits $965B valuation, overtakes OpenAI",
     "https://www.cnbc.com/2026/05/28/anthropic-open-ai-startup-value.html"),
    ("2026-06-08", "OpenAI confidentially files for IPO",
     "https://www.cnbc.com/2026/06/08/openai-confidentially-files-for-ipo-prepping-wall-street-for-ai-debut.html"),
]

# The contract as a condition tree, from the Polymarket "AI bubble burst in
# 2026?" market (condition id 0x857398c4...). Node types:
#   drawdown, met while `ticker` closes at least `threshold` below its
#              running all-time closing high
#   count, met while at least `min_met` of its children are met
#   manual, no automated data source yet (Phase 3/4); status is unknown
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
                {"key": "openai_bankruptcy", "label": "OpenAI declares bankruptcy",
                 "type": "docket", "entity": "OpenAI"},
                {"key": "anthropic_bankruptcy", "label": "Anthropic declares bankruptcy",
                 "type": "docket", "entity": "Anthropic"},
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
                    "index (SiliconData SDH100RT) is Bloomberg/enterprise, future plan.",
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
