"""Google Cloud: land raw files in GCS and load silver into BigQuery.

Authentication uses Application Default Credentials: either
GOOGLE_APPLICATION_CREDENTIALS pointing at the service-account key that
Terraform creates, or `gcloud auth application-default login`.

Two modes (see docs/cloud.md):
- BigQuery sandbox (no billing account): no GCS bucket, data is loaded
  straight from the local Parquet file. The sandbox has no DML, so dbt runs
  with `--vars '{incremental: false}'`, and storage is capped at 10 GiB, so
  only the configured `cloud_years` are loaded.
- Billing enabled (free tier): raw files are also archived in GCS and the
  load reads from gs://.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import duckdb

from ppd.config import Settings
from ppd.ingest import Manifest
from ppd.logging_utils import get_logger, log

LOG = get_logger("ppd.cloud")

# Only the columns the warehouse uses. Street-level address fields stay local.
BQ_COLUMNS = [
    "transaction_id", "price", "sale_date", "sale_year", "sale_month", "postcode",
    "postcode_outward", "postcode_area", "property_type", "is_new_build", "tenure",
    "town_city", "district", "county", "ppd_category", "load_seq",
]


def _project() -> str:
    project = os.environ.get("PPD_GCP_PROJECT")
    if not project:
        raise RuntimeError("Set PPD_GCP_PROJECT (terraform output project_id)")
    return project


def upload_landing(settings: Settings, manifest: Manifest) -> int:
    """Copy landed files to gs://<bucket>/<prefix>/landing/, skipping ones already there."""
    bucket_name = settings.storage.get("gcs_bucket")
    if not bucket_name:
        log(LOG, "no gcs_bucket configured; skipping upload")
        return 0
    from google.cloud import storage

    bucket = storage.Client(project=_project()).bucket(bucket_name)
    prefix = settings.storage["gcs_prefix"].strip("/")
    uploaded = 0
    for e in manifest.entries:
        blob = bucket.blob(f"{prefix}/landing/{e.name}")
        if blob.exists():
            blob.reload()
            if (blob.metadata or {}).get("sha256") == e.sha256:
                continue
        blob.metadata = {"sha256": e.sha256, "load_seq": str(e.load_seq)}
        blob.upload_from_filename(str(settings.path("landing") / e.name), timeout=600)
        uploaded += 1
        log(LOG, "uploaded to gcs", blob=blob.name, bytes=e.bytes)
    return uploaded


def load_silver_to_bigquery(settings: Settings) -> int:
    from google.cloud import bigquery

    project = _project()
    years = settings.raw.get("cloud", {}).get("years") or []
    glob = str(settings.path("silver") / "**" / "*.parquet")
    where = f"where sale_year in ({', '.join(str(int(y)) for y in years)})" if years else ""

    client = bigquery.Client(project=project)
    table_id = f"{project}.ppd_raw.silver_transactions"
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,  # load job, not DML
        time_partitioning=bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.MONTH, field="sale_date"),
        clustering_fields=["district", "property_type"],
    )
    with tempfile.TemporaryDirectory() as tmp:
        local = Path(tmp) / "silver.parquet"
        duckdb.connect().execute(
            f"copy (select {', '.join(BQ_COLUMNS)} from read_parquet('{glob}', "
            f"hive_partitioning = true) {where}) to '{local}' (format parquet, compression zstd)"
        )
        bucket_name = settings.storage.get("gcs_bucket")
        if bucket_name:
            from google.cloud import storage

            prefix = settings.storage["gcs_prefix"].strip("/")
            blob = storage.Client(project=project).bucket(bucket_name).blob(
                f"{prefix}/silver/silver.parquet")
            blob.upload_from_filename(str(local), timeout=1200)
            job = client.load_table_from_uri(
                f"gs://{bucket_name}/{blob.name}", table_id, job_config=job_config)
        else:
            with local.open("rb") as fh:
                job = client.load_table_from_file(fh, table_id, job_config=job_config)
        job.result()
    rows = client.get_table(table_id).num_rows
    log(LOG, "silver loaded to bigquery", table=table_id, rows=rows, years=years or "all")
    return rows
