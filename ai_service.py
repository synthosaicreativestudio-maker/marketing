import os
import logging
from typing import Optional

from openai_service import OpenAIService
from gemini_service import GeminiService


logger = logging.getLogger(__name__)


class AIService:
    """Единая точка входа для работы с AI-провайдерами.
    
    Автоматически выбирает провайдер на основе переменной окружения AI_PROVIDER.
    Поддерживает fallback: если выбранный провайдер недоступен, пытается использовать альтернативный.
    """

    def __init__(self) -> None:
        # Определяем провайдер из переменной окружения
        self.provider_name = os.getenv("AI_PROVIDER", "OPENAI").upper()
        
        logger.info(f"Initializing AIService with provider: {self.provider_name}")
        
        # Инициализируем оба сервиса
        self.openai_service = OpenAIService()
        self.gemini_service = GeminiService()
        
        # Выбираем активный провайдер
        if self.provider_name == "GEMINI":
            self.active_service = self.gemini_service
            self.fallback_service = self.openai_service
        else:
            self.active_service = self.openai_service
            self.fallback_service = self.gemini_service
        
        # Проверяем доступность
        if not self.active_service.is_enabled():
            logger.warning(
                f"Primary AI provider '{self.provider_name}' is not available. "
                f"Checking fallback..."
            )
            if self.fallback_service.is_enabled():
                logger.info("Switching to fallback provider")
                self.active_service = self.fallback_service
            else:
                logger.error("Both AI providers are unavailable!")
        else:
            logger.info(f"AI provider '{self.provider_name}' is ready")

    def is_enabled(self) -> bool:
        """Проверяет, доступен ли хотя бы один AI-провайдер."""
        return self.active_service.is_enabled()
    
    def get_provider_name(self) -> str:
        """Возвращает имя активного провайдера для логирования."""
        if self.active_service == self.openai_service:
            return "OpenAI"
        elif self.active_service == self.gemini_service:
            return "Gemini"
        return "Unknown"

    def ask(self, user_id: int, content: str) -> Optional[str]:
        """Отправляет запрос активному AI-провайдеру.
        
        Args:
            user_id: ID пользователя Telegram
            content: Текст сообщения пользователя
            
        Returns:
            Ответ от AI или None в случае ошибки
        """
        if not self.is_enabled():
            logger.warning("No AI providers available")
            return None
        
        provider_name = self.get_provider_name()
        logger.debug(f"Routing request to {provider_name} for user {user_id}")
        
        try:
            return self.active_service.ask(user_id, content)
        except Exception as e:
            logger.error(f"Error calling {provider_name}: {e}", exc_info=True)
            return None
