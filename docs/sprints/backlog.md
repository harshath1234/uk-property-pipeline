# Product backlog

Solo portfolio project, run in short sprints. Each sprint has a goal, a set of
user stories, a definition of done, and a short retro in its own file.

**Product goal:** a reproducible pipeline that turns HM Land Registry Price
Paid Data into a tested star-schema warehouse and a public dashboard, runnable
end to end from one command.

**Definition of done (every story)**
- Code is in the repo, linted (ruff) and covered by at least one test.
- CI passes on the pull request.
- Any figure shown anywhere comes from a real run, never typed in by hand.
- README or docs updated if behaviour changed.

| ID | Story | Sprint | Status |
|---|---|---|---|
| S0-1 | As a reviewer, I can clone the repo and see the layout, licence and how to run it. | 0 | Done |
| S0-2 | As the developer, every push runs lint and tests in CI. | 0 | Done |
| S1-1 | As the pipeline, I download each source file once, and re-running does not re-download unchanged files. | 1 | Done |
| S1-2 | As an analyst, raw files that break the published schema fail loudly before they reach the warehouse. | 1 | Done |
| S2-1 | As the pipeline, I convert raw CSV to typed Parquet with Spark, partitioned by year and month. | 2 | Done |
| S2-2 | As the pipeline, I apply the monthly additions, changes and deletes so silver holds the current state. | 2 | Done |
| S3-1 | As an analyst, I query a star schema (sales fact + date, location, property dimensions). | 3 | Done |
| S3-2 | As an analyst, dbt tests guard keys, accepted values and relationships. | 3 | Done |
| S4-1 | As an application team, I have a normalised PostgreSQL model with keys, indexes and versioned migrations. | 4 | Done |
| S4-2 | As an interviewer, I can read advanced SQL (CTEs, window functions) with query plans. | 4 | Done |
| S5-1 | As an operator, a monthly scheduled DAG runs the whole pipeline with retries and logs. | 5 | Done |
| S5-2 | As a reviewer, `docker compose up` runs everything end to end. | 5 | Done |
| S6-1 | As an operator, cloud resources (bucket, dataset, service account) are created with Terraform. | 6 | Done |
| S6-2 | As an analyst, the same dbt models build in BigQuery. | 6 | Done |
| S7-1 | As a data owner, a Great Expectations suite validates silver data each run. | 7 | Done |
| S7-2 | As the pipeline, I parse ONS house-price Excel workbooks whose layouts vary. | 7 | Done |
| S8-1 | As a reviewer, I see a live dashboard built from the marts. | 8 | Done |
| S8-2 | As a new team member, I have a data dictionary, lineage and a runbook. | 8 | Done |

## Not in this project (see docs/roadmap.md)
Kafka/streaming, Databricks, Snowflake, Redshift, MongoDB, SQL Server, AWS, Azure.
