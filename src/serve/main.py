"""FastAPI serving: models:/aep-demand@champion.

Rollback is reassigning the @champion alias in MLflow — no redeploy, no
rebuild. This process picks it up within CACHE_TTL_SECONDS (checks the
alias's version number, not on every request; reloads the model only if it
changed). The replay CSV itself is static for the life of the demo, loaded
once and cached forever.
"""
import os
import time

import google.auth.transport.requests
import google.oauth2.id_token
import mlflow
import mlflow.xgboost
import pandas as pd
from fastapi import FastAPI, HTTPException
from mlflow.tracking import MlflowClient
from pydantic import BaseModel

try:  # flat layout at runtime (Dockerfile copies data.py next to main.py) vs. src.* package in tests
    from data import FEATURE_COLS, add_features, load_series
except ImportError:
    from src.data import FEATURE_COLS, add_features, load_series

MODEL_NAME = "aep-demand"  # kept in sync with train.py/promote.py by hand — same registered model, one string
ALIAS = "champion"
DATA_URI = os.environ.get("DATA_URI", "gs://mlops-loop-120915-mlops/data/AEP_hourly.csv")
CACHE_TTL_SECONDS = 15 * 60

app = FastAPI(title="AEP Demand Forecast API", version="1.0.0")

_state: dict = {"version": None, "checked_at": 0.0, "model": None, "run_id": None, "params": {}, "metrics": {}, "features": None}


def should_refresh(has_model: bool, checked_at: float, now: float, ttl: float = CACHE_TTL_SECONDS, force: bool = False) -> bool:
    """Pure gate: always refresh before the first successful load; otherwise only after the TTL."""
    return force or not has_model or (now - checked_at) >= ttl


def _mint_mlflow_token() -> None:
    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI")
    if not tracking_uri:
        return
    mlflow.set_tracking_uri(tracking_uri)
    os.environ["MLFLOW_TRACKING_TOKEN"] = google.oauth2.id_token.fetch_id_token(
        google.auth.transport.requests.Request(), tracking_uri
    )


def _refresh(force: bool = False) -> None:
    now = time.monotonic()
    if not should_refresh(_state["model"] is not None, _state["checked_at"], now, force=force):
        return

    _mint_mlflow_token()
    client = MlflowClient()
    try:
        version = client.get_model_version_by_alias(MODEL_NAME, ALIAS)
    except Exception:
        _state["checked_at"] = now  # registry hiccup or no champion yet: keep serving the last good model
        return

    if _state["model"] is None or version.version != _state["version"]:
        run = client.get_run(version.run_id)
        _state["model"] = mlflow.xgboost.load_model(f"models:/{MODEL_NAME}@{ALIAS}")
        _state["version"] = version.version
        _state["run_id"] = version.run_id
        _state["params"] = run.data.params
        _state["metrics"] = run.data.metrics

    if _state["features"] is None:
        _state["features"] = add_features(load_series(DATA_URI))

    _state["checked_at"] = now


class ModelInfo(BaseModel):
    version: str
    run_id: str
    trained_at: str
    holdout_mae: float


class Prediction(BaseModel):
    target_hour: str
    prediction: float
    actual: float | None
    model_version: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/model-info", response_model=ModelInfo)
def model_info():
    _refresh()
    if _state["model"] is None:
        raise HTTPException(503, "no @champion model registered yet")
    return ModelInfo(
        version=_state["version"],
        run_id=_state["run_id"],
        trained_at=_state["params"]["train_end"],
        holdout_mae=float(_state["metrics"]["holdout_mae"]),
    )


@app.get("/predict", response_model=Prediction)
def predict(at: str | None = None):
    """Forecast for one hour. `at` (ISO timestamp) defaults to the hour right after the champion's training window."""
    _refresh()
    if _state["model"] is None:
        raise HTTPException(503, "no @champion model registered yet")

    features = _state["features"]
    # Default target = the hour right after the champion's own training window
    # (its train_end is the last hour it saw) — the replay's simulated "now",
    # not the CSV's real 2018 tail the model was never trained anywhere near.
    default_target = pd.Timestamp(_state["params"]["train_end"]) + pd.Timedelta(hours=1)
    target = pd.Timestamp(at) if at else default_target
    if target not in features.index:
        raise HTTPException(404, f"no data for {target} (need lag_168 history: 7 days before it in the replay series)")

    row = features.loc[target]
    prediction = float(_state["model"].predict(row[FEATURE_COLS].to_frame().T)[0])
    return Prediction(
        target_hour=target.isoformat(),
        prediction=prediction,
        actual=float(row["target"]),
        model_version=_state["version"],
    )
