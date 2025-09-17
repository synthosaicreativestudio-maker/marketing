import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler
from auth_service import AuthService

logger = logging.getLogger(__name__)

async def start_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, auth_service: AuthService):
    load_dotenv()
    web_app_url = os.getenv("WEB_APP_URL")

    if not web_app_url:
        logger.error("WEB_APP_URL не установлен в .env файле.")
        await update.message.reply_text("Произошла ошибка: не удалось получить URL для авторизации.")
        return

    telegram_id = update.effective_user.id
    is_authorized = await auth_service.get_user_auth_status(telegram_id)

    if not is_authorized:
        keyboard = [[InlineKeyboardButton("Авторизоваться", web_app={"url": web_app_url})]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Привет! Я бот для маркетинговых задач. Для начала работы, пожалуйста, авторизуйтесь.",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text("С возвращением! Вы уже авторизованы.") # В будущем здесь будет главное меню

def setup_handlers(application, auth_service: AuthService):
    application.add_handler(CommandHandler("start", lambda update, context: start_command_handler(update, context, auth_service)))
    logger.info("Обработчики команд настроены.")