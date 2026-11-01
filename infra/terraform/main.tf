terraform {
  required_version = ">= 1.6"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  # dbt writes to these; ppd_raw is filled by the pipeline's load job
  datasets = ["ppd_raw", "staging", "marts", "reporting", "reference"]
  labels   = { project = "uk-property-pipeline", managed_by = "terraform" }
  apis     = concat(["bigquery.googleapis.com", "iam.googleapis.com"], var.create_bucket ? ["storage.googleapis.com"] : [])
}

# ---------------------------------------------------------------- APIs
resource "google_project_service" "apis" {
  for_each           = toset(local.apis)
  service            = each.value
  disable_on_destroy = false
}

# ---------------------------------------------------------------- identity
# One service account for the pipeline, with the narrowest roles it needs.
resource "google_service_account" "pipeline" {
  account_id   = "ppd-pipeline"
  display_name = "UK property pipeline (ingest, load, dbt)"
  depends_on   = [google_project_service.apis]
}

# Run query and load jobs (project level: BigQuery has no dataset-level job role)
resource "google_project_iam_member" "bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

# ---------------------------------------------------------------- BigQuery
resource "google_bigquery_dataset" "ds" {
  for_each                   = toset(local.datasets)
  dataset_id                 = each.value
  location                   = var.region
  labels                     = local.labels
  delete_contents_on_destroy = true
  # The sandbox forces a 60-day table expiry; with billing, keep tables forever.
  default_table_expiration_ms = var.sandbox ? 60 * 24 * 60 * 60 * 1000 : null
  depends_on                  = [google_project_service.apis]
}

# Read/write only on the pipeline's own datasets
resource "google_bigquery_dataset_iam_member" "editor" {
  for_each   = google_bigquery_dataset.ds
  dataset_id = each.value.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.pipeline.email}"
}

# ---------------------------------------------------------------- storage (billing only)
resource "google_storage_bucket" "raw" {
  count                       = var.create_bucket ? 1 : 0
  name                        = "${var.project_id}-ppd-raw"
  location                    = var.region
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = true
  labels                      = local.labels

  versioning { enabled = true }

  # keep old versions of re-published yearly files for 30 days, then delete
  lifecycle_rule {
    condition {
      days_since_noncurrent_time = 30
      with_state                 = "ARCHIVED"
    }
    action { type = "Delete" }
  }
  depends_on = [google_project_service.apis]
}

resource "google_storage_bucket_iam_member" "object_admin" {
  count  = var.create_bucket ? 1 : 0
  bucket = google_storage_bucket.raw[0].name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.pipeline.email}"
}

# ---------------------------------------------------------------- budget guard (billing only)
resource "google_billing_budget" "cap" {
  count           = var.billing_account_id == "" ? 0 : 1
  billing_account = var.billing_account_id
  display_name    = "ppd monthly budget"
  budget_filter { projects = ["projects/${var.project_number}"] }
  amount {
    specified_amount {
      currency_code = "GBP"
      units         = tostring(var.monthly_budget_gbp)
    }
  }
  threshold_rules { threshold_percent = 0.5 }
  threshold_rules { threshold_percent = 1.0 }
}
