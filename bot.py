import logging
import os
from dotenv import load_dotenv
from telegram.ext import Application

# Загружаем .env как можно раньше, до импортов, читающих переменные окружения
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

from auth_service import AuthService
from handlers import setup_handlers
from openai_service import OpenAIService
from appeals_service import AppealsService
from response_monitor import ResponseMonitor

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

    # Инициализация OpenAI (опционально)
    logger.info("Инициализация OpenAIService (Assistants Threads)...")
    openai_service = OpenAIService()
    if not openai_service.is_enabled():
        logger.warning("OpenAIService отключен: отсутствуют OPENAI_API_KEY/OPENAI_ASSISTANT_ID")

    # Инициализация сервиса обращений
    logger.info("Инициализация AppealsService...")
    appeals_service = AppealsService()
    if not appeals_service.is_available():
        logger.warning("AppealsService отключен: лист 'обращения' недоступен")

    # Инициализация монитора ответов
    logger.info("Инициализация ResponseMonitor...")
    response_monitor = ResponseMonitor(appeals_service, token)
    if appeals_service.is_available():
        logger.info("ResponseMonitor готов к работе")
    else:
        logger.warning("ResponseMonitor отключен: AppealsService недоступен")

    # --- Создание и настройка приложения ---
    logger.info("Создание экземпляра бота...")
    application = Application.builder().token(token).build()

    # --- Регистрация обработчиков ---
    logger.info("Регистрация обработчиков...")
    try:
        setup_handlers(application, auth_service, openai_service, appeals_service)
        logger.info("Обработчики успешно зарегистрированы")
    except Exception as e:
        logger.error(f"Ошибка регистрации обработчиков: {e}")
        return

    # --- Запуск мониторинга ответов ---
    if appeals_service.is_available():
        logger.info("Запуск мониторинга ответов специалистов...")
        try:
            # Запускаем мониторинг в фоновом режиме
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.create_task(response_monitor.start_monitoring(interval_seconds=60))
            logger.info("Мониторинг ответов запущен (проверка каждую минуту)")
        except Exception as e:
            logger.error(f"Ошибка запуска мониторинга ответов: {e}")

    # --- Запуск бота ---
    logger.info("Запуск бота...")
    try:
        application.run_polling()
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске бота: {e}", exc_info=True)
    finally:
        # Останавливаем мониторинг при завершении работы бота
        if appeals_service.is_available():
            try:
                loop.run_until_complete(response_monitor.stop_monitoring())
            except Exception as e:
                logger.error(f"Ошибка остановки мониторинга: {e}")

if __name__ == "__main__":
    main()
