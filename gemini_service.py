import os
import logging
from typing import Dict, List, Optional

from google import genai
from google.genai import types


logger = logging.getLogger(__name__)


class GeminiService:
    """Сервис для работы с Google Gemini API.
    
    Функционал:
    - Управление историей диалогов в памяти (user_id -> chat_history)
    - Ограничение истории до 10 последних сообщений
    - Поддержка настройки температуры и максимального количества токенов
    - Обработка ошибок и логирование
    """

    def __init__(self) -> None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GeminiService disabled: missing GEMINI_API_KEY")
            self.client = None
        else:
            try:
                # В google-genai SDK прокси подхватывается автоматически из окружения (HTTP_PROXY/HTTPS_PROXY)
                # Переменные уже прописаны в .env и подгружаются systemd.
                # Явное указание в HttpOptions вызывало ошибку валидации.
                self.client = genai.Client(api_key=api_key)
                logger.info("GeminiService initialized successfully (proxy managed by env)")
            except Exception as e:
                logger.error(f"Failed to initialize GeminiService: {e}", exc_info=True)
                self.client = None
        
        # Загрузка системного промпта
        system_prompt_path = os.getenv("SYSTEM_PROMPT_FILE", "system_prompt.txt")
        self.system_instruction = None
        
        # Проверка существования файла промпта
        if os.path.exists(system_prompt_path):
            try:
                with open(system_prompt_path, 'r', encoding='utf-8') as f:
                    self.system_instruction = f.read()
                    logger.info(f"System prompt loaded from {system_prompt_path}, size: {len(self.system_instruction)} chars")
            except Exception as e:
                logger.error(f"Failed to load system prompt from {system_prompt_path}: {e}", exc_info=True)
        else:
            logger.warning(f"System prompt file not found: {system_prompt_path}")
        
        # Хранилище истории диалогов: user_id -> list of Content objects
        self.user_histories: Dict[int, List[types.Content]] = {}
        
        # Настройки модели
        self.model_name = "gemini-3-pro-preview"
        self.max_history_messages = 10  # Храним последние 10 сообщений + 2pinned

    def is_enabled(self) -> bool:
        """Проверяет, доступен ли сервис."""
        return self.client is not None

    def _get_or_create_history(self, user_id: int) -> List[types.Content]:
        """Получает или создает историю для пользователя.
        
        Реализация Context Injection (ТЗ Блок А-1):
        Вместо системного параметра вставляем 2 фейковых сообщения.
        """
        if user_id not in self.user_histories:
            self.user_histories[user_id] = []
            # Добавляем системный промпт как первое сообщение (Role: User)
            if self.system_instruction:
                self.user_histories[user_id].append(
                    types.Content(
                        role="user",
                        parts=[types.Part(text=self.system_instruction)]
                    )
                )
                # Подтверждение от модели (Role: Model)
                self.user_histories[user_id].append(
                    types.Content(
                        role="model",
                        parts=[types.Part(text="Принято. Я работаю в режиме маркетингового ассистента Этажей. Готов к вопросам.")]
                    )
                )
            logger.info(f"Created new chat history for user {user_id} with Fake History Injection")
        
        return self.user_histories[user_id]

    def _add_to_history(self, user_id: int, role: str, content: str) -> None:
        """Добавляет сообщение в историю с защитой Context Pinning (ТЗ Блок А-2)."""
        history = self._get_or_create_history(user_id)
        
        # Добавляем новое сообщение
        history.append(
            types.Content(
                role=role,
                parts=[types.Part(text=content)]
            )
        )
        
        # Ограничение размера истории с защитой индексов 0 и 1
        # Новая история = [Msg0, Msg1] + [Последние 10 сообщений]
        if len(history) > self.max_history_messages + 2:
            # Удаляем самое старое сообщение послеPinned (индекс 2)
            history.pop(2)
            logger.debug(f"History Pinning: removed message at index 2 for user {user_id}. Context preserved.")

    def ask(self, user_id: int, content: str) -> Optional[str]:
        """Отправляет запрос в Gemini и возвращает ответ.
        
        Args:
            user_id: ID пользователя Telegram
            content: Текст сообщения пользователя
            
        Returns:
            Ответ от Gemini или None в случае ошибки
        """
        if not self.is_enabled():
            return None
        
        try:
            # Добавляем сообщение пользователя в историю
            self._add_to_history(user_id, "user", content)
            
            # Получаем всю историю для отправки
            history = self._get_or_create_history(user_id)
            
            # Конфигурация генерации для Gemini 3 Pro (ТЗ 1.3)
            config = types.GenerateContentConfig(
                temperature=1.0,  # Рекомендация для Gemini 3 / Thinking Models
                max_output_tokens=2000,
                top_p=0.95,
                top_k=40,
                # Отключение фильтров безопасности (ТЗ 1.3)
                safety_settings=[
                    types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_CIVIC_INTEGRITY", threshold="BLOCK_NONE"),
                ]
            )
            
            # Отправляем запрос в Gemini
            logger.info(f"Sending request to Gemini for user {user_id} (history: {len(history)} messages)")
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=history,
                config=config
            )
            
            # Извлекаем текст ответа
            if response and response.text:
                reply_text = response.text
                
                # Добавляем ответ модели в историю
                self._add_to_history(user_id, "model", reply_text)
                
                logger.info(f"Received response from Gemini for user {user_id}: {len(reply_text)} chars")
                return reply_text
            else:
                logger.warning(f"Empty response from Gemini for user {user_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error calling Gemini API for user {user_id}: {e}", exc_info=True)
            return None

    def clear_history(self, user_id: int) -> None:
        """Очищает историю диалога для пользователя."""
        if user_id in self.user_histories:
            del self.user_histories[user_id]
            logger.info(f"Cleared chat history for user {user_id}")
