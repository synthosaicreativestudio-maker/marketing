"""Example auth plugin.

Contract: expose register(dispatcher, bot, settings) -> handle with 'unregister' callable.
"""
from telegram import Update
from telegram.ext import CommandHandler, CallbackContext


def _auth_start(update: Update, context: CallbackContext):
    user = update.effective_user
    name = user.first_name or user.username if user else 'пользователь'
    update.message.reply_text(f"Привет, {name}! Чтобы авторизоваться, отправьте ваш код: /code <код>")


def _auth_code(update: Update, context: CallbackContext):
    args = context.args
    if not args:
        update.message.reply_text("Укажите код: /code <код>")
        return
    code = args[0]
    # Здесь должен быть реальный механизм проверки кода
    if code == "1234":
        update.message.reply_text("Авторизация успешна")
    else:
        update.message.reply_text("Неверный код")


def register(dispatcher, bot, settings):
    start_h = CommandHandler('auth', _auth_start)
    code_h = CommandHandler('code', _auth_code)
    dispatcher.add_handler(start_h)
    dispatcher.add_handler(code_h)

    def unregister():
        try:
            dispatcher.remove_handler(start_h)
            dispatcher.remove_handler(code_h)
        except Exception:
            pass

    return {'name': 'auth', 'unregister': unregister}
