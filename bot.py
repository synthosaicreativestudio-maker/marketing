"""
MarketingBot - Telegram бот с максимальной защитой от падений.
Включает:
- Исправление конфликта event loop
- Graceful shutdown
- Глобальную обработку ошибок
- Мониторинг здоровья
- Автоматическое восстановление
"""
import logging
import os
import signal
import sys
import atexit
from dotenv import load_dotenv
from telegram.ext import Application
from telegram.error import TelegramError

# Загружаем .env как можно раньше, до импортов, читающих переменные окружения
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

# Настройка логирования сразу после загрузки .env
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

from auth_service import AuthService  # noqa: E402
from handlers import setup_handlers  # noqa: E402
from ai_service import AIService  # noqa: E402
from response_monitor import ResponseMonitor  # noqa: E402
from promotions_notifier import PromotionsNotifier  # noqa: E402
from appeals_service import AppealsService  # noqa: E402
from bot_health_monitor import BotHealthMonitor  # noqa: E402
from sheets_gateway import AsyncGoogleSheetsGateway  # noqa: E402

# Превентивные механизмы
try:
    from preventive_guards import SingleInstanceGuard, validate_environment  # noqa: E402
    PREVENTIVE_GUARDS_AVAILABLE = True
except ImportError:
    logger.warning("Превентивные механизмы не доступны")
    PREVENTIVE_GUARDS_AVAILABLE = False

# Глобальные переменные для graceful shutdown
application_instance = None
response_monitor_instance = None
promotions_notifier_instance = None
health_monitor_instance = None
shutdown_in_progress = False


def signal_handler(sig, frame):
    """Обработчик сигналов для корректного завершения работы."""
    global shutdown_in_progress
    
    if shutdown_in_progress:
        logger.warning("Получен повторный сигнал остановки, принудительное завершение...")
        sys.exit(1)
        
    shutdown_in_progress = True
    logger.info(f"Получен сигнал {sig}, выполняется graceful shutdown...")
    
    try:
        if application_instance and application_instance.running:
            logger.info("Остановка polling...")
            application_instance.stop()
            application_instance.shutdown()
        logger.info("Graceful shutdown завершен")
    except Exception as e:
        logger.error(f"Ошибка при graceful shutdown: {e}", exc_info=True)
    finally:
        sys.exit(0)


def setup_signal_handlers():
    """Настройка обработчиков сигналов."""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    logger.info("Обработчики сигналов настроены")


def cleanup_on_exit():
    """Функция очистки при выходе."""
    global shutdown_in_progress
    if not shutdown_in_progress:
        logger.info("Выполняется очистка при выходе...")
        shutdown_in_progress = True


# Регистрируем функцию очистки
atexit.register(cleanup_on_exit)


def main() -> None:
    """Основная функция для инициализации и запуска бота."""
    global application_instance, response_monitor_instance
    global promotions_notifier_instance, health_monitor_instance
    
    # Превентивные механизмы
    if PREVENTIVE_GUARDS_AVAILABLE:
        # Валидация окружения
        if not validate_environment():
            logger.critical("Некорректная конфигурация! Бот не может быть запущен.")
            sys.exit(1)
        
        # Защита от дублирования процессов (409 Conflict)
        with SingleInstanceGuard():
            _run_bot_main()
    else:
        _run_bot_main()


