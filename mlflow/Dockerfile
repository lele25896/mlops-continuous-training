FROM python:3.12-slim

RUN pip install --no-cache-dir mlflow==2.22.0 google-cloud-storage==2.19.0

# GCS bucket is mounted natively as a volume by Cloud Run (no gcsfuse install
# needed here) — see terraform/mlflow.tf. Backend store lives on that mount,
# artifact store talks to GCS directly via google-cloud-storage.
ENV BACKEND_STORE_PATH=/mnt/gcs/mlflow.db
ENV ARTIFACT_ROOT=gs://mlops-loop-120915-mlops/mlflow-artifacts

# ponytail: 1 gunicorn worker — gunicorn's default sizes off host CPU count,
# not the Cloud Run cgroup limit, which OOM-killed a 512Mi container. Single
# writer to sqlite anyway (max_instance_count=1), so no concurrency lost.
CMD mlflow server \
    --host 0.0.0.0 \
    --port ${PORT:-8080} \
    --workers 1 \
    --backend-store-uri sqlite:///${BACKEND_STORE_PATH} \
    --default-artifact-root ${ARTIFACT_ROOT}
