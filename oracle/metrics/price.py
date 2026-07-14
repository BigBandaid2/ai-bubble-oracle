"""Price appreciation: how far each index has run since its era's start.

The exemplar of a one-module, multi-leaf contribution: this file declares a
sub-branch (the Price appreciation blend) plus its two leaves, and carries the
Data Sources documentation (the `ir` blocks) for all three pipelines. No single
index carries the whole price argument on its own.

IR strings may embed live example values as {{field}} tokens, materialized at
generate time from the engine's per-node examples (see datasources._build_ir):
{{asOf}} {{dotWk}} {{aiWk}} plus per-node {{rawNow}} {{smNow}} {{peakF}}
{{intensity}} {{equiv}} {{proj}} {{daysFromPeak}} {{phase}} {{display}} {{obs}}
{{checksPass}} {{checksN}} {{verdictWord}} {{verdictLong}} {{intensityPct}}.
Typed example values (numbers/booleans) use {"live": "<field>", "scale": k}.
"""

BRANCH = {
    "key": "price_appreciation", "label": "Price appreciation",
    "parent": "valuation", "order": 10,
    "ir": {
        "group": "tn_price_appreciation", "group_name": "Price appreciation blend (WIP)",
        "foreign_from": "PRICE APPR.",
        "assets": [
            {
                "id": "int_price_blend", "group": "tn_price_appreciation", "layer": "intermediate", "status": "live",
                "name": "int_price_blend", "mat": "table", "cadence": "on generate",
                "dagster": "thennow/int_price_blend", "dbt": "int_price_blend",
                "grain": "one row per (era, day)",
                "why": "Price appreciation is not one index. This blends the Nasdaq and S&P intensities into one price-appreciation curve, so no single index carries the whole argument.",
                "desc": "Pointwise weighted average of int_ixic_intensity and int_gspc_intensity on the shared daily grid (equal by default, adjustable on the page). Its inputs come from the Nasdaq and S&P pipelines; they are shown dimmed in this graph. Only conforming inputs are blended. _blend.",
                "upstream": ["int_ixic_intensity", "int_gspc_intensity"],
                "schema": [
                    {"col": "date", "type": "DATE", "kind": "key", "ex": "{{asOf}}"},
                    {"col": "intensity", "type": "NUMERIC", "kind": "derived", "ex": {"live": "intensity"}, "note": "equal-weight mean of Nasdaq + S&P"},
                ],
                "transforms": [{"tag": "blend", "text": "weighted mean of the two index intensities"}],
                "tests": ["not_null: intensity"],
                "cardinality": "1:1 on the shared daily grid.",
            },
            {
                "id": "graph.price_appreciation", "group": "tn_price_appreciation", "layer": "serve", "status": "live",
                "name": "graph: price_appreciation", "mat": "exposure (JSON)", "cadence": "on generate",
                "dagster": "thennow (exposure)", "dbt": "exposure: price_appreciation",
                "grain": "one roll-up block on thennow.html",
                "why": "The Price-appreciation node the reader sees: the blended Nasdaq + S&P curve matched to a dot-com date and rate-scaled. One of the two inputs to the Valuation roll-up.",
                "desc": "Same alignment + projection as a leaf, run on the blended curve. _evaluate + _emit.",
                "upstream": ["int_price_blend"],
                "json": "{ \"intensityNow\": {{intensity}}, \"equivalentDotcomDate\": \"{{equiv}}\",\n  \"projectedPeakDate\": \"{{proj}}\", \"phase\": \"{{phase}}\" }",
                "transforms": [
                    {"tag": "lookup", "text": "value-match on the dot-com ramp → equivalent date"},
                    {"tag": "rate-scale", "text": "remaining distance × AI pace → projected top"},
                ],
                "cardinality": "one roll-up node; feeds the Valuation blend.",
            },
        ],
        "graph": {"explicit": {
            "viewBox": "0 0 660 300",
            "nodes": [
                {"id": "int_ixic_intensity", "cx": 170, "cy": 44, "w": 210, "foreign": True},
                {"id": "int_gspc_intensity", "cx": 490, "cy": 44, "w": 210, "foreign": True},
                {"id": "int_price_blend", "cx": 330, "cy": 150},
                {"id": "graph.price_appreciation", "cx": 330, "cy": 240, "short": "graph: price appreciation"},
            ],
            "spine": [["int_price_blend", "graph.price_appreciation"]],
            "curves": [
                "M170,67 C 170,112 280,120 300,127",
                "M490,67 C 490,112 380,120 360,127",
            ],
        }},
        "source_info": {
            "blurb": "Price appreciation blend (WIP): the sub-roll-up that combines the Nasdaq and S&P 500 leaves into one price-appreciation curve. Its two inputs (shown dimmed, from their own pipelines) are averaged by weight, then the same alignment + projection gives one date. Its output is itself an input to the Valuation roll-up.",
            "options": [
                {"t": "Weights", "d": "Each index's share of the blend, split evenly by default and adjustable with the sliders on thennow.html. The blended curve and its projected top recompute live."},
            ],
            "ambiguities": [
                {"t": "Which index leads", "d": "The Nasdaq usually reads more stretched than the broader S&P; the weights decide how much each voice counts in the combined price signal."},
            ],
            "caveats": [
                {"t": "WIP prototype", "d": "Method and copy will change. Direct URL only."},
                {"t": "Blends conforming inputs only", "d": "A leaf that fails its validator is shown but left out of the blend, so a non-conforming index cannot skew the price-appreciation date."},
            ],
            "cardinality": [
                {"asset": "int_price_blend", "count": "1:1", "meaning": "Equal-weight mean of the Nasdaq and S&P intensities on the shared daily grid."},
                {"asset": "graph.price_appreciation", "count": "1 roll-up", "meaning": "The Price-appreciation date; feeds the Valuation blend."},
            ],
        },
    },
}

