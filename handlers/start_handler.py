import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown

WEB_APP_URL = os.getenv("WEB_APP_AUTH_URL")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение при команде /start."""
    user = update.effective_user
    name = escape_markdown(user.first_name or "пользователь")
    welcome_message = f"Добрый день, {name}, для продолжения вам необходимо авторизоваться"

    keyboard = [
        [InlineKeyboardButton("Авторизоваться", web_app={"url": WEB_APP_URL})]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(welcome_message, reply_markup=reply_markup)