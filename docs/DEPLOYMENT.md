## GitHub Pages deployment (current state)

This document explains the two deployment approaches present in this repository and the steps required to make the "Deploy Mini App to GitHub Pages" workflow succeed.

### Two supported deployment approaches

- Deploy via GitHub Actions (`actions/deploy-pages@v3`)
  - Uses the GitHub Pages API to create a deployment from the artifact produced by the workflow.
  - Advantages: clean, integrates with Actions, no extra branch required.
  - Requirements: GitHub Pages must be enabled for the repository (one-time UI toggle) or the token used to call the Pages API must have admin/Pages scope and repo write permissions.

- Branch-based deploy (push to `gh-pages` branch)
  - Uses `peaceiris/actions-gh-pages` or similar to push build output to `gh-pages` branch.
  - Advantages: works when Pages API access is restricted; simple to debug.
  - Requirements: workflow must have `contents: write` permission so the `GITHUB_TOKEN` can push the branch.


### Current repository status (as of last check)

- The repository contains a workflow at `.github/workflows/deploy.yml` that uses `actions/deploy-pages@v3` and requests the following workflow permissions:

  ```yaml
  permissions:
    pages: write
    id-token: write
    contents: read
  ```

- Historically a branch-based workflow (`deploy-gh-pages.yml`) was added and removed during experimentation. When used, it required `contents: write` permission to allow the action to push the `gh-pages` branch.

- Recent deploy-action runs failed with a 404 when trying to create a deployment. The job logs showed errors like:

  - "HttpError: Cannot find any run with github.run_id <id>"
  - "Error: Failed to create deployment (status: 404) ... Ensure GitHub Pages has been enabled"

- An attempt to set Pages site source via the REST API returned 403: "Resource not accessible by personal access token". That indicates the token in `.env` lacks the admin/Pages permission to change Pages settings.


### Exact steps to get `actions/deploy-pages@v3` working

Choose one of the options below:

1) Manual one-time enable (recommended, simplest):
   - Open the repository in GitHub.
   - Go to Settings → Pages.
   - Under "Build and deployment", select "GitHub Actions" (or set Source to Branch `main` and path `/docs` if you prefer branch deploy) and Save.
   - Re-run the `Deploy Mini App to GitHub Pages` workflow. It should be able to create a deployment.

2) Programmatic enable (requires admin token):
   - Provide a personal access token with repository admin rights and pages scope.
   - Use the Pages API to set the source. Example:

   ```bash
   export GITHUB_PAT=...
   curl -X PUT -H "Authorization: token $GITHUB_PAT" \
     -H "Accept: application/vnd.github+json" \
     https://api.github.com/repos/<owner>/<repo>/pages \
     --data '{"source":{"branch":"main","path":"/docs"}}'
   ```

   - Re-run the deploy workflow.


### Notes and troubleshooting

- If you see permission errors when deploying with `actions/deploy-pages@v3`, verify both the workflow `permissions` block and the repository Pages settings.
- If using branch deploy, ensure the workflow contains `permissions: contents: write` at either job or workflow level.
- Avoid storing long-lived PATs in `.env` within the repository. Use repository Secrets instead.