NASDAQ = {
    "key": "nasdaq", "label": "Nasdaq", "parent": "price_appreciation", "order": 10,
    "kind": "price", "source": ("prices", "^IXIC"),
    "formula": lambda r: r["close"], "cadence": "daily",
    "type": "ratio_from_start", "direction": "up", "unit": "nasdaq_close",
    "unitLabel": "Nasdaq",
    "ir": {
        "group": "tn_price", "group_name": "Price · Nasdaq (WIP)", "foreign_from": "NASDAQ",
        "assets": [
            {
                "id": "raw.yahoo_ixic", "group": "tn_price", "layer": "source", "status": "live",
                "name": "raw.yahoo_ixic", "mat": "API response (JSON)", "cadence": "daily",
                "dagster": "thennow/yahoo_ixic", "dbt": "source('yahoo','ixic')",
                "grain": "one JSON document (daily bars for ^IXIC)",
                "why": "The price tap for the valuations branch: the Nasdaq Composite, the bubble's defining index.",
                "desc": "Yahoo v8 chart for ^IXIC, split-adjusted daily closes. This pipeline is self-contained; it shares nothing downstream with the CAPE chain.",
                "upstream": [],
                "transforms": [{"tag": "extract", "text": "HTTP GET ^IXIC daily bars"}],
                "cardinality": "one document, full daily history since 1971.",
            },
            {
                "id": "ixic_prices", "group": "tn_price", "layer": "raw", "status": "live",
                "name": "ixic_prices", "mat": "table (^IXIC rows)", "cadence": "daily",
                "dagster": "thennow/ixic_prices", "dbt": "ixic_prices",
                "grain": "one row per trading day",
                "why": "The landed ^IXIC daily close.",
                "desc": "The ^IXIC slice of the prices table in oracle.db.",
                "upstream": ["raw.yahoo_ixic"],
                "schema": [
                    {"col": "date", "type": "TEXT", "kind": "key", "ex": "2000-03-10", "note": "the declared peak day"},
                    {"col": "close", "type": "REAL", "kind": "pass", "ex": {"live": "peak"}, "note": "Nasdaq close (smoothed peak shown)"},
                ],
                "transforms": [{"tag": "flatten", "text": "epoch/OHLC arrays → daily rows"}],
                "tests": ["unique: date", "not_null: close"],
                "cardinality": "daily trading days since 1971.",
            },
            {
                "id": "stg_ixic_filled", "group": "tn_price", "layer": "staging", "status": "live",
                "name": "stg_ixic_filled", "mat": "table", "cadence": "on generate",
                "dagster": "thennow/stg_ixic_filled", "dbt": "stg_ixic_filled",
                "grain": "one row per calendar day, per era window",
                "why": "A gap-free daily grid so the smoother sees every day, weekends and holidays included.",
                "desc": "Trims ^IXIC to the two declared era windows and forward-fills non-trading days with the last close (no invented intra-gap motion). oracle/thennow.py (_grid + _fill).",
                "upstream": ["ixic_prices"],
                "schema": [
                    {"col": "era", "type": "STRING", "kind": "key", "ex": "ai", "note": "dotcom | ai"},
                    {"col": "date", "type": "DATE", "kind": "key", "ex": "{{asOf}}"},
                    {"col": "close", "type": "NUMERIC", "kind": "derived", "ex": {"live": "rawNow"}, "note": "forward-filled"},
                ],
                "transforms": [
                    {"tag": "trim", "text": "to the declared era windows"},
                    {"tag": "forward-fill", "text": "carry last close over non-trading days"},
                ],
                "cardinality": "daily; {{dotWk}}+{{aiWk}} weekly points shipped.",
            },
            {
                "id": "int_ixic_metric", "group": "tn_price", "layer": "intermediate", "status": "live",
                "name": "int_ixic_metric", "mat": "table", "cadence": "on generate",
                "dagster": "thennow/int_ixic_metric", "dbt": "int_ixic_metric",
                "grain": "one row per (era, day)",
                "why": "Applies the declared formula. For price the metric input is just the close.",
                "desc": "Registry: formula = close, type = ratio_from_start. The generic normalization step below indexes it.",
                "upstream": ["stg_ixic_filled"],
                "schema": [
                    {"col": "date", "type": "DATE", "kind": "key", "ex": "{{asOf}}"},
                    {"col": "value", "type": "NUMERIC", "kind": "derived", "ex": {"live": "rawNow"}, "note": "= close"},
                ],
                "transforms": [{"tag": "formula", "text": "value = close"}],
                "cardinality": "1:1 with the daily grid.",
            },
            {
                "id": "int_ixic_smoothed", "group": "tn_price", "layer": "intermediate", "status": "live",
                "name": "int_ixic_smoothed", "mat": "table", "cadence": "on generate",
                "dagster": "thennow/int_ixic_smoothed", "dbt": "int_ixic_smoothed",
                "grain": "one row per (era, day)",
                "why": "A centered mean so the equivalent point reads cleanly, with intensity=100% anchored to the declared peak.",
                "desc": "Centered moving average, edge-truncated at today, materialized at both the 90-day '3-month' (default) and 30-day '1-month' windows; the page's Options drawer toggles which one is read. _smooth_centered.",
                "upstream": ["int_ixic_metric"],
                "schema": [
                    {"col": "date", "type": "DATE", "kind": "key", "ex": "{{asOf}}"},
                    {"col": "smoothed", "type": "NUMERIC", "kind": "derived", "ex": {"live": "smNow"}, "note": "now; smoothed peak ≈ {{peak}}"},
                ],
                "transforms": [{"tag": "smooth", "text": "centered 90-day mean (min-periods at the edge)"}],
                "tests": ["not_null: smoothed"],
                "cardinality": "1:1 with the daily grid.",
            },
            {
                "id": "int_ixic_intensity", "group": "tn_price", "layer": "intermediate", "status": "live",
                "name": "int_ixic_intensity", "mat": "table", "cadence": "on generate",
                "dagster": "thennow/int_ixic_intensity", "dbt": "int_ixic_intensity",
                "grain": "one row per (era, day)",
                "why": "The shared 0–1 intensity: 0 at the dot-com starting level, 1 at the declared peak.",
                "desc": "ratio_from_start: index each era to its own start, then map onto the dot-com appreciation range. AI's high absolute price is normalized away, so this reads 'how far it has run'. _normalize.",
                "upstream": ["int_ixic_smoothed"],
                "schema": [
                    {"col": "date", "type": "DATE", "kind": "key", "ex": "{{asOf}}"},
                    {"col": "progress", "type": "NUMERIC", "kind": "derived", "ex": "days ÷ ramp × 100"},
                    {"col": "intensity", "type": "NUMERIC", "kind": "derived", "ex": {"live": "intensity"}, "note": "0 start, 1 peak"},
                ],
                "transforms": [{"tag": "normalize", "text": "intensity = (appreciation − 1) / (dot-com peak appreciation − 1)"}],
                "tests": ["accepted_range: dot-com spans 0→1 to the peak"],
                "cardinality": "1:1; weekly-downsampled for the page.",
            },
            {
                "id": "int_ixic_validated", "group": "tn_price", "layer": "intermediate", "status": "live",
                "name": "int_ixic_validated", "mat": "table", "cadence": "on generate",
                "dagster": "thennow/int_ixic_validated", "dbt": "int_ixic_validated",
                "grain": "one verdict per metric (+ one row per check)",
                "why": "A gate. Only a series that rises, peaks, and falls like the dot-com reference, with AI below that peak and moving toward it, earns a projection. A non-conforming metric is still shown, but its projected date is suppressed so it can't fake precision.",
                "desc": "Two passes over the daily curves: candidacy (covers both eras, real dynamic range) then shape (interior peak, AI below the peak, AI rising). Emits {valid, checks[], observations}. The verdict and numbers are computed; a cached, hash-gated Haiku call writes the prose on top (deterministic fallback). _validate + observe.refresh_observations.",
                "upstream": ["int_ixic_intensity"],
                "schema": [
                    {"col": "check", "type": "TEXT", "kind": "key", "ex": "rise, peak, fall"},
                    {"col": "pass", "type": "BOOLEAN", "kind": "derived", "ex": {"live": "valid"}, "note": "{{checksPass}}/{{checksN}} checks pass → {{verdictWord}}"},
                    {"col": "observations", "type": "TEXT", "kind": "derived", "ex": "Haiku · cached", "note": "{{obs}}"},
                ],
                "transforms": [
                    {"tag": "validate", "text": "candidacy + shape checks → verdict"},
                    {"tag": "observe", "text": "cached, hash-gated Haiku prose (deterministic fallback)"},
                ],
                "tests": ["not_null: valid", "accepted_values: valid in (true, false)"],
                "cardinality": "1 verdict per metric; gates the projection downstream.",
            },
            {
                "id": "graph.nasdaq", "group": "tn_price", "layer": "serve", "status": "live",
                "name": "graph: nasdaq", "mat": "exposure (JSON)", "cadence": "on generate",
                "dagster": "thennow (exposure)", "dbt": "exposure: nasdaq",
                "grain": "one leaf block on thennow.html",
                "why": "The Nasdaq leaf the reader sees: today's Nasdaq intensity matched to a dot-com date, rate-scaled to a projected top. One of the two inputs to the Price-appreciation blend.",
                "desc": "Match today's intensity on the dot-com ramp → equivalent date; rate-scale the remainder → projected peak. Ships exact daily scalars + a weekly series still carrying the native Nasdaq value for hover/CSV. Projection drawn only if int_ixic_validated conforms. _evaluate + _emit.",
                "upstream": ["int_ixic_validated"],
                "json": "{ \"intensityNow\": {{intensity}}, \"equivalentDotcomDate\": \"{{equiv}}\",\n  \"daysFromPeak\": {{daysFromPeak}}, \"projectedPeakDate\": \"{{proj}}\",\n  \"nasdaqNow\": {{rawNow}}, \"display\": \"{{display}}\" }",
                "transforms": [
                    {"tag": "lookup", "text": "value-match on the dot-com ramp → equivalent date"},
                    {"tag": "rate-scale", "text": "remaining distance × AI pace → projected top"},
                    {"tag": "downsample", "text": "daily scalars + weekly plot series"},
                ],
                "cardinality": "one leaf node on the Then-and-Now page.",
            },
        ],
        "graph": {"vchain": {
            "ids": ["raw.yahoo_ixic", "ixic_prices", "stg_ixic_filled", "int_ixic_metric",
                    "int_ixic_smoothed", "int_ixic_intensity", "int_ixic_validated", "graph.nasdaq"],
            "shorts": {"raw.yahoo_ixic": "raw: yahoo ^IXIC", "graph.nasdaq": "graph: nasdaq"},
        }},
        "source_info": {
            "blurb": "Price · Nasdaq (WIP): the Nasdaq leaf on its own self-contained daily pipeline. ^IXIC indexed to each era's start, so it reads 'how far the cycle has run'. One of the two inputs to the Price-appreciation blend; on price alone AI looks earlier and less stretched than 1995–2000.",
            "options": [
                {"t": "Smoothing window", "d": "A centered moving average on the daily series, materialized at two windows: 90-day '3-month' (default) and 30-day '1-month', anchored so intensity=100% lands on the declared 2000 peak. The page's Options drawer toggles between them and every projected date shifts."},
            ],
            "ambiguities": [
                {"t": "Price, not a multiple", "d": "This leaf measures appreciation, not richness. Its counterweight is the Valuation multiple (CAPE) leaf, which reads late. The Valuation roll-up reconciles them."},
                {"t": "Nasdaq is one of two", "d": "Price appreciation blends this Nasdaq leaf with the broader S&P 500 leaf, so neither index alone drives the price argument."},
            ],
            "caveats": [
                {"t": "WIP prototype", "d": "Method and copy will change. Not linked in the site nav; reachable by direct URL only."},
                {"t": "Declared clock", "d": "The cycle dates (Netscape 1995-08-09, peak 2000-03-10, low 2002-10-09) are declared, not derived, and shared by every metric."},
                {"t": "Validated and annotated", "d": "A two-pass validator gates the projection: a non-conforming series is shown but its date is suppressed. A cached, hash-gated Haiku call writes one or two sentences of observation on top of the computed verdict (deterministic fallback with no key)."},
            ],
            "cardinality": [
                {"asset": "raw.yahoo_ixic", "count": "1 doc", "meaning": "Full ^IXIC daily history from Yahoo."},
                {"asset": "stg_ixic_filled", "count": "{{dotWk}}+{{aiWk}}", "meaning": "Weekly plot points shipped, computed on a gap-free daily grid."},
                {"asset": "int_ixic_intensity", "count": "1:1", "meaning": "Each day mapped to 0–1 intensity (0 dot-com start, 1 the 2000 peak)."},
                {"asset": "int_ixic_validated", "count": "1 verdict", "meaning": "{{checksN}} checks → {{verdictLong}}."},
                {"asset": "graph.nasdaq", "count": "1 leaf", "meaning": "The Nasdaq leaf's projected top; one input to the Price-appreciation blend."},
            ],
        },
    },
}

