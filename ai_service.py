import logging
from typing import Optional

from gemini_service import GeminiService


logger = logging.getLogger(__name__)


class AIService:
    """Унифицированный сервис для работы с AI (только Gemini)."""

    def __init__(self) -> None:
        """Инициализация AI сервиса с Gemini."""
        logger.info("Initializing AIService with Gemini")
        
        # Инициализация Gemini сервиса
        self.gemini_service = GeminiService()
        
        # Проверка доступности Gemini
        if not self.gemini_service.is_enabled():
            logger.error("GeminiService is not available!")
        else:
            logger.info("GeminiService is ready")

    def is_enabled(self) -> bool:
        """Проверяет, доступен ли AI сервис."""
        return self.gemini_service.is_enabled()

    def ask(self, user_id: int, content: str) -> Optional[str]:
        """Отправляет запрос в Gemini и возвращает ответ.
        
        Args:
            user_id: ID пользователя Telegram
            content: Текст сообщения пользователя
            
        Returns:
            Ответ от Gemini или None в случае ошибки
        """
        if not self.is_enabled():
            logger.error("AIService is not enabled")
            return None
        
        try:
            return self.gemini_service.ask(user_id, content)
        except Exception as e:
            logger.error(f"Error in AIService.ask: {e}", exc_info=True)
            return None

    def get_provider_name(self) -> str:
        """Возвращает имя активного провайдера."""
        return "Gemini"
