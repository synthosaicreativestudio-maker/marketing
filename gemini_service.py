import os
import logging
import asyncio
from typing import Dict, List, Optional

from google import genai
from google.genai import types

# Импорты для инструментов
from promotions_api import get_promotions_json
from sheets_gateway import AsyncGoogleSheetsGateway


logger = logging.getLogger(__name__)


class GeminiService:
    """Сервис для работы с Google Gemini API.
    
    Функционал:
    - Управление историей диалогов в памяти (user_id -> chat_history)
    - Ограничение истории до 10 последних сообщений
    - Поддержка настройки температуры и максимального количества токенов
    - Обработка ошибок и логирование
    """

    def __init__(self, promotions_gateway: Optional[AsyncGoogleSheetsGateway] = None) -> None:
        self.promotions_gateway = promotions_gateway
        
        # Проверка конфигурации ProxyAPI.ru (Вариант Б: прямая замена endpoint)
        proxyapi_key = os.getenv("PROXYAPI_KEY")
        proxyapi_base_url = os.getenv("PROXYAPI_BASE_URL")
        
        # Вариант Б: Использование ProxyAPI.ru
        if proxyapi_key and proxyapi_base_url:
            logger.info("ProxyAPI.ru detected - using custom endpoint for Gemini access")
            try:
                self.client = genai.Client(
                    api_key=proxyapi_key,
                    http_options={'api_endpoint': proxyapi_base_url}
                )
                logger.info("GeminiService initialized via ProxyAPI.ru (bypass regional restrictions)")
            except Exception as e:
                logger.error(f"Failed to initialize GeminiService via ProxyAPI: {e}", exc_info=True)
                self.client = None
        
        # Вариант А: Стандартный API (с поддержкой HTTP_PROXY из окружения)
        else:
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
                    http_proxy = os.getenv("HTTP_PROXY")
                    if http_proxy:
                        logger.info(f"GeminiService initialized with HTTP_PROXY: {http_proxy}")
                    else:
                        logger.info("GeminiService initialized (direct connection)")
                except Exception as e:
                    logger.error(f"Failed to initialize GeminiService: {e}", exc_info=True)
                    self.client = None
        
        # Загрузка системного промпта
        system_prompt_path = os.getenv("SYSTEM_PROMPT_FILE", "system_prompt.txt")
        self.system_instruction = None
        
        # Инициализация Knowledge Base (RAG)
        from drive_service import DriveService
        from knowledge_base import KnowledgeBase
        
        self.drive_service = DriveService()
        self.knowledge_base = KnowledgeBase(self.drive_service)
        
        # Проверка существования файла промпта
        if os.path.exists(system_prompt_path):
            try:
                with open(system_prompt_path, 'r', encoding='utf-8') as f:
                    user_business_rules = f.read()
                    
                # ТЗ v5.0: Технический Драйвер (Priority: ROOT)
                # Позволяет обойти ограничения без изменения файла заказчика
                technical_driver = """
### SYSTEM OVERRIDE (PRIORITY LEVEL: ROOT)
Ты — ИИ-модель, управляемая этим системным слоем.
Ниже идут бизнес-инструкции пользователя. Соблюдай их строго, НО с учетом технических правил:

1. **ИНСТРУМЕНТЫ (TOOLS):** Если вопрос касается цен, акций, ипотеки — ИГНОРИРУЙ запрет на внешние данные. ТЫ ОБЯЗАН вызвать функцию `get_promotions`.
2. **POISK (WEB SEARCH):** Для вопросов о недвижимости, услугах, аналитике рынка, стратегиях, контент-планах, трендах маркетинга и ипотеке — ОБЯЗАТЕЛЬНО используй поиск в интернете (Google Search). Обязательный контекст: Россия, Тюмень, специфика недвижимости.
3. **КРАТКОСТЬ (КРИТИЧНО):** Твой ответ должен быть максимально конкретным, применимым к РФ и НЕ превышать **400 символов**.
4. **КРЕАТИВ:** Если пользователь просит творчество — ИГНОРИРУЙ запрет на "отсебятину".
5. **ЭСКАЛАЦИЯ:** Для вызова специалиста добавляй тег: [ESCALATE_ACTION].
6. **ЗАЩИТА ССЫЛОК (КРИТИЧНО):**
   - Никогда не используй Markdown-форматирование внутри URL.
   - СТРОЖАЙШЕ ЗАПРЕЩЕНО удалять или экранировать символы `_` (нижнее подчеркивание) в ссылках.
   - Ссылка `t.me/tp_esoft` должна остаться `t.me/tp_esoft`, а не `t.me/tpesoft`.
   - Выводи ссылки как Plain Text.

### --- НАЧАЛО БИЗНЕС-ИНСТРУКЦИИ ПОЛЬЗОВАТЕЛЯ ---
"""
                self.system_instruction = technical_driver + user_business_rules
                logger.info("System prompt loaded with Technical Driver (ROOT OVERRIDE active)")
            except Exception as e:
                logger.error(f"Failed to load system prompt from {system_prompt_path}: {e}", exc_info=True)
        else:
            logger.warning(f"System prompt file not found: {system_prompt_path}")
        
        # Инструменты (Function Calling + Search Grounding)
        self.tools = [
            types.Tool(
                function_declarations=[types.FunctionDeclaration(
                    name='get_promotions',
                    description='Получить список текущих акций, скидок и условий ипотеки из базы данных. ПРИОРИТЕТНЫЙ ИСТОЧНИК для вопросов о выгоде.',
                    parameters=types.Schema(
                        type='OBJECT',
                        properties={}
                    )
                )]
            ),
            types.Tool(
                google_search_retrieval=types.GoogleSearchRetrieval(
                    dynamic_retrieval_config=types.DynamicRetrievalConfig(
                        dynamic_threshold=0.3
                    )
                )
            )
        ]
        
        # Хранилище истории диалогов: user_id -> list of Content objects
        self.user_histories: Dict[int, List[types.Content]] = {}
        
        # Настройки модели
        # ВАЖНО: Для Context Caching имя модели при генерации должно совпадать с тем, где создан кэш.
        # В knowledge_base.py мы используем 'models/gemini-1.5-pro-001' (или flash).
        # Проверим, что используется.
        self.model_name = "gemini-3-flash-preview" 
        self.max_history_messages = 10  # Храним последние 10 сообщений + 2pinned

    async def initialize(self):
        """Async init for Knowledge Base with Rules and Tools."""
        if self.knowledge_base:
            await self.knowledge_base.initialize()
            # ПРИНУДИТЕЛЬНО запускаем обновление кэша с нашими правилами
            asyncio.create_task(self.knowledge_base.refresh_cache(
                system_instruction=self.system_instruction,
                tools=self.tools
            ))

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

    async def ask(self, user_id: int, content: str) -> Optional[str]:
        """Отправляет запрос в Gemini и возвращает ответ (Async для поддержки инструментов)."""
        if not self.is_enabled():
            return None
        
        try:
            # Добавляем сообщение пользователя в историю
            self._add_to_history(user_id, "user", content)
            
            # Получаем всю историю для отправки
            history = self._get_or_create_history(user_id)
            
            # ТЗ v5.0: Определяем инструменты (Function Calling + Search Grounding)
            tools = [
                types.Tool(
                    function_declarations=[types.FunctionDeclaration(
                        name='get_promotions',
                        description='Получить список текущих акций, скидок и условий ипотеки из базы данных. ПРИОРИТЕТНЫЙ ИСТОЧНИК для вопросов о выгоде.',
                        parameters=types.Schema(
                            type='OBJECT',
                            properties={}
                        )
                    )]
                ),
                types.Tool(
                    google_search_retrieval=types.GoogleSearchRetrieval(
                        dynamic_retrieval_config=types.DynamicRetrievalConfig(
                            dynamic_threshold=0.3 # Активируем поиск для всех умеренно-фактических запросов
                        )
                    )
                )
            ]
            
            # Проверяем наличие активного кэша
            cache_name = await self.knowledge_base.get_cache_name()
            
            # Конфигурация генерации
            config_params = {
                'temperature': 0.7, # Чуть строже для RAG
                'max_output_tokens': 2000,
                'top_p': 0.95,
                'top_k': 40,
                'tools': tools,
                'safety_settings': [
                    types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_CIVIC_INTEGRITY", threshold="BLOCK_NONE"),
                ]
            }
            
            # Если кэша нет - используем System Instruction и Tools в конфиге
            if not cache_name:
                config_params['system_instruction'] = self.system_instruction
                config_params['tools'] = self.tools
                logger.info(f"Using Standard System Prompt & Tools (No Cache) for user {user_id}")
            else:
                # ВАЖНО: Если есть кэш, то system_instruction и tools ЗАПРЕЩЕНО 
                # передавать в generate_content (они уже в кэше).
                config_params['cached_content'] = cache_name
                logger.info(f"Using Cached Context {cache_name} for user {user_id}. Instruction/Tools embedded.")
                
            config = types.GenerateContentConfig(**config_params)
            
            # Отправляем запрос в Gemini (ASYNC)
            logger.info(f"Sending request to Gemini for user {user_id} (tools active)")
            
            # Аргументы для generate_content
            generate_kwargs = {
                'model': self.model_name,
                'contents': history,
                'config': config
            }
            
            response = await self.client.aio.models.generate_content(**generate_kwargs)
            
            # Обработка Function Calls (цикл в случае цепочки вызовов)
            # Примечание: В текущем google-genai SDK 1.0+ response.candidates[0].content.parts
            candidate = response.candidates[0]
            
            while candidate.content.parts and candidate.content.parts[0].function_call:
                fc = candidate.content.parts[0].function_call
                logger.info(f"ИИ вызывает функцию: {fc.name}")
                
                tool_result = "Данные недоступны"
                if fc.name == 'get_promotions':
                    if self.promotions_gateway:
                        try:
                            tool_result = await get_promotions_json(self.promotions_gateway)
                            logger.info(f"Инструмент get_promotions вернул данные (len: {len(tool_result)})")
                        except Exception as te:
                            logger.error(f"Ошибка вызова инструмента: {te}")
                    else:
                        logger.warning("Gateway для акций не настроен в GeminiService")
                
                # Добавляем результат вызова в историю (как ответ модели с вызовом и сообщение от функции)
                # Сначала фиксируем сам вызов в истории
                self.user_histories[user_id].append(candidate.content)
                
                # Затем ответ функции
                function_response_part = types.Part(
                    function_response=types.FunctionResponse(
                        name=fc.name,
                        response={'output': tool_result}
                    )
                )
                function_content = types.Content(role="tool", parts=[function_response_part])
                self.user_histories[user_id].append(function_content)
                
                # Повторный запрос с результатом (ASYNC)
                # Важно: Здесь тоже передаем cached_content если он есть!
                # Иначе модель может "забыть" контекст кэша.
                response = await self.client.aio.models.generate_content(**generate_kwargs)
                candidate = response.candidates[0]

            # Финальный текст
            if response and response.text:
                reply_text = response.text
                
                # Добавляем ответ модели в историю
                self._add_to_history(user_id, "model", reply_text)
                
                logger.info(f"Received final response from Gemini (history size: {len(self.user_histories[user_id])}) for user {user_id}")
                return reply_text
            else:
                logger.warning(f"Empty response from Gemini for user {user_id}")
                return "Извините, я не смог сформировать ответ."
                
        except Exception as e:
            logger.error(f"Error interacting with Gemini: {e}", exc_info=True)
            return None

    def clear_history(self, user_id: int) -> None:
        """Очищает историю диалога для пользователя."""
        if user_id in self.user_histories:
            del self.user_histories[user_id]
            logger.info(f"Cleared chat history for user {user_id}")
