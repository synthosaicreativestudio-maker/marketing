# Deploy Runbook (Cloud Run + GitHub Actions)

This runbook shows how to deploy the application to Google Cloud Run using the provided GitHub Actions workflow `.github/workflows/deploy-cloudrun-multi.yaml`.

Required GitHub Secrets
- GCP_SA_JSON — Service account JSON (full JSON) with roles: Cloud Run Admin, Storage Admin (or Artifact Registry Writer), Cloud Build Editor, Service Account User.
- GCP_PROJECT_ID — GCP project id
- GCP_REGION — Cloud Run region (e.g. europe-west1)
- TELEGRAM_BOT_TOKEN — Telegram bot token
- SHEET_ID — Google Sheet ID
- REDIS_URL — Redis URL for worker (if using RQ)

Steps to deploy manually (local / troubleshooting)
1. Build locally and test:
   - docker build -t gcr.io/<PROJECT>/marketing:local .
   - docker run --env TELEGRAM_BOT_TOKEN=... -p 8000:8000 gcr.io/<PROJECT>/marketing:local

2. Use the workflow
   - Push to `main` or `safe/push-sheets-clean` to trigger the workflow.

3. Troubleshooting
- If deploy fails due to permissions, ensure the service account in `GCP_SA_JSON` has proper roles.
- If image push fails, check `gcloud auth configure-docker` step and permissions.

Notes
- Worker service is deployed without `--allow-unauthenticated` by default — adjust if you need public access.
- For production, use Secret Manager to pass BOT token / SA json to the Cloud Run service rather than embedding them in env.

