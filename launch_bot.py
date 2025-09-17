#!/usr/bin/env python3
"""Launch bot in isolated subprocess to avoid event loop conflicts."""

import os
import subprocess
import sys

from dotenv import load_dotenv


def main():
    # Load .env file
    load_dotenv()

    # Read token from environment
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        # Check for legacy name for compatibility
        token = os.environ.get("TELEGRAM_TOKEN")

    if not token:
        print("❌ TELEGRAM_BOT_TOKEN or TELEGRAM_TOKEN not found in .env or environment!")
        return 1

    print("🚀 Starting MarketingBot...")
    print(f"📱 Token: {token[:15]}...")

    # The current environment is already updated by load_dotenv.
    # We ensure the specific variable the bot script expects is set.
    env = os.environ.copy()
    env['TELEGRAM_BOT_TOKEN'] = token

    # Start bot in subprocess
    try:
        proc = subprocess.Popen(
            [sys.executable, 'bot.py'],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        print(f"✅ Bot started with PID: {proc.pid}")
        print("📋 Bot output:")
        print("-
