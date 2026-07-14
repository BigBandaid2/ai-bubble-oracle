<!-- See CONTRIBUTING.md for the ground rules and docs/ADDING-A-METRIC.md
for the metric walkthrough. -->

**What this changes**

**Payload impact**

<!-- "Byte-identical" (refactor), or list the added/changed payload keys.
Workflow: `python main.py payload` before/after, `git diff --no-index`. -->

**For new metrics**

- Expected verdict (conforms / counter-argument) and why:
- Source license and fallback-CSV status:

**Checklist**

- [ ] `python main.py check` green
- [ ] `python main.py verify-pages` green after regenerating
- [ ] No new dependencies (stdlib only)
- [ ] No licensed data committed; new CSVs carry `#` provenance headers
- [ ] New metric modules include their `ir` block
- [ ] No `ORACLE_ENABLE` in `.github/workflows/daily-update.yml`
