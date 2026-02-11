"""
Утилиты для работы с Google Sheets с поддержкой Circuit Breaker паттерна.
"""
import logging
import time
from enum import Enum
from typing import Callable, Any, Optional

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Состояния Circuit Breaker"""
    CLOSED = "closed"  # Нормальная работа, запросы проходят
    OPEN = "open"  # Сервис недоступен, запросы блокируются
    HALF_OPEN = "half_open"  # Тестовый режим, пробуем один запрос


class CircuitBreaker:
    """
    Реализация Circuit Breaker паттерна для защиты от каскадных ошибок.
    
    Circuit Breaker автоматически блокирует запросы к проблемному сервису
    при превышении порога ошибок и восстанавливает работу после таймаута.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception
    ):
        """
        Инициализация Circuit Breaker.
        
        Args:
            failure_threshold: количество последовательных ошибок для открытия circuit
            recovery_timeout: время в секундах до попытки восстановления (half-open)
            expected_exception: тип исключения, которое считается ошибкой
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = CircuitState.CLOSED
        
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Выполняет функцию через Circuit Breaker.
        
        Args:
            func: функция для выполнения
            *args: позиционные аргументы
            **kwargs: именованные аргументы
            
        Returns:
            Результат выполнения функции
            
        Raises:
            CircuitBreakerOpenError: если circuit открыт
            Exception: исключение из функции
        """
        # Проверяем состояние circuit
        if self.state == CircuitState.OPEN:
            # Проверяем, прошло ли достаточно времени для попытки восстановления
            if self.last_failure_time and (time.time() - self.last_failure_time) >= self.recovery_timeout:
                logger.info("Circuit Breaker переходит в состояние HALF_OPEN для тестового запроса")
                self.state = CircuitState.HALF_OPEN
                self.failure_count = 0
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit Breaker открыт. Последняя ошибка: {self.last_failure_time}"
                )
        
        # Выполняем функцию
        try:
            result = func(*args, **kwargs)
            # Успешное выполнение - сбрасываем счетчик ошибок
            if self.state == CircuitState.HALF_OPEN:
                logger.info("Тестовый запрос успешен, Circuit Breaker закрывается")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
            elif self.state == CircuitState.CLOSED:
                # Сбрасываем счетчик при успехе в закрытом состоянии
                self.failure_count = 0
            return result
            
        except self.expected_exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            logger.warning(
                f"Ошибка в Circuit Breaker (попытка {self.failure_count}/{self.failure_threshold}): {e}"
            )
            
            # Проверяем, нужно ли открыть circuit
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.error(
                    f"Circuit Breaker открыт после {self.failure_count} последовательных ошибок. "
                    f"Запросы будут заблокированы на {self.recovery_timeout} секунд."
                )
            
            # Пробрасываем исключение дальше
            raise
    
    def reset(self):
        """Сбрасывает состояние Circuit Breaker в начальное состояние."""
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        logger.info("Circuit Breaker сброшен в состояние CLOSED")
    
    def get_state(self) -> CircuitState:
        """Возвращает текущее состояние Circuit Breaker."""
        return self.state


class CircuitBreakerOpenError(Exception):
    """Исключение, выбрасываемое когда Circuit Breaker открыт."""
    pass


# Глобальные экземпляры Circuit Breaker для разных сервисов
_promotions_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60,
    expected_exception=Exception
)

_appeals_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60,
    expected_exception=Exception
)

_auth_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60,
    expected_exception=Exception
)


def get_promotions_circuit_breaker() -> CircuitBreaker:
    """Возвращает Circuit Breaker для сервиса акций."""
    return _promotions_circuit_breaker


def get_appeals_circuit_breaker() -> CircuitBreaker:
    """Возвращает Circuit Breaker для сервиса обращений."""
    return _appeals_circuit_breaker


def get_auth_circuit_breaker() -> CircuitBreaker:
    """Возвращает Circuit Breaker для сервиса авторизации."""
    return _auth_circuit_breaker


_analytics_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60,
    expected_exception=Exception
)


def get_analytics_circuit_breaker() -> CircuitBreaker:
    """Возвращает Circuit Breaker для сервиса аналитики."""
    return _analytics_circuit_breaker
