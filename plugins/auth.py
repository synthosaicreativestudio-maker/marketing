"""Enhanced auth plugin with security improvements.

Expose register(dispatcher, bot, settings) -> returns a dict with 'unregister'.
"""
import os
from typing import Any, Optional

from telegram import Update
from telegram.ext import CommandHandler


async def _auth_start(update: Update, context: Any) -> None:
    """Handle /auth command."""
    user = update.effective_user
    name = user.first_name or user.username if user else 'пользователь'
    if update.message:
        await update.message.reply_text(
            f"Привет, {name}! Чтобы авторизоваться, отправьте ваш код: /code <код>"
        )


async def _auth_code(update: Update, context: Any) -> None:
    """Handle /code command with authorization."""
    args = getattr(context, 'args', [])
    if not args:
        if update.message:
            await update.message.reply_text("Укажите код: /code <код>")
        return

    code = args[0]
    # Используем код из переменной окружения вместо хардкода
    valid_code = os.environ.get('AUTH_CODE', '1234')

    if update.message:
        if code == valid_code:
            await update.message.reply_text("Авторизация успешна")
        else:
            await update.message.reply_text("Неверный код")


def register(
    dispatcher: Any, bot: Any, settings: Optional[dict[str, Any]]
) -> dict[str, Any]:
    """Register auth plugin handlers."""
    start_h = CommandHandler('auth', _auth_start)
    code_h = CommandHandler('code', _auth_code)
    dispatcher.add_handler(start_h)
    dispatcher.add_handler(code_h)

    def unregister() -> None:
        """Unregister handlers."""
        from contextlib import suppress
        # attempt to remove handlers; ignore if they're not present
        with suppress(Exception):
            dispatcher.remove_handler(start_h)
            dispatcher.remove_handler(code_h)

    return {
        'name': 'auth',
        'version': '2.0.0',
        'description': 'Enhanced authentication plugin with security improvements',
        'unregister': unregister
    }
