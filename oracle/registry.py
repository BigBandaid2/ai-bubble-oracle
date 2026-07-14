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
