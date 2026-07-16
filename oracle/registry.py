"""Module discovery, activation gating, and (from Phase 2) tree assembly.

The contributor contract: a data source is one module in oracle/sources/
exporting a SOURCE spec dict; a metric is one module in oracle/metrics/
exporting a METRIC spec (or METRICS list) and optionally its own SOURCE.
Discovery walks both packages with pkgutil; underscore-prefixed modules are
skipped (they are templates/fixtures). A broken module fails the build loudly:
the public site must never silently drop a leaf.

SOURCE spec fields (see any module in oracle/sources/ for a live example):
  kind             str, unique; what metric declarations reference
  label            human name
  requires         [env var names]; non-empty => credential-gated
  redistributable  False => data must never be committed (csv must be None)
  csv              committed fallback CSV path or None
  ddl              optional CREATE TABLE IF NOT EXISTS ... for bespoke schema
  order            int; update() sequencing in cmd_update
  date_col/value_col  the columns the engine reads through `load`
  update           (conn) -> None, or None; must degrade gracefully offline
  load             (conn, arg) -> ordered rows, or None for tracker-only sources

Activation: a module is active when its `requires` env vars are all present
(and, for metrics from Phase 2 on, `enabled_by_default`/ORACLE_ENABLE says so).
The nightly Action sets no ORACLE_* variables, so the public site is
public-data-only by construction.
"""

import importlib
import os
import pkgutil


def _iter_modules(pkg):
    for m in sorted(mm.name for mm in pkgutil.iter_modules(pkg.__path__)):
        if m.startswith("_"):
            continue
        yield importlib.import_module(f"{pkg.__name__}.{m}")


_SOURCES = None


def sources():
    """{kind: SOURCE spec} for every module in oracle/sources/ (memoized)."""
    global _SOURCES
    if _SOURCES is None:
        from . import sources as pkg
        out = {}
        for mod in _iter_modules(pkg):
            spec = getattr(mod, "SOURCE", None)
            if spec is None:
                continue
            if spec["kind"] in out:
                raise RuntimeError(f"duplicate source kind {spec['kind']!r} ({mod.__name__})")
            out[spec["kind"]] = spec
        _SOURCES = out
    return _SOURCES


def missing_env(spec):
    """Names of the spec's required env vars that are not set."""
    return sorted(v for v in spec.get("requires", []) if not os.environ.get(v))


def ordered_sources():
    """Active sources with an update step, in declared order, plus the skip
    list [(spec, missing_vars)] for reporting."""
    active, skipped = [], []
    for s in sorted(sources().values(), key=lambda s: (s.get("order", 999), s["kind"])):
        miss = missing_env(s)
        if miss:
            skipped.append((s, miss))
        elif s.get("update"):
            active.append(s)
    return active, skipped


def ensure_schema(conn):
    """Apply any bespoke-schema DDL declared by active sources (idempotent)."""
    for s in sources().values():
        if s.get("ddl") and not missing_env(s):
            conn.executescript(s["ddl"])
    conn.commit()


# ---------------------------------------------------------------------- metrics
_METRICS = None


def _discover_metrics():
    """(metrics, branches) from every module in oracle/metrics/ + _tree.py."""
    global _METRICS
    if _METRICS is None:
        from . import metrics as pkg
        from .metrics import _tree
        metrics, branches = [], list(_tree.BRANCHES)
        for mod in _iter_modules(pkg):
            metrics += getattr(mod, "METRICS", [mod.METRIC] if hasattr(mod, "METRIC") else [])
            branches += getattr(mod, "BRANCHES", [mod.BRANCH] if hasattr(mod, "BRANCH") else [])
        seen = set()
        for spec in metrics + branches:
            if spec["key"] in seen:
                raise RuntimeError(f"duplicate tree key {spec['key']!r} across metric modules")
            seen.add(spec["key"])
        _METRICS = (metrics, branches)
    return _METRICS


def _source_kinds(spec):
    if "series" in spec:
        return [kind for kind, _arg in spec["series"].values()]
    return [spec["source"][0]]


