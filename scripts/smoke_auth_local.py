#!/usr/bin/env python3
"""Smoke test for local auth flow.

Usage:
  export BOT_TOKEN=...   (optional, for signature validation and bot notification)
  export GCP_SA_JSON=... (optional, if you want to verify Google Sheet update)
  export SHEET_ID=...    (optional)

  .venv312/bin/python scripts/smoke_auth_local.py --partner-code 111098 \
    --phone "+7 982 770-1055" --user-id 123456

What it does:
- generates signed initData if BOT_TOKEN present (using scripts/generate_initdata.py)
- posts to /api/webapp/auth (default http://127.0.0.1:8000/api/webapp/auth)
- prints response
- if SHEET_ID and GCP_SA_JSON present, optionally reads sheet row to confirm update
"""
import argparse
import json
import os
import subprocess  # nosec B404
import sys

import requests


def generate_initdata(bot_token, user_id, first_name='Smoke'):
    from pathlib import Path
    gen_script = Path('scripts/generate_initdata.py')
    if not gen_script.exists():
        raise FileNotFoundError('scripts/generate_initdata.py not found')
    if not Path(sys.executable).exists():
        raise FileNotFoundError(f'Python executable not found: {sys.executable}')
    cmd = [
        sys.executable, str(gen_script), '--bot-token', bot_token,
        '--user-id', str(user_id), '--first-name', first_name
    ]
    out = subprocess.check_output(cmd)  # nosec B603
    return out.decode().strip()


def post_auth(url, initdata, partner_code, phone):
    payload = {
        'init_data': initdata,
        'partner_code': partner_code,
        'partner_phone': phone
    }
    r = requests.post(url, json=payload, timeout=10)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, r.text


def check_sheet(sheet_id, partner_code, phone):
    try:
        import gspread
        sa = None
        sa_json = os.environ.get('GCP_SA_JSON')
        sa_file = os.environ.get('GCP_SA_FILE')
        if sa_json:
            sa = json.loads(sa_json)
            creds = gspread.service_account_from_dict(sa)
        elif sa_file:
            from pathlib import Path as _Path
            if _Path(sa_file).exists():
                creds = gspread.service_account(filename=_Path(sa_file))
            else:
                print('Service account file not found, skipping sheet check')
                return None
        else:
            print('No service account info, skipping sheet check')
            return None
        sh = creds.open_by_key(sheet_id)
        ws = sh.sheet1
        rows = ws.get_all_values()
        # find matching
        digit_phone = ''.join(ch for ch in phone if ch.isdigit())
        for idx, row in enumerate(rows[1:], start=2):
            a = (row[0].strip() if len(row) >= 1 else '')
            c = (row[2].strip() if len(row) >= 3 else '')
            normalized_c = c.replace('+', '').replace('-', '').replace(' ', '')
            if a == partner_code and digit_phone.endswith(normalized_c):
                return idx, row
        return None
    except Exception as e:
        print('Sheet check failed:', e)
        return None


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--partner-code', required=True)
    p.add_argument('--phone', required=True)
    p.add_argument('--user-id', type=int, default=0)
    p.add_argument('--url', default='http://127.0.0.1:8000/api/webapp/auth')
    args = p.parse_args()

    bot_token = os.environ.get('BOT_TOKEN') or os.environ.get('TELEGRAM_BOT_TOKEN')
    if bot_token and args.user_id:
        print('Generating signed initData...')
        initdata = generate_initdata(bot_token, args.user_id)
    else:
        print('No BOT_TOKEN or no user-id provided; using dummy initData')
        initdata = 'dummy'

    print('Posting to', args.url)
    status, body = post_auth(args.url, initdata, args.partner_code, args.phone)
    print('HTTP', status)
    if isinstance(body, dict):
        print('Body:', json.dumps(body, ensure_ascii=False, indent=2))
    else:
        print('Body:', body)

    # optional sheet check
    sheet_id = os.environ.get('SHEET_ID')
    if sheet_id:
        print('Checking sheet for update...')
        res = check_sheet(sheet_id, args.partner_code, args.phone)
        if res:
            idx, row = res
            print('Found match at row', idx)
            print(row)
        else:
            print('No matching row found or unable to verify')

    print('Smoke finished')
