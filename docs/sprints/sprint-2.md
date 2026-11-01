# Sprint 2: Spark bronze and silver

**Goal:** typed Parquet with the monthly changes applied, safe to re-run.

Delivered
- `src/ppd/spark_transform.py`
  - Bronze: one Parquet folder per landed file version, partitioned by
    `sale_year` / `sale_month`, with source file and load sequence columns.
  - Quarantine: rows whose price, date or ID fail to parse are written to
    `data/quarantine/` and counted in the log, not dropped silently.
  - Silver: merge rules from ADR 0002 (latest yearly snapshot, newer monthly
    changes only, latest row wins, deletes remove), plus derived postcode
    outward code and area.
- Tests (`tests/test_spark.py`): additions, changes and deletes applied with
  exact expected counts; no duplicate transaction IDs; re-run gives the same
  row count; malformed rows quarantined.

## Retro
- **Problem:** Spark 4 runs in ANSI mode, so a single bad price crashed the
  job instead of becoming NULL. Fixed with `try_cast` / `try_to_timestamp`.
  The quarantine test caught it.
- **Learned:** yearly files are re-published every month, so a deletion can
  show up as a row disappearing from the yearly file rather than a `D`
  record. Treating the newest yearly file as the authority for its year
  handles both.
