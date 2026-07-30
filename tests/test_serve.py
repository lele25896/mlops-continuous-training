"""Refresh gate: pure function, no cloud credentials needed."""
from src.serve.main import should_refresh


def test_refreshes_before_first_successful_load():
    assert should_refresh(has_model=False, checked_at=0.0, now=100.0, ttl=900) is True


def test_no_refresh_within_ttl():
    assert should_refresh(has_model=True, checked_at=100.0, now=200.0, ttl=900) is False


def test_refreshes_after_ttl_elapsed():
    assert should_refresh(has_model=True, checked_at=0.0, now=901.0, ttl=900) is True


def test_forced_refresh_ignores_ttl():
    assert should_refresh(has_model=True, checked_at=100.0, now=100.5, ttl=900, force=True) is True


if __name__ == "__main__":
    test_refreshes_before_first_successful_load()
    test_no_refresh_within_ttl()
    test_refreshes_after_ttl_elapsed()
    test_forced_refresh_ignores_ttl()
    print("OK")
