import logging
import os
from dotenv import load_dotenv
from telegram.ext import Application
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
    logger.info(f"Загружен TELEGRAM_TOKEN: {'<TOKEN_FOUND>' if token else 'None'}")
    if not token:
        logger.critical("TELEGRAM_TOKEN не найден в .env файле! Бот не может быть запущен.")
        return

    # --- Инициализация сервисов ---
    logger.info("Инициализация сервисов...")
    logger.info("Инициализация Google Sheets сервиса...")
    sheets_service = GoogleSheetsService()
    logger.info(f"Google Sheets клиент инициализирован: {sheets_service.client is not None}")
    if not sheets_service.client:
        logger.critical("Не удалось инициализировать GoogleSheetsService. Проверьте credentials.json и доступы.")
        return
        
    logger.info("Инициализация AuthService...")
    auth_service = AuthService(sheets_service)
    logger.info(f"AuthService sheet инициализирован: {auth_service.sheet is not None}")
    if not auth_service.sheet:
        logger.critical("Не удалось загрузить таблицу авторизации. Проверьте SHEET_URL в .env.")
        return

    # --- Создание и настройка приложения ---
    logger.info("Создание экземпляра бота...")
    application = Application.builder().token(token).build()

    # --- Регистрация обработчиков ---
    logger.info("Регистрация обработчиков...")
    try:
        setup_handlers(application, auth_service)
        logger.info("Обработчики успешно зарегистрированы")
    except Exception as e:
        logger.error(f"Ошибка регистрации обработчиков: {e}")
        return

    # --- Запуск бота ---
    logger.info("Запуск бота...")
    try:
        application.run_polling()
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске бота: {e}", exc_info=True)

if __name__ == "__main__":
    main()
