"""
Превентивные механизмы для предотвращения типичных проблем бота.
"""
import os
import sys
import psutil
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class SingleInstanceGuard:
    """
    Механизм защиты от запуска нескольких экземпляров бота.
    Предотвращает 409 Conflict ошибки.
    """
    
    def __init__(self, lockfile_path: str = "/tmp/marketingbot.lock"):
        self.lockfile_path = Path(lockfile_path)
        self.pid = os.getpid()
        
    def __enter__(self):
        """Проверяет и создает lock-файл при входе."""
        if self.lockfile_path.exists():
            # Проверяем, жив ли процесс из lock-файла
            try:
                with open(self.lockfile_path, 'r') as f:
                    old_pid = int(f.read().strip())
                
                # Проверяем, существует ли процесс
                if psutil.pid_exists(old_pid):
                    try:
                        proc = psutil.Process(old_pid)
                        # Проверяем, что это действительно наш бот
                        if 'python' in proc.name().lower() and 'bot.py' in ' '.join(proc.cmdline()):
                            logger.critical(
                                f"❌ КРИТИЧЕСКАЯ ОШИБКА: Бот уже запущен (PID: {old_pid})\n"
                                f"Это приведет к 409 Conflict ошибкам!\n"
                                f"Остановите предыдущий экземпляр: kill {old_pid}"
                            )
                            sys.exit(1)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        # Процесс не существует или нет доступа - можно продолжать
                        pass
                
                # Старый процесс не существует, удаляем stale lock
                logger.warning(f"Удаляю stale lock-файл от процесса {old_pid}")
                self.lockfile_path.unlink()
                
            except (ValueError, IOError) as e:
                logger.warning(f"Ошибка чтения lock-файла: {e}, удаляю его")
                self.lockfile_path.unlink()
        
        # Создаем новый lock-файл
        with open(self.lockfile_path, 'w') as f:
            f.write(str(self.pid))
        logger.info(f"✅ SingleInstanceGuard активирован (PID: {self.pid})")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Удаляет lock-файл при выходе."""
        try:
            if self.lockfile_path.exists():
                with open(self.lockfile_path, 'r') as f:
                    current_pid = int(f.read().strip())
                
                # Удаляем только если это наш PID
                if current_pid == self.pid:
                    self.lockfile_path.unlink()
                    logger.info("✅ SingleInstanceGuard деактивирован")
        except Exception as e:
            logger.error(f"Ошибка при удалении lock-файла: {e}")


class MemoryMonitor:
    """
    Мониторинг потребления памяти и автоматический restart при утечке.
    Предотвращает неконтролируемый рост памяти.
    """
    
    def __init__(self, 
                 max_memory_mb: int = 200,
                 check_interval_seconds: int = 300):
        """
        Args:
            max_memory_mb: Максимальный размер памяти в МБ
            check_interval_seconds: Интервал проверки в секундах
        """
        self.max_memory_mb = max_memory_mb
        self.check_interval = check_interval_seconds
        self.process = psutil.Process()
        self.initial_memory = self.get_memory_mb()
        
    def get_memory_mb(self) -> float:
        """Возвращает текущее потребление памяти в МБ."""
        return self.process.memory_info().rss / 1024 / 1024
    
    def check_memory(self) -> bool:
        """
        Проверяет потребление памяти.
        
        Returns:
            True если память в норме, False если превышен лимит
        """
        current_memory = self.get_memory_mb()
        
        if current_memory > self.max_memory_mb:
            logger.critical(
                f"❌ УТЕЧКА ПАМЯТИ ОБНАРУЖЕНА!\n"
                f"Текущее потребление: {current_memory:.1f}MB\n"
                f"Максимум: {self.max_memory_mb}MB\n"
                f"Требуется перезапуск бота!"
            )
            return False
        
        # Логируем каждые 100MB роста
        if current_memory - self.initial_memory > 100:
            logger.warning(
                f"⚠️  Память выросла на {current_memory - self.initial_memory:.1f}MB "
                f"(сейчас: {current_memory:.1f}MB)"
            )
            
        return True


class CoroutineValidator:
    """
    Валидатор для отслеживания unawaited coroutines.
    Предотвращает RuntimeWarning и блокировки Event Loop.
    """
    
    @staticmethod
    def enable_warnings():
        """Включает строгий режим для coroutines."""
        import warnings
        import asyncio
        
        # Делаем RuntimeWarning для unawaited coroutines более заметными
        warnings.filterwarnings('error', category=RuntimeWarning, 
                              message='.*coroutine.*was never awaited')
        
        # Включаем debug mode для asyncio
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.set_debug(True)
        
        logger.info("✅ Строгий режим для coroutines активирован")


class CircuitBreakerMonitor:
    """
    Мониторинг Circuit Breaker для предотвращения каскадных ошибок.
    """
    
    def __init__(self, max_failures: int = 5, timeout: int = 60):
        self.max_failures = max_failures
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = 0
        
    def record_failure(self, service_name: str):
        """Записывает ошибку сервиса."""
        import time
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.max_failures:
            logger.error(
                f"⚠️  Circuit Breaker OPEN для {service_name}!\n"
                f"Количество ошибок: {self.failure_count}\n"
                f"Сервис временно недоступен на {self.timeout} секунд"
            )
    
    def record_success(self):
        """Сбрасывает счетчик при успехе."""
        self.failure_count = 0


def validate_environment() -> bool:
    """
    Валидация окружения перед запуском бота.
    Предотвращает запуск с некорректной конфигурацией.
    """
    required_vars = [
        'TELEGRAM_TOKEN',
        'SHEET_ID',
        'APPEALS_SHEET_ID',
        'GCP_SA_FILE'
    ]
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    if missing:
        logger.critical(
            "❌ КРИТИЧЕСКАЯ ОШИБКА: Отсутствуют переменные окружения:\n" +
            "\n".join(f"  - {var}" for var in missing) +
            "\n\nПроверьте файл .env!"
        )
        return False
    
    logger.info("✅ Все переменные окружения настроены корректно")
    return True
