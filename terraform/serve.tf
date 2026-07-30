# Fase 6 — serving API. PUBBLICO, come fraud/defect: nessun rischio nel
# leggere @champion via HTTP, l'unico scrittore su MLflow resta il job.

resource "google_service_account" "serve" {
  account_id   = "serving-api"
  display_name = "Serving API runtime SA"
}

# Read-only: legge il CSV di replay e scarica gli artifact del modello da
# GCS, non scrive mai (a differenza di mlflow-server e retrain-job).
resource "google_storage_bucket_iam_member" "serve_bucket_access" {
  bucket = var.data_bucket
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.serve.email}"
}

# Stesso meccanismo di token nativo di retrain-job (Fase 4): il servizio
# minta il proprio ID token per chiamare il tracking server privato.
resource "google_cloud_run_v2_service_iam_member" "serve_mlflow_invoker" {
  name     = google_cloud_run_v2_service.mlflow.name
  location = google_cloud_run_v2_service.mlflow.location
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.serve.email}"
}

resource "google_cloud_run_v2_service" "serve" {
  name                = "serving-api"
  location            = var.region
  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.serve.email

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}/serve:latest"

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      ports {
        container_port = 8080
      }

      env {
        name  = "MLFLOW_TRACKING_URI"
        value = google_cloud_run_v2_service.mlflow.uri
      }

      liveness_probe {
        http_get {
          path = "/health"
        }
      }
    }
  }
}

resource "google_cloud_run_v2_service_iam_member" "serve_public" {
  name     = google_cloud_run_v2_service.serve.name
  location = google_cloud_run_v2_service.serve.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

output "serve_url" {
  value = google_cloud_run_v2_service.serve.uri
}
