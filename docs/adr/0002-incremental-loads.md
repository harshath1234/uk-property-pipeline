# ADR 0002: Incremental and idempotent loads

**Status:** accepted · **Date:** 2026-11-01

## Context
HM Land Registry republishes the monthly change file on the 20th working day
of each month. Each row carries a record status: A (addition), C (change) or
D (delete), keyed on the transaction unique identifier.

## Decision
1. **Ingest is idempotent.** Every downloaded file is hashed (SHA-256) and
   recorded in a manifest. Re-running skips a file whose remote size and
   ETag are unchanged, and never duplicates a file whose content hash is
   already present.
2. **Bronze is append-only, one folder per source file and content hash.**
   Re-processing the same file overwrites its own folder, so it is safe to
   repeat.
3. **Silver is rebuilt by merge.** Latest record per transaction wins, ordered
   by (load order, record status precedence). A `D` removes the transaction.
4. **dbt fact table is incremental** on `transaction_id` with a merge strategy,
   so the gold layer is also safe to re-run.

## Consequences
- Running the whole pipeline twice in a row produces the same row counts.
  Tests check this: `tests/test_spark.py::test_rerun_is_idempotent`,
  `tests/test_ingest.py` and `tests/test_postgres.py`.
