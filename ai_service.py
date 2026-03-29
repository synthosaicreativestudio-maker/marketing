import logging
from typing import Optional, AsyncGenerator
from gemini_service import GeminiService
from yandex_service import YandexService
from sheets_gateway import AsyncGoogleSheetsGateway

logger = logging.getLogger(__name__)

class AIService:
    """Facade for AI providers, now primarily routing through OpenClaw Engine via GeminiService."""
    
    def __init__(self, promotions_gateway: Optional[AsyncGoogleSheetsGateway] = None) -> None:
        self.gemini_service = GeminiService(promotions_gateway=promotions_gateway)
        self.yandex_service = YandexService()
        
        logger.info(f"AIService активен с провайдером: {self.get_provider_name()}")

    def is_enabled(self) -> bool:
        # Now always true because OpenClaw Gateway acts as the unified proxy
        return True

    async def ask(self, user_id: int, content: str, external_history: Optional[str] = None) -> Optional[str]:
        return await self.gemini_service.ask(user_id, content, external_history=external_history)

    async def ask_stream(self, user_id: int, content: str, external_history: Optional[str] = None) -> AsyncGenerator[str, None]:
        async for chunk in self.gemini_service.ask_stream(user_id, content, external_history=external_history):
            yield chunk

    def get_provider_name(self) -> str:
        return "OpenClaw-Gateway"

    async def force_refresh_rag(self) -> bool:
        # OpenClaw node.js natively handles its own RAG now. 
        # We just return True for compatibility with older admin dashboard buttons.
        logger.info("force_refresh_rag ignored as OpenClaw handles Knowledge Base natively.")
        return True

    def clear_history(self, user_id: int) -> None:
        if self.gemini_service:
            self.gemini_service.clear_history(user_id)

    async def refresh_system_prompt(self) -> bool:
        if self.gemini_service:
            return await self.gemini_service.refresh_system_prompt()
        return False
