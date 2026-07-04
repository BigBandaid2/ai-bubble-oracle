"""Human-readable status report over the condition tree."""

from . import db
from .conditions import evaluate

STATUS_TAG = {"met": "[MET]", "not_met": "[not met]", "unknown": "[no data]"}


def fmt_pct(x):
    return f"{x * 100:+.1f}%"


def _node_lines(node, depth, lines):
    indent = "  " * depth
    tag = STATUS_TAG[node["status"]]
    last = f"  last met: {node['last_met']}" if node["last_met"] else ""
    lines.append(f"{indent}{tag} {node['label']}{last}")
    s = node["stats"]
    if node["type"] == "drawdown" and s:
        room = s["close"] / s["trigger"] - 1.0
        lines.append(
            f"{indent}      {node['ticker']}: close {s['close']:.2f} ({s['date']})"
            f" | ATH {s['ath']:.2f} | drawdown {s['drawdown'] * 100:.1f}%"
            f" | trigger @ {s['trigger']:.2f} ({fmt_pct(room)} above it)"
        )
    elif node["type"] == "count" and s:
        unknown = f", {s['unknown']} with no data" if s["unknown"] else ""
        lines.append(
            f"{indent}      {s['count']} of {s['total']} children met, needs {s['needed']}{unknown}"
        )
    elif node["type"] == "rental" and s:
        lines.append(
            f"{indent}      H100 rental ${s['usd_hr']:.2f}/hr ({s['date']}, {s['source']})"
            f" | trigger <= ${s['threshold']:.2f} for {s['days']} straight days"
        )
    for child in node["children"]:
        _node_lines(child, depth + 1, lines)


def status_report(conn):
    updated = db.get_meta(conn, "last_update") or "never"
    root = evaluate(conn)
    lines = [f"AI Bubble Oracle - condition tree (close-ATH basis; last update: {updated})", ""]
    _node_lines(root, 0, lines)

    lines.append("")
    ev = conn.execute(
        "SELECT condition_key, ticker, basis, date, kind, drawdown, price, ath FROM events"
        " WHERE date >= '2025-01-01' ORDER BY date"
    ).fetchall()
    if ev:
        lines.append("## Threshold-crossing events since 2025-01-01 (full history: `python main.py events`)")
        for e in ev:
            lines.append(
                f"   {e['date']}  {e['ticker']:5s} {e['kind']:9s} ({e['basis']} basis)"
                f"  drawdown {e['drawdown'] * 100:.1f}%  price {e['price']:.2f} vs ATH {e['ath']:.2f}"
                f"  [{e['condition_key']}]"
            )
        lines.append("")
        lines.append(
            "NOTE: whether a pre-existing drawdown (e.g. SMCI, down >50% since 2024)\n"
            "counts as having 'occurred' is a known rules ambiguity (see README).\n"
            "Window logic over these events lands in Phase 2."
        )
    return "\n".join(lines)
