# Running on Google Cloud (BigQuery)

Two ways, depending on whether your GCP project has a billing account.

| | BigQuery sandbox | Billing enabled (free tier) |
|---|---|---|
| Card needed | No | Yes |
| GCS bucket for raw files | No (load straight from your laptop) | Yes |
| Storage | 10 GiB lifetime cap | 10 GiB/month free |
| Table expiry | 60 days (re-run to refresh) | None |
| DML (MERGE/DELETE) | Not supported → fact table fully rebuilt | Supported → incremental |
| Terraform vars | `sandbox = true`, `create_bucket = false` | `sandbox = false`, `create_bucket = true` |

Sandbox limits are from Google's documentation:
https://docs.cloud.google.com/bigquery/docs/sandbox

## Steps
1. Create a project at console.cloud.google.com and note its ID.
2. Install the gcloud CLI and Terraform, then:
   ```bash
   gcloud auth application-default login
   cd infra/terraform
   cp example.tfvars terraform.tfvars      # set project_id
   terraform init && terraform plan && terraform apply
   ```
3. Create a key for the service account Terraform made (or keep using your
   own login for a personal project):
   ```bash
   gcloud iam service-accounts keys create gcp-key.json \
     --iam-account "$(terraform output -raw service_account_email)"
   ```
   `gcp-key*.json` is git-ignored. Never commit it.
4. Run the cloud stages after a normal local run:
   ```bash
   export PPD_GCP_PROJECT=<project id>
   export GOOGLE_APPLICATION_CREDENTIALS=$PWD/infra/terraform/gcp-key.json
   export PPD_BQ_SANDBOX=1                 # sandbox only
   make gcp-load
   ```
   With a bucket, also set `PPD_STORAGE_BACKEND=gcs` and
   `PPD_STORAGE_GCS_BUCKET=$(terraform output -raw bucket_name)` so raw files
   are archived in GCS and the load reads from `gs://`.
5. Screenshot the BigQuery console showing the `marts` and `reporting`
   datasets for the README.

## Cost guard-rails
- dbt's BigQuery profile sets `maximum_bytes_billed` to 5 GB per query.
- `cloud.years` in `config/pipeline.yaml` limits how many years are loaded.
- With billing, set `billing_account_id` to get a budget alert at 50% / 100%
  of £5.

## Medians differ slightly
DuckDB's `median()` is exact; BigQuery's `APPROX_QUANTILES` is approximate.
Small differences between the two targets are expected.
