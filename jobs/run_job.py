"""Cloud Run Job entrypoint: mint an MLflow auth token from the job's own
runtime service account identity (same mechanism validated in Fase 1's
smoke test, now used for real instead of via gcloud impersonation), then
train -> promote in sequence.
"""
import os

import google.auth.transport.requests
import google.oauth2.id_token

import train
import promote


def _mlflow_token(audience: str) -> str:
    return google.oauth2.id_token.fetch_id_token(google.auth.transport.requests.Request(), audience)


def main() -> None:
    tracking_uri = os.environ["MLFLOW_TRACKING_URI"]
    os.environ["MLFLOW_TRACKING_TOKEN"] = _mlflow_token(tracking_uri)
    train.main()
    promote.main()


if __name__ == "__main__":
    main()
