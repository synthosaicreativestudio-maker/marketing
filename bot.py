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
import asyncio
import time
import socket
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
from utils import alert_admin  # noqa: E402
from handlers import setup_handlers  # noqa: E402
from ai_service import AIService  # noqa: E402
from response_monitor import ResponseMonitor  # noqa: E402
from promotions_notifier import PromotionsNotifier  # noqa: E402
from appeals_service import AppealsService  # noqa: E402
from bot_health_monitor import BotHealthMonitor  # noqa: E402
from sheets_gateway import AsyncGoogleSheetsGateway  # noqa: E402
from polling_watchdog import PollingWatchdog  # noqa: E402
from task_tracker import task_tracker  # noqa: E402
from user_profile_manager_sheets import UserProfileManagerSheets  # noqa: E402

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
polling_watchdog_instance = None
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
        
        logger.info("📜 ЗАПУСК БОТА. ОБЯЗАТЕЛЬНО ПРОЧТИТЕ ПРАВИЛА: docs/RULES_RU.md")
        logger.info("⚠️  Убедитесь, что это ЕДИНСТВЕННЫЙ запущенный экземпляр бота!")
        
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
    
    # 4. Менеджер профилей пользователей (Long-term memory)
    profile_manager = UserProfileManagerSheets(auth_gateway)
    logger.info("Менеджер профилей (Google Sheets) инициализирован")
    
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

    # Инициализация AI сервиса
    try:
        logger.info("Инициализация AIService...")
        ai_service = AIService(promotions_gateway=promotions_gateway)
        if not ai_service.is_enabled():
            logger.warning("AIService отключен: ни один провайдер не доступен")
        else:
            logger.info(
                "AIService активен: backend=%s, provider=%s",
                ai_service.get_backend_name(),
                ai_service.get_provider_name(),
            )
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
        # Увеличиваем таймауты для работы через прокси
        from telegram.request import HTTPXRequest
        request_config = HTTPXRequest(connection_pool_size=10, read_timeout=60.0, write_timeout=60.0, connect_timeout=60.0, http_version="1.1")
        application = Application.builder().token(token).request(request_config).build()
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

    # Инициализация PollingWatchdog
    global polling_watchdog_instance
    try:
        logger.info("Инициализация PollingWatchdog...")
        watchdog = PollingWatchdog(
            max_silence_seconds=120,  # 2 минуты без getUpdates = проблема
            check_interval_seconds=30,  # Проверка каждые 30 секунд
            max_restart_attempts=3,  # Максимум 3 перезапуска
            restart_cooldown_hours=1  # За 1 час
        )
        polling_watchdog_instance = watchdog
        logger.info("PollingWatchdog готов к работе")
    except Exception as e:
        logger.error(f"Ошибка инициализации PollingWatchdog: {e}", exc_info=True)
        watchdog = None

    # --- Регистрация обработчиков ---
    logger.info("Регистрация обработчиков...")
    try:
        setup_handlers(application, auth_service, ai_service, appeals_service, promotions_gateway, profile_manager)
        logger.info("Обработчики успешно зарегистрированы")
    except Exception as e:
        logger.error(f"Ошибка регистрации обработчиков: {e}", exc_info=True)
        sys.exit(1)

    # --- Настройка мониторинга через post_init callback ---
    async def post_init(application: Application) -> None:
        """Инициализация мониторинга после запуска приложения."""
        
        # --- NEW: Proxy Monitor (CRITICAL) ---
        try:
            from monitors.proxy_monitor import ProxyMonitor
            proxy_monitor = ProxyMonitor(check_interval=300) # Проверка каждые 5 минут
            await proxy_monitor.start(application.bot)
            logger.info("ProxyMonitor service started")
        except Exception as e:
            logger.error(f"Failed to start ProxyMonitor: {e}")

        # Добавляем middleware для обновления Watchdog heartbeat
        if watchdog:
            async def watchdog_heartbeat_middleware(update, context):
                """Обновляет heartbeat Watchdog при каждом полученном update."""
                try:
                    watchdog.heartbeat()
                except Exception as e:
                    logger.error(f"Ошибка обновления watchdog heartbeat: {e}")
            
            # Регистрируем middleware с наивысшим приоритетом
            from telegram import Update
            from telegram.ext import TypeHandler
            application.add_handler(
                TypeHandler(Update, watchdog_heartbeat_middleware),
                group=-1  # Самый высокий приоритет - выполняется первым
            )
            logger.info("Watchdog heartbeat middleware зарегистрирован")
        
        # Инициализация активного AI backend в фоне
        if ai_service and ai_service.is_enabled():
            try:
                task_tracker.create_tracked_task(ai_service.initialize(), "ai_init")
                backend = ai_service.get_backend_name() if hasattr(ai_service, 'get_backend_name') else "unknown"
                logger.info(
                    "AI backend initialization triggered in background (%s)",
                    backend,
                )
            except Exception as e:
                logger.error(f"Failed to trigger AI backend initialization: {e}")

            # Периодическое обновление системного промпта из Google Docs
            prompt_refresh_hours = int(
                os.getenv("SYSTEM_PROMPT_REFRESH_HOURS", "168") or 168
            )
            prompt_refresh_seconds = prompt_refresh_hours * 3600

            async def periodic_prompt_refresh():
                """Автообновление системного промпта из Google Docs (по умолчанию раз в неделю)."""
                while True:
                    await asyncio.sleep(prompt_refresh_seconds)
                    try:
                        success = await ai_service.refresh_system_prompt(force=True)
                        if success:
                            logger.info(
                                "✅ Системный промпт автоматически обновлён из Google Docs"
                            )
                        else:
                            logger.warning(
                                "⚠️ Не удалось автообновить системный промпт"
                            )
                    except Exception as e:
                        logger.error(f"Ошибка автообновления промпта: {e}")

            task_tracker.create_tracked_task(
                periodic_prompt_refresh(), "prompt_auto_refresh"
            )
            logger.info(
                "Автообновление промпта запущено (каждые %d ч)", prompt_refresh_hours
            )
        
        # Фоновый heartbeat для Watchdog (чтобы не убивал бота когда нет сообщений)
        if watchdog:
            async def background_heartbeat():
                while True:
                    watchdog.heartbeat()
                    await asyncio.sleep(30)
            task_tracker.create_tracked_task(background_heartbeat(), "watchdog_heartbeat")
            logger.info("Watchdog background heartbeat task started")

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
                task_tracker.create_tracked_task(response_monitor.start_monitoring(interval_seconds=60), "response_monitor")
                logger.info("Мониторинг ответов запущен (проверка каждую минуту)")
            except Exception as e:
                logger.error(f"Ошибка запуска мониторинга ответов: {e}", exc_info=True)

        # Запуск мониторинг акций
        if promotions_notifier:
            logger.info("Запуск мониторинга новых акций...")
            try:
                task_tracker.create_tracked_task(promotions_notifier.start_monitoring(interval_minutes=15), "promotions_notifier")
                logger.info("Мониторинг акций запущен (проверка каждые 15 минут)")
            except Exception as e:
                logger.error(f"Ошибка запуска мониторинга акций: {e}", exc_info=True)


        # Запуск PollingWatchdog
        if watchdog:
            logger.info("Запуск PollingWatchdog...")
            try:
                # Устанавливаем callback для перезапуска polling
                async def restart_polling_callback():
                    """
                    Kill Switch: Принудительное завершение процесса при зависании polling.
                    
                    Когда event loop мертв или заблокирован, graceful restart невозможен.
                    Единственный способ - убить процесс и позволить Systemd перезапустить его.
                    
                    Используем os._exit(1) вместо sys.exit(), чтобы обойти cleanup-хуки,
                    которые могут зависнуть, если event loop уже мертв.
                    """
                    logger.critical(
                        "💀 WATCHDOG KILL SWITCH АКТИВИРОВАН! "
                        "Polling freeze detected (>120s without getUpdates). "
                        "Committing suicide via os._exit(1) to trigger Systemd restart."
                    )
                    # Небольшая пауза для записи лога
                    await asyncio.sleep(0.5)
                    # KILL SWITCH: Принудительное завершение процесса
                    os._exit(1)
                
                watchdog.set_restart_callback(restart_polling_callback)
                
                # Запускаем мониторинг в фоне
                task_tracker.create_tracked_task(watchdog.start_monitoring(), "watchdog_monitor")
                logger.info("PollingWatchdog запущен (проверка каждые 30 секунд)")
            except Exception as e:
                logger.error(f"Ошибка запуска PollingWatchdog: {e}", exc_info=True)
        
        # Мониторинг памяти (защита от memory leak)
        if PREVENTIVE_GUARDS_AVAILABLE:
            try:
                from preventive_guards import MemoryMonitor
                import psutil

                total_mb = psutil.virtual_memory().total / 1024 / 1024
                env_limit = int(os.getenv("MEMORY_MAX_MB", "0") or 0)
                default_limit = max(900, int(total_mb * 0.60))
                max_memory_mb = env_limit if env_limit > 0 else default_limit

                alert_cooldown = int(os.getenv("MEMORY_ALERT_COOLDOWN_SEC", "1800") or 1800)
                breach_required = int(os.getenv("MEMORY_BREACH_REQUIRED", "2") or 2)
                breach_window = int(os.getenv("MEMORY_BREACH_WINDOW_SEC", "1800") or 1800)
                restart_on_breach = os.getenv("MEMORY_RESTART_ON_BREACH", "true").lower() in ("1", "true", "yes", "y")

                memory_monitor = MemoryMonitor(max_memory_mb=max_memory_mb)
                last_alert_ts = 0.0
                breach_times = []

                async def check_memory_periodically():
                    """Периодическая проверка памяти с алертами и антиспамом."""
                    nonlocal last_alert_ts, breach_times
                    while True:
                        await asyncio.sleep(300)  # Каждые 5 минут
                        if not memory_monitor.check_memory():
                            now = time.time()
                            breach_times = [t for t in breach_times if (now - t) <= breach_window]
                            breach_times.append(now)

                            if (now - last_alert_ts) >= alert_cooldown:
                                server_name = socket.gethostname()
                                await alert_admin(
                                    application.bot,
                                    f"🖥 Сервер: {server_name}\nКритическое потребление памяти: {memory_monitor.get_memory_mb():.0f}MB!",
                                    "CRITICAL"
                                )
                                last_alert_ts = now

                            if restart_on_breach and len(breach_times) >= breach_required:
                                logger.critical(
                                    f"Memory limit exceeded on {socket.gethostname()}, "
                                    f"breaches: {len(breach_times)} in {breach_window}s. Restarting..."
                                )
                                os._exit(1)  # Systemd перезапустит

                task_tracker.create_tracked_task(check_memory_periodically(), "memory_monitor")
                logger.info(
                    "Memory monitor запущен "
                    f"(лимит: {memory_monitor.max_memory_mb}MB, cooldown: {alert_cooldown}s)"
                )
            except Exception as e:
                logger.error(f"Ошибка запуска Memory monitor: {e}")
        
        # Heartbeat алерты (подтверждение что бот жив)
        HEARTBEAT_INTERVAL = 3600 * 6  # Каждые 6 часов
        bot_start_time = time.time()
        
        async def heartbeat_alert():
            """Периодический алерт о работоспособности бота."""
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                uptime_hours = (time.time() - bot_start_time) / 3600
                try:
                    import psutil
                    process = psutil.Process()
                    memory_mb = process.memory_info().rss / 1024 / 1024
                    stats = f"Uptime: {uptime_hours:.1f}h, Memory: {memory_mb:.0f}MB"
                except Exception:
                    stats = f"Uptime: {uptime_hours:.1f}h"
                
                server_name = socket.gethostname()
                await alert_admin(application.bot, f"💓 Heartbeat ({server_name}): {stats}", "INFO")
        
        task_tracker.create_tracked_task(heartbeat_alert(), "heartbeat_alert")
        logger.info("Heartbeat алерты запущены (каждые 6 часов)")

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


        # Остановка PollingWatchdog
        if watchdog:
            try:
                await watchdog.stop_monitoring()
                logger.info("PollingWatchdog остановлен")
            except Exception as e:
                logger.error(f"Ошибка остановки PollingWatchdog: {e}")

        # Закрытие AI-клиента и других сетевых ресурсов
        if ai_service:
            try:
                await ai_service.close()
                logger.info("AIService resources closed")
            except Exception as e:
                logger.error(f"Ошибка закрытия AIService: {e}")

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
                               "Проверьте активные процессы и systemd сервисы. "
                               "АЛЕРТ НЕ ОТПРАВЛЕН ВО ИЗБЕЖАНИЕ СПАМА.")
                # НЕ отправляем алерт админу, чтобы не спамить при рестарте
                # Просто логируем и позволяем боту упасть, чтобы systemd его поднял (или не поднял)
                # При конфликте лучше упасть и подождать, чем спамить
                await asyncio.sleep(10) # Пауза перед падением
                sys.exit(1) # Принудительный выход для перезапуска сервиса
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
            # --- Режим запуска (Webhook или Polling) ---
            webhook_url = os.getenv("WEBHOOK_URL")
            webhook_port = int(os.getenv("WEBHOOK_PORT", "8001"))
            webhook_secret = os.getenv("WEBHOOK_SECRET")
            
            if webhook_url:
                logger.info(f"Запуск в режиме WEBHOOK на {webhook_url}:{webhook_port}")
                application.run_webhook(
                    listen="0.0.0.0",
                    port=webhook_port,
                    url_path=token,
                    webhook_url=None,
                    secret_token=webhook_secret,
                )
            else:
                logger.info("Запуск в режиме POLLING...")
                application.run_polling(
                    poll_interval=1.0,
                    timeout=30,
                    read_timeout=30,
                    write_timeout=20,
                    connect_timeout=10,
                    pool_timeout=10,
                    stop_signals=(signal.SIGINT, signal.SIGTERM),
                    allowed_updates=None,
                    drop_pending_updates=True,
                    close_loop=False
                )
            
            logger.info("Бот завершил работу нормально (run_polling/webhook returned)")
            break # Успешный выход из while-цикла при ручной остановке
            
        except (TelegramError, ConnectionError, TimeoutError, socket.error) as e:
            restart_count += 1
            wait_time = min(30, 5 * restart_count)
            logger.error(f"⚠️ Сетевая ошибка (попытка {restart_count}/{max_restart_attempts}): {e}")
            if restart_count < max_restart_attempts:
                logger.info(f"Ожидание {wait_time}с перед перезапуском...")
                time.sleep(wait_time)
            else:
                logger.critical("❌ Достигнут лимит попыток перезапуска при сетевых ошибках.")
                sys.exit(1)
                
        except Exception as e:
            logger.critical(f"Критическая неожиданная ошибка: {e}", exc_info=True)
            # Для неизвестных ошибок лучше упасть, чтобы systemd перезапустил весь процесс
            sys.exit(1)
        
        except KeyboardInterrupt:
            logger.info("Прерывание пользователем.")
            break
            
    logger.info("Бот завершил работу")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"Критическая ошибка в main(): {e}", exc_info=True)
        sys.exit(1)
