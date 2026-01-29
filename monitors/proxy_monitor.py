import asyncio
import logging
import os
import aiohttp
from utils import alert_admin

logger = logging.getLogger(__name__)

class ProxyMonitor:
    """
    Монитор доступности прокси-сервера Gemini.
    Периодически проверяет доступность PROXYAPI_BASE_URL.
    При падении отправляет уведомление админу.
    """
    def __init__(self, check_interval: int = 300):
        self.proxy_url = os.getenv("PROXYAPI_BASE_URL")
        self.check_interval = check_interval
        self._is_running = False
        self._last_status = True  # Считаем, что изначально всё ок, чтобы не спамить при старте, если всё ок
        # Но если старт с ошибкой - первый чек это покажет.
        
        # Если URL не задан, монитор бесполезен
        if not self.proxy_url:
            logger.warning("ProxyMonitor отключен: PROXYAPI_BASE_URL не задан")
            self._disabled = True
        else:
            self._disabled = False
            logger.info(f"ProxyMonitor инициализирован для {self.proxy_url}")

    async def start(self, bot):
        """Запуск цикла мониторинга."""
        if self._disabled or self._is_running:
            return

        self._is_running = True
        logger.info("ProxyMonitor started")
        asyncio.create_task(self._monitor_loop(bot))

    async def _monitor_loop(self, bot):
        """Бесконечный цикл проверки."""
        while self._is_running:
            try:
                is_available = await self._check_proxy()
                
                # Логика смены статуса (State Change)
                if is_available != self._last_status:
                    if not is_available:
                        # UP -> DOWN
                        msg = f"🚨 **CRITICAL: Proxy недоступен!**\nURL: `{self.proxy_url}`\nИИ перестанет отвечать."
                        logger.error("Proxy is DOWN. Alerting admin.")
                        await alert_admin(bot, msg, level="CRITICAL")
                    else:
                        # DOWN -> UP
                        msg = f"✅ **RESOLVED: Proxy снова онлайн**\nURL: `{self.proxy_url}`\nРабота ИИ восстановлена."
                        logger.info("Proxy recovered. Alerting admin.")
                        await alert_admin(bot, msg, level="WARNING") # Warning чтобы привлечь внимание, но позитивно
                    
                    self._last_status = is_available
                
            except Exception as e:
                logger.error(f"Error in ProxyMonitor loop: {e}")
            
            await asyncio.sleep(self.check_interval)

    async def _check_proxy(self) -> bool:
        """Пинг прокси простым GET запросом."""
        # Используем тайм-аут поменьше для теста
        timeout = aiohttp.ClientTimeout(total=10)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Просто проверяем коннект. 
                # Если это nginx proxy_pass на google, он может вернуть 404 на корень, но это значит он ЖИВ.
                # Если connection refused/timeout - он МЕРТВ.
                async with session.get(self.proxy_url) as _:
                    # Любой статус ответа означает, что TCP соединение есть (даже 404 или 500)
                    # Главное, не ClientConnectorError
                    return True
        except Exception as e:
            logger.debug(f"Proxy check failed: {e}")
            return False
