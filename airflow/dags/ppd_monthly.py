"""Monthly HM Land Registry pipeline (Airflow 3).

HM Land Registry publishes on the 20th working day of each month, so the DAG
runs on the 1st at 06:00 UTC, after every release has landed.

ingest ──(nothing new? skip the rest)──> validate -> transform -> quality
       -> dbt -> [postgres, site]

Each stage calls the same `ppd` CLI used locally, so the DAG holds no business
logic and every step can be re-run by hand. Retries use exponential backoff;
every stage is idempotent (ADR 0002), so a retry is always safe.
"""

from __future__ import annotations

from datetime import timedelta

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag, task

DEFAULT_ARGS = {
    "owner": "data-engineering",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=30),
    "execution_timeout": timedelta(hours=2),
}


def stage(task_id: str, command: str, **kwargs) -> BashOperator:
    return BashOperator(
        task_id=task_id,
        bash_command=f"ppd {command}",
        append_env=True,  # pass PPD_* settings from the container through
        **kwargs,
    )


@dag(
    dag_id="ppd_monthly",
    description="HM Land Registry Price Paid Data: ingest -> Spark -> dbt -> Postgres -> site",
    schedule="0 6 1 * *",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,  # the source is current-state; there is nothing to backfill per run
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["ppd", "land-registry"],
)
def ppd_monthly():
    @task.short_circuit(task_id="ingest")
    def ingest() -> bool:
        """Download new releases. Returns False (skips downstream) if nothing changed."""
        from ppd import ingest as ingest_mod
        from ppd.config import load_settings

        results = ingest_mod.run(load_settings())
        print(f"ingest results: {results}")
        return any(v == "landed" for v in results.values())

    validate = stage("validate", "validate")
    transform = stage("transform", "transform", execution_timeout=timedelta(hours=4))
    quality = stage("quality", "quality")
    dbt_build = stage("dbt_build", "dbt")
    postgres = stage("load_postgres", "postgres")
    site = stage("export_site", "site")

    ingest() >> validate >> transform >> quality >> dbt_build >> [postgres, site]


ppd_monthly()
