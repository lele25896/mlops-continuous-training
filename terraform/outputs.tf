output "github_ci_service_account" {
  value = google_service_account.github_ci.email
}

output "workload_identity_provider" {
  value = google_iam_workload_identity_pool_provider.github.name
}
