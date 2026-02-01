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
    Использует два уровня защиты:
    1. Lock-файл с PID для tracking процессов
    2. Socket-binding на локальный порт 60001 (гарантированная защита на уровне ОС)
    """
    
    def __init__(self, lockfile_path: str = "/tmp/marketingbot.lock", port: int = 60001):
        self.lockfile_path = Path(lockfile_path)
        self.port = port
        self.pid = os.getpid()
        self.socket = None
        
    def __enter__(self):
        """Активирует защиту при входе."""
        # 1. Socket Lock (самый надежный - ОС не даст открыть тот же порт)
        import socket
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # SO_REUSEADDR не используем специально, чтобы порт освобождался не мгновенно
            # и чтобы предотвратить race condition
            self.socket.bind(('127.0.0.1', self.port))
            self.socket.listen(1)
            logger.info(f"✅ Socket Lock активирован (Port: {self.port})")
        except socket.error as e:
            logger.critical(
                f"❌ КРИТИЧЕСКАЯ ОШИБКА: Порт {self.port} занят!\n"
                f"Это означает, что ДРУГОЙ ЭКЗЕМПЛЯР БОТА УЖЕ РАБОТАЕТ.\n"
                f"Невозможно запустить две копии одновременно.\n"
                f"Ошибка: {e}"
            )
            sys.exit(1)

        # 2. File Lock (для удобства человека - чтобы видеть PID)
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
                        if 'python' in proc.name().lower() and any(x in ' '.join(proc.cmdline()) for x in ['bot.py', 'main.py']):
                            logger.critical(
                                f"❌ КРИТИЧЕСКАЯ ОШИБКА: Lock-файл указывает на живой процесс (PID: {old_pid})\n"
                                f"Это приведет к 409 Conflict ошибкам!\n"
                                f"Остановите предыдущий экземпляр: kill {old_pid}"
                            )
                            sys.exit(1)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                
                # Старый процесс не существует, удаляем stale lock
                logger.warning(f"Удаляю stale lock-файл от процесса {old_pid}")
                self.lockfile_path.unlink()
                
            except (ValueError, IOError) as e:
                logger.warning(f"Ошибка чтения lock-файла: {e}, удаляю его")
                self.lockfile_path.unlink()

        # 3. Агрессивный поиск клонов по имени процесса (на случай, если они не создали lock)
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['pid'] == self.pid:
                    continue
                cmdline = ' '.join(proc.info['cmdline'] or [])
                # Ищем процессы, которые выглядят как наш бот
                if 'python' in proc.info['name'].lower() and 'bot.py' in cmdline:
                    logger.critical(
                        f"⚠️ ОБНАРУЖЕН КЛОН БОТА! PID: {proc.info['pid']}, CMD: {cmdline}\n"
                        f"Это приведет к конфликту API. Завершите этот процесс перез запуском нового."
                    )
                    # Мы не убиваем его сами (это опасно), но выходим с ошибкой
                    sys.exit(1)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        # Создаем новый lock-файл
        with open(self.lockfile_path, 'w') as f:
            f.write(str(self.pid))
        logger.info(f"✅ SingleInstanceGuard активирован (PID: {self.pid})")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Снимает защиту при выходе."""
        # 1. Удаляем lock-файл
        try:
            if self.lockfile_path.exists():
                with open(self.lockfile_path, 'r') as f:
                    current_pid = int(f.read().strip())
                
                # Удаляем только если это наш PID
                if current_pid == self.pid:
                    self.lockfile_path.unlink()
                    logger.info("✅ File Lock удален")
        except Exception as e:
            logger.error(f"Ошибка при удалении lock-файла: {e}")
            
        # 2. Закрываем сокет
        if self.socket:
            try:
                self.socket.close()
                logger.info("✅ Socket Lock освобожден")
            except Exception as e:
                logger.error(f"Ошибка при закрытии сокета: {e}")


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
    Валидация окружения перед запуском бота (наличие, формат, существование файлов).
    """
    import json

    errors = []

    # TELEGRAM_TOKEN
    token = os.getenv('TELEGRAM_TOKEN')
    if not token:
        errors.append("TELEGRAM_TOKEN не задан")
    elif ':' not in token or len(token.split(':')) != 2:
        errors.append("TELEGRAM_TOKEN имеет неверный формат (ожидается: '123456:ABC-DEF...')")

    # SHEET_ID
    sheet_id = os.getenv('SHEET_ID')
    if not sheet_id:
        errors.append("SHEET_ID не задан")
    elif len(sheet_id) < 10:
        errors.append("SHEET_ID имеет неверный формат (слишком короткий)")

    # APPEALS_SHEET_ID
    appeals_sheet_id = os.getenv('APPEALS_SHEET_ID')
    if not appeals_sheet_id:
        errors.append("APPEALS_SHEET_ID не задан")
    elif len(appeals_sheet_id) < 10:
        errors.append("APPEALS_SHEET_ID имеет неверный формат (слишком короткий)")

    # GCP_SA_FILE
    sa_file = os.getenv('GCP_SA_FILE')
    if not sa_file:
        errors.append("GCP_SA_FILE не задан")
    elif not Path(sa_file).exists():
        errors.append(f"GCP_SA_FILE не существует: {sa_file}")
    else:
        try:
            with Path(sa_file).open(encoding='utf-8') as f:
                json.load(f)
        except json.JSONDecodeError as e:
            errors.append(f"GCP_SA_FILE содержит невалидный JSON: {e}")

    if errors:
        logger.critical("❌ Ошибки конфигурации:\n" + "\n".join(f"  - {e}" for e in errors))
        return False

    logger.info("✅ Все переменные окружения настроены корректно")
    return True
