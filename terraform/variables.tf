variable "project_id" {
  type        = string
  description = "GCP project ID (dedicated project, not shared with other CV repos)"
}

variable "region" {
  type    = string
  default = "europe-west1"
}

variable "github_repo" {
  type        = string
  description = "GitHub repo allowed to assume the CI service account, as \"owner/repo\""
}

variable "data_bucket" {
  type    = string
  default = "mlops-loop-120915-mlops"
}
