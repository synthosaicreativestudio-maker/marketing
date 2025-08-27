"""
Модуль для централизованной обработки ошибок
Обеспечивает единообразную обработку исключений во всем проекте
"""

import logging
import traceback
from typing import Optional, Callable, Any
from functools import wraps

logger = logging.getLogger(__name__)

class ErrorHandler:
    """Централизованный обработчик ошибок"""
    
    @staticmethod
    def log_error(error: Exception, context: str = "", user_id: Optional[int] = None):
        """Логирует ошибку с контекстом"""
        error_msg = f"Error in {context}: {str(error)}"
        if user_id:
            error_msg = f"User {user_id} - {error_msg}"
        
        logger.error(error_msg)
        logger.debug(f"Full traceback: {traceback.format_exc()}")
    
    @staticmethod
    def handle_sheets_error(error: Exception, operation: str) -> bool:
        """Обрабатывает ошибки Google Sheets"""
        ErrorHandler.log_error(error, f"Google Sheets {operation}")
        
        # Определяем тип ошибки и возвращаем успешность операции
        if "Service Unavailable" in str(error):
            logger.warning("Google Sheets временно недоступен")
            return False
        elif "Permission" in str(error):
            logger.error("Недостаточно прав для доступа к Google Sheets")
            return False
        elif "Quota" in str(error):
            logger.warning("Превышен лимит запросов к Google Sheets")
            return False
        
        return False
    
    @staticmethod
    def handle_telegram_error(error: Exception, operation: str, user_id: Optional[int] = None) -> bool:
        """Обрабатывает ошибки Telegram API"""
        ErrorHandler.log_error(error, f"Telegram {operation}", user_id)
        
        error_str = str(error).lower()
        if "blocked" in error_str:
            logger.info(f"User {user_id} blocked the bot")
            return False
        elif "chat not found" in error_str:
            logger.warning(f"Chat not found for user {user_id}")
            return False
        elif "flood" in error_str:
            logger.warning("Telegram rate limit exceeded")
            return False
        
        return False
    
    @staticmethod
    def handle_openai_error(error: Exception, operation: str) -> Optional[str]:
        """Обрабатывает ошибки OpenAI API"""
        ErrorHandler.log_error(error, f"OpenAI {operation}")
        
        error_str = str(error).lower()
        if "rate limit" in error_str:
            return "Превышен лимит запросов к AI. Попробуйте позже."
        elif "insufficient" in error_str or "quota" in error_str:
            return "Недостаточно средств на счете AI. Обратитесь к администратору."
        elif "invalid" in error_str:
            return "Неверные параметры запроса к AI."
        
        return "Ошибка AI сервиса. Попробуйте позже."

def safe_execute(context_name: str = ""):
    """Декоратор для безопасного выполнения функций с обработкой ошибок"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                ErrorHandler.log_error(e, context_name or func.__name__)
                return None
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                ErrorHandler.log_error(e, context_name or func.__name__)
                return None
        
        return async_wrapper if hasattr(func, '__code__') and func.__code__.co_flags & 0x80 else sync_wrapper
    
    return decorator

def validate_config():
    """Валидирует конфигурацию проекта"""
    import os
    errors = []
    
    # Проверяем обязательные переменные окружения
    required_vars = ['TELEGRAM_TOKEN', 'SHEET_URL', 'TICKETS_SHEET_URL']
    for var in required_vars:
        if not os.getenv(var):
            errors.append(f"Отсутствует переменная окружения: {var}")
    
    # Проверяем файлы
    required_files = ['credentials.json']
    for file in required_files:
        if not os.path.exists(file):
            errors.append(f"Отсутствует файл: {file}")
    
    if errors:
        logger.error("Ошибки конфигурации:")
        for error in errors:
            logger.error(f"  - {error}")
        return False
    
    logger.info("Конфигурация валидна")
    return True