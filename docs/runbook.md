# Runbook

## Normal monthly run
Airflow runs `ppd_monthly` at 06:00 UTC on the 1st. If HM Land Registry has
published nothing new, `ingest` returns False and every later task is
skipped (shown in pink in the Airflow grid). That is a success, not a failure.

## Where to look
| What | Where |
|---|---|
| Structured logs | each task's log in Airflow, or stdout of `ppd <stage>` (JSON lines) |
| Files landed and their checksums | `data/landing/_manifest.json` |
| Raw schema check results | `data/reports/raw_validation.json` |
| Rows that failed parsing | `data/quarantine/` |
| Great Expectations results | `data/reports/quality.json`, HTML in `data/gx/uncommitted/data_docs/` |
| Stage timings | `data/reports/run_timings.json` |

## Failures and what to do
| Symptom | Likely cause | Action |
|---|---|---|
| `ingest` retries then fails with ConnectionError | HMLR site down or network | Airflow retries with backoff; if still failing, re-run the task later. Nothing partial is left in landing. |
| `validate` fails, `failures_by_check` shows one column | HMLR changed a code list or the column layout | Read the release notes on gov.uk; update `schema.py`, `seeds/`, and the GE suite together. |
| `transform` log shows quarantined rows | Malformed price/date/ID rows | Inspect `data/quarantine/`; a handful is normal, thousands means a format change. |
| `quality` fails on `ExpectColumnMedianToBeBetween` | Unit or parsing bug (e.g. pence vs pounds) | Compare the partition median with last month's report before overriding. |
| dbt `assert_fact_matches_staging` fails | Incremental merge missed rows | `ppd dbt --full-refresh` rebuilds the fact table from staging. |
| Postgres `reconciliation failed` | Address join didn't match some staged rows | Query `staging.sale_load` for rows with no matching `ppd.property`. |
| Out of memory in Spark | Too many years for the laptop | Lower `PPD_SOURCE_YEARS` or raise `PPD_SPARK_DRIVER_MEMORY`. |

## Re-running safely
Every stage is idempotent (ADR 0002). To rebuild everything derived but keep
downloads: `make clean && make run`. To force a fresh download: delete
`data/landing/` too.

## Changing the Postgres schema
Add a new file `postgres/migrations/V00N__description.sql`. Never edit an
applied migration: the runner refuses to start if a checksum changes.
