import logging
import os
from dotenv import load_dotenv
from telegram.ext import Application

# Загружаем .env как можно раньше, до импортов, читающих переменные окружения
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

from auth_service import AuthService  # noqa: E402
from handlers import setup_handlers  # noqa: E402
from openai_service import OpenAIService  # noqa: E402
from response_monitor import ResponseMonitor  # noqa: E402
from promotions_notifier import PromotionsNotifier  # noqa: E402

# Импортируем AppealsService после загрузки переменных окружения
from appeals_service import AppealsService  # noqa: E402

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

    # Инициализация сервиса обращений (Google Sheets)
    logger.info("Инициализация AppealsService (Google Sheets)...")
    appeals_service = AppealsService()
    if not appeals_service.is_available():
        logger.warning("AppealsService отключен: лист 'обращения' недоступен")

    # Инициализация монитора ответов
    logger.info("Инициализация ResponseMonitor...")
    if appeals_service and appeals_service.is_available():
        response_monitor = ResponseMonitor(appeals_service, token)
        logger.info("ResponseMonitor готов к работе")
    else:
        response_monitor = None
        logger.warning("ResponseMonitor отключен: AppealsService недоступен")

    # --- Создание и настройка приложения ---
    logger.info("Создание экземпляра бота...")
    application = Application.builder().token(token).build()

    # Инициализация уведомлений о акциях
    logger.info("Инициализация PromotionsNotifier...")
    promotions_notifier = PromotionsNotifier(application.bot, auth_service)
    logger.info("PromotionsNotifier готов к работе")

    # --- Регистрация обработчиков ---
    logger.info("Регистрация обработчиков...")
    try:
        setup_handlers(application, auth_service, openai_service, appeals_service)
        logger.info("Обработчики успешно зарегистрированы")
    except Exception as e:
        logger.error(f"Ошибка регистрации обработчиков: {e}")
        return

    # --- Настройка мониторинга через post_init callback ---
    async def post_init(application: Application) -> None:
        """Инициализация мониторинга после запуска приложения."""
        import asyncio
        # Запуск мониторинга ответов специалистов
        if response_monitor and appeals_service and appeals_service.is_available():
            logger.info("Запуск мониторинга ответов специалистов...")
            try:
                asyncio.create_task(response_monitor.start_monitoring(interval_seconds=60))
                logger.info("Мониторинг ответов запущен (проверка каждую минуту)")
            except Exception as e:
                logger.error(f"Ошибка запуска мониторинга ответов: {e}")
        
        # Запуск мониторинга акций
        logger.info("Запуск мониторинга новых акций...")
        try:
            asyncio.create_task(promotions_notifier.start_monitoring(interval_minutes=15))
            logger.info("Мониторинг акций запущен (проверка каждые 15 минут)")
        except Exception as e:
            logger.error(f"Ошибка запуска мониторинга акций: {e}")
    
    async def post_stop(application: Application) -> None:
        """Остановка мониторинга при завершении работы бота."""
        if response_monitor and appeals_service and appeals_service.is_available():
            try:
                await response_monitor.stop_monitoring()
            except Exception as e:
                logger.error(f"Ошибка остановки мониторинга: {e}")
    
    # Регистрация хуков
    application.post_init = post_init
    application.post_stop = post_stop

    # --- Запуск бота ---
    logger.info("Запуск бота...")
    try:
        application.run_polling()
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске бота: {e}", exc_info=True)
        

if __name__ == "__main__":
    main()
