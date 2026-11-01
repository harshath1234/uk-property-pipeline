# ADR 0001: Overall architecture

**Status:** accepted · **Date:** 2026-11-01

## Context
The project must show end-to-end data engineering on public data, run from
one command on a laptop, and also deploy to one cloud on a free tier.

## Decision
- **Source:** HM Land Registry Price Paid Data (England and Wales sales).
  Yearly files for the backfill, the monthly change file for incremental loads.
- **Layers (medallion):** landing (raw files) → bronze (typed Parquet per file)
  → silver (current state of each transaction) → gold (dbt marts).
- **Processing:** PySpark for landing → silver, because the full history is
  ~30M rows and the monthly file carries change records that need a merge.
- **Warehouse:** dbt with two targets. DuckDB locally (free, zero setup) and
  BigQuery in the cloud. Same SQL models for both.
- **Operational store:** PostgreSQL holds a normalised (3NF) model and serves
  as the Airflow metadata database.
- **Orchestration:** Apache Airflow, one monthly DAG.
- **Cloud:** GCP only (GCS + BigQuery), provisioned with Terraform.
- **Dashboard:** static site built from mart extracts, deployed to GitHub Pages
  by GitHub Actions.

## Consequences
- Two warehouse targets mean SQL must stay portable (no DuckDB-only functions
  in models; adapter-specific bits go in macros).
- Spark is more than the monthly file needs; it is justified by the backfill
  and by keeping one code path for both.
