"""Boundary tests for replay windows — off-by-one on time ranges is the classic bug."""
import pandas as pd

from src.data import add_features, get_window, next_train_end


def _synthetic_features(n_hours: int = 24 * 400) -> pd.DataFrame:
    idx = pd.date_range("2004-01-01", periods=n_hours, freq="h")
    series = pd.Series(range(n_hours), index=idx, dtype=float)
    return add_features(series)


def test_next_train_end_first_call_anchors_on_min_train_days():
    start = pd.Timestamp("2004-01-01")
    assert next_train_end(None, start, min_train_days=180) == start + pd.Timedelta(days=180)


def test_next_train_end_advances_by_step_ignoring_series_start():
    prev = pd.Timestamp("2005-01-01")
    result = next_train_end(prev, pd.Timestamp("2004-01-01"), min_train_days=180, step_days=7)
    assert result == prev + pd.Timedelta(days=7)


def test_holdout_is_exactly_holdout_days_long_and_ends_at_train_end():
    df = _synthetic_features()
    train_end = df.index[300 * 24]
    train_df, holdout_df = get_window(df, train_end, holdout_days=7)
    assert len(holdout_df) == 7 * 24
    assert holdout_df.index.max() == train_end
    assert train_df.index.max() < holdout_df.index.min()


def test_holdout_no_off_by_one_at_arbitrary_offset():
    df = _synthetic_features()
    train_end = df.index[200 * 24 + 5]
    _, holdout_df = get_window(df, train_end, holdout_days=7)
    assert holdout_df.index[-1] == train_end
    assert (holdout_df.index.to_series().diff().dropna() == pd.Timedelta(hours=1)).all()


if __name__ == "__main__":
    test_next_train_end_first_call_anchors_on_min_train_days()
    test_next_train_end_advances_by_step_ignoring_series_start()
    test_holdout_is_exactly_holdout_days_long_and_ends_at_train_end()
    test_holdout_no_off_by_one_at_arbitrary_offset()
    print("OK")
