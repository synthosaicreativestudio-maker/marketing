#!/usr/bin/env python3
"""Send an inline keyboard with a Web App button to a chat via Bot API.

Usage:
  export BOT_TOKEN=...
  python scripts/send_webapp_button.py --chat-id 12345 --url https://abcd.ngrok.io/webapp/index.html
"""
import argparse
import json
import os

import requests


def send_button(bot_token: str, chat_id: int, url: str, text: str = 'Open Web App'):
    api = f'https://api.telegram.org/bot{bot_token}/sendMessage'
    payload = {
        'chat_id': chat_id,
        'text': text,
        'reply_markup': json.dumps({
            'inline_keyboard': [[{'text': 'Авторизоваться', 'web_app': {'url': url}}]]
        })
    }
    r = requests.post(api, data=payload)
    r.raise_for_status()
    return r.json()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--chat-id', type=int, required=True)
    p.add_argument('--url', required=True)
    p.add_argument('--text', default='Откройте Web App для авторизации')
    args = p.parse_args()
    bot_token = os.environ.get('BOT_TOKEN')
    if not bot_token:
        raise SystemExit('Set BOT_TOKEN env var')
    print(send_button(bot_token, args.chat_id, args.url, args.text))
