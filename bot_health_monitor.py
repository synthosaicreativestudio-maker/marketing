"""
Модуль для мониторинга здоровья бота и автоматического восстановления.
"""
import logging
import asyncio
import time
from typing import Optional
from telegram import Bot
from telegram.error import TelegramError, NetworkError, TimedOut

logger = logging.getLogger(__name__)


class BotHealthMonitor:
    """Мониторинг здоровья бота и автоматическое восстановление."""
    
    def __init__(
        self, 
        bot: Bot, 
        check_interval: int = 300,
        sheets_gateway=None,
        auth_service=None
    ):
        """
        Инициализация монитора здоровья.
        
        Args:
            bot: Экземпляр Telegram бота
            check_interval: Интервал проверки здоровья в секундах (по умолчанию 5 минут)
            sheets_gateway: Gateway для Google Sheets (опционально)
            auth_service: AuthService для переподключения (опционально)
        """
        self.bot = bot
        self.check_interval = check_interval
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self.last_successful_check = time.time()
        self.consecutive_failures = 0
        self.max_failures = 3
        
        # Для мониторинга Google Sheets
        self.sheets_gateway = sheets_gateway
        self.auth_service = auth_service
        self.sheets_consecutive_failures = 0
        self.last_sheets_reconnect = time.time()
        
    async def start_monitoring(self):
        """Запускает мониторинг здоровья."""
        if self.is_running:
            logger.warning("Мониторинг здоровья уже запущен")
            return
            
        self.is_running = True
        logger.info(f"Запуск мониторинга здоровья бота (проверка каждые {self.check_interval} сек)")
        self._task = asyncio.create_task(self._monitoring_loop())
        
    async def stop_monitoring(self):
        """Останавливает мониторинг здоровья."""
        if not self.is_running:
            return
            
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Мониторинг здоровья остановлен")
        
    async def _monitoring_loop(self):
        """Основной цикл мониторинга."""
        while self.is_running:
            try:
                # Проверяем здоровье бота через getMe
                is_healthy = await self._check_bot_health()
                
                if is_healthy:
                    self.last_successful_check = time.time()
                    self.consecutive_failures = 0
                    logger.debug("Проверка здоровья бота: OK")
                else:
                    self.consecutive_failures += 1
                    logger.warning(
                        f"Проверка здоровья бота: FAILED "
                        f"(подряд ошибок: {self.consecutive_failures}/{self.max_failures})"
                    )
                    
                    if self.consecutive_failures >= self.max_failures:
                        logger.error(
                            f"КРИТИЧЕСКОЕ: Бот не отвечает после {self.max_failures} попыток. "
                            f"Последняя успешная проверка: {time.time() - self.last_successful_check:.0f} сек назад"
                        )
                
                # Проверяем Google Sheets (если настроено)
                if self.auth_service:
                    await self._check_and_reconnect_sheets()
                        
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                logger.info("Мониторинг здоровья остановлен (получен сигнал отмены)")
                break
            except Exception as e:
                logger.error(f"Ошибка в цикле мониторинга здоровья: {e}", exc_info=True)
                self.consecutive_failures += 1
                try:
                    await asyncio.sleep(60)  # Ждем минуту при ошибке
                except asyncio.CancelledError:
                    break
                    
    async def _check_bot_health(self) -> bool:
        """
        Проверяет здоровье бота через getMe.
        
        Returns:
            True если бот здоров, False в противном случае
        """
        try:
            # Простая проверка через getMe с таймаутом
            me = await asyncio.wait_for(self.bot.get_me(), timeout=10.0)
            return me is not None
        except (TelegramError, NetworkError, TimedOut, asyncio.TimeoutError) as e:
            logger.warning(f"Ошибка при проверке здоровья бота: {e}")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при проверке здоровья бота: {e}", exc_info=True)
            return False
    
    async def _check_and_reconnect_sheets(self):
        """
        Проверяет доступность Google Sheets и автоматически переподключается при проблемах.
        """
        try:
            # Проверяем, есть ли worksheet
            if not self.auth_service.worksheet:
                self.sheets_consecutive_failures += 1
                logger.warning(
                    f"⚠️  Google Sheets недоступен "
                    f"(подряд ошибок: {self.sheets_consecutive_failures})"
                )
                
                # Пытаемся переподключиться не чаще чем раз в 2 минуты
                time_since_last_reconnect = time.time() - self.last_sheets_reconnect
                if time_since_last_reconnect > 120:
                    logger.info("🔄 Попытка переподключения к Google Sheets (non-blocking)...")
                    # Выполняем переподключение в отдельном потоке
                    await asyncio.to_thread(self._reconnect_sheets)
                    self.last_sheets_reconnect = time.time()
                else:
                    logger.debug(
                        f"Пропуск переподключения (последнее было {time_since_last_reconnect:.0f} сек назад)"
                    )
            else:
                # Sheets доступен
                if self.sheets_consecutive_failures > 0:
                    logger.info("✅ Google Sheets восстановлен")
                self.sheets_consecutive_failures = 0
                
        except Exception as e:
            logger.error(f"Ошибка при проверке Google Sheets: {e}", exc_info=True)
    
    def _reconnect_sheets(self):
        """
        Попытка переподключения к Google Sheets (синхронная, выполняется в to_thread).
        """
        try:
            from sheets_gateway import _get_client_and_sheet

            logger.info("Переподключение к Google Sheets...")
            _, worksheet = _get_client_and_sheet()
            
            if worksheet:
                self.auth_service.worksheet = worksheet
                logger.info("✅ Google Sheets успешно переподключен")
                self.sheets_consecutive_failures = 0
                return True
            else:
                logger.warning("⚠️  Не удалось переподключить Google Sheets")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка переподключения к Google Sheets: {e}")
            return False
