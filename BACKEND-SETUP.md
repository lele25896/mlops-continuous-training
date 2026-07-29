# Backend setup (one-time, manual)

Chicken-egg: Terraform needs a state bucket and a CI identity before CI can
run Terraform. Do this once, by hand, with your own `gcloud` auth.

## 1. New GCP project

```
gcloud projects create mlops-loop-120915 --name="MLOps Continuous Training"
gcloud config set project mlops-loop-120915
gcloud billing projects link mlops-loop-120915 --billing-account=01848B-AE8053-ECCE44
```

Enable the APIs Terraform itself needs to bootstrap (the rest are enabled by
`google_project_service` in `main.tf` as each phase adds resources):

```
gcloud services enable cloudresourcemanager.googleapis.com serviceusage.googleapis.com iam.googleapis.com billingbudgets.googleapis.com
```

## 2. Budget alert (cost guardrail)

```
gcloud billing budgets create \
  --billing-account=01848B-AE8053-ECCE44 \
  --display-name="mlops-continuous-training €1/mese" \
  --budget-amount=1EUR \
  --filter-projects=projects/mlops-loop-120915 \
  --threshold-rule=percent=0.5 \
  --threshold-rule=percent=1.0
```

## 3. Buckets

One bucket for tfstate, one for data (AEP CSV) + MLflow artifacts —
separate so a `terraform destroy` never touches training data.

```
gsutil mb -l europe-west1 gs://mlops-loop-120915-tfstate
gsutil versioning set on gs://mlops-loop-120915-tfstate

gsutil mb -l europe-west1 gs://mlops-loop-120915-mlops
```

Upload the AEP CSV (not in git):

```
gsutil cp data/AEP_hourly.csv gs://mlops-loop-120915-mlops/data/AEP_hourly.csv
```

Edit `terraform/main.tf` `backend "gcs" { bucket = "..." }` to the tfstate
bucket name. Fill in `terraform/terraform.tfvars`: `project_id`,
`github_repo` ("owner/repo").

## 4. First apply (local, your own credentials)

```
gcloud auth application-default login
cd terraform
terraform init
terraform apply
```

This creates the `github-ci` service account and the Workload Identity
Federation pool/provider, plus whatever infra each phase has added to
`main.tf` so far.

## 5. Grant CI access to the state bucket

The bucket isn't Terraform-managed (can't reference it from its own
backend), so grant it manually:

```
gsutil iam ch serviceAccount:github-ci@mlops-loop-120915.iam.gserviceaccount.com:objectAdmin \
  gs://mlops-loop-120915-tfstate
```

## 6. GitHub Actions secrets/vars

In the repo settings, add as repo variables (not secrets — WIF is keyless):

- `GCP_PROJECT_ID`
- `GCP_WORKLOAD_IDENTITY_PROVIDER` — from `terraform output workload_identity_provider`
- `GCP_CI_SERVICE_ACCOUNT` — from `terraform output github_ci_service_account`

From here on, push to `main` runs `terraform apply` through CI, keyless.
