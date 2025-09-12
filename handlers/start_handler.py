from telegram import Update
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение при команде /start."""
    user = update.effective_user
    name = escape_markdown(user.first_name or "пользователь")
    welcome_message = f"Добрый день, {name}, для продолжения вам необходимо авторизоваться"

    await update.message.reply_text(welcome_message)