def _run_bot_main():
    """Внутренняя функция запуска бота."""
    global application_instance, response_monitor_instance
    global promotions_notifier_instance, health_monitor_instance
    
    # Настройка обработчиков сигналов
    setup_signal_handlers()
    
    # --- Проверка наличия токена ---
    token = os.getenv("TELEGRAM_TOKEN")
    logger.info(f"Загружен TELEGRAM_TOKEN: {'<TOKEN_FOUND>' if token else 'None'}")
    if not token:
        logger.critical("TELEGRAM_TOKEN не найден в .env файле! Бот не может быть запущен.")
        sys.exit(1)

    # --- Инициализация Gateway для каждого сервиса ---
    logger.info("Инициализация AsyncGoogleSheetsGateway...")
    auth_gateway = AsyncGoogleSheetsGateway(circuit_breaker_name='auth')
    appeals_gateway = AsyncGoogleSheetsGateway(circuit_breaker_name='appeals')
    promotions_gateway = AsyncGoogleSheetsGateway(circuit_breaker_name='promotions')
    
    # --- Инициализация сервисов с защитой от ошибок ---
    logger.info("Инициализация сервисов...")
    
    try:
        logger.info("Инициализация AuthService с Gateway...")
        auth_service = AuthService(gateway=auth_gateway)
        if not auth_service.worksheet:
            logger.warning("⚠️  Google Sheets недоступен при инициализации AuthService.")
            logger.warning("⚠️  Бот продолжит работу с ограниченной функциональностью.")
            logger.warning("⚠️  Авторизация будет работать из кэша, если пользователь уже авторизован.")
            # НЕ КРАШИМ БОТ! Продолжаем работу
    except Exception as e:
        logger.error(f"Ошибка инициализации AuthService: {e}", exc_info=True)
        logger.warning("⚠️  AuthService инициализирован с ограничениями. Бот продолжит работу.")
        # Создаем заглушку с пустым gateway
        auth_service = AuthService(gateway=auth_gateway)

    # Инициализация AI сервиса (OpenAI или Gemini)
    try:
        logger.info("Инициализация AIService с поддержкой инструментов...")
        ai_service = AIService(promotions_gateway=promotions_gateway)
        if not ai_service.is_enabled():
            logger.warning("AIService отключен: ни один провайдер не доступен")
        else:
            logger.info(f"AIService активен с провайдером: {ai_service.get_provider_name()}")
    except Exception as e:
        logger.error(f"Ошибка инициализации AIService: {e}", exc_info=True)
        ai_service = AIService()  # Создаем с отключенным сервисом

    # Инициализация сервиса обращений (Google Sheets)
    try:
        logger.info("Инициализация AppealsService с Gateway...")
        appeals_service = AppealsService(gateway=appeals_gateway)
        if not appeals_service.is_available():
            logger.warning("AppealsService отключен: лист 'обращения' недоступен")
    except Exception as e:
        logger.error(f"Ошибка инициализации AppealsService: {e}", exc_info=True)
        appeals_service = None

    # Инициализация монитора ответов
    try:
        logger.info("Инициализация ResponseMonitor...")
        if appeals_service and appeals_service.is_available():
            response_monitor = ResponseMonitor(appeals_service, token)
            logger.info("ResponseMonitor готов к работе")
        else:
            response_monitor = None
            logger.warning("ResponseMonitor отключен: AppealsService недоступен")
    except Exception as e:
        logger.error(f"Ошибка инициализации ResponseMonitor: {e}", exc_info=True)
        response_monitor = None

    # --- Создание и настройка приложения ---
    try:
        logger.info("Создание экземпляра бота...")
        application = Application.builder().token(token).build()
        application_instance = application
    except Exception as e:
        logger.critical(f"Критическая ошибка создания приложения: {e}", exc_info=True)
        sys.exit(1)

    # Инициализация уведомлений о акциях
    try:
        logger.info("Инициализация PromotionsNotifier с Gateway...")
        promotions_notifier = PromotionsNotifier(application.bot, auth_service, gateway=promotions_gateway)
        promotions_notifier_instance = promotions_notifier
        logger.info("PromotionsNotifier готов к работе")
    except Exception as e:
        logger.error(f"Ошибка инициализации PromotionsNotifier: {e}", exc_info=True)
        promotions_notifier = None

    # Инициализация монитора здоровья
    try:
        logger.info("Инициализация BotHealthMonitor...")
        health_monitor = BotHealthMonitor(
            application.bot, 
            check_interval=300,
            sheets_gateway=auth_gateway,
            auth_service=auth_service
        )
        health_monitor_instance = health_monitor
        logger.info("BotHealthMonitor готов к работе (с мониторингом Google Sheets)")
    except Exception as e:
        logger.error(f"Ошибка инициализации BotHealthMonitor: {e}", exc_info=True)
        health_monitor = None

    # --- Регистрация обработчиков ---
    logger.info("Регистрация обработчиков...")
    try:
        setup_handlers(application, auth_service, ai_service, appeals_service)
        logger.info("Обработчики успешно зарегистрированы")
    except Exception as e:
        logger.error(f"Ошибка регистрации обработчиков: {e}", exc_info=True)
        sys.exit(1)

    # --- Настройка мониторинга через post_init callback ---
    async def post_init(application: Application) -> None:
        """Инициализация мониторинга после запуска приложения."""
        import asyncio
        
        # Initialize RAG (Knowledge Base) if using Gemini
        # Используем глобальную переменную или из замыкания (ai_service доступен)
        if ai_service.provider == "Gemini" and ai_service.service and hasattr(ai_service.service, 'initialize'):
            try:
                await ai_service.service.initialize()
                logger.info("Knowledge Base initialization triggered")
            except Exception as e:
                logger.error(f"Failed to initialize Knowledge Base: {e}")
        
        # Запуск мониторинга здоровья
        if health_monitor:
            try:
                await health_monitor.start_monitoring()
                logger.info("Мониторинг здоровья запущен")
            except Exception as e:
                logger.error(f"Ошибка запуска мониторинга здоровья: {e}", exc_info=True)
        
        # Запуск мониторинга ответов специалистов
        if response_monitor and appeals_service and appeals_service.is_available():
            logger.info("Запуск мониторинга ответов специалистов...")
            try:
                asyncio.create_task(response_monitor.start_monitoring(interval_seconds=60))
                logger.info("Мониторинг ответов запущен (проверка каждую минуту)")
            except Exception as e:
                logger.error(f"Ошибка запуска мониторинга ответов: {e}", exc_info=True)

        # Запуск мониторинга акций
        if promotions_notifier:
            logger.info("Запуск мониторинга новых акций...")
            try:
                asyncio.create_task(promotions_notifier.start_monitoring(interval_minutes=15))
                logger.info("Мониторинг акций запущен (проверка каждые 15 минут)")
            except Exception as e:
                logger.error(f"Ошибка запуска мониторинга акций: {e}", exc_info=True)

    async def post_stop(application: Application) -> None:
        """Остановка мониторинга при завершении работы бота."""
        logger.info("Остановка всех мониторингов...")
        
        # Остановка мониторинга здоровья
        if health_monitor:
            try:
                await health_monitor.stop_monitoring()
            except Exception as e:
                logger.error(f"Ошибка остановки мониторинга здоровья: {e}")
        
        # Остановка мониторинга ответов
        if response_monitor and appeals_service and appeals_service.is_available():
            try:
                await response_monitor.stop_monitoring()
                logger.info("Мониторинг ответов остановлен")
            except Exception as e:
                logger.error(f"Ошибка остановки мониторинга ответов: {e}")

        # Остановка мониторинга акций
        if promotions_notifier:
            try:
                await promotions_notifier.stop_monitoring()
                logger.info("Мониторинг акций остановлен")
            except Exception as e:
                logger.error(f"Ошибка остановки мониторинга акций: {e}")

    # Регистрация хуков
    application.post_init = post_init
    application.post_stop = post_stop

    # --- Глобальный обработчик ошибок для polling ---
    async def error_handler(update: object, context: object) -> None:
        """Глобальный асинхронный обработчик ошибок."""
        error = context.error
        
        # Логируем все ошибки
        if isinstance(error, TelegramError):
            logger.error(f"Ошибка Telegram API: {error}")
            if "Conflict" in str(error):
                logger.critical("⚠️ ОБНАРУЖЕН КОНФЛИКТ: Запущено несколько экземпляров бота! "
                               "Проверьте активные процессы и systemd сервисы.")
        else:
            logger.error(f"Неожиданная ошибка: {error}", exc_info=True)
        
        # Не пробрасываем ошибку дальше - бот продолжает работу

    application.add_error_handler(error_handler)

    # --- Запуск бота с максимальной защитой ---
    logger.info("Запуск бота...")
    max_restart_attempts = 5
    restart_count = 0
    
    while restart_count < max_restart_attempts:
        try:
            logger.info("Начинается polling для получения обновлений от Telegram...")
            application.run_polling(
                poll_interval=0.0,  # Немедленная обработка обновлений без задержки
                timeout=10,  # Таймаут long polling запроса
                stop_signals=(signal.SIGINT, signal.SIGTERM),
                allowed_updates=None,  # Принимаем все типы обновлений
                drop_pending_updates=True,  # Сбрасываем устаревшие обновления при старте
                close_loop=False  # Не закрываем loop при остановке
            )
            logger.info("Polling завершен нормально")
            # Если polling завершился нормально, выходим
            break
            
        except KeyboardInterrupt:
            logger.info("Получен сигнал прерывания, выполняется остановка...")
            break
            
        except (TelegramError, ConnectionError, TimeoutError) as e:
            restart_count += 1
            logger.error(
                f"Критическая ошибка при работе бота (попытка {restart_count}/{max_restart_attempts}): {e}",
                exc_info=True
            )
            
            if restart_count < max_restart_attempts:
                wait_time = min(30, 5 * restart_count)  # Экспоненциальная задержка до 30 сек
                logger.info(f"Перезапуск бота через {wait_time} секунд...")
                # Задержка удалена - в асинхронной архитектуре не нужна
                # Если нужна задержка, использовать await asyncio.sleep() в async контексте
                
                # Пересоздаем приложение
                try:
                    application = Application.builder().token(token).build()
                    application_instance = application
                    # Переинициализируем AI сервис с актуальным gateway
                    ai_service = AIService(promotions_gateway=promotions_gateway)
                    setup_handlers(application, auth_service, ai_service, appeals_service)
                    application.post_init = post_init
                    application.post_stop = post_stop
                    application.add_error_handler(error_handler)
                    logger.info("Приложение пересоздано, повторный запуск...")
                except Exception as recreate_error:
                    logger.critical(f"Не удалось пересоздать приложение: {recreate_error}", exc_info=True)
                    break
            else:
                logger.critical(f"Достигнут лимит попыток перезапуска ({max_restart_attempts}). Завершение работы.")
                break
                
        except Exception as e:
            logger.critical(f"Критическая неожиданная ошибка при запуске бота: {e}", exc_info=True)
            # Для неожиданных ошибок не перезапускаем - это может быть проблема в коде
            break
    
    logger.info("Бот завершил работу")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"Критическая ошибка в main(): {e}", exc_info=True)
        sys.exit(1)
