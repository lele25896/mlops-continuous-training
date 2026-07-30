# Fase 4 — Cloud Run Job "retrain-loop" + Cloud Scheduler trigger.
# Job checks drift -> train -> promote (Fase 5 wires the drift gate into
# jobs/run_job.py; some daily triggers are no-ops when there's no drift and
# <7 days since the last training run).

resource "google_service_account" "retrain_job" {
  account_id   = "retrain-job"
  display_name = "Retrain loop job runtime SA"
}

# Same bucket, same role as mlflow-server: the client (train.py) writes
# artifacts to GCS directly, doesn't proxy them through the mlflow server.
resource "google_storage_bucket_iam_member" "retrain_job_bucket_access" {
  bucket = var.data_bucket
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.retrain_job.email}"
}

# Lets the job mint its own ID token for the mlflow service's audience at
# runtime (google.oauth2.id_token.fetch_id_token in jobs/run_job.py) — no
# impersonation needed, unlike the Fase 1 local dev workaround.
resource "google_cloud_run_v2_service_iam_member" "retrain_job_mlflow_invoker" {
  name     = google_cloud_run_v2_service.mlflow.name
  location = google_cloud_run_v2_service.mlflow.location
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.retrain_job.email}"
}

resource "google_cloud_run_v2_job" "retrain" {
  name                = "retrain-loop"
  location            = var.region
  deletion_protection = false

  template {
    template {
      service_account = google_service_account.retrain_job.email
      max_retries     = 0 # ponytail: a broken run should surface red, not retry silently into a corrupted state
      timeout         = "1800s"

      containers {
        image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}/retrain-job:latest"

        resources {
          limits = {
            cpu    = "1"
            memory = "1Gi"
          }
        }

        env {
          name  = "MLFLOW_TRACKING_URI"
          value = google_cloud_run_v2_service.mlflow.uri
        }
      }
    }
  }
}

resource "google_service_account" "retrain_scheduler" {
  account_id   = "retrain-scheduler"
  display_name = "Cloud Scheduler trigger for retrain-loop"
}

# Triggering a Job execution goes through the Cloud Run Admin API's `:run`
# method, not a service URL — run.invoker on the job resource covers it.
resource "google_cloud_run_v2_job_iam_member" "scheduler_invoker" {
  name     = google_cloud_run_v2_job.retrain.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.retrain_scheduler.email}"
}

resource "google_cloud_scheduler_job" "retrain_trigger" {
  name      = "retrain-loop-trigger"
  schedule  = "0 6 * * *"
  time_zone = "Etc/UTC"
  depends_on = [google_project_service.apis]

  http_target {
    # Cloud Run Jobs execution is exposed on the v1 namespaced path even for
    # v2 job resources — a known Knative-API-origin quirk, this is Google's
    # documented shape for scheduling job runs.
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.retrain.name}:run"
    http_method = "POST"

    oauth_token {
      service_account_email = google_service_account.retrain_scheduler.email
    }
  }
}

output "retrain_job_name" {
  value = google_cloud_run_v2_job.retrain.name
}
