output "project_id" {
  value = var.project_id
}

output "service_account_email" {
  value = google_service_account.pipeline.email
}

output "bucket_name" {
  value = var.create_bucket ? google_storage_bucket.raw[0].name : ""
}

output "datasets" {
  value = [for d in google_bigquery_dataset.ds : d.dataset_id]
}
