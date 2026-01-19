import logging
from config import settings
from handlers.auth import register_auth_handlers
from handlers.chat import register_chat_handlers
from handlers.appeals import register_appeals_handlers
from handlers.promotions import register_promotions_handlers
from handlers.callback import register_callback_handlers

logger = logging.getLogger(__name__)

def setup_handlers(application, auth_service, ai_service, appeals_service):
    """
    Централизованная регистрация всех обработчиков.
    Модули включаются/выключаются на основе config.settings.
    """
    logger.info("Инициализация обработчиков модулей...")

    # 1. Авторизация (Базовый модуль, всегда включен)
    register_auth_handlers(application, auth_service)

    # 2. Чат с ИИ
    if settings.ENABLE_AI_CHAT:
        register_chat_handlers(application, auth_service, ai_service, appeals_service)
        logger.info("Модуль AI Chat подключен")

    # 3. Обращения
    if settings.ENABLE_APPEALS:
        register_appeals_handlers(application, auth_service, appeals_service)
        logger.info("Модуль Appeals подключен")

    # 4. Акции
    if settings.ENABLE_PROMOTIONS:
        register_promotions_handlers(application, auth_service)
        logger.info("Модуль Promotions подключен")

    # 5. Callback-кнопки
    if settings.ENABLE_CALLBACKS:
        register_callback_handlers(application, auth_service, appeals_service)
        logger.info("Модуль Callbacks подключен")
