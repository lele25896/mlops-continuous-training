terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  # Bucket created manually in bootstrap (BACKEND-SETUP.md) — chicken-egg,
  # backend config can't reference a Terraform-managed resource.
  backend "gcs" {
    bucket = "mlops-loop-120915-tfstate"
    prefix = "mlops-loop"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  # Growing per phase: Fase 1 adds run.googleapis.com, Fase 4 adds
  # cloudscheduler, etc. Kept minimal here on purpose.
  apis = [
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudscheduler.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each           = toset(local.apis)
  service            = each.value
  disable_on_destroy = false
}

# --- Service accounts ----------------------------------------------------

resource "google_service_account" "github_ci" {
  account_id   = "github-ci"
  display_name = "GitHub Actions CI (WIF, keyless)"
}

# CI project-level roles. Bucket IAM for state is granted manually in
# bootstrap (BACKEND-SETUP.md) since the bucket itself isn't Terraform-managed.
resource "google_project_iam_member" "github_ci_roles" {
  for_each = toset([
    "roles/run.admin",
    "roles/artifactregistry.admin",
    "roles/iam.serviceAccountAdmin",
    "roles/iam.serviceAccountUser",
    "roles/resourcemanager.projectIamAdmin",
    "roles/iam.workloadIdentityPoolAdmin",
    "roles/storage.admin",
  ])
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.github_ci.email}"
}

# --- Workload Identity Federation (keyless CI) ----------------------------

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github-pool"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
  }
  attribute_condition = "assertion.repository == \"${var.github_repo}\""

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "github_ci_wif" {
  service_account_id = google_service_account.github_ci.name
  role                = "roles/iam.workloadIdentityUser"
  member              = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repo}"
}
