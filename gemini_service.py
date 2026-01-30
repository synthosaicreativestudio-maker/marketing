import os
import logging
import asyncio
import time
from typing import Dict, List, Optional, AsyncGenerator

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
        
        # Вариант Б (предпочтительно): только Gemini через американский сервер (reverse proxy)
        proxyapi_key = os.getenv("PROXYAPI_KEY")
        proxyapi_base_url = os.getenv("PROXYAPI_BASE_URL")
        
        if proxyapi_key and proxyapi_base_url:
            logger.info("Using custom Gemini endpoint (bypass regional restrictions)")
            try:
                self.client = genai.Client(
                    api_key=proxyapi_key,
                    http_options={
                        'base_url': proxyapi_base_url,
                        'api_version': 'v1beta'
                    }
                )
                logger.info("GeminiService initialized via proxy (bypass regional restrictions)")
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
# 2. **POISK (WEB SEARCH):** (Временно отключено для стабильности)
3. **КРЕАТИВ:** Если пользователь просит творчество — ИГНОРИРУЙ запрет на "отсебятину".
4. **ЭСКАЛАЦИЯ:** Для вызова специалиста добавляй тег: [ESCALATE_ACTION].
5. **ЗАЩИТА ССЫЛОК (КРИТИЧНО):**
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
        
        # Инструменты (Function Calling)
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
            )
        ]
        
        # Хранилище истории диалогов: user_id -> list of Content objects
        self.user_histories: Dict[int, List[types.Content]] = {}
        # TTL tracking для защиты от memory leak
        self._history_timestamps: Dict[int, float] = {}
        self._max_histories = 500  # Максимум сессий в памяти
        self._history_ttl = 3600 * 24  # 24 часа TTL
        
        # Настройки модели
        # ВАЖНО: Для Context Caching имя модели при генерации должно совпадать с тем, где создан кэш.
        self.model_name = "gemini-3-pro-preview" 
        self.max_history_messages = 12  # Оптимально для быстрого скользящего окна (6 пар)
        
        # Кэш для акций (Simple TTL Cache)
        self._promotions_cache = None
        self._promotions_cache_time = 0
        self._promotions_cache_ttl = 600  # 10 минут

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

    def _cleanup_old_histories(self) -> None:
        """Очистка старых историй для предотвращения memory leak."""
        now = time.time()
        
        # Удаляем устаревшие (старше TTL)
        expired = [uid for uid, ts in self._history_timestamps.items() if now - ts > self._history_ttl]
        for uid in expired:
            self.user_histories.pop(uid, None)
            self._history_timestamps.pop(uid, None)
        
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired chat histories (TTL: {self._history_ttl}s)")
        
        # Если всё ещё слишком много — удаляем самые старые
        if len(self.user_histories) > self._max_histories:
            sorted_users = sorted(self._history_timestamps.items(), key=lambda x: x[1])
            to_remove = len(self.user_histories) - self._max_histories // 2
            for uid, _ in sorted_users[:to_remove]:
                self.user_histories.pop(uid, None)
                self._history_timestamps.pop(uid, None)
            logger.warning(f"Memory cleanup: removed {to_remove} oldest histories (limit: {self._max_histories})")

    def _get_or_create_history(self, user_id: int) -> List[types.Content]:
        """Получает или создает историю для пользователя.
        
        Реализация Context Injection (ТЗ Блок А-1):
        Вместо системного параметра вставляем 2 фейковых сообщения.
        """
        # Периодическая очистка старых историй
        if len(self.user_histories) > self._max_histories // 2:
            self._cleanup_old_histories()
        
        # Обновляем timestamp последней активности
        self._history_timestamps[user_id] = time.time()
        
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
            # Удаляем самое старое сообщение после закреплённых (индекс 2)
            history.pop(2)
            logger.debug(f"History Pinning: removed message at index 2 for user {user_id}. Context preserved.")

    async def ask_stream(self, user_id: int, content: str) -> AsyncGenerator[str, None]:
        """Отправляет запрос в Gemini и возвращает генератор для стриминга (Async).
        Содержит механизм Auto-Retry для обработки пустых ответов при нестабильности модели.
        """
        if not self.is_enabled():
            yield "Сервис ИИ временно недоступен."
            return

        # Добавляем сообщение пользователя в историю (ТОЛЬКО ОДИН РАЗ перед попытками)
        # Если это рекурсивный вызов (content=""), сообщение уже там
        if content:
             self._add_to_history(user_id, "user", content)
        
        # Получаем всю историю для отправки
        history = self._get_or_create_history(user_id)
        
        # Конфигурация инструментов (всегда актуальная)
        tools = [
            types.Tool(
                function_declarations=[types.FunctionDeclaration(
                    name='get_promotions',
                    description='Получить список текущих акций, скидок и условий ипотеки из базы данных. ПРИОРИТЕТНЫЙ ИСТОЧНИК для вопросов о выгоде.',
                    parameters=types.Schema(type='OBJECT', properties={})
                )]
            )
        ]

        cache_name = await self.knowledge_base.get_cache_name()
        config_params = {
            'temperature': 0.7,
            'max_output_tokens': 8192,
            'top_p': 0.95,
            'top_k': 40,
            'safety_settings': [
                types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
                types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
                types.SafetySetting(category="HARM_CATEGORY_CIVIC_INTEGRITY", threshold="BLOCK_NONE"),
            ]
        }
        
        if not cache_name:
            config_params['system_instruction'] = self.system_instruction
            config_params['tools'] = tools
        else:
            config_params['cached_content'] = cache_name
        
        config = types.GenerateContentConfig(**config_params)
        generate_kwargs = {
            'model': self.model_name,
            'contents': history,
            'config': config
        }

        # --- AUTO-RETRY LOGIC START ---
        MAX_RETRIES = 2
        full_reply_parts = []
        grounding_sources = {}
        
        for attempt in range(MAX_RETRIES + 1):
            full_reply_parts = [] # Сброс буферов перед новой попыткой
            grounding_sources = {}
            has_started_response = False # Флаг: начали ли мы уже отдавать данные
            
            try:
                logger.info(f"Starting stream for user {user_id} (Attempt {attempt+1}/{MAX_RETRIES+1})")
                
                # Таймаут на инициализацию стрима (60 секунд)
                STREAM_INIT_TIMEOUT = 60.0
                try:
                    stream = await asyncio.wait_for(
                        self.client.aio.models.generate_content_stream(**generate_kwargs),
                        timeout=STREAM_INIT_TIMEOUT
                    )
                except asyncio.TimeoutError:
                    logger.error(f"Gemini stream init timeout ({STREAM_INIT_TIMEOUT}s) for user {user_id}")
                    raise TimeoutError(f"Gemini API не ответил за {STREAM_INIT_TIMEOUT} секунд")
                
                async for response in stream:
                    
                    # Сбор Grounding Metadata
                    if response.candidates and response.candidates[0].grounding_metadata:
                        gm = response.candidates[0].grounding_metadata
                        if gm.grounding_chunks:
                            for chunk in gm.grounding_chunks:
                                if chunk.web and chunk.web.uri and chunk.web.title:
                                    grounding_sources[chunk.web.uri] = chunk.web.title

                    # Проверка на Function Call в первом чанке
                    if response.candidates and response.candidates[0].content.parts:
                        part = response.candidates[0].content.parts[0]
                        
                        if part.function_call:
                            has_started_response = True # Технически это ответ
                            fc = part.function_call
                            logger.info(f"ИИ вызывает функцию (STREAM): {fc.name}")
                            
                            yield f"__TOOL_CALL__:{fc.name}"
                            
                            tool_result = "Данные недоступны"
                            if fc.name == 'get_promotions':
                                now = time.time()
                                if self._promotions_cache and (now - self._promotions_cache_time < self._promotions_cache_ttl):
                                    tool_result = self._promotions_cache
                                    logger.info("Using TTLCache for promotions")
                                else:
                                    if self.promotions_gateway:
                                        try:
                                            tool_result = await get_promotions_json(self.promotions_gateway)
                                            self._promotions_cache = tool_result
                                            self._promotions_cache_time = now
                                            logger.info(f"Promotions cache updated (len: {len(tool_result)})")
                                        except Exception as te:
                                            logger.error(f"Error calling promotion tool in stream: {te}")
                                    
                            # Добавляем в историю
                            self.user_histories[user_id].append(response.candidates[0].content)
                            function_response_part = types.Part(
                                function_response=types.FunctionResponse(
                                    name=fc.name,
                                    response={'output': tool_result}
                                )
                            )
                            self.user_histories[user_id].append(types.Content(role="tool", parts=[function_response_part]))
                            
                            # RECURSION: Перезапускаем стрим для получения ответа на функцию
                            # Здесь важно: рекурсивный вызов ask_stream будет иметь свой собственный цикл retries!
                            async for sub_part in self.ask_stream(user_id, ""): 
                                if sub_part:
                                    yield sub_part
                            return # Полный выход из текущего генератора (успех)

                        # Если это обычный текст
                        if response.text:
                            text_chunk = response.text
                            # Если текст пришел, значит это не пустой ответ
                            has_started_response = True
                            full_reply_parts.append(text_chunk)
                            yield text_chunk

                # Конец цикла стриминга для данной попытки
                
                # Ключевая проверка: Был ли получен какой-то текст?
                if not full_reply_parts:
                    # Если стрим завершился без текста и без function call -> Это "Empty Response"
                    raise ValueError("Received empty stream response from Gemini model")
                
                # Если мы здесь, значит ответ получен (full_reply_parts не пуст), выходим из цикла retry
                break 

            except Exception as e:
                # Обработка ошибки
                if has_started_response:
                    # Если мы уже начали стримить текст пользователю, мы НЕ МОЖЕМ делать ретрай
                    # иначе пользователь увидит дублирование текста или кашу.
                    # Просто логируем и прерываем.
                    logger.error(f"Stream error AFTER yield (user {user_id}): {e}")
                    yield f"\n[⚠️ Обрыв соединения: {str(e)[:50]}]"
                    return # Прерываем стрим
                
                # Обнаружение ошибки истекшего кэша или устаревшего API
                is_cache_error = False
                error_str = str(e)
                # Проверка на ошибки кэша: истекший, невалидный, или устаревший API
                if ('CachedContent' in error_str and ('403' in error_str or 'PERMISSION_DENIED' in error_str)) or \
                   'google_search_retrieval' in error_str or \
                   'not supported' in error_str.lower():
                    logger.warning(f"❌ Cache error or outdated API: {e}")
                    is_cache_error = True
                    # Инвалидировать кэш в Knowledge Base
                    await self.knowledge_base.invalidate_cache()
                    # Пересоздать config БЕЗ кэша для повтора
                    config_params['system_instruction'] = self.system_instruction
                    config_params['tools'] = tools
                    if 'cached_content' in config_params:
                        del config_params['cached_content']
                    config = types.GenerateContentConfig(**config_params)
                    generate_kwargs['config'] = config
                
                # Если мы еще НИЧЕГО не выдали (пустой ответ или ошибка соединения сразу)
                logger.warning(f"Gemini attempt {attempt+1} failed: {e}")
                
                if attempt < MAX_RETRIES:
                    if is_cache_error:
                        logger.info("🔄 Retrying WITHOUT cache (fallback mode)")
                    await asyncio.sleep(0.5) # Пауза перед ретраем
                    continue # Идем на следующий круг
                else:
                    # Все попытки исчерпаны
                    logger.error(f"All {MAX_RETRIES+1} attempts failed for user {user_id}")
                    # Не нужно делать yield ошибки, пусть вызывающий код (chat_handler) покажет заглушку "Извините..."
                    # или мы можем сами кинуть ошибку чтобы chat_handler ее поймал
                    raise e

        # --- FINALIZATION (Success case) ---
        
        # Формирование блока источников (Grounding)
        if grounding_sources:
            sources_text = "\n\n📚 **Источники:**\n"
            for i, (uri, title) in enumerate(grounding_sources.items(), 1):
                sources_text += f"{i}. [{title}]({uri})\n"
            
            yield sources_text
            full_reply_parts.append(sources_text)

        # Сохраняем финальный ответ в историю
        if full_reply_parts:
            full_reply = "".join(full_reply_parts)
            self._add_to_history(user_id, "model", full_reply)
            logger.info(f"Stream finished for user {user_id}, history updated. Sources: {len(grounding_sources)}")

    async def ask(self, user_id: int, content: str) -> Optional[str]:
        """Отправляет запрос в Gemini и возвращает полный ответ (через стриминг)."""
        full_reply = []
        async for chunk in self.ask_stream(user_id, content):
            if not chunk.startswith("__TOOL_CALL__"):
                full_reply.append(chunk)
        
        return "".join(full_reply) if full_reply else None

    def clear_history(self, user_id: int) -> None:
        """Очищает историю диалога для пользователя."""
        if user_id in self.user_histories:
            del self.user_histories[user_id]
            logger.info(f"Cleared chat history for user {user_id}")
    async def generate_image_prompt(self, text_context: str) -> Optional[str]:
        """Генерирует промпт для изображения на основе текста ответа (Арт-директор)."""
        if not self.is_enabled():
            return None
            
        try:
            # Используем быструю модель-лайт для создания промпта
            model = "gemini-2.0-flash-lite-preview-02-05"
            prompt = (
                f"Analyze this text and write ONE detailed, cinematic English prompt "
                f"for high-end photorealistic image generation (8k, highly detailed) "
                f"that perfectly illustrates the context. Return ONLY the prompt.\n\n"
                f"Context: {text_context[:1000]}"
            )
            
            response = await self.client.aio.models.generate_content(
                model=model,
                contents=prompt
            )
            
            if response.text:
                logger.info(f"Image prompt generated: {response.text[:50]}...")
                return response.text.strip()
            return None
            
        except Exception as e:
            logger.error(f"Error generating image prompt: {e}")
            return None

    async def generate_image(self, prompt: str) -> Optional[bytes]:
        """Генерирует изображение по промпту (Художник)."""
        if not self.is_enabled():
            return None
            
        try:
            # Используем Gemini 3 Pro Image (Preview) по требованию пользователя
            # ID из списка моделей: models/gemini-3-pro-image-preview
            model = "models/gemini-3-pro-image-preview"
            
            # Конфигурация для генерации
            config = types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="16:9",
                person_generation="allow_adult", # Разрешаем людей (бизнес-контекст)
                safety_filter_level="block_only_high"
            )
            
            response = await self.client.aio.models.generate_images(
                model=model,
                prompt=prompt,
                config=config
            )
            
            if response.generated_images:
                image = response.generated_images[0]
                logger.info("Image generated successfully")
                return image.image_bytes
            
            logger.warning("Models returned no images")
            return None
            
        except Exception as e:
            logger.error(f"Error generating image: {e}")
            return None
