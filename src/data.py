"""AEP hourly load: source series, lag/calendar features, replay windows.

Replay has no dedicated cursor store: the caller (train.py) reads train_end
from the last successful MLflow run's params and advances it 7 days here.
MLflow is already the state, no second place to keep it (see plan doc).
"""
from __future__ import annotations

import io

import pandas as pd

LAGS = (1, 24, 168)
FEATURE_COLS = ["lag_1", "lag_24", "lag_168", "hour", "dayofweek", "month"]


def load_series(source: str) -> pd.Series:
    """Hourly AEP_MW series, deduped and gap-filled.

    Source AEP dataset has duplicate hours at DST fall-back and 1h gaps at
    spring-forward: average dupes, then interpolate small gaps on the hourly
    grid. ponytail: limit=3 covers DST; a longer real outage stays NaN and
    gets dropped downstream by add_features, not silently invented.
    """
    if source.startswith("gs://"):
        from google.cloud import storage

        bucket_name, _, blob_name = source[5:].partition("/")
        raw = storage.Client().bucket(bucket_name).blob(blob_name).download_as_bytes()
        df = pd.read_csv(io.BytesIO(raw))
    else:
        df = pd.read_csv(source)

    df["Datetime"] = pd.to_datetime(df["Datetime"])
    series = df.groupby("Datetime")["AEP_MW"].mean().sort_index()
    series = series.asfreq("h").interpolate(limit=3)
    series.name = "AEP_MW"
    return series


def add_features(series: pd.Series) -> pd.DataFrame:
    """One row per hour: target = value at t, features = past values + calendar."""
    df = pd.DataFrame({"target": series})
    for lag in LAGS:
        df[f"lag_{lag}"] = series.shift(lag)
    df["hour"] = series.index.hour
    df["dayofweek"] = series.index.dayofweek
    df["month"] = series.index.month
    return df.dropna()


def next_train_end(
    prev_train_end: pd.Timestamp | None,
    series_start: pd.Timestamp,
    min_train_days: int,
    step_days: int = 7,
) -> pd.Timestamp:
    """First call anchors on min_train_days of history; every call after advances 7 days."""
    if prev_train_end is None:
        return series_start + pd.Timedelta(days=min_train_days)
    return prev_train_end + pd.Timedelta(days=step_days)


def get_window(
    features: pd.DataFrame, train_end: pd.Timestamp, holdout_days: int = 7, min_train_days: int = 180
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Expanding train window + trailing holdout, both ending exactly at train_end.

    Holdout = last `holdout_days` up to and including train_end (no off-by-one:
    holdout_start is train_end - holdout_days + 1h so the holdout is exactly
    holdout_days*24 rows and its last row IS train_end, not train_end - 1h).
    Train = everything strictly before the holdout.
    """
    holdout_start = train_end - pd.Timedelta(days=holdout_days) + pd.Timedelta(hours=1)
    train_df = features[features.index < holdout_start]
    holdout_df = features[(features.index >= holdout_start) & (features.index <= train_end)]
    return train_df, holdout_df
