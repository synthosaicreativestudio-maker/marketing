#!/usr/bin/env python3
"""Generate initData and POST to local /api/webapp/auth to simulate a real Web App open.

Usage:
  export BOT_TOKEN=...
  python scripts/test_auth_via_bot.py --user-id 12345 --partner-code 111098 \
    --phone "+7 982 770-1055"

This script will generate a signed initData for the given BOT_TOKEN and user id,
then POST it to http://127.0.0.1:8000/api/webapp/auth and print the response.
"""
import argparse
import os
import subprocess  # nosec B404
import sys

import requests


def generate_initdata(bot_token, user_id):
    # call the helper script in the repo
    cmd = [
        sys.executable, 'scripts/generate_initdata.py',
        '--bot-token', bot_token, '--user-id', str(user_id)
    ]
    out = subprocess.check_output(cmd)  # nosec B603
    return out.decode().strip()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--user-id', type=int, required=True)
    p.add_argument('--partner-code', required=True)
    p.add_argument('--phone', required=True)
    p.add_argument('--url', default='http://127.0.0.1:8000/api/webapp/auth')
    args = p.parse_args()
    bot_token = os.environ.get('BOT_TOKEN')
    if not bot_token:
        raise SystemExit('Set BOT_TOKEN env var')
    initdata = generate_initdata(bot_token, args.user_id)
    payload = {
        'init_data': initdata,
        'partner_code': args.partner_code,
        'partner_phone': args.phone
    }
    r = requests.post(args.url, json=payload, timeout=30)
    print('STATUS', r.status_code)
    try:
        print(r.json())
    except Exception:
        print(r.text)
