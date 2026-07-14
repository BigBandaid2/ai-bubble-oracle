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
                out["children"].append(node(spec["key"], spec["label"]))
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
