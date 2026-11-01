# Copy to terraform.tfvars (git-ignored) and fill in.
project_id = "your-gcp-project-id"
region     = "europe-west2"

# BigQuery sandbox (no card): keep these defaults.
sandbox       = true
create_bucket = false

# With billing enabled instead:
# sandbox            = false
# create_bucket      = true
# billing_account_id = "XXXXXX-XXXXXX-XXXXXX"
# project_number     = "123456789012"
# monthly_budget_gbp = 5
