#!/usr/bin/env python3
"""Generate Telegram WebApp initData for local testing.

Usage:
  python scripts/generate_initdata.py --bot-token <BOT_TOKEN> --user-id 12345

Prints an URL-encoded initData string suitable to pass to /api/webapp/auth as initData.
"""
import argparse
import hashlib
import hmac
import json
import time
import urllib.parse


def make_initdata(bot_token: str, user: dict) -> str:
    params = {
        'user': json.dumps(user, separators=(',', ':')),
        'auth_date': str(int(time.time()))
    }
    items = sorted(params.items())
    data_check_string = '\n'.join(f"{k}={v}" for k, v in items)
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    mac = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    params['hash'] = mac
    qs = '&'.join(f"{k}={urllib.parse.quote_plus(v)}" for k, v in params.items())
    return qs


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--bot-token', required=True)
    p.add_argument('--user-id', type=int, required=True)
    p.add_argument('--first-name', default='Test')
    args = p.parse_args()
    user = {'id': args.user_id, 'first_name': args.first_name, 'is_bot': False}
    print(make_initdata(args.bot_token, user))
