"""Promotion gate: does the latest registered version beat @champion?

Both versions were evaluated on their own holdout by train.py (same 7-day
window shape each run) — promote.py only compares the logged holdout_mae,
it doesn't re-score anything. Alias, not stage: Staging/Production are
deprecated in MLflow in favor of aliases.
"""
import os

import pandas as pd
from mlflow.exceptions import MlflowException
from mlflow.tracking import MlflowClient

MODEL_NAME = "aep-demand"  # kept in sync with train.py's MODEL_NAME by hand: same registered model, one string
ALIAS = "champion"
# ponytail: guardrail is a round number well above the MAE observed in Fase 2
# (139/180 MW on the first two folds) — a coarse sanity gate against a broken
# run (NaNs, bad join), not a tuned threshold. Revisit once more folds exist.
MAX_MAE = 1000.0


def should_promote(challenger_mae: float, champion_mae: float | None, max_mae: float = MAX_MAE) -> bool:
    """Pure gate logic. Ties do not promote — avoids alias churn for no gain."""
    if challenger_mae > max_mae:
        return False
    if champion_mae is None:
        return True
    return challenger_mae < champion_mae


def _metric(client: MlflowClient, version) -> float:
    return client.get_run(version.run_id).data.metrics["holdout_mae"]


def _current_champion(client: MlflowClient, name: str):
    try:
        return client.get_model_version_by_alias(name, ALIAS)
    except MlflowException:
        return None


def _latest_challenger(client: MlflowClient, name: str):
    versions = client.search_model_versions(f"name='{name}'")
    return max(versions, key=lambda v: int(v.version))


def champion_train_end(client: MlflowClient) -> pd.Timestamp | None:
    """train_end of the run behind @champion, for drift.py's reference window. None if no champion yet."""
    champion = _current_champion(client, MODEL_NAME)
    if champion is None:
        return None
    return pd.Timestamp(client.get_run(champion.run_id).data.params["train_end"])


def main() -> None:
    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI")
    client = MlflowClient(tracking_uri=tracking_uri) if tracking_uri else MlflowClient()

    challenger = _latest_challenger(client, MODEL_NAME)
    challenger_mae = _metric(client, challenger)
    champion = _current_champion(client, MODEL_NAME)
    champion_mae = _metric(client, champion) if champion else None

    if should_promote(challenger_mae, champion_mae):
        client.set_registered_model_alias(MODEL_NAME, ALIAS, challenger.version)
        prior = f" (was v{champion.version}, mae={champion_mae:.1f})" if champion else " (first champion)"
        print(f"PROMOTED: v{challenger.version} mae={challenger_mae:.1f} -> @{ALIAS}{prior}")
    else:
        reason = "guardrail" if challenger_mae > MAX_MAE else "not better than champion"
        print(f"NOT PROMOTED: v{challenger.version} mae={challenger_mae:.1f} ({reason})")


if __name__ == "__main__":
    main()
