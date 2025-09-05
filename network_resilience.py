"""
Network Resilience Module
Реализует отказоустойчивое взаимодействие с внешними API используя библиотеку tenacity.
Соответствует техническому плану: Раздел 3.2
"""

import logging
import requests
from typing import Any, Callable, Optional, Tuple, Type
from functools import wraps

# Импортируем tenacity
try:
    from tenacity import (
        retry, 
        stop_after_attempt, 
        wait_exponential, 
        retry_if_exception_type,
        before_sleep_log,
        after_log
    )
    TENACITY_AVAILABLE = True
except ImportError:
    TENACITY_AVAILABLE = False
    logging.warning("Библиотека tenacity не установлена. Отказоустойчивость отключена.")

from config_manager import config_manager

logger = logging.getLogger(__name__)

# Определяем типы временных исключений, которые требуют повтора
TRANSIENT_NETWORK_EXCEPTIONS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
    requests.exceptions.HTTPError,  # Для HTTP 5xx ошибок
    ConnectionError,
    TimeoutError,
)

# Дополнительные исключения для Google Sheets API
GOOGLE_API_TRANSIENT_EXCEPTIONS = (
    Exception,  # Общие сетевые ошибки gspread
)

# Telegram API специфичные исключения
TELEGRAM_API_TRANSIENT_EXCEPTIONS = (
    Exception,  # Telegram API ошибки
)

class NetworkResilienceConfig:
    """
    Конфигурация для retry логики на основе настроек из config.ini.
    """
    
    def __init__(self):
        self.max_attempts = config_manager.get_max_retry_attempts()
        self.min_wait = config_manager.get_retry_min_wait()
        self.max_wait = config_manager.get_retry_max_wait()
        self.multiplier = config_manager.get_retry_multiplier()
        self.connection_timeout = config_manager.get_connection_timeout()
        self.read_timeout = config_manager.get_read_timeout()
    
    def get_retry_decorator(self, exception_types: Tuple[Type[Exception], ...], 
                          operation_name: str = "network_operation"):
        """
        Создает декоратор retry с настройками из конфигурации.
        
        Args:
            exception_types: Типы исключений для повтора
            operation_name: Название операции для логирования
            
        Returns:
            Декоратор retry или заглушка, если tenacity недоступна
        """
        if not TENACITY_AVAILABLE:
            # Возвращаем заглушку, если tenacity не установлена
            def dummy_decorator(func):
                @wraps(func)
                def wrapper(*args, **kwargs):
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        logger.error(f"Ошибка {operation_name} (без retry): {e}")
                        raise
                return wrapper
            return dummy_decorator
        
        return retry(
            stop=stop_after_attempt(self.max_attempts),
            wait=wait_exponential(
                multiplier=self.multiplier,
                min=self.min_wait,
                max=self.max_wait
            ),
            retry=retry_if_exception_type(exception_types),
            before_sleep=before_sleep_log(logger, logging.WARNING, exc_info=True),
            after=after_log(logger, logging.INFO)
        )

# Глобальная конфигурация сетевой отказоустойчивости
network_config = NetworkResilienceConfig()

def resilient_http_request(url: str, method: str = 'GET', **kwargs) -> requests.Response:
    """
    Выполняет HTTP запрос с автоматическим повтором при сбоях.
    
    Args:
        url: URL для запроса
        method: HTTP метод
        **kwargs: Дополнительные параметры для requests
        
    Returns:
        requests.Response: Ответ сервера
        
    Raises:
        requests.exceptions.RequestException: При невосстановимых ошибках
    """
    @network_config.get_retry_decorator(
        TRANSIENT_NETWORK_EXCEPTIONS, 
        f"HTTP {method} {url}"
    )
    def _make_request():
        # Устанавливаем таймауты из конфигурации
        timeout = kwargs.pop('timeout', (network_config.connection_timeout, network_config.read_timeout))
        
        logger.debug(f"Выполнение HTTP {method} запроса: {url}")
        
        response = requests.request(method, url, timeout=timeout, **kwargs)
        
        # Проверяем статус ответа
        if response.status_code >= 500:
            # HTTP 5xx ошибки - серверные, требуют повтора
            logger.warning(f"Серверная ошибка HTTP {response.status_code}: {url}")
            response.raise_for_status()
        elif response.status_code >= 400:
            # HTTP 4xx ошибки - клиентские, повтор бесполезен
            logger.error(f"Клиентская ошибка HTTP {response.status_code}: {url}")
            response.raise_for_status()
        
        logger.debug(f"HTTP запрос успешен: {response.status_code}")
        return response
    
    return _make_request()

