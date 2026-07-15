"""Generate the standalone thennow.html page (the Then-and-Now roll-up tree).

Kept separate from the dashboard on purpose: it is a WIP prototype reachable by
direct URL, not linked in the site nav and marked noindex. Same __DATA__ inject
pattern as the dashboard.
"""

import json

from .config import DASHBOARD_PATH
from .thennow import compute_thennow
from . import ogcard

THENNOW_PATH = DASHBOARD_PATH.parent / "thennow.html"
TEMPLATE_PATH = DASHBOARD_PATH.parent / "oracle" / "thennow_template.html"
OG_CARD_PATH = DASHBOARD_PATH.parent / "og-card.svg"


def write_thennow_page(conn, path=THENNOW_PATH):
    payload = compute_thennow(conn)
    if payload is None:
        return None
    data = json.dumps(payload, separators=(",", ":"))
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    path.write_text(template.replace("__DATA__", data), encoding="utf-8")
    # regenerate the social share card so og-card.svg (rasterized to
    # og-image.png by the nightly build) always shows the current projection
    OG_CARD_PATH.write_text(ogcard.build_svg(payload), encoding="utf-8")
    return path
