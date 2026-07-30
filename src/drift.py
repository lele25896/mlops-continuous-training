"""Drift check: champion's training window (reference) vs the newest replay
window (current). run_job.py uses this to decide whether today's execution
trains at all; train.py logs the resulting share as a metric on the same run
as holdout_mae, so drift is graphable over time in the MLflow UI.

Both windows are 7-day feature slices from get_window, the exact same shape
train.py already produces for holdout — no new windowing logic.
"""
import os
from datetime import datetime, timezone

import pandas as pd
from evidently import Report
from evidently.presets import DataDriftPreset

try:  # flat layout at runtime (jobs/Dockerfile copies src/ next to run_job.py) vs. src.* package in tests
    from data import FEATURE_COLS, add_features, get_window, load_series
except ImportError:
    from src.data import FEATURE_COLS, add_features, get_window, load_series

REPORT_BUCKET = os.environ.get("DRIFT_REPORT_BUCKET", "mlops-loop-120915-mlops")
HOLDOUT_DAYS = 7
# ponytail: round guardrails, not tuned — revisit once real drift history exists.
DRIFT_SHARE_THRESHOLD = 0.5
MIN_DAYS_BETWEEN_TRAININGS = 7


def feature_drift_share(reference: pd.DataFrame, current: pd.DataFrame):
    """Returns (share, Snapshot). Pure w.r.t. I/O — takes FEATURE_COLS frames directly."""
    report = Report(metrics=[DataDriftPreset()])
    snapshot = report.run(reference_data=reference[FEATURE_COLS], current_data=current[FEATURE_COLS])
    share = snapshot.dict()["metrics"][0]["value"]["share"]
    return share, snapshot


def evaluate(data_uri: str, champion_train_end: pd.Timestamp, candidate_train_end: pd.Timestamp):
    """Returns (drift_share, evidently Snapshot) comparing the two windows' features."""
    features = add_features(load_series(data_uri))
    _, reference = get_window(features, champion_train_end, HOLDOUT_DAYS)
    _, current = get_window(features, candidate_train_end, HOLDOUT_DAYS)
    return feature_drift_share(reference, current)


def save_report_html(snapshot, run_id: str, bucket: str) -> str:
    from google.cloud import storage

    path = f"drift-reports/{run_id}.html"
    local = f"/tmp/{run_id}.html"
    snapshot.save_html(local)
    storage.Client().bucket(bucket).blob(path).upload_from_filename(local)
    return f"gs://{bucket}/{path}"


def should_retrain(
    drift_share: float,
    last_train_time: pd.Timestamp | None,
    now: datetime | None = None,
    threshold: float = DRIFT_SHARE_THRESHOLD,
    min_days: int = MIN_DAYS_BETWEEN_TRAININGS,
) -> bool:
    """Pure gate: no prior training, drift above threshold, or scheduled retrain due."""
    if last_train_time is None:
        return True
    if drift_share > threshold:
        return True
    now = now or datetime.now(timezone.utc)
    return (now - last_train_time).days >= min_days