def metric_missing_env(spec):
    """The metric's own `requires` plus every referenced source's, unmet only."""
    req = set(spec.get("requires", []))
    for kind in _source_kinds(spec):
        src = sources().get(kind)
        if src:
            req |= set(src.get("requires", []))
    return sorted(v for v in req if not os.environ.get(v))


def _env_set(name):
    return set(filter(None, (os.environ.get(name) or "").split(",")))


def is_active(spec):
    """A metric is built when it is enabled (by default or via ORACLE_ENABLE),
    not disabled via ORACLE_DISABLE, and every required credential is present.
    The nightly Action sets neither variable, so the public site is
    public-data-only by construction."""
    enabled = (spec.get("enabled_by_default", True) or spec["key"] in _env_set("ORACLE_ENABLE"))
    if spec["key"] in _env_set("ORACLE_DISABLE"):
        enabled = False
    return enabled and not metric_missing_env(spec)


def _stub_reason(spec):
    miss = metric_missing_env(spec)
    if miss:
        return spec.get("requires_label") or f"needs {', '.join(miss)}"
    return spec.get("requires_label", "disabled")


def build_tree():
    """Assemble the Then & Now tree from discovered branches + metrics,
    replacing the old hardcoded literal. Active metrics become engine leaves;
    discovered-but-inactive metrics become stub rows (shown in the sidebar
    tree as 'available, needs credentials', never blended, no card)."""
    metrics, branches = _discover_metrics()
    from .metrics._tree import ROOT
    kids = {}
    for b in branches:
        kids.setdefault(b["parent"], []).append(("branch", b))
    for m in metrics:
        tag = "leaf" if is_active(m) else "stub"
        kids.setdefault(m["parent"], []).append((tag, m))

    def node(key, label):
        out = {"key": key, "label": label, "children": []}
        for tag, spec in sorted(kids.get(key, []), key=lambda t: (t[1].get("order", 999), t[1]["key"])):
            if tag == "leaf":
                out["children"].append({"key": spec["key"], "label": spec["label"], "metric": spec})
            elif tag == "stub":
                out["children"].append({"key": spec["key"], "label": spec["label"],
                                        "stub": True, "requires": _stub_reason(spec)})
            else:
                sub = node(spec["key"], spec["label"])
                if spec.get("weights"):
                    # declared default child weights (see the branch's comment in
                    # metrics/_tree.py); the engine blend and the page's sliders
                    # both start from these
                    sub["weights"] = spec["weights"]
                out["children"].append(sub)
        return out

    return node(ROOT["key"], ROOT["label"])


def required_tickers():
    """Every Yahoo ticker the ACTIVE metric set reads (kind 'prices')."""
    metrics, _branches = _discover_metrics()
    out = []
    for m in metrics:
        if not is_active(m):
            continue
        pairs = list(m["series"].values()) if "series" in m else [m["source"]]
        out += [arg for kind, arg in pairs if kind == "prices" and arg]
    return list(dict.fromkeys(out))


def ir_entries():
    """The Data Sources IR bundle order: post-order DFS of the tree (children
    before their branch), ACTIVE metrics only, branches always. Reproduces the
    old hand-authored GROUPS order exactly. Entries without an `ir` block are
    skipped (the metric still runs; it just isn't documented on the page)."""
    metrics, branches = _discover_metrics()
    kids = {}
    for b in branches:
        kids.setdefault(b["parent"], []).append(("branch", b))
    for m in metrics:
        if is_active(m):
            kids.setdefault(m["parent"], []).append(("leaf", m))

    out = []

    def walk(key):
        for tag, spec in sorted(kids.get(key, []), key=lambda t: (t[1].get("order", 999), t[1]["key"])):
            if tag == "branch":
                walk(spec["key"])
            if "ir" in spec:
                out.append({"spec": spec, "branch": tag == "branch"})

    from .metrics._tree import ROOT
    walk(ROOT["key"])
    return out


