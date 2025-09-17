import logging
import os
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Импорт наших модулей
from google_sheets_service import GoogleSheetsService
from auth_service import AuthService
from handlers import setup_handlers

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

def main() -> None:
    """Основная функция для инициализации и запуска бота."""
    # --- Проверка наличия токена ---
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logger.critical("TELEGRAM_TOKEN не найден в .env файле! Бот не может быть запущен.")
        return

    # --- Инициализация сервисов ---
    logger.info("Инициализация сервисов...")
    sheets_service = GoogleSheetsService()
    if not sheets_service.client:
        logger.critical("Не удалось инициализировать GoogleSheetsService. Проверьте credentials.json и доступы.")
        return
        
    auth_service = AuthService(sheets_service)
    if not auth_service.sheet:
        logger.critical("Не удалось загрузить таблицу авторизации. Проверьте SHEET_URL в .env.")
        return

    # --- Создание и настройка приложения ---
    logger.info("Создание экземпляра бота...")
    application = Application.builder().token(token).build()

    # --- Регистрация обработчиков ---
    logger.info("Регистрация обработчиков...")
    setup_handlers(application, auth_service)

    # --- Запуск бота ---
    logger.info("Запуск бота...")
    application.run_polling()


if __name__ == "__main__":
    main()
