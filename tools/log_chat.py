#!/usr/bin/env python3
"""Простая утилита для дописывания сообщений в лог переписки
`docs/CONVERSATION_LOG.md`."""

import sys
from datetime import datetime
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parents[1] / 'docs' / 'CONVERSATION_LOG.md'


def append_message(author: str, message: str):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    entry = f"- {timestamp} | {author}: {message}\n"
    with LOG_PATH.open('a', encoding='utf-8') as f:
        f.write(entry)


def main():
    if len(sys.argv) < 3:
        print('Usage: log_chat.py "Author" "Message"')
        sys.exit(2)
    author = sys.argv[1]
    message = sys.argv[2]
    append_message(author, message)


if __name__ == '__main__':
    main()
