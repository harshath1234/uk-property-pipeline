variable "project_id" {
  description = "GCP project ID that will hold the datasets"
  type        = string
}

variable "region" {
  description = "Location for BigQuery datasets and the bucket (London by default)"
  type        = string
  default     = "europe-west2"
}

variable "sandbox" {
  description = "true if the project uses the BigQuery sandbox (no billing account)"
  type        = bool
  default     = true
}

variable "create_bucket" {
  description = "Create a GCS bucket for raw files. Needs billing enabled on the project."
  type        = bool
  default     = false
}

variable "billing_account_id" {
  description = "Billing account for the budget alert. Leave empty in the sandbox."
  type        = string
  default     = ""
}

variable "project_number" {
  description = "Numeric project number (only needed for the budget alert)"
  type        = string
  default     = ""
}

variable "monthly_budget_gbp" {
  description = "Budget alert amount in GBP"
  type        = number
  default     = 5
}
