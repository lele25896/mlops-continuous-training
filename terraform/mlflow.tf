# Fase 1 — MLflow tracking server + registry.
# PRIVATO: nessun invoker allUsers, si raggiunge solo via
# `gcloud run services proxy mlflow --port=8080`.

resource "google_artifact_registry_repository" "images" {
  location      = var.region
  repository_id = "mlops"
  format        = "DOCKER"
}

resource "google_service_account" "mlflow" {
  account_id   = "mlflow-server"
  display_name = "MLflow tracking server runtime SA"
}

# Backend store (sqlite) + artifact store both live in this bucket.
resource "google_storage_bucket_iam_member" "mlflow_bucket_access" {
  bucket = var.data_bucket
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.mlflow.email}"
}

resource "google_cloud_run_v2_service" "mlflow" {
  name                = "mlflow"
  location            = var.region
  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.mlflow.email

    # Single writer, by design: GCS FUSE has no file locking, so more than
    # one instance writing the sqlite backend store corrupts it. This is the
    # whole bet Fase 1 falsifies — see scripts/smoke_mlflow.py.
    scaling {
      max_instance_count = 1
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}/mlflow:latest"

      # Default 512Mi OOM-killed the container: gunicorn without --workers
      # sizes off host CPU count, not the cgroup limit. Bumped as margin on
      # top of pinning --workers 1 in the Dockerfile.
      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }

      ports {
        container_port = 8080
      }

      volume_mounts {
        name       = "gcs-store"
        mount_path = "/mnt/gcs"
      }
    }

    volumes {
      name = "gcs-store"
      gcs {
        bucket    = var.data_bucket
        read_only = false
      }
    }
  }
}

output "mlflow_service_name" {
  value = google_cloud_run_v2_service.mlflow.name
}

# The service is private; this is what makes `gcloud run services proxy`
# work for the developer without exposing it publicly.
resource "google_cloud_run_v2_service_iam_member" "mlflow_developer_invoker" {
  name     = google_cloud_run_v2_service.mlflow.name
  location = google_cloud_run_v2_service.mlflow.location
  role     = "roles/run.invoker"
  member   = "user:gabriele.giacometti2@gmail.com"
}

# `gcloud run services proxy` hangs for user-account credentials (reproduced
# on Windows and in Cloud Shell alike — a CLI bug, not local networking).
# Smoke-testing instead impersonates this SA to mint a correctly-audienced ID
# token — the same mechanism the retrain Job / serving API will use for real
# in later fases.
resource "google_cloud_run_v2_service_iam_member" "mlflow_selftest_invoker" {
  name     = google_cloud_run_v2_service.mlflow.name
  location = google_cloud_run_v2_service.mlflow.location
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.mlflow.email}"
}

resource "google_service_account_iam_member" "developer_impersonate_mlflow_sa" {
  service_account_id = google_service_account.mlflow.name
  role                = "roles/iam.serviceAccountTokenCreator"
  member              = "user:gabriele.giacometti2@gmail.com"
}
