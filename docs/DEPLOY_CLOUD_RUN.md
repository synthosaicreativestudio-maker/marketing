Deploy to Cloud Run — инструкции и секреты

Required GitHub Secrets:
- GCP_SA_JSON — содержимое service account JSON (для CI deployment)
- GCP_PROJECT_ID — GCP project id
- GCP_REGION — region for Cloud Run
- CLOUD_RUN_SERVICE_NAME — desired Cloud Run service name
- TELEGRAM_BOT_TOKEN — token for bot
- SHEET_ID — Google Sheet ID

Optional:
- REDIS_URL — Redis instance URL for RQ worker (e.g., managed Memorystore or Redis Cloud)

Deployment notes:
- The CI workflow `deploy-cloudrun.yaml` builds Docker image and pushes to GCR, then deploys Cloud Run.

New multi-service workflow:
- `deploy-cloudrun-multi.yaml` builds the image once and deploys two Cloud Run services:
  - web service (default name: `marketing-web`) — serves the FastAPI app and Mini App static files
  - worker service (default name: `marketing-worker`) — runs the RQ worker; requires `REDIS_URL`

Override service names by setting repository secrets `WEB_SERVICE_NAME` and `WORKER_SERVICE_NAME` or by setting env vars when invoking `gcloud` locally.
- For background workers (RQ), you can either:
  - Deploy a separate Cloud Run service that runs the RQ worker command: `rq worker default` with REDIS_URL set; or
  - Use a managed VM/Compute Engine or Kubernetes for long-running workers.

Secrets and environment variables should be set in Cloud Run service settings (or via `gcloud run deploy --set-env-vars`).

Local testing:
- Run Redis locally: `docker run -p 6379:6379 redis:7`
- Start worker in another terminal: `rq worker default --url redis://localhost:6379/0`
- Start app: `.venv312/bin/uvicorn app.main:app --reload`

CI notes:
- Ensure the service account in `GCP_SA_JSON` has the following roles: Cloud Run Admin, Storage Admin, Cloud Build Service Account. It must also have permissions to deploy/configure services and access Secret Manager if used.
- Add the required secrets to GitHub repository settings: `GCP_SA_JSON`, `GCP_PROJECT_ID`, `GCP_REGION`, `TELEGRAM_BOT_TOKEN`, `SHEET_ID`, and `REDIS_URL` (for worker).
