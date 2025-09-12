## Security notes

1) Do not store long-lived personal access tokens (PATs) or other secrets in repository files.
   - The repository currently contains a `.env` file with `GITHUB_PAT`. This is risky and should be removed from version control.

2) Recommendations
   - Revoke the PAT that was added to `.env` and create a new one only if absolutely necessary.
   - Use GitHub repository Secrets (Settings → Secrets → Actions) to store tokens used by workflows.
   - For local development, keep `.env` in `.gitignore` and never commit it.

3) Rotating secrets
   - If a secret was committed, consider rotating it and removing it from git history using the BFG repo cleaner or git filter-repo.
