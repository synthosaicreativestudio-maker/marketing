import logging
import os
import json

from dotenv import load_dotenv
from telegram import Update, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from telegram.helpers import escape_markdown

# New import for modular handler
from handlers.start_handler import start
from google_sheets_service import GoogleSheetsService

# Загружаем переменные окружения из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEB_APP_URL = os.getenv("WEB_APP_AUTH_URL")

# Initialize GoogleSheetsService
sheets_service = GoogleSheetsService()

async def web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает данные, полученные из Web App."""
    user = update.effective_user
    data = json.loads(update.effective_message.web_app_data.data)
    logger.info(f"Received data from Web App for user {user.id}: {data}")

    partner_code = data.get("code")
    partner_phone = data.get("phone")

    if not partner_code or not partner_phone:
        await update.effective_message.reply_text("Ошибка: не получены все необходимые данные из Mini App.")
        return

    # Placeholder for Google Sheets interaction
    auth_success = await sheets_service.find_and_update_user(
        partner_code, partner_phone, user.id
    )

    if auth_success:
        await update.effective_message.reply_text("Авторизация прошла успешно!")
    else:
        await update.effective_message.reply_text("Данные не найдены, повторите авторизацию.")
        # Re-attach inline button for re-authorization (similar to start command)
        # This part needs to be carefully implemented to avoid circular dependencies
        # For now, just send the message. The button re-attachment will be a separate task.


def main() -> None:
    """Запускает бота."""
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN не найден в .env файле!")
        return

    # Создаем приложение
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Добавляем обработчик команды /start
    application.add_handler(CommandHandler("start", start))

    # Добавляем обработчик для данных из Web App
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data))

    # Запускаем бота
    logger.info("Бот запускается...")
    application.run_polling()


if __name__ == "__main__":
    main()
