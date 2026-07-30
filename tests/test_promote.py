"""Promotion gate: pure function, no cloud credentials needed."""
from src.promote import should_promote


def test_challenger_better_promotes():
    assert should_promote(challenger_mae=100.0, champion_mae=150.0) is True


def test_challenger_worse_does_not_promote():
    assert should_promote(challenger_mae=150.0, champion_mae=100.0) is False


def test_challenger_tie_does_not_promote():
    assert should_promote(challenger_mae=100.0, champion_mae=100.0) is False


def test_no_champion_yet_promotes_if_under_guardrail():
    assert should_promote(challenger_mae=200.0, champion_mae=None, max_mae=1000.0) is True


def test_no_champion_yet_blocked_by_guardrail():
    assert should_promote(challenger_mae=2000.0, champion_mae=None, max_mae=1000.0) is False


def test_guardrail_blocks_even_if_better_than_champion():
    assert should_promote(challenger_mae=1500.0, champion_mae=3000.0, max_mae=1000.0) is False


if __name__ == "__main__":
    test_challenger_better_promotes()
    test_challenger_worse_does_not_promote()
    test_challenger_tie_does_not_promote()
    test_no_champion_yet_promotes_if_under_guardrail()
    test_no_champion_yet_blocked_by_guardrail()
    test_guardrail_blocks_even_if_better_than_champion()
    print("OK")
