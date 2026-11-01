# Sprints 5, 6 and 7

## Sprint 5: orchestration and containers
**Goal:** one scheduled DAG and one command to run everything.

Delivered
- `airflow/dags/ppd_monthly.py` (Airflow 3): runs on the 1st of each month,
  after HM Land Registry's 20th-working-day release. A short-circuit task
  skips everything downstream when no new file landed. Retries with
  exponential backoff; one active run at a time; no catch-up.
- `docker/Dockerfile` (pipeline, non-root, Java for Spark),
  `docker/Dockerfile.airflow`, `docker-compose.yml` (Postgres + pipeline, Airflow
  behind a profile).
- `tests/test_dag.py` and a CI job that installs Airflow and checks the DAG.

Checked: `airflow dags test ppd_monthly` ran every task to success on the
synthetic fixture, and a second run skipped all downstream tasks because
nothing new had landed.

## Sprint 6: GCP
**Goal:** the same models in BigQuery, with infrastructure as code.

Delivered
- `infra/terraform/`: APIs, a pipeline service account with dataset-level
  `bigquery.dataEditor` and project `bigquery.jobUser`, five datasets,
  optional versioned GCS bucket with lifecycle rule, optional budget alert.
- `src/ppd/cloud.py`: silver → BigQuery with a load job (month-partitioned on
  `sale_date`, clustered by district and property type).
- dbt `bigquery` target; `PPD_BQ_SANDBOX=1` switches the fact table to a full
  rebuild because the sandbox has no DML.

## Sprint 7: data quality and messy Excel
Delivered
- `src/ppd/quality.py`: 17 Great Expectations checks run per sale-year
  partition (memory stays flat), JSON report and HTML Data Docs.
- `src/ppd/ons_excel.py`: parses ONS house-price workbooks whose layout varies
  (title rows, header wording, sheet order, period formats, suppression
  markers), plus a reconciliation against this pipeline's own medians.

## Retro (5–7)
- **Problem:** the package located its config relative to its own source
  file, which breaks once it is pip-installed into an image. Fixed with
  `PPD_PROJECT_ROOT` and a working-directory fallback.
- **Problem:** the BigQuery sandbox allows no DML and caps lifetime storage at
  10 GiB, so incremental MERGE and a full 9-year load won't work there. Added
  a sandbox switch and a `cloud.years` setting.
- **Not verified in this build:** Docker image build, Terraform plan and the
  BigQuery run. CI builds the image and validates Terraform; the BigQuery run
  needs a GCP project (see `docs/cloud.md`).
