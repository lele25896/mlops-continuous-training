"""Train one XGBoost run on the current replay window and log it to MLflow.

Cursor: read train_end from the last FINISHED run's params in this
experiment, advance 7 days (first run anchors on MIN_TRAIN_DAYS of history).
No gate here — Fase 3 (promote.py) decides champion/challenger promotion.
"""
import os

import mlflow
import mlflow.xgboost
import pandas as pd
from sklearn.metrics import mean_absolute_error
from xgboost import XGBRegressor

from data import FEATURE_COLS, add_features, get_window, load_series, next_train_end

EXPERIMENT = "aep-demand"
MODEL_NAME = "aep-demand"
DATA_URI = os.environ.get("DATA_URI", "gs://mlops-loop-120915-mlops/data/AEP_hourly.csv")
MIN_TRAIN_DAYS = 180
HOLDOUT_DAYS = 7


def _last_train_end(experiment_name: str) -> pd.Timestamp | None:
    exp = mlflow.get_experiment_by_name(experiment_name)
    if exp is None:
        return None
    runs = mlflow.search_runs(experiment_ids=[exp.experiment_id], max_results=5000)
    if runs.empty or "params.train_end" not in runs.columns:
        return None
    finished = runs[runs["status"] == "FINISHED"]
    if finished.empty:
        return None
    return pd.Timestamp(finished["params.train_end"].max())


def main() -> None:
    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI")
    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(EXPERIMENT)

    series = load_series(DATA_URI)
    train_end = next_train_end(_last_train_end(EXPERIMENT), series.index.min(), MIN_TRAIN_DAYS)

    if train_end > series.index.max():
        print(f"replay exhausted: train_end {train_end} past last available data {series.index.max()}")
        return

    features = add_features(series)
    train_df, holdout_df = get_window(features, train_end, HOLDOUT_DAYS, MIN_TRAIN_DAYS)

    model = XGBRegressor(n_estimators=200, max_depth=5, learning_rate=0.05)
    model.fit(train_df[FEATURE_COLS], train_df["target"])
    mae = mean_absolute_error(holdout_df["target"], model.predict(holdout_df[FEATURE_COLS]))

    with mlflow.start_run():
        mlflow.log_param("train_end", train_end.isoformat())
        mlflow.log_param("train_rows", len(train_df))
        mlflow.log_metric("holdout_mae", mae)
        mlflow.xgboost.log_model(model, artifact_path="model", registered_model_name=MODEL_NAME)

    print(f"OK: train_end={train_end.isoformat()} holdout_mae={mae:.1f}")


if __name__ == "__main__":
    main()
