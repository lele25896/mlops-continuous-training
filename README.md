# MLOps Continuous Training

Closed-loop continuous training on GCP: MLflow tracking + model registry,
champion/challenger promotion gate, Evidently drift detection, automated
retraining via Cloud Run Jobs, rollback by reassigning the `@champion` alias
(no redeploy).

+ Data: hourly AEP energy load (same dataset as
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

MLflow tracking server is live (private Cloud Run service, SQLite backend on
a natively-mounted GCS volume, `max_instance_count=1`). The concurrency risk
that design depends on — GCS FUSE has no file locking — was load-tested
before building anything on top of it: see [scripts/smoke_mlflow.py](scripts/smoke_mlflow.py).

Training loop is in place: [src/data.py](src/data.py) slices the AEP replay
into expanding-train / 7-day-holdout windows and builds lag/calendar
features, [src/train.py](src/train.py) trains an XGBoost model each run and
logs it to the registry. The replay cursor lives entirely in MLflow — each
run reads `train_end` from the last finished run's params and advances it,
no separate state store. Verified against the live server (two runs, cursor
advanced 2005-03-30 → 2005-04-06 as expected); see
[FASE-2-TRAINING.md](FASE-2-TRAINING.md).

Registry gate, drift detection, and serving land phase by phase; see commit
history.

## Local setup

One-time manual steps (project, billing, buckets, first `terraform apply`):
[BACKEND-SETUP.md](BACKEND-SETUP.md).
