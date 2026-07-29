# MLOps Continuous Training

Closed-loop continuous training on GCP: MLflow tracking + model registry,
champion/challenger promotion gate, Evidently drift detection, automated
retraining via Cloud Run Jobs, rollback by reassigning the `@champion` alias
(no redeploy).

Data: hourly AEP energy load (same dataset as
[Energy-Consumption-Forecasting](https://github.com/lele25896/Energy-Consumption-Forecasting)),
replayed on a rolling weekly cursor to simulate time passing. Model: XGBoost
+ lag/calendar features — the point of this project is the lifecycle around
the model, not the model itself.

```
Cloud Scheduler (daily)
  └→ Cloud Run Job "retrain-loop"
       1. read replay cursor from last successful MLflow run, advance 7 days
       2. drift check (Evidently): new window vs. champion's training window
       3. retrain if (drift above threshold) OR (>7 days since last training)
       4. log run + metrics + artifacts to MLflow
       5. gate: does challenger beat champion on the same holdout? → reassign @champion
  └→ MLflow server (Cloud Run service, private, max-instances=1)
       backend store: SQLite on a natively-mounted GCS volume
       artifact store: gs://<bucket>/mlflow-artifacts
  └→ Serving API (Cloud Run service, public)
       loads models:/aep-demand@champion, 15 min TTL
       /predict, /model-info (version, run_id, training date)
```

## Status

Bootstrap only — GCP project, buckets, WIF/CI identity in place. MLflow
server, training, registry, drift, and serving land phase by phase; see
commit history.

## Local setup

One-time manual steps (project, billing, buckets, first `terraform apply`):
[BACKEND-SETUP.md](BACKEND-SETUP.md).