SP500 = {
    "key": "sp500", "label": "S&P 500", "parent": "price_appreciation", "order": 20,
    "kind": "sp500", "source": ("prices", "^GSPC"),
    "formula": lambda r: r["close"], "cadence": "daily",
    "type": "ratio_from_start", "direction": "up", "unit": "sp500_close",
    "unitLabel": "S&P 500",
    "ir": {
        "group": "tn_sp500", "group_name": "Price · S&P 500 (WIP)", "foreign_from": "S&P 500",
        "assets": [
            {
                "id": "raw.yahoo_gspc", "group": "tn_sp500", "layer": "source", "status": "live",
                "name": "raw.yahoo_gspc", "mat": "API response (JSON)", "cadence": "daily",
                "dagster": "thennow/yahoo_gspc", "dbt": "source('yahoo','gspc')",
                "grain": "one JSON document (daily bars for ^GSPC)",
                "why": "The broad-market counterpart to the Nasdaq leaf: the S&P 500, a wider read on the same price cycle.",
                "desc": "Yahoo v8 chart for ^GSPC, split-adjusted daily closes. Its own self-contained chain; it shares nothing downstream with the Nasdaq or CAPE pipelines.",
                "upstream": [],
                "transforms": [{"tag": "extract", "text": "HTTP GET ^GSPC daily bars"}],
                "cardinality": "one document, full daily history since 1970.",
            },
            {
                "id": "gspc_prices", "group": "tn_sp500", "layer": "raw", "status": "live",
                "name": "gspc_prices", "mat": "table (^GSPC rows)", "cadence": "daily",
                "dagster": "thennow/gspc_prices", "dbt": "gspc_prices",
                "grain": "one row per trading day",
                "why": "The landed ^GSPC daily close.",
                "desc": "The ^GSPC slice of the prices table in oracle.db.",
                "upstream": ["raw.yahoo_gspc"],
                "schema": [
                    {"col": "date", "type": "TEXT", "kind": "key", "ex": "2000-03-24", "note": "the S&P's own 2000 top"},
                    {"col": "close", "type": "REAL", "kind": "pass", "ex": {"live": "peak"}, "note": "S&P close (smoothed peak shown)"},
                ],
                "transforms": [{"tag": "flatten", "text": "epoch/OHLC arrays → daily rows"}],
                "tests": ["unique: date", "not_null: close"],
                "cardinality": "daily trading days since 1970.",
            },
            {
                "id": "stg_gspc_filled", "group": "tn_sp500", "layer": "staging", "status": "live",
                "name": "stg_gspc_filled", "mat": "table", "cadence": "on generate",
                "dagster": "thennow/stg_gspc_filled", "dbt": "stg_gspc_filled",
                "grain": "one row per calendar day, per era window",
                "why": "A gap-free daily grid so the smoother sees every day, weekends and holidays included.",
                "desc": "Trims ^GSPC to the two declared era windows and forward-fills non-trading days with the last close. Identical machinery to the Nasdaq chain, run on its own data. _grid + _fill.",
                "upstream": ["gspc_prices"],
                "schema": [
                    {"col": "era", "type": "STRING", "kind": "key", "ex": "ai", "note": "dotcom | ai"},
                    {"col": "date", "type": "DATE", "kind": "key", "ex": "{{asOf}}"},
                    {"col": "close", "type": "NUMERIC", "kind": "derived", "ex": {"live": "rawNow"}, "note": "forward-filled"},
                ],
                "transforms": [
                    {"tag": "trim", "text": "to the declared era windows"},
                    {"tag": "forward-fill", "text": "carry last close over non-trading days"},
                ],
                "cardinality": "daily; {{dotWk}}+{{aiWk}} weekly points shipped.",
            },
            {
                "id": "int_gspc_metric", "group": "tn_sp500", "layer": "intermediate", "status": "live",
                "name": "int_gspc_metric", "mat": "table", "cadence": "on generate",
                "dagster": "thennow/int_gspc_metric", "dbt": "int_gspc_metric",
                "grain": "one row per (era, day)",
                "why": "Applies the declared formula. For the S&P the metric input is just the close.",
                "desc": "Registry: formula = close, type = ratio_from_start. Same declaration as Nasdaq, different source.",
                "upstream": ["stg_gspc_filled"],
                "schema": [
                    {"col": "date", "type": "DATE", "kind": "key", "ex": "{{asOf}}"},
                    {"col": "value", "type": "NUMERIC", "kind": "derived", "ex": {"live": "rawNow"}, "note": "= close"},
                ],
                "transforms": [{"tag": "formula", "text": "value = close"}],
                "cardinality": "1:1 with the daily grid.",
            },
            {
                "id": "int_gspc_smoothed", "group": "tn_sp500", "layer": "intermediate", "status": "live",
                "name": "int_gspc_smoothed", "mat": "table", "cadence": "on generate",
                "dagster": "thennow/int_gspc_smoothed", "dbt": "int_gspc_smoothed",
                "grain": "one row per (era, day)",
                "why": "A centered mean so the equivalent point reads cleanly, anchored so intensity=100% lands on the declared peak.",
                "desc": "Centered moving average, edge-truncated at today, materialized at both the 90-day '3-month' (default) and 30-day '1-month' windows; the page's Options drawer toggles which one is read. _smooth_centered.",
                "upstream": ["int_gspc_metric"],
                "schema": [
                    {"col": "date", "type": "DATE", "kind": "key", "ex": "{{asOf}}"},
                    {"col": "smoothed", "type": "NUMERIC", "kind": "derived", "ex": {"live": "smNow"}, "note": "now; smoothed peak ≈ {{peak}}"},
                ],
                "transforms": [{"tag": "smooth", "text": "centered 90-day mean (min-periods at the edge)"}],
                "tests": ["not_null: smoothed"],
                "cardinality": "1:1 with the daily grid.",
            },
            {
                "id": "int_gspc_intensity", "group": "tn_sp500", "layer": "intermediate", "status": "live",
                "name": "int_gspc_intensity", "mat": "table", "cadence": "on generate",
                "dagster": "thennow/int_gspc_intensity", "dbt": "int_gspc_intensity",
                "grain": "one row per (era, day)",
                "why": "The shared 0–1 intensity: 0 at the dot-com starting level, 1 at the declared peak.",
                "desc": "ratio_from_start: index each era to its own start, then map onto the dot-com appreciation range, same as Nasdaq. _normalize.",
                "upstream": ["int_gspc_smoothed"],
                "schema": [
                    {"col": "date", "type": "DATE", "kind": "key", "ex": "{{asOf}}"},
                    {"col": "progress", "type": "NUMERIC", "kind": "derived", "ex": "days ÷ ramp × 100"},
                    {"col": "intensity", "type": "NUMERIC", "kind": "derived", "ex": {"live": "intensity"}, "note": "0 start, 1 peak"},
                ],
                "transforms": [{"tag": "normalize", "text": "intensity = (appreciation − 1) / (dot-com peak appreciation − 1)"}],
                "tests": ["accepted_range: dot-com spans 0→1 to the peak"],
                "cardinality": "1:1; weekly-downsampled for the page.",
            },
            {
                "id": "int_gspc_validated", "group": "tn_sp500", "layer": "intermediate", "status": "live",
                "name": "int_gspc_validated", "mat": "table", "cadence": "on generate",
                "dagster": "thennow/int_gspc_validated", "dbt": "int_gspc_validated",
                "grain": "one verdict per metric (+ one row per check)",
                "why": "The same gate as every metric, run independently on the S&P. Earns a projection only if the S&P rises, peaks, and falls like the dot-com reference with AI below that peak and rising.",
                "desc": "Two passes over the S&P's daily curves: candidacy then shape. Emits {valid, checks[], observations}; the verdict and numbers are computed, a cached hash-gated Haiku call writes the prose (deterministic fallback). _validate + observe.refresh_observations.",
                "upstream": ["int_gspc_intensity"],
                "schema": [
                    {"col": "check", "type": "TEXT", "kind": "key", "ex": "rise, peak, fall"},
                    {"col": "pass", "type": "BOOLEAN", "kind": "derived", "ex": {"live": "valid"}, "note": "{{checksPass}}/{{checksN}} checks pass → {{verdictWord}}"},
                    {"col": "observations", "type": "TEXT", "kind": "derived", "ex": "Haiku · cached", "note": "{{obs}}"},
                ],
                "transforms": [
                    {"tag": "validate", "text": "candidacy + shape checks → verdict"},
                    {"tag": "observe", "text": "cached, hash-gated Haiku prose (deterministic fallback)"},
                ],
                "tests": ["not_null: valid", "accepted_values: valid in (true, false)"],
                "cardinality": "1 verdict per metric; gates the projection downstream.",
            },
            {
                "id": "graph.sp500", "group": "tn_sp500", "layer": "serve", "status": "live",
                "name": "graph: sp500", "mat": "exposure (JSON)", "cadence": "on generate",
                "dagster": "thennow (exposure)", "dbt": "exposure: sp500",
                "grain": "one leaf block on thennow.html",
                "why": "The S&P leaf the reader sees, the second input to the Price-appreciation blend. Broader and less concentrated than the Nasdaq, so it usually reads a touch earlier.",
                "desc": "Same _evaluate() + _emit() as the Nasdaq leaf, run on the S&P's own intensity. Projection drawn only if int_gspc_validated conforms.",
                "upstream": ["int_gspc_validated"],
                "json": "{ \"intensityNow\": {{intensity}}, \"equivalentDotcomDate\": \"{{equiv}}\",\n  \"daysFromPeak\": {{daysFromPeak}}, \"projectedPeakDate\": \"{{proj}}\",\n  \"sp500Now\": {{rawNow}}, \"display\": \"{{display}}\" }",
                "transforms": [
                    {"tag": "lookup", "text": "value-match on the dot-com ramp → equivalent date"},
                    {"tag": "rate-scale", "text": "remaining distance × AI pace → projected top"},
                    {"tag": "downsample", "text": "daily scalars + weekly plot series"},
                ],
                "cardinality": "one leaf node on the Then-and-Now page.",
            },
        ],
        "graph": {"vchain": {
            "ids": ["raw.yahoo_gspc", "gspc_prices", "stg_gspc_filled", "int_gspc_metric",
                    "int_gspc_smoothed", "int_gspc_intensity", "int_gspc_validated", "graph.sp500"],
            "shorts": {"raw.yahoo_gspc": "raw: yahoo ^GSPC", "graph.sp500": "graph: sp500"},
        }},
        "source_info": {
            "blurb": "Price · S&P 500 (WIP): the broad-market price leaf on its own daily pipeline, wholly separate from the Nasdaq chain. ^GSPC indexed to each era's start. Wider and less tech-concentrated than the Nasdaq, so it is the second, steadier voice in the Price-appreciation blend.",
            "options": [
                {"t": "Smoothing window", "d": "The same centered daily moving average as every metric, materialized at 90-day '3-month' (default) and 30-day '1-month' windows, anchored so intensity=100% lands on the declared 2000 peak."},
            ],
            "ambiguities": [
                {"t": "Broad vs narrow", "d": "The S&P captures the whole market, the Nasdaq the tech-heavy leaders. Blending them keeps the price argument from resting on one index's composition."},
            ],
            "caveats": [
                {"t": "WIP prototype", "d": "Method and copy will change. Direct URL only."},
                {"t": "Same clock, same gate", "d": "Runs on the identical declared clock, centered smoothing, and two-pass validator + cached observation as the other metrics; only the source differs."},
            ],
            "cardinality": [
                {"asset": "raw.yahoo_gspc", "count": "1 doc", "meaning": "Full ^GSPC daily history from Yahoo."},
                {"asset": "stg_gspc_filled", "count": "{{dotWk}}+{{aiWk}}", "meaning": "Weekly plot points shipped, computed on a gap-free daily grid."},
                {"asset": "int_gspc_intensity", "count": "1:1", "meaning": "Each day mapped to 0–1 intensity (0 dot-com start, 1 the 2000 peak)."},
                {"asset": "int_gspc_validated", "count": "1 verdict", "meaning": "{{checksN}} checks → {{verdictLong}}."},
                {"asset": "graph.sp500", "count": "1 leaf", "meaning": "The S&P leaf's projected top; the second input to the Price-appreciation blend."},
            ],
        },
    },
}

METRICS = [NASDAQ, SP500]