def src_groups():
    """thennow.html's leaf-kind / branch-key → Data Sources group anchor map,
    from the modules' ir declarations (replaces the old SRC_GROUP literal)."""
    metrics, branches = _discover_metrics()
    out = {}
    for m in metrics:
        if is_active(m) and "ir" in m:
            out[m["kind"]] = m["ir"]["group"]
    for b in branches:
        if "ir" in b:
            out[b["key"]] = b["ir"]["group"]
    return out


def report():
    """One console block on what the module system resolved to."""
    metrics, _branches = _discover_metrics()
    active = [m for m in metrics if is_active(m)]
    stubs = [(m, _stub_reason(m)) for m in metrics if not is_active(m)]
    line = f"metrics: {len(active)} active"
    if stubs:
        details = "; ".join(f"{m['key']}: {r}" for m, r in stubs)
        line += f" · {len(stubs)} stub ({details})"
    print(line)


# -------------------------------------------------------------------- spec lint
_CADENCES = {"daily", "weekly", "monthly", "quarterly", "annual"}
_TYPES = {"ratio_from_start", "absolute_level"}
_DIRECTIONS = {"up", "down"}


def _lint_metric(spec, srcs, branch_keys, errs, where):
    def bad(msg):
        errs.append(f"{where}: {msg}")

    for field in ("key", "label", "parent", "kind", "formula", "cadence",
                  "type", "direction", "unit", "unitLabel"):
        if field not in spec:
            bad(f"missing required field {field!r}")
    if ("source" in spec) == ("series" in spec):
        bad("must declare exactly one of 'source' or 'series'")
    if spec.get("cadence") not in _CADENCES:
        bad(f"cadence must be one of {sorted(_CADENCES)}")
    if spec.get("type") not in _TYPES:
        bad(f"type must be one of {sorted(_TYPES)}")
    if spec.get("direction") not in _DIRECTIONS:
        bad("direction must be 'up' or 'down'")
    if spec.get("parent") not in branch_keys:
        bad(f"parent {spec.get('parent')!r} is not a known branch key")
    if not isinstance(spec.get("order", 0), int):
        bad("order must be an int")
    if not isinstance(spec.get("requires", []), list) or \
            not all(isinstance(v, str) for v in spec.get("requires", [])):
        bad("requires must be a list of env-var name strings")
    # every referenced source kind must be registered
    probe_row = {}
    try:
        for kind in _source_kinds(spec):
            src = srcs.get(kind)
            if src is None:
                bad(f"references unregistered source kind {kind!r}")
            elif "series" not in spec:
                probe_row[src["value_col"]] = 1.0
        if "series" in spec:
            probe_row = {alias: 1.0 for alias in spec["series"]}
    except (KeyError, TypeError):
        bad("malformed source/series declaration")
    # formula probe: synthetic row; only the engine-tolerated exceptions allowed
    f = spec.get("formula")
    if not callable(f):
        bad("formula must be callable")
    elif probe_row:
        try:
            f(probe_row)
        except (KeyError, TypeError, ZeroDivisionError):
            pass                       # engine tolerates these per-row
        except Exception as e:         # noqa: BLE001 — lint reports anything else
            bad(f"formula raised {type(e).__name__} on a synthetic row: {e}")
    # IR (optional; a metric without one runs but isn't documented on the
    # Data Sources page) must be pure JSON prose + the fields the page needs
    if "ir" in spec:
        _lint_ir(spec["ir"], bad)


def _lint_ir(ir, bad):
    import json
    try:
        json.dumps(ir)
    except (TypeError, ValueError) as e:
        bad(f"ir is not JSON-serializable: {e}")
        return
    for field in ("group", "group_name", "source_info"):
        if field not in ir:
            bad(f"ir missing {field!r}")
    forms = [f for f in ("assets", "leaf_chain", "rollup") if f in ir]
    if len(forms) != 1:
        bad("ir must declare exactly one of 'assets', 'leaf_chain', or 'rollup'")
    g = ir.get("graph") or {}
    if not any(k in g for k in ("vchain", "join", "explicit")):
        bad("ir.graph must declare one of 'vchain', 'join', or 'explicit'")
    info = ir.get("source_info") or {}
    for field in ("blurb", "options", "ambiguities", "caveats", "cardinality"):
        if field not in info:
            bad(f"ir.source_info missing {field!r}")


