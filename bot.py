#!/usr/bin/env python3
"""Modern Telegram bot with authorization flow using python-telegram-bot v21+."""
import asyncio
import logging
import os
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from plugins.loader import load_plugins

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    user = update.effective_user
    name = None
    if user:
        name = user.first_name or user.username
    display_name = name if name else "пользователь"
    text = f"Привет, {display_name}!\nВам необходимо пройти авторизацию."

    keyboard = [[InlineKeyboardButton("Авторизоваться", callback_data='authorize')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)


async def handle_authorize_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle authorization callback."""
    query = update.callback_query
    await query.answer()
    # Here you would typically redirect the user to your web app for authorization
    # For this example, we'll just send a message with a link
    webapp_url = os.environ.get("WEBAPP_URL", "https://your-webapp-url.com/auth")
    # Replace with your actual webapp URL
    await query.edit_message_text(
        text=(
            f"Для авторизации, пожалуйста, перейдите по ссылке: {webapp_url}"
        )
    )


async def main() -> None:
    """Start the bot."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        log.error("TELEGRAM_BOT_TOKEN env var not set!")
        return

    # Create application
    app = Application.builder().token(token).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        CallbackQueryHandler(handle_authorize_callback, pattern='^authorize$')
    )

    # Load plugins
    cfg_path = Path('config/plugins.json')
    plugins: list = []
    try:
        plugins = (
            load_plugins(app, app.bot, cfg_path) if callable(load_plugins) else []
        )
    except Exception as e:
        log.warning("Failed to load plugins: %s", e)
        plugins = []

    log.info("Starting bot polling (python-telegram-bot v21+)")
    try:
        await app.run_polling()
    finally:
        from contextlib import suppress
        for h in plugins:
            with suppress(Exception):
                unregister_func = h.get('unregister')
                if unregister_func:
                    unregister_func()

if __name__ == "__main__":
    asyncio.run(main())
