"""Cloud Run Job entrypoint: mint an MLflow auth token from the job's own
runtime service account identity (same mechanism validated in Fase 1's
smoke test, now used for real instead of via gcloud impersonation), then
check drift -> train -> promote.

Retrain decision (drift.should_retrain): always on the first-ever run (no
champion, no prior run yet), on drift above threshold, or when >=7 real days
have passed since the last training run. Otherwise this execution is a no-op
and the replay cursor does not move — daily scheduler triggers, weekly-ish
training, same as the plan's "train if drift OR 7 days" rule.
"""
import os

import google.auth.transport.requests
import google.oauth2.id_token
from mlflow.tracking import MlflowClient

import drift
import promote
import train


def _mlflow_token(audience: str) -> str:
    return google.oauth2.id_token.fetch_id_token(google.auth.transport.requests.Request(), audience)


def main() -> None:
    tracking_uri = os.environ["MLFLOW_TRACKING_URI"]
    os.environ["MLFLOW_TRACKING_TOKEN"] = _mlflow_token(tracking_uri)

    candidate_train_end = train.next_candidate_train_end()
    if candidate_train_end is None:
        print("replay exhausted: nothing to check")
        return

    client = MlflowClient(tracking_uri=tracking_uri)
    last_train_time = train.last_run_time(train.EXPERIMENT)
    champion_end = promote.champion_train_end(client)

    share, snapshot = (0.0, None)
    if champion_end is not None:
        share, snapshot = drift.evaluate(train.DATA_URI, champion_end, candidate_train_end)

    if not drift.should_retrain(share, last_train_time):
        print(f"SKIPPED: drift_share={share:.2f} <= threshold and <{drift.MIN_DAYS_BETWEEN_TRAININGS} days since last training")
        return

    report_uri = None
    if snapshot is not None:
        try:
            report_uri = drift.save_report_html(snapshot, candidate_train_end.strftime("%Y%m%d"), drift.REPORT_BUCKET)
        except Exception as exc:  # pragma: no cover - best-effort artifact upload
            print(f"drift report upload failed (non-fatal): {exc}")

    train.main(drift_share=share, drift_report_uri=report_uri)
    promote.main()


if __name__ == "__main__":
    main()
