"""IPO froth: the average first-day pop, Ritter's classic speculation gauge
(1999 months ran 60-120%). Zero-IPO months carry no reading (forward-filled)."""

METRIC = {
    "key": "ipo_froth", "label": "IPO froth", "parent": "speculation", "order": 20,
    "kind": "ipo", "source": ("ipo", None),
    "formula": lambda r: r["avg_first_day_return"], "cadence": "monthly",
    "type": "absolute_level", "direction": "up", "unit": "pct",
    "unitLabel": "IPO first-day %",
    "ir": {
        "group": "tn_ipo", "group_name": "IPO froth (WIP)", "foreign_from": "IPO",
        "leaf_chain": {
            "p": "ipo", "cadence": "monthly",
            "src": {
                "id": "seed.ritter_ipoall", "seed": True, "mat": "xlsx (authored seed)", "cadence": "~annual refresh",
                "dbt": "seed('ipo_issuance')",
                "grain": "one spreadsheet (monthly IPO stats since 1960)",
                "why": "The classic speculation gauge: Jay Ritter's monthly IPO counts and average first-day returns, the academic reference data on IPO underpricing.",
                "desc": "Authored from IPOALL.xlsx at site.warrington.ufl.edu/ritter/ipo-data/ (retrieved 2026-07-08, data through 2025-12). Ritter refreshes roughly annually, so this is a committed seed, not a live fetch; the CSV carries the citation. Returns use his net IPO definition (excludes SPACs, penny stocks, units, closed-end funds, ADRs, banks).",
                "tx": "manual convert of IPOALL.xlsx → data/ipo_issuance.csv", "card": "monthly 1960-2025 in the source; 1990+ committed.",
            },
            "raw": {
                "id": "ipo_issuance", "mat": "table · seed import", "cadence": "on update",
                "grain": "one row per month",
                "why": "The landed monthly IPO stats.",
                "desc": "month, average first-day return, gross and net counts. Months with zero qualifying IPOs carry a NULL return (never 0), so the forward-fill holds the last real reading. oracle/sources/ipo.py.",
                "tx": "idempotent seed import",
                "schema": [
                    {"col": "month", "type": "TEXT", "kind": "key", "ex": "1999-12-01"},
                    {"col": "avg_first_day_return", "type": "REAL", "kind": "pass", "ex": {"live": "rawNow"}, "note": "percent; Dec 1999 was 115.3"},
                    {"col": "ipo_count_gross", "type": "INTEGER", "kind": "pass", "ex": 33},
                    {"col": "ipo_count_net", "type": "INTEGER", "kind": "pass", "ex": 7},
                ],
                "card": "432 monthly rows, 1990-01 to 2025-12.",
            },
            "metricWhy": "Applies the declared formula: the average first-day pop.",
            "metricDesc": "Registry: formula = avg_first_day_return, type = absolute_level: a first-day percentage means the same thing in any era.",
            "metricTx": "value = avg first-day return %", "metricNote": "percent",
            "graphWhy": "The froth thermometer: 1999 months ran 60-120% average pops. The AI era started cold (Dec 2022 was NEGATIVE) and is only warming, so this leaf honestly reads very early.",
            "graphDesc": "Match today's smoothed pop on the dot-com ramp, rate-scale the remainder. The AI series ends at Ritter's latest month and forward-fills to today, labeled as such. _evaluate + _emit.",
        },
        "graph": {"vchain": {
            "ids": ["seed.ritter_ipoall", "ipo_issuance", "stg_ipo_filled", "int_ipo_metric",
                    "int_ipo_smoothed", "int_ipo_intensity", "int_ipo_validated", "graph.ipo_froth"],
            "shorts": {"seed.ritter_ipoall": "seed: Ritter IPOALL", "graph.ipo_froth": "graph: IPO froth"},
        }},
        "source_info": {
            "blurb": "IPO froth (WIP): the Speculation branch's issuance leaf. Jay Ritter's monthly average first-day IPO returns (University of Florida), the academic reference on underpricing. 1999 months averaged 60-120% pops; the AI era started NEGATIVE in late 2022 and is only warming, so this leaf honestly reads very early.",
            "options": [
                {"t": "First-day return, not counts", "d": "The pop is the froth thermometer; monthly gross and net counts ride along in the table for context."},
            ],
            "ambiguities": [
                {"t": "Net definition", "d": "Returns use Ritter's net IPO definition (no SPACs, penny stocks, units, closed-end funds, ADRs, banks), which is what makes 1999 comparable to 2025."},
            ],
            "caveats": [
                {"t": "Authored seed", "d": "Ritter refreshes roughly annually; data ends 2025-12 and forward-fills to today, labeled as such. The committed CSV carries the citation; no stated license, academic attribution given."},
                {"t": "Why not paid data", "d": "massive.com (Polygon) was evaluated as a fallback: its IPO records start 2002-02 with no first-day-price field, its stock prices start 2003, and its terms bar committing fetched data to a public repo. Nothing it sells reaches the dot-com window, so the whole page runs on open sources."},
            ],
            "cardinality": [
                {"asset": "ipo_issuance", "count": "432 rows", "meaning": "Monthly 1990-01 to 2025-12; 16 zero-IPO months carry NULL returns."},
                {"asset": "int_ipo_intensity", "count": "1:1", "meaning": "Intensity {{intensityPct}}% (below 0 = calmer than the 1995 start)."},
                {"asset": "int_ipo_validated", "count": "1 verdict", "meaning": "{{checksPass}}/{{checksN}} checks pass → conforms, reads very early."},
                {"asset": "graph.ipo_froth", "count": "1 leaf", "meaning": "Projected top {{projDash}}; speculation has not frothed yet."},
            ],
        },
    },
}
