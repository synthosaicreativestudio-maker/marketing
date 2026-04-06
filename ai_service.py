import logging
import os
from typing import AsyncGenerator, Optional

from gemini_service import GeminiService
from openclaw_legacy_service import OpenClawLegacyService
from sheets_gateway import AsyncGoogleSheetsGateway

logger = logging.getLogger(__name__)


class AIService:
    """Facade for the active chat backend."""

    def __init__(self, promotions_gateway: Optional[AsyncGoogleSheetsGateway] = None) -> None:
        raw_backend = os.getenv("AI_BACKEND", "direct_gemini").strip().lower()
        if raw_backend in {"openclaw", "openclaw_legacy", "legacy_openclaw"}:
            self.backend_name = "openclaw_legacy"
            self.provider_name = "OpenClaw-Legacy"
            self.service = OpenClawLegacyService(promotions_gateway=promotions_gateway)
        else:
            self.backend_name = "direct_gemini"
            self.provider_name = "Direct-Gemini"
            self.service = GeminiService(promotions_gateway=promotions_gateway)

        # Backward compatibility for legacy call sites.
        self.gemini_service = self.service
        logger.info(f"AIService активен с провайдером: {self.get_provider_name()}")

    def is_enabled(self) -> bool:
        return bool(self.service) and self.service.is_enabled()

    async def initialize(self) -> None:
        if self.service and hasattr(self.service, "initialize"):
            await self.service.initialize()

    async def wait_for_ready(self) -> bool:
        if self.service and hasattr(self.service, "wait_for_ready"):
            return await self.service.wait_for_ready()
        return self.is_enabled()

    async def ask(
        self,
        user_id: int,
        content: str,
        external_history: Optional[str] = None,
        system_context: Optional[str] = None,
    ) -> Optional[str]:
        return await self.service.ask(
            user_id,
            content,
            external_history=external_history,
            system_context=system_context,
        )

    async def ask_stream(
        self,
        user_id: int,
        content: str,
        external_history: Optional[str] = None,
        system_context: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        async for chunk in self.service.ask_stream(
            user_id,
            content,
            external_history=external_history,
            system_context=system_context,
        ):
            yield chunk

    def get_provider_name(self) -> str:
        return self.provider_name

    def get_backend_name(self) -> str:
        return self.backend_name

    async def force_refresh_rag(self) -> bool:
        logger.info(
            "force_refresh_rag requested for backend %s; separate RAG refresh is not required.",
            self.backend_name,
        )
        return True

    async def refresh_knowledge_base(self) -> bool:
        """Compatibility alias for older admin handlers."""
        return await self.force_refresh_rag()

    def clear_history(self, user_id: int) -> None:
        if self.service:
            self.service.clear_history(user_id)

    async def refresh_system_prompt(self, force: bool = False) -> bool:
        if self.service:
            return await self.service.refresh_system_prompt(force=force)
        return False

    async def close(self) -> None:
        if self.service:
            await self.service.close()
