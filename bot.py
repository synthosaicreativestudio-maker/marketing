import logging
import os

from dotenv import load_dotenv
from telegram import Update, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler
from telegram.helpers import escape_markdown

# New import for modular handler
from handlers.start_handler import start

# Загружаем переменные окружения из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEB_APP_URL = os.getenv("WEB_APP_AUTH_URL")


def main() -> None:
    """Запускает бота."""
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN не найден в .env файле!")
        return

    # Создаем приложение
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Добавляем обработчик команды /start
    application.add_handler(CommandHandler("start", start))

    # Запускаем бота
    logger.info("Бот запускается...")
    application.run_polling()


if __name__ == "__main__":
    main()