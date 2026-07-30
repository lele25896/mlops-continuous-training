"""Falsification test for Fase 1 (see plan): SQLite backend store on a GCS
FUSE volume has no file locking, so it only works with a single writer
(max_instance_count=1 on the Cloud Run service). This logs 50 sequential runs
+ 5 concurrent runs against the deployed server and checks none were lost or
corrupted. Run against `gcloud run services proxy mlflow --port=8080`.

If this fails: switch to Postgres free tier (Plan B in the plan doc), same
architecture, only --backend-store-uri changes.
"""
import concurrent.futures
import os
import sys

import mlflow

TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:8080")
EXPERIMENT = "smoke-test"
N_SEQUENTIAL = 50
N_PARALLEL = 5


def log_run(i: int) -> str:
    mlflow.set_tracking_uri(TRACKING_URI)
    with mlflow.start_run(run_name=f"smoke-{i}") as run:
        mlflow.log_param("i", i)
        mlflow.log_metric("value", float(i))
        return run.info.run_id


def main() -> None:
    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT)

    sequential_ids = [log_run(i) for i in range(N_SEQUENTIAL)]

    with concurrent.futures.ThreadPoolExecutor(max_workers=N_PARALLEL) as pool:
        parallel_ids = list(
            pool.map(log_run, range(N_SEQUENTIAL, N_SEQUENTIAL + N_PARALLEL))
        )

    expected = set(sequential_ids + parallel_ids)
    total = N_SEQUENTIAL + N_PARALLEL
    assert len(expected) == total, f"only {len(expected)}/{total} unique run_ids returned"

    exp = mlflow.get_experiment_by_name(EXPERIMENT)
    runs = mlflow.search_runs(experiment_ids=[exp.experiment_id], max_results=1000)
    found = set(runs["run_id"])

    missing = expected - found
    if missing:
        print(f"FAIL: {len(missing)}/{total} runs missing from backend store: {missing}")
        sys.exit(1)

    print(f"OK: all {total} runs (50 sequential + 5 parallel) readable back. SQLite/GCS-FUSE holds.")


if __name__ == "__main__":
    main()
