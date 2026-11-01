# Follow-up projects

This project proves the skills in the table in the README. These skills are
**not** proven by it, so each needs its own small project before it goes on a
CV as hands-on experience.

| Skill | Small project that would prove it | Effort |
|---|---|---|
| Kafka / streaming | Stream a live public feed (e.g. TfL Unified API arrivals, or Carbon Intensity API) into Kafka (Redpanda locally), consume with Python or Spark Structured Streaming into Parquet, with a dead-letter topic | 2 weeks |
| Databricks | Run this repo's Spark job as a Databricks Free Edition job writing Delta tables; add a Delta `MERGE` for the monthly changes | 1 week |
| Snowflake | Add a `snowflake` dbt target to this repo during a 30-day trial; screenshot results; note that the trial ends | 3–4 days |
| AWS | Mirror `infra/terraform` for S3 + Glue Catalog + Athena on the free tier | 1 week |
| Azure | Same pattern with ADLS Gen2 + Synapse serverless, or Azure Data Factory triggering the Docker image | 1 week |
| Amazon Redshift | Redshift Serverless trial loaded from S3 with `COPY` | 3–4 days |
| MongoDB | Store raw API JSON (from the streaming project) in MongoDB Atlas free tier, then flatten into the warehouse | 3–4 days |
| SQL Server | Port `postgres/migrations` to SQL Server (Docker `mcr.microsoft.com/mssql/server`) and note the dialect differences | 2–3 days |

Until then, list these under "Familiar with" or leave them off, not under core
skills.
