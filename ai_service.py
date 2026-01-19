import logging
from typing import Optional

from gemini_service import GeminiService
from sheets_gateway import AsyncGoogleSheetsGateway

logger = logging.getLogger(__name__)


class AIService:
    """Унифицированный сервис для работы с AI (только Gemini)."""

    def __init__(self, promotions_gateway: Optional[AsyncGoogleSheetsGateway] = None) -> None:
        """Инициализация AI сервиса с Gemini."""
        logger.info("Initializing AIService with Gemini")
        
        # Инициализация Gemini сервиса
        self.gemini_service = GeminiService(promotions_gateway=promotions_gateway)
        
        # Проверка доступности Gemini
        if not self.gemini_service.is_enabled():
            logger.error("GeminiService is not available!")
        else:
            logger.info("GeminiService is ready")

    def is_enabled(self) -> bool:
        """Проверяет, доступен ли AI сервис."""
        return self.gemini_service.is_enabled()

    async def ask(self, user_id: int, content: str) -> Optional[str]:
        """Отправляет запрос в Gemini и возвращает ответ (Асинхронно)."""
        if not self.is_enabled():
            return None
        return await self.gemini_service.ask(user_id, content)

    async def ask_stream(self, user_id: int, content: str):
        """Прокси для потокового вызова Gemini."""
        if not self.is_enabled():
            yield "Сервис ИИ недоступен."
            return
        
        async for chunk in self.gemini_service.ask_stream(user_id, content):
            yield chunk

    def get_provider_name(self) -> str:
        """Возвращает имя активного провайдера."""
        return "Gemini"
