"""
Polling Watchdog - мониторинг активности Telegram polling.

Этот модуль отслеживает, когда последний раз бот получал обновления от Telegram API.
Если polling молчит более N секунд, watchdog логирует критическую ошибку и может
инициировать перезапуск polling.
"""

import logging
import time
import asyncio
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class PollingWatchdog:
    """
    Сторожевой таймер для мониторинга активности Telegram polling.
    
    Отслеживает timestamp последнего getUpdates и проверяет, не остановился ли polling.
    При обнаружении остановки может автоматически перезапустить его.
    """
    
    def __init__(
        self,
        max_silence_seconds: int = 120,
        check_interval_seconds: int = 30,
        max_restart_attempts: int = 3,
        restart_cooldown_hours: int = 1
    ):
        """
        Инициализация Polling Watchdog.
        
        Args:
            max_silence_seconds: Максимальная длительность молчания (без getUpdates) в секундах
            check_interval_seconds: Интервал проверки активности в секундах
            max_restart_attempts: Максимальное количество попыток перезапуска в течение cooldown периода
            restart_cooldown_hours: Период cooldown для подсчета перезапусков (в часах)
        """
        self.max_silence_seconds = max_silence_seconds
        self.check_interval_seconds = check_interval_seconds
        self.max_restart_attempts = max_restart_attempts
        self.restart_cooldown_hours = restart_cooldown_hours
        
        self.last_update_time = time.time()  # Timestamp последнего getUpdates
        self.restart_callback: Optional[Callable] = None  # Callback для перезапуска polling
        self.monitoring_task: Optional[asyncio.Task] = None  # Task мониторинга
        self.is_monitoring = False  # Флаг активного мониторинга
        
        # Tracking перезапусков для предотвращения restart loop
        self.restart_history = []  # List of restart timestamps
        
        logger.info(
            f"PollingWatchdog инициализирован: "
            f"max_silence={max_silence_seconds}s, "
            f"check_interval={check_interval_seconds}s, "
            f"max_restarts={max_restart_attempts}/{restart_cooldown_hours}h"
        )
    
    def heartbeat(self):
        """
        Обновляет timestamp последней активности polling.
        
        Этот метод должен вызываться каждый раз, когда бот получает обновление от Telegram.
        """
        self.last_update_time = time.time()
    
    def set_restart_callback(self, callback: Callable):
        """
        Устанавливает callback функцию для перезапуска polling.
        
        Args:
            callback: Асинхронная функция для перезапуска polling
        """
        self.restart_callback = callback
        logger.info("Callback для перезапуска polling установлен")
    
    def _should_allow_restart(self) -> bool:
        """
        Проверяет, разрешен ли перезапуск на основе истории перезапусков.
        
        Предотвращает restart loop: не более max_restart_attempts за restart_cooldown период.
        
        Returns:
            bool: True если перезапуск разрешен, False если достигнут лимит
        """
        current_time = time.time()
        cooldown_seconds = self.restart_cooldown_hours * 3600
        
        # Очищаем старые записи из истории (старше cooldown периода)
        self.restart_history = [
            timestamp for timestamp in self.restart_history
            if current_time - timestamp < cooldown_seconds
        ]
        
        # Проверяем лимит перезапусков
        if len(self.restart_history) >= self.max_restart_attempts:
            logger.error(
                f"🚫 Достигнут лимит перезапусков: "
                f"{len(self.restart_history)}/{self.max_restart_attempts} "
                f"за последние {self.restart_cooldown_hours}h. Перезапуск запрещен."
            )
            return False
        
        return True
    
    async def _check_polling_health(self):
        """
        Проверяет здоровье polling и принимает меры при обнаружении проблем.
        """
        current_time = time.time()
        silence_duration = current_time - self.last_update_time
        
        if silence_duration > self.max_silence_seconds:
            logger.critical(
                f"⚠️ POLLING МЕРТВ! Нет активности {silence_duration:.0f} секунд "
                f"(лимит: {self.max_silence_seconds}s)"
            )
            
            # Проверяем, можем ли мы перезапустить
            if not self._should_allow_restart():
                logger.critical(
                    "Автоматический перезапуск заблокирован из-за превышения лимита. "
                    "Требуется ручное вмешательство."
                )
                return
            
            # Пытаемся перезапустить polling
            if self.restart_callback:
                try:
                    logger.warning("🔄 Инициирован автоматический перезапуск polling...")
                    
                    # Записываем timestamp перезапуска
                    self.restart_history.append(current_time)
                    
                    # Вызываем callback для перезапуска
                    await self.restart_callback()
                    
                    # Обновляем last_update_time после перезапуска
                    self.last_update_time = time.time()
                    
                    logger.info("✅ Polling успешно перезапущен watchdog'ом")
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка при автоматическом перезапуске polling: {e}", exc_info=True)
            else:
                logger.error(
                    "Callback для перезапуска не установлен. "
                    "Polling мертв, но автоматический перезапуск невозможен."
                )
        elif silence_duration > self.max_silence_seconds * 0.5:
            # Warning при достижении 50% от лимита
            logger.warning(
                f"⚠️ Polling молчит {silence_duration:.0f}s "
                f"({silence_duration / self.max_silence_seconds * 100:.0f}% от лимита)"
            )
    
    async def start_monitoring(self):
        """
        Запускает мониторинг polling в фоновом режиме.
        """
        if self.is_monitoring:
            logger.warning("PollingWatchdog уже запущен")
            return
        
        self.is_monitoring = True
        logger.info(f"🐕 PollingWatchdog запущен (проверка каждые {self.check_interval_seconds}s)")
        
        while self.is_monitoring:
            try:
                await self._check_polling_health()
            except Exception as e:
                logger.error(f"Ошибка в PollingWatchdog._check_polling_health: {e}", exc_info=True)
            
            # Ждем до следующей проверки
            await asyncio.sleep(self.check_interval_seconds)
        
        logger.info("PollingWatchdog остановлен")
    
    async def stop_monitoring(self):
        """
        Останавливает мониторинг polling.
        """
        logger.info("Остановка PollingWatchdog...")
        self.is_monitoring = False
        
        if self.monitoring_task and not self.monitoring_task.done():
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("PollingWatchdog остановлен")
    
    def get_status(self) -> dict:
        """
        Возвращает текущий статус watchdog.
        
        Returns:
            dict: Статус с информацией о последней активности и перезапусках
        """
        current_time = time.time()
        silence_duration = current_time - self.last_update_time
        
        return {
            "is_monitoring": self.is_monitoring,
            "last_update_time": self.last_update_time,
            "silence_duration_seconds": silence_duration,
            "max_silence_seconds": self.max_silence_seconds,
            "is_healthy": silence_duration < self.max_silence_seconds,
            "restart_count_recent": len(self.restart_history),
            "restart_limit": self.max_restart_attempts,
            "can_restart": self._should_allow_restart()
        }
