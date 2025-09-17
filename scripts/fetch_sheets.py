"""Safe helper to download and summarize Google Sheets referenced in the repo's env file.

Usage (locally):
  1. Put your Google service account JSON in the repo root as `credentials.json` (DO NOT commit it).
  2. Install dependencies: pip install -r scripts/requirements.txt
  3. Run: python scripts/fetch_sheets.py --sheet-url "<SHEET_URL>" --out summary.json

The script prints a short summary (sheet titles, number of worksheets, rows/cols counts and a small preview of each worksheet).
It does not modify any remote data.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from typing import Any, Dict, List

import gspread
from google.oauth2.service_account import Credentials


def extract_spreadsheet_id(url: str) -> str:
    # Extracts spreadsheet ID from a Google Sheets URL
    m = re.search(r"/d/([a-zA-Z0-9-_]+)", url)
    if not m:
        raise ValueError("Could not extract spreadsheet ID from URL: %s" % url)
    return m.group(1)


def get_client(creds_path: str) -> gspread.Client:
    if not os.path.exists(creds_path):
        raise FileNotFoundError(f"Credentials file not found: {creds_path}")
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
    return gspread.authorize(creds)


def summarize_sheet(client: gspread.Client, sheet_url: str, max_preview_rows: int = 20) -> Dict[str, Any]:
    ss_id = extract_spreadsheet_id(sheet_url)
    ss = client.open_by_key(ss_id)
    summary: Dict[str, Any] = {
        "spreadsheet_id": ss_id,
        "title": ss.title,
        "worksheets": [],
    }
    for ws in ss.worksheets():
        rows = ws.row_count
        cols = ws.col_count
        values = ws.get_all_values()
        preview = values[:max_preview_rows]
        summary["worksheets"].append(
            {
                "title": ws.title,
                "rows": rows,
                "cols": cols,
                "data_rows": len(values),
                "preview": preview,
            }
        )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sheet-url", required=True, help="Google Sheet URL to summarize")
    parser.add_argument("--creds", default="credentials.json", help="Path to service account credentials JSON")
    parser.add_argument("--out", default=None, help="Optional output JSON file")
    args = parser.parse_args()

    client = get_client(args.creds)
    try:
        summ = summarize_sheet(client, args.sheet_url)
    except Exception as e:
        print("Error while fetching sheet:", e)
        raise

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(summ, f, ensure_ascii=False, indent=2)
        print(f"Summary written to {args.out}")
    else:
        print(json.dumps(summ, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
