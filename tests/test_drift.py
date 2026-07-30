"""Drift gate: winter-vs-summer feature share, and the pure retrain decision."""
from datetime import datetime, timezone

import pandas as pd

from src.data import add_features
from src.drift import feature_drift_share, should_retrain


def _hourly_series(start: str, days: int, base: float) -> pd.Series:
    idx = pd.date_range(start, periods=days * 24, freq="h")
    return pd.Series(base, index=idx, dtype=float)


def test_feature_drift_share_detects_seasonal_shift():
    summer = add_features(_hourly_series("2004-07-01", 30, base=100.0))
    winter = add_features(_hourly_series("2004-01-01", 30, base=100.0))
    # lag features track a constant series (no drift there); month/calendar
    # columns are what should flag as drifted between a July and a January window.
    share, _ = feature_drift_share(summer, winter)
    assert share > 0


def test_feature_drift_share_no_drift_on_identical_window():
    window = add_features(_hourly_series("2004-07-01", 30, base=100.0))
    share, _ = feature_drift_share(window, window)
    assert share == 0


def test_should_retrain_true_when_no_prior_training():
    assert should_retrain(drift_share=0.0, last_train_time=None) is True


def test_should_retrain_true_on_drift_above_threshold():
    last = pd.Timestamp("2026-07-25", tz="UTC")
    now = datetime(2026, 7, 26, tzinfo=timezone.utc)
    assert should_retrain(drift_share=0.9, last_train_time=last, now=now, threshold=0.5) is True


def test_should_retrain_true_when_min_days_elapsed_even_without_drift():
    last = pd.Timestamp("2026-07-01", tz="UTC")
    now = datetime(2026, 7, 26, tzinfo=timezone.utc)
    assert should_retrain(drift_share=0.0, last_train_time=last, now=now, min_days=7) is True


def test_should_retrain_false_when_recent_and_no_drift():
    last = pd.Timestamp("2026-07-25", tz="UTC")
    now = datetime(2026, 7, 26, tzinfo=timezone.utc)
    assert should_retrain(drift_share=0.1, last_train_time=last, now=now, threshold=0.5, min_days=7) is False


if __name__ == "__main__":
    test_feature_drift_share_detects_seasonal_shift()
    test_feature_drift_share_no_drift_on_identical_window()
    test_should_retrain_true_when_no_prior_training()
    test_should_retrain_true_on_drift_above_threshold()
    test_should_retrain_true_when_min_days_elapsed_even_without_drift()
    test_should_retrain_false_when_recent_and_no_drift()
    print("OK")
