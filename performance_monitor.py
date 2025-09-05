"""
Модуль мониторинга производительности
Отслеживает метрики работы бота и предоставляет статистику
"""

import time
import threading
from collections import defaultdict, deque
from typing import Dict, Any
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """Метрики производительности"""
    
    # Счетчики операций
    total_requests: int = 0
    successful_operations: int = 0
    failed_operations: int = 0
    
    # Время выполнения операций (последние 100)
    execution_times: deque = field(default_factory=lambda: deque(maxlen=100))
    
    # Статистика по типам операций
    operation_stats: Dict[str, Dict[str, int]] = field(default_factory=lambda: defaultdict(lambda: {'count': 0, 'errors': 0}))
    
    # Google Sheets метрики
    sheets_requests: int = 0
    sheets_errors: int = 0
    
    # OpenAI метрики
    openai_requests: int = 0
    openai_errors: int = 0
    openai_tokens_used: int = 0
    
    # Telegram метрики
    telegram_messages_sent: int = 0
    telegram_errors: int = 0
    
    # Авторизация
    auth_attempts: int = 0
    auth_successes: int = 0
    auth_failures: int = 0
    
    # Время запуска
    start_time: float = field(default_factory=time.time)

class PerformanceMonitor:
    """Монитор производительности"""
    
    def __init__(self):
        self.metrics = PerformanceMetrics()
        self._lock = threading.RLock()
    
    def record_operation(self, operation_type: str, execution_time: float, success: bool = True):
        """Записывает метрики операции"""
        with self._lock:
            self.metrics.total_requests += 1
            self.metrics.execution_times.append(execution_time)
            
            if success:
                self.metrics.successful_operations += 1
            else:
                self.metrics.failed_operations += 1
                self.metrics.operation_stats[operation_type]['errors'] += 1
            
            self.metrics.operation_stats[operation_type]['count'] += 1
    
    def record_sheets_operation(self, success: bool = True):
        """Записывает метрики Google Sheets"""
        with self._lock:
            self.metrics.sheets_requests += 1
            if not success:
                self.metrics.sheets_errors += 1
    
    def record_openai_operation(self, success: bool = True, tokens_used: int = 0):
        """Записывает метрики OpenAI"""
        with self._lock:
            self.metrics.openai_requests += 1
            self.metrics.openai_tokens_used += tokens_used
            if not success:
                self.metrics.openai_errors += 1
    
    def record_telegram_operation(self, success: bool = True):
        """Записывает метрики Telegram"""
        with self._lock:
            self.metrics.telegram_messages_sent += 1
            if not success:
                self.metrics.telegram_errors += 1
    
    def record_auth_attempt(self, success: bool):
        """Записывает попытку авторизации"""
        with self._lock:
            self.metrics.auth_attempts += 1
            if success:
                self.metrics.auth_successes += 1
            else:
                self.metrics.auth_failures += 1
    
    def get_average_response_time(self) -> float:
        """Получает среднее время ответа"""
        with self._lock:
            if not self.metrics.execution_times:
                return 0.0
            return sum(self.metrics.execution_times) / len(self.metrics.execution_times)
    
    def get_success_rate(self) -> float:
        """Получает процент успешных операций"""
        with self._lock:
            if self.metrics.total_requests == 0:
                return 0.0
            return (self.metrics.successful_operations / self.metrics.total_requests) * 100
    
    def get_uptime(self) -> float:
        """Получает время работы в секундах"""
        return time.time() - self.metrics.start_time
    
    def get_detailed_stats(self) -> Dict[str, Any]:
        """Получает детальную статистику"""
        with self._lock:
            uptime = self.get_uptime()
            
            stats = {
                'uptime_seconds': uptime,
                'uptime_formatted': self._format_uptime(uptime),
                'total_requests': self.metrics.total_requests,
                'requests_per_minute': (self.metrics.total_requests / uptime * 60) if uptime > 0 else 0,
                'success_rate': self.get_success_rate(),
                'average_response_time': self.get_average_response_time(),
                
                'google_sheets': {
                    'requests': self.metrics.sheets_requests,
                    'errors': self.metrics.sheets_errors,
                    'error_rate': (self.metrics.sheets_errors / max(1, self.metrics.sheets_requests)) * 100
                },
                
                'openai': {
                    'requests': self.metrics.openai_requests,
                    'errors': self.metrics.openai_errors,
                    'tokens_used': self.metrics.openai_tokens_used,
                    'error_rate': (self.metrics.openai_errors / max(1, self.metrics.openai_requests)) * 100
                },
                
                'telegram': {
                    'messages_sent': self.metrics.telegram_messages_sent,
                    'errors': self.metrics.telegram_errors,
                    'error_rate': (self.metrics.telegram_errors / max(1, self.metrics.telegram_messages_sent)) * 100
                },
                
                'authorization': {
                    'attempts': self.metrics.auth_attempts,
                    'successes': self.metrics.auth_successes,
                    'failures': self.metrics.auth_failures,
                    'success_rate': (self.metrics.auth_successes / max(1, self.metrics.auth_attempts)) * 100
                },
                
                'operations': dict(self.metrics.operation_stats)
            }
            
            return stats
    
    def _format_uptime(self, seconds: float) -> str:
        """Форматирует время работы"""
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if days > 0:
            return f"{days}д {hours}ч {minutes}м {secs}с"
        elif hours > 0:
            return f"{hours}ч {minutes}м {secs}с"
        elif minutes > 0:
            return f"{minutes}м {secs}с"
        else:
            return f"{secs}с"
    
    def reset_metrics(self):
        """Сбрасывает все метрики"""
        with self._lock:
            self.metrics = PerformanceMetrics()
            logger.info("Метрики производительности сброшены")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Получает статус здоровья системы"""
        stats = self.get_detailed_stats()
        
        health = {
            'status': 'healthy',
            'issues': []
        }
        
        # Проверяем критические метрики
        if stats['success_rate'] < 90:
            health['status'] = 'degraded'
            health['issues'].append(f"Низкий процент успешных операций: {stats['success_rate']:.1f}%")
        
        if stats['google_sheets']['error_rate'] > 10:
            health['status'] = 'degraded'
            health['issues'].append(f"Высокий процент ошибок Google Sheets: {stats['google_sheets']['error_rate']:.1f}%")
        
        if stats['openai']['error_rate'] > 20:
            health['status'] = 'degraded'
            health['issues'].append(f"Высокий процент ошибок OpenAI: {stats['openai']['error_rate']:.1f}%")
        
        if stats['average_response_time'] > 10:
            health['status'] = 'degraded'
            health['issues'].append(f"Медленное время ответа: {stats['average_response_time']:.2f}с")
        
        if len(health['issues']) > 3:
            health['status'] = 'unhealthy'
        
        return health

# Декоратор для автоматического мониторинга
def monitor_performance(operation_type: str):
    """Декоратор для мониторинга производительности функций"""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise e
            finally:
                execution_time = time.time() - start_time
                performance_monitor.record_operation(operation_type, execution_time, success)
        
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise e
            finally:
                execution_time = time.time() - start_time
                performance_monitor.record_operation(operation_type, execution_time, success)
        
        import asyncio
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator

# Глобальный экземпляр монитора
performance_monitor = PerformanceMonitor()