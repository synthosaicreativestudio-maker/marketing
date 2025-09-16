#!/usr/bin/env python3
"""Minimal Telegram bot: /start handler greets the user and requests authorization."""
import os
import logging
from pathlib import Path

from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

from plugins.loader import load_plugins

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    name = None
    if user:
        name = user.first_name or user.username
    display_name = name if name else "пользователь"
    text = f"Привет, {display_name}!\nВам необходимо пройти авторизацию."
    # You can extend here: send buttons, request phone, link to web-auth, etc.
    update.message.reply_text(text)


def main() -> None:
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        log.error("TELEGRAM_TOKEN is not set in environment")
        print("Set TELEGRAM_TOKEN in .env or environment before running the bot")
        return

    updater = Updater(token=token)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))

    # load plugins
    cfg_path = Path('config/plugins.json')
    plugins = load_plugins(dp, updater.bot, cfg_path)

    log.info("Starting bot polling")
    updater.start_polling()
    try:
        updater.idle()
    finally:
        # cleanup plugins
        for h in plugins:
            try:
                h.get('unregister', lambda: None)()
            except Exception:
                pass


if __name__ == "__main__":
    main()