def resilient_google_sheets_operation(operation_name: str):
    """
    Декоратор для операций Google Sheets с автоматическим повтором.
    
    Args:
        operation_name: Название операции для логирования
        
    Returns:
        Декоратор функции
    """
    def decorator(func: Callable) -> Callable:
        @network_config.get_retry_decorator(
            GOOGLE_API_TRANSIENT_EXCEPTIONS,
            f"Google Sheets {operation_name}"
        )
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger.debug(f"Выполнение операции Google Sheets: {operation_name}")
            try:
                result = func(*args, **kwargs)
                logger.debug(f"Операция Google Sheets успешна: {operation_name}")
                return result
            except Exception as e:
                logger.warning(f"Ошибка Google Sheets операции {operation_name}: {e}")
                raise
        return wrapper
    return decorator

def resilient_telegram_api_operation(operation_name: str):
    """
    Декоратор для операций Telegram API с автоматическим повтором.
    
    Args:
        operation_name: Название операции для логирования
        
    Returns:
        Декоратор функции
    """
    def decorator(func: Callable) -> Callable:
        @network_config.get_retry_decorator(
            TELEGRAM_API_TRANSIENT_EXCEPTIONS,
            f"Telegram API {operation_name}"
        )
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger.debug(f"Выполнение операции Telegram API: {operation_name}")
            try:
                result = func(*args, **kwargs)
                logger.debug(f"Операция Telegram API успешна: {operation_name}")
                return result
            except Exception as e:
                logger.warning(f"Ошибка Telegram API операции {operation_name}: {e}")
                raise
        return wrapper
    return decorator

async def resilient_async_operation(operation: Callable, operation_name: str, 
                                  exception_types: Optional[Tuple[Type[Exception], ...]] = None) -> Any:
    """
    Выполняет асинхронную операцию с повторными попытками.
    
    Args:
        operation: Асинхронная функция для выполнения
        operation_name: Название операции для логирования
        exception_types: Типы исключений для повтора
        
    Returns:
        Результат операции
    """
    if exception_types is None:
        exception_types = TRANSIENT_NETWORK_EXCEPTIONS
    
    if not TENACITY_AVAILABLE:
        # Простая попытка без retry, если tenacity недоступна
        try:
            return await operation()
        except Exception as e:
            logger.error(f"Ошибка {operation_name} (без retry): {e}")
            raise
    
    # Создаем retry декоратор для async функции
    @network_config.get_retry_decorator(exception_types, operation_name)
    async def _execute_operation():
        return await operation()
    
    return await _execute_operation()

def test_network_resilience():
    """
    Тестирует работу модуля сетевой отказоустойчивости.
    """
    logger.info("🧪 Тестирование сетевой отказоустойчивости...")
    
    # Тест 1: HTTP запрос
    try:
        response = resilient_http_request('https://httpbin.org/status/200')
        logger.info(f"✅ HTTP тест успешен: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ HTTP тест неудачен: {e}")
    
    # Тест 2: Декоратор Google Sheets
    @resilient_google_sheets_operation("test_operation")
    def test_sheets_operation():
        logger.info("Тестовая операция Google Sheets")
        return "success"
    
    try:
        result = test_sheets_operation()
        logger.info(f"✅ Google Sheets тест успешен: {result}")
    except Exception as e:
        logger.error(f"❌ Google Sheets тест неудачен: {e}")
    
    # Тест 3: Конфигурация
    logger.info("📊 Конфигурация retry:")
    logger.info(f"   Максимум попыток: {network_config.max_attempts}")
    logger.info(f"   Минимальная задержка: {network_config.min_wait}с")
    logger.info(f"   Максимальная задержка: {network_config.max_wait}с")
    logger.info(f"   Множитель: {network_config.multiplier}")
    
    logger.info("🧪 Тестирование завершено")

if __name__ == "__main__":
    # Настройка логирования для тестирования
    logging.basicConfig(level=logging.INFO)
    test_network_resilience()