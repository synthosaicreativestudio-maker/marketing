#!/usr/bin/env python3
"""Set Telegram webhook for bot (useful for Cloud Run deployments).

Usage:
  export BOT_TOKEN=...
  python scripts/setup_webhook.py --url https://your-service.run.app/
"""
import argparse
import os

import requests


def set_webhook(bot_token: str, url: str):
    api = f'https://api.telegram.org/bot{bot_token}/setWebhook'
    payload = {'url': url, 'max_connections': 40}
    r = requests.post(api, json=payload, timeout=10)
    r.raise_for_status()
    return r.json()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument(
        '--url', required=True, help='Public HTTPS URL where Telegram will send updates'
    )
    p.add_argument('--drop', action='store_true', help='Drop webhook (set empty url)')
    args = p.parse_args()
    bot_token = os.environ.get('BOT_TOKEN') or os.environ.get('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        raise SystemExit('Set BOT_TOKEN or TELEGRAM_BOT_TOKEN env var')
    if args.drop:
        print('Dropping webhook...')
        print(set_webhook(bot_token, ''))
    else:
        print(set_webhook(bot_token, args.url))
