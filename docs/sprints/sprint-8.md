# Sprint 8: dashboard, documentation, hand-over

**Goal:** a reviewer can see results, understand the data and operate the
pipeline without asking.

Delivered
- `site/index.html`: static dashboard (headline tiles, monthly median by
  property type, top districts by year, run metadata with file checksums),
  light and dark mode, table view for every chart. Shows a warning banner
  whenever its data came from the synthetic fixture.
- `src/ppd/export_site.py`: marts → `site/data/dashboard.json`.
- `.github/workflows/pages.yml`: deploys `site/` and refuses fixture data.
- `scripts/summarise_run.py`: collects every figure from a run into
  `reports/results.json`.
- Docs: data dictionary with lineage diagram, runbook, cloud guide, follow-up
  roadmap, README skill-to-file map.

## Retro (whole project)
- **Went well:** testing each stage on a small synthetic fixture with the
  exact source layout made the whole pipeline runnable in about a minute,
  in CI and in Airflow.
- **Would do differently:** decide the warehouse targets before writing
  models; two medians (exact vs approximate) were found late.
- **Next:** first real run, commit query plans and dashboard data, then the
  streaming project from `docs/roadmap.md`.
