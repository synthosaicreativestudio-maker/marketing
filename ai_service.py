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

    async def ask(self, user_id: int, content: str, external_history: Optional[str] = None) -> Optional[str]:
        """Отправляет запрос в Gemini и возвращает ответ (Асинхронно)."""
        if not self.is_enabled():
            return None
        return await self.gemini_service.ask(user_id, content, external_history=external_history)

    async def ask_stream(self, user_id: int, content: str, external_history: Optional[str] = None):
        """Прокси для потокового вызова Gemini."""
        if not self.is_enabled():
            yield "Сервис ИИ недоступен."
            return
        
        async for chunk in self.gemini_service.ask_stream(user_id, content, external_history=external_history):
            yield chunk


    def get_provider_name(self) -> str:
        """Возвращает имя активных провайдеров."""
        active = []
        if self.gemini_service.or_client:
            models_short = [m.split("/")[-1] for m in self.gemini_service.or_models]
            active.append(f"OpenRouter({', '.join(models_short)})")
        if self.gemini_service.gemini_clients:
            active.append(f"Gemini({self.gemini_service.gemini_model})")
        if hasattr(self.gemini_service, 'oa_client') and self.gemini_service.oa_client:
            active.append(f"OpenAI({self.gemini_service.oa_model})")
        return " + ".join(active) if active else "None"

    async def refresh_knowledge_base(self):
        """Ручное обновление базы знаний."""
        if self.gemini_service and self.gemini_service.knowledge_base:
            await self.gemini_service.knowledge_base.refresh_cache(
                system_instruction=self.gemini_service.system_instruction,
                tools=self.gemini_service.tools
            )
            return True
        return False
