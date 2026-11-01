# UK Property Data Pipeline

[![CI](https://github.com/harshath1234/uk-property-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/harshath1234/uk-property-pipeline/actions/workflows/ci.yml)

An end-to-end data engineering project on **HM Land Registry Price Paid Data**:
every residential property sale in England and Wales, published monthly with
additions, corrections and deletions.

**Live dashboard:** https://harshath1234.github.io/uk-property-pipeline/

```
HMLR CSV ──> ingest ──> Spark ──> Great ──> dbt star schema ──> dashboard
 (yearly +   checksums   bronze/   Expectations (DuckDB or        (GitHub Pages)
  monthly    retries     silver                  BigQuery)
  changes)   manifest    CDC merge          └──> PostgreSQL 3NF + SQL pack
            ────────────── orchestrated monthly by Airflow ──────────────
            CI: GitHub Actions · Infra: Terraform (GCP) · Runs in Docker
```

## Run it

**One command (Docker):**
```bash
docker compose up --build            # downloads the data and runs every stage
```
Quick demo without downloading (synthetic test data, ~1 minute):
```bash
PPD_RUN_ARGS="--from-dir tests/fixtures/ppd" docker compose up --build
```

**Without Docker** (Python 3.11+, Java 17+, PostgreSQL 15+):
```bash
pip install -e ".[dev,dbt,quality,ons]"
make run            # real data
make e2e-fixture    # synthetic data, same code path
make test
```
Then `make site-preview` and open http://localhost:8000.

Airflow UI: `docker compose --profile airflow up --build` → http://localhost:8080.
BigQuery: see [docs/cloud.md](docs/cloud.md).

## Results (from the last real run)

> Fill this table from `reports/results.json` after `make run` and
> `python scripts/summarise_run.py`. Do not edit numbers by hand.

| Measure | Value |
|---|---|
| Source files / size | `[from results.json]` |
| Raw rows validated (pandera) | `[from results.json]` |
| Rows quarantined | `[from results.json]` |
| Silver rows (current sales) | `[from results.json]` |
| Sale date range | `[from results.json]` |
| Great Expectations | `[n checks × n partitions, pass/fail]` |
| dbt models / tests passed | `[from results.json]` |
| PostgreSQL sales / properties | `[from results.json]` |
| Full run time (laptop spec) | `[from results.json stage_seconds]` |

## What each skill is proven by

| Skill | Where to look |
|---|---|
| Python ETL, config, logging, error handling | `src/ppd/ingest.py`, `config.py`, `logging_utils.py`, `cli.py` |
| Idempotent and incremental loads | `docs/adr/0002-incremental-loads.md`, `ingest.py` manifest, `spark_transform.py` merge, `fct_sales.sql` |
| PySpark | `src/ppd/spark_transform.py` (typed bronze, quarantine, window-function merge) |
| Data quality | `src/ppd/schema.py` (pandera), `src/ppd/quality.py` (Great Expectations), dbt tests |
| dbt, dimensional modelling, star schema | `dbt/models/`, `docs/erd.md` |
| PostgreSQL schema design, keys, indexes, migrations | `postgres/migrations/`, `src/ppd/migrate.py`, `docs/erd.md` |
| Advanced SQL, query tuning | `sql/queries/`, `sql/README.md`, `sql/plans/` |
| Airflow orchestration | `airflow/dags/ppd_monthly.py`, `tests/test_dag.py` |
| Docker | `docker/`, `docker-compose.yml` |
| CI/CD (GitHub Actions) | `.github/workflows/ci.yml`, `pages.yml` |
| GCP (BigQuery, GCS, IAM) and Terraform | `infra/terraform/`, `src/ppd/cloud.py`, `docs/cloud.md` |
| Messy Excel extraction | `src/ppd/ons_excel.py`, `tests/test_ons_excel.py` |
| Testing | `tests/` (pytest, fake HTTP, real Spark and PostgreSQL) |
| Documentation and governance | `docs/data_dictionary.md` (with lineage), `docs/runbook.md`, ADRs |
| Agile delivery | `docs/sprints/` (backlog, sprint goals, retros) |

Not covered here (planned): Kafka, Databricks, Snowflake, AWS, Azure, Redshift,
MongoDB, SQL Server. See [docs/roadmap.md](docs/roadmap.md).

## Design decisions
- **Medallion layers.** Landing keeps files byte-for-byte as downloaded;
  bronze is typed per file version; silver is the merged current state.
  Anything downstream can be rebuilt from landing.
- **The monthly file is change data.** Rows are A (add), C (change) or D
  (delete). Silver keeps the latest row per transaction and drops deletes;
  yearly files, which HMLR re-publishes monthly, act as snapshots
  ([ADR 0002](docs/adr/0002-incremental-loads.md)).
- **Two warehouses, one set of models.** DuckDB for free local runs, BigQuery
  in the cloud. Adapter differences live in four macros.
- **Postgres alongside the warehouse.** A normalised model shows OLTP-style
  design (natural vs surrogate keys, `NULLS NOT DISTINCT`, BRIN vs B-tree).
- **Bad rows are kept, not dropped.** Parse failures go to `data/quarantine/`
  and are counted in the logs.

## Repository layout
```
src/ppd/          pipeline package (ingest, schema, spark, quality, cloud, postgres, site, ONS)
dbt/              staging → star schema → reporting marts, tests, seeds, macros
postgres/         versioned SQL migrations
sql/              advanced query pack and saved query plans
airflow/dags/     monthly DAG
infra/terraform/  GCP: datasets, service account, IAM, bucket, budget
docker/           images and Postgres init
site/             static dashboard (GitHub Pages)
docs/             ADRs, ERDs, data dictionary, runbook, sprints, cloud guide
tests/            pytest suite and synthetic fixtures
```

## Data and licence
Contains HM Land Registry data © Crown copyright and database right, licensed
under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
Address data is subject to Royal Mail and Ordnance Survey conditions, so the
public dashboard shows aggregates only. No data is stored in this repository;
`tests/fixtures/` holds small **synthetic** files used only for tests.

Code: MIT ([LICENSE](LICENSE)).
