# fetch_sheets helper

Small helper to download and summarise Google Sheets referenced in the repository's env file.

Security notes:
- Never commit `credentials.json` or any service account secrets to the repository.
- Use a Google service account with readonly scopes.

Quick usage:

1. Create a Google service account and download `credentials.json` to the project root (DO NOT commit it).
2. Install dependencies:

```bash
python -m pip install -r scripts/requirements.txt
```

3. Run the script for a sheet URL:

```bash
python scripts/fetch_sheets.py --sheet-url "<SHEET_URL>" --out sheet_summary.json
```

This will create `sheet_summary.json` with basic metadata and a small preview of each worksheet.
