"""DAG integrity test. Runs in the CI `dag-check` job, which installs Airflow;
skipped elsewhere."""

from pathlib import Path

import pytest

pytest.importorskip("airflow")

from airflow.dag_processing.dagbag import DagBag  # noqa: E402

DAGS = Path(__file__).resolve().parents[1] / "airflow" / "dags"


@pytest.fixture(scope="module")
def dag():
    bag = DagBag(dag_folder=str(DAGS))
    assert bag.import_errors == {}
    return bag.dags["ppd_monthly"]


def test_order_of_stages(dag):
    assert dag.get_task("ingest").downstream_task_ids == {"validate"}
    assert dag.get_task("transform").downstream_task_ids == {"quality"}
    assert dag.get_task("dbt_build").downstream_task_ids == {"load_postgres", "export_site"}


def test_retries_and_no_catchup(dag):
    assert dag.catchup is False
    assert dag.max_active_runs == 1
    for t in dag.tasks:
        assert t.retries >= 3, t.task_id
