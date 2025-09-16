#!/usr/bin/env python3
"""Minimal Telegram bot: /start handler greets the user and requests authorization."""
import os
import logging
from pathlib import Path

from telegram import Update
from telegram.ext import CommandHandler
try:
    # v13.x
    from telegram.ext import Updater, CallbackContext
    PTB_V13 = True
except Exception:
    # v20+ fallback
    PTB_V13 = False
    try:
        from telegram.ext import ApplicationBuilder, ContextTypes
    except Exception:
        ApplicationBuilder = None
        ContextTypes = None

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

    plugins = []
    if PTB_V13:
        # python-telegram-bot v13 compatible code
        updater = Updater(token=token, use_context=True)
        dp = updater.dispatcher
        dp.add_handler(CommandHandler("start", start))

        # load plugins (v13 expects bot instance)
        cfg_path = Path('config/plugins.json')
        plugins = load_plugins(dp, updater.bot, cfg_path)

        log.info("Starting bot polling (ptb v13)")
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
    else:
        # Try to run with python-telegram-bot v20+ Application API
        if ApplicationBuilder is None:
            log.error("No compatible telegram.ext API found (neither Updater nor ApplicationBuilder)")
            return

        app = ApplicationBuilder().token(token).build()
        # v20 handlers expect async callbacks or ContextTypes
        # Wrap legacy start into async if needed
        async def _start(update: Update, context):
            # call legacy start synchronously
            try:
                start(update, context)
            except Exception:
                # if start is sync and raises, ignore to avoid stopping the app
                pass

        app.add_handler(CommandHandler("start", _start))

        # load plugins - plugins should handle both sync and async handlers
        cfg_path = Path('config/plugins.json')
        plugins = load_plugins(app, app.bot, cfg_path) if hasattr(load_plugins, '__call__') else []

        log.info("Starting bot polling (ptb v20+)")
        try:
            app.run_polling()
        finally:
            for h in plugins:
                try:
                    h.get('unregister', lambda: None)()
                except Exception:
                    pass


if __name__ == "__main__":
    main()
