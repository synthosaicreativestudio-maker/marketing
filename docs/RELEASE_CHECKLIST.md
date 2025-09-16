# Release checklist

Before deploying to production, ensure the following:

- [ ] All unit and integration tests pass locally and in CI
- [ ] `TELEGRAM_BOT_TOKEN`, `GCP_SA_JSON`, `GCP_PROJECT_ID`, `GCP_REGION`, `SHEET_ID` and `REDIS_URL` are added to GitHub Secrets
- [ ] Service account used in `GCP_SA_JSON` has roles: Cloud Run Admin, Cloud Build Editor, Storage Admin / Artifact Registry Writer, Service Account User
- [ ] Dockerfile builds locally: `docker build -t test-image .`
- [ ] If using Redis for worker, check `REDIS_URL` accessibility from Cloud Run
- [ ] Configure health check endpoint and logs: `/healthz`
- [ ] If using webhooks, update webhook URL to the Cloud Run service URL via `scripts/setup_webhook.py`
- [ ] Prepare a rollback plan (previous Docker image tag or GCR digest)

Post-deploy checks:
- [ ] Run smoke test with `scripts/smoke_auth_local.py` against the deployed URL (use GCP Identity Token if service is not public)
- [ ] Check Google Sheet for updated row
- [ ] Confirm bot delivers confirmation message to user

Rollback example:
```bash
# Deploy previous image
gcloud run deploy marketing-web --image gcr.io/$PROJECT/marketing:<OLD_TAG> --region $REGION --platform managed --quiet
```
