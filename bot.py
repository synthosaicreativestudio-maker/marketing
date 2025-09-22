import logging
import os
from dotenv import load_dotenv
from telegram.ext import Application

# Загружаем .env как можно раньше, до импортов, читающих переменные окружения
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

from auth_service import AuthService
from handlers import setup_handlers

# .env уже загружен выше

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
    logger.info("Инициализация AuthService (sheets.py)...")
    auth_service = AuthService()
    if not auth_service.worksheet:
        logger.critical("Не удалось инициализировать доступ к Google Sheets. Проверьте SHEET_ID/GCP_SA_JSON.")
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