def _lint_source(spec, errs, where):
    def bad(msg):
        errs.append(f"{where}: {msg}")

    for field in ("kind", "label", "requires", "redistributable", "csv",
                  "date_col", "value_col"):
        if field not in spec:
            bad(f"missing required field {field!r}")
    if spec.get("redistributable") is False and spec.get("csv") is not None:
        bad("redistributable: False requires csv: None (licensed data must never be committed)")
    if not isinstance(spec.get("requires", []), list):
        bad("requires must be a list of env-var name strings")
    for fn in ("update", "load"):
        if spec.get(fn) is not None and not callable(spec[fn]):
            bad(f"{fn} must be callable or None")


def check():
    """The contributor-contract lint. Returns a list of problem strings (empty
    = green). Covers every DISCOVERED module plus the _template.py fixture, the
    repo-level data-licensing rule, the workflow guard, and the templates'
    __DATA__ sentinels. Runs with no network and no credentials."""
    from .config import PROJECT_DIR
    errs = []

    srcs = sources()
    for kind, s in srcs.items():
        _lint_source(s, errs, f"source {kind}")
        # licensed sources must have no committed data for their kind
        if s.get("redistributable") is False:
            ext = PROJECT_DIR / "data" / f"ext_{kind}.csv"
            if ext.exists():
                errs.append(f"source {kind}: redistributable=False but {ext.name} is committed")

    metrics, branches = _discover_metrics()
    branch_keys = {b["key"] for b in branches} | {"ai_peak"}
    for b in branches:
        for field in ("key", "label", "parent", "order"):
            if field not in b:
                errs.append(f"branch {b.get('key', '?')}: missing {field!r}")
        if "ir" in b:
            _lint_ir(b["ir"], lambda msg, _k=b.get("key", "?"): errs.append(f"branch {_k}: {msg}"))
    for m in metrics:
        _lint_metric(m, srcs, branch_keys, errs, f"metric {m.get('key', '?')}")

    # the underscore template is not discovered; lint it explicitly so the
    # credential-gating path is exercised on every CI run
    tpl_path = PROJECT_DIR / "oracle" / "metrics" / "_template.py"
    if tpl_path.exists():
        tpl = importlib.import_module("oracle.metrics._template")
        t_metric = getattr(tpl, "METRIC", None)
        t_source = getattr(tpl, "SOURCE", None)
        if t_metric is None or t_source is None:
            errs.append("_template.py must export both METRIC and SOURCE")
        else:
            _lint_source(t_source, errs, "template source")
            _lint_metric(t_metric, {**srcs, t_source["kind"]: t_source},
                         branch_keys, errs, "template metric")
            if t_metric.get("enabled_by_default", True):
                errs.append("_template.py METRIC must set enabled_by_default: False")
            if not t_metric.get("requires") and not t_source.get("requires"):
                errs.append("_template.py must declare `requires` (it demonstrates credential gating)")
            if is_active(t_metric):
                errs.append("_template.py fixture unexpectedly ACTIVE (env leak into lint?)")
            ext = PROJECT_DIR / "data" / f"ext_{t_source['kind']}.csv"
            if t_source.get("redistributable") is False and ext.exists():
                errs.append(f"template source: redistributable=False but {ext.name} is committed")

    # the public site must stay public-data-only: the nightly Action never
    # activates gated modules
    wf = PROJECT_DIR / ".github" / "workflows" / "daily-update.yml"
    if wf.exists() and "ORACLE_ENABLE" in wf.read_text(encoding="utf-8"):
        errs.append("daily-update.yml must not set ORACLE_ENABLE (public site is public-data-only)")

    # each template carries exactly one __DATA__ sentinel (verify-pages relies on it)
    for tmpl in ("thennow_template.html", "dashboard_template.html", "datasources_template.html"):
        n = (PROJECT_DIR / "oracle" / tmpl).read_text(encoding="utf-8").count("__DATA__")
        if n != 1:
            errs.append(f"oracle/{tmpl}: expected exactly one __DATA__ sentinel, found {n}")

    return errs
