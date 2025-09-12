## Open issues and next work items

This file collects remaining work and recommended next steps.

1) Enable GitHub Pages (required for deploy action)
   - See `docs/DEPLOYMENT.md` for manual and programmatic options.

2) Implement Google Sheets integration
   - Replace placeholder methods in `google_sheets_service.py` with calls to the Google Sheets API using a service account JSON key.
   - Add instructions or helper to create service account and set `GOOGLE_APPLICATION_CREDENTIALS` or the equivalent environment variable.

3) Add scheduler/service for periodic checks
   - Implement `scheduler_service.py` or integrate an external scheduler (cron or GitHub Actions) to periodically verify partner auth status and send reminders.

4) Add tests
   - Unit tests for `handlers/start_handler.py` and `google_sheets_service.py` (mocking Google APIs).
   - Add a fast CI job to run tests on pushes.

5) Remove sensitive tokens from repository
   - `GITHUB_PAT` is currently present in `.env`. Replace with repository Secrets and remove from repo history if necessary.

6) Documentation improvements
   - Add small HOWTOs: "How to run locally", "How to add a Google service account", "How to enable Pages".
