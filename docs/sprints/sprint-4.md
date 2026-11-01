# Sprint 4: PostgreSQL model and SQL pack

**Goal:** a normalised relational model with real keys, indexes and
versioned migrations, plus advanced SQL an interviewer can read.

Delivered
- `postgres/migrations/V001–V004`: reference tables, county → district →
  property hierarchy, sales, unlogged staging table, analyst view.
  `UNIQUE NULLS NOT DISTINCT` natural key on addresses, BRIN index on dates.
- `src/ppd/migrate.py`: applies migrations in order, one transaction each,
  records checksums and refuses edited migrations.
- `src/ppd/load_postgres.py`: DuckDB → CSV → `COPY` → set-based upserts in
  one transaction; source deletes removed; row-count reconciliation.
- `sql/queries/01–05`: repeat-sales growth, ranked districts, new-build
  premium, gaps-and-islands streaks, rolling volume.
- `scripts/explain_queries.py` saves `EXPLAIN (ANALYZE, BUFFERS)` plans.
- `docs/erd.md`: Mermaid ERDs for Postgres and the star schema.
- Tests: migrations apply once, edited migration refused, second load
  changes nothing, every query in the pack runs.

## Retro
- **Problem:** first version joined addresses with `IS NOT DISTINCT FROM`,
  which PostgreSQL can't hash-join. Switched to `coalesce(col, '')` keys with
  a matching expression index.
- **Open:** query plans must come from the real ~10M-row run; the synthetic
  fixture has no repeat sales, so its plans would mean nothing.
