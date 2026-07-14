"""Metric modules for the Then & Now analogy engine.

One module = one contribution: it exports a METRIC spec dict (or METRICS list),
optionally a BRANCH (a new roll-up under the tree), and optionally its own
SOURCE (a data source private to this metric). See oracle/registry.py for the
spec fields, docs/ADDING-A-METRIC.md for the walkthrough, and _template.py for
a commented skeleton. Underscore-prefixed modules are not discovered.
"""
