import os
import logging
import asyncio
import time
from typing import Dict, List, Optional, AsyncGenerator

from google import genai
from google.genai import types
from openai import AsyncOpenAI

# Импорты для инструментов
from promotions_api import get_promotions_json
from sheets_gateway import AsyncGoogleSheetsGateway


logger = logging.getLogger(__name__)


class GeminiService:
    """Сервис для работы с Google Gemini API и OpenRouter.
    
    Функционал:
    - Управление историей диалогов в памяти (user_id -> chat_history)
    - Ограничение истории до 10 последних сообщений
    - Поддержка настройки температуры и максимального количества токенов
    - Обработка ошибок и логирование (Gemini + OpenRouter/DeepSeek)
    """

    def __init__(self, promotions_gateway: Optional[AsyncGoogleSheetsGateway] = None) -> None:
        self.promotions_gateway = promotions_gateway
        
        # 1. Пул клиентов Gemini
        self.gemini_clients = []
        gemini_keys_str = os.getenv("GEMINI_API_KEYS", "")
        gemini_keys = [k.strip() for k in gemini_keys_str.split(",") if k.strip()]
        
        # Если старый ключ тоже есть, добавим его в начало (или используем если нет новых)
        old_gemini_key = os.getenv("GEMINI_API_KEY")
        if old_gemini_key and old_gemini_key not in gemini_keys:
            gemini_keys.insert(0, old_gemini_key)
            
        proxyapi_key = os.getenv("PROXYAPI_KEY")
        proxyapi_base_url = os.getenv("PROXYAPI_BASE_URL")
        
        for key in gemini_keys:
            try:
                if proxyapi_key and proxyapi_base_url:
                    # Вариант Б: через прокси
                    api_version = os.getenv("PROXYAPI_VERSION", "v1beta")
                    client = genai.Client(
                        api_key=key,
                        http_options={'base_url': proxyapi_base_url, 'api_version': api_version}
                    )
                else:
                    # Вариант А: напрямую (с поддержкой системного прокси)
                    client = genai.Client(api_key=key)
                
                self.gemini_clients.append(client)
                logger.info(f"Gemini client initialized with key ...{key[-4:]}")
            except Exception as e:
                logger.error(f"Failed to init Gemini client with key ...{key[-4:]}: {e}")
        
        self.client = self.gemini_clients[0] if self.gemini_clients else None
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

        # 2. Пул моделей OpenRouter
        self.or_client = None
        self.or_api_key = os.getenv("OPENROUTER_API_KEY")
        or_models_str = os.getenv("OPENROUTER_MODELS", "qwen/qwen-2.5-72b-instruct:free,meta-llama/llama-3.3-70b-instruct:free,deepseek/deepseek-r1-0528:free")
        self.or_models = [m.strip() for m in or_models_str.split(",") if m.strip()]
        
        if self.or_api_key:
            try:
                self.or_client = AsyncOpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=self.or_api_key,
                    default_headers={
                        "HTTP-Referer": "https://github.com/synthosaicreativestudio-maker/marketingbot",
                        "X-Title": "MarketingBot"
                    }
                )
                logger.info(f"OpenRouter client initialized. Models pool: {self.or_models}")
            except Exception as e:
                logger.error(f"Failed to initialize OpenRouter: {e}")
        
        # 3. Резервный провайдер Groq (сверхбыстрый LPU) — через прокси для обхода геоблокировки
        self.groq_client = None
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        
        if self.groq_api_key:
            try:
                # Используем тот же прокси что и для Gemini (американский сервер)
                groq_proxy_url = os.getenv("GROQ_PROXY_URL", os.getenv("PROXYAPI_BASE_URL"))
                
                if groq_proxy_url:
                    # Настраиваем httpx клиент с прокси
                    import httpx
                    http_client = httpx.AsyncClient(
                        proxy="http://root:LEJ6U5chSK@37.1.212.51:8080",
                        timeout=60.0
                    )
                    self.groq_client = AsyncOpenAI(
                        base_url="https://api.groq.com/openai/v1",
                        api_key=self.groq_api_key,
                        http_client=http_client
                    )
                    logger.info(f"Groq client initialized via US proxy. Model: {self.groq_model}")
                else:
                    # Без прокси (напрямую)
                    self.groq_client = AsyncOpenAI(
                        base_url="https://api.groq.com/openai/v1",
                        api_key=self.groq_api_key
                    )
                    logger.info(f"Groq client initialized (direct). Model: {self.groq_model}")
            except Exception as e:
                logger.error(f"Failed to initialize Groq: {e}")


        
        # Загрузка системного промпта
        system_prompt_path = os.getenv("SYSTEM_PROMPT_FILE", "system_prompt.txt")
        self.system_instruction = None
        
        # Инициализация Knowledge Base (RAG)
        from drive_service import DriveService
        from knowledge_base import KnowledgeBase
        from memory_archiver import MemoryArchiver
        
        self.drive_service = DriveService()
        self.knowledge_base = KnowledgeBase(self.drive_service)
        self.memory_archiver = MemoryArchiver(self.drive_service)
        
        # Проверка существования файла промпта
        if os.path.exists(system_prompt_path):
            try:
                with open(system_prompt_path, 'r', encoding='utf-8') as f:
                    user_business_rules = f.read()
                    
                # ТЗ v5.0: Технический Драйвер (Priority: ROOT)
                # Позволяет обойти ограничения без изменения файла заказчика
                technical_driver = """
### SYSTEM OVERRIDE (PRIORITY LEVEL: ROOT)
Ты - ИИ-модель, управляемая этим системным слоем.
Ниже идут бизнес-инструкции пользователя. Соблюдай их строго, НО с учетом технических правил:

1. **ИНСТРУМЕНТЫ (TOOLS):** Если вопрос касается цен, акций, ипотеки - ИГНОРИРУЙ запрет на внешние данные. ТЫ ОБЯЗАН вызвать функцию `get_promotions`.
2. **БАЗА ЗНАНИЙ (RAG):** Твои основные рабочие регламенты и файлы компании загружены в контекст. Всегда проверяй их перед ответом.
3. **ЭСКАЛАЦИЯ:** Для вызова специалиста добавляй тег: [ESCALATE_ACTION].
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
        
        # Helper for rotation
        self.current_or_model_index = 0
        
        # Хранилище истории диалогов: user_id -> list of Content objects
        self.user_histories: Dict[int, List[types.Content]] = {}
        # TTL tracking для защиты от memory leak
        self._history_timestamps: Dict[int, float] = {}
        self._max_histories = 500  # Максимум сессий в памяти
        self._history_ttl = 3600 * 24  # 24 часа TTL
        
        # Настройки модели
        # ВАЖНО: Для Context Caching имя модели при генерации должно совпадать с тем, где создан кэш.
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-pro") 
        self.max_history_messages = 12  # Оптимально для быстрого скользящего окна (6 пар)
        
        # Кэш для акций (Simple TTL Cache)
        self._promotions_cache = None
        self._promotions_cache_time = 0
        self._promotions_cache_ttl = 600  # 10 минут
        
        # Tools (Google Search, etc) - будут загружены в initialize()
        self.tools = None

    async def initialize(self):
        """Async init for Knowledge Base with Rules and Tools."""
        # Активация инструментов (Google Search)
        self.tools = [types.Tool(google_search_retrieval=types.GoogleSearchRetrieval())]
        logger.info("Google Search Grounding activated in GeminiService tools pool.")

        if self.knowledge_base:
            await self.knowledge_base.initialize()
            
            # Запускаем фоновое автообновление каждые 6 часов
            await self.knowledge_base.start_auto_refresh(interval_hours=6)
            
            # ПРИНУДИТЕЛЬНО запускаем первое обновление кэша с нашими правилами
            asyncio.create_task(self.knowledge_base.refresh_cache(
                system_instruction=self.system_instruction,
                tools=self.tools
            ))

    def is_enabled(self) -> bool:
        """Проверяет, доступен ли какой-либо ИИ-сервис."""
        return self.client is not None or self.or_client is not None

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

    async def ask_stream(self, user_id: int, content: str, external_history: Optional[str] = None) -> AsyncGenerator[str, None]:
        """Отправляет запрос в Gemini и возвращает генератор для стриминга (Async).
        external_history - текст истории из Google Таблицы (ячейка E).
        """
        if not self.is_enabled():
            yield "Сервис ИИ временно недоступен."
            return

        # --- UNIVERSAL RAG CONTEXT ---
        rag_context = ""
        if self.knowledge_base:
            try:
                # Получаем топ-5 релевантных фрагментов
                rag_context = self.knowledge_base.get_relevant_context(content, top_k=5)
                if rag_context:
                    logger.info(f"Universal RAG: Found relevant context (len: {len(rag_context)})")
            except Exception as e:
                logger.error(f"Error getting RAG context: {e}")

        # --- MULTI-PROVIDER FALLBACK LOGIC (Priority: Gemini → OpenRouter → Groq) ---
        
        # 1. GEMINI PRIMARY (5 keys with rotation, context caching enabled)
        if self.gemini_clients:
            for i, client in enumerate(self.gemini_clients):
                try:
                    logger.info(f"Trying Gemini Client #{i+1}/{len(self.gemini_clients)}")
                    has_content = False
                    async for chunk in self._ask_stream_gemini_client(user_id, content, client, external_history, rag_context):
                        if chunk:
                            if not has_content:
                                logger.info(f"✅ Gemini client #{i+1} started responding")
                                has_content = True
                            yield chunk
                    if has_content:
                        return
                except Exception as e:
                    logger.warning(f"Gemini client #{i+1} failed: {e}")
                    continue

        # 2. OpenRouter FALLBACK (Pool of free models)
        if self.or_client:
            logger.info("Gemini exhausted, trying OpenRouter fallback...")
            for model_id in self.or_models:
                try:
                    logger.info(f"Trying OpenRouter model: {model_id}")
                    has_content = False
                    
                    gen = self._ask_stream_openrouter_model(user_id, content, model_id, external_history, rag_context)
                    
                    try:
                        first_chunk = await asyncio.wait_for(gen.__anext__(), timeout=15.0)
                        if first_chunk:
                            logger.info(f"✅ OpenRouter {model_id} started responding")
                            has_content = True
                            yield first_chunk
                    except asyncio.TimeoutError:
                        logger.warning(f"Timeout waiting for {model_id}")
                        continue
                    except StopAsyncIteration:
                        continue
                    
                    async for chunk in gen:
                        if chunk:
                            yield chunk
                    
                    if has_content:
                        return
                except Exception as e:
                    logger.warning(f"OpenRouter model {model_id} failed: {e}")
                    continue

        # 3. Groq LAST RESORT (if enabled)
        if self.groq_client:
            try:
                logger.info(f"Trying Groq last resort: {self.groq_model}")
                has_content = False
                gen = self._ask_stream_groq(user_id, content, external_history, rag_context)
                
                try:
                    first_chunk = await asyncio.wait_for(gen.__anext__(), timeout=15.0)
                    if first_chunk:
                        logger.info(f"✅ Groq {self.groq_model} started responding")
                        has_content = True
                        yield first_chunk
                except asyncio.TimeoutError:
                    logger.warning("Timeout waiting for Groq")
                except StopAsyncIteration:
                    pass
                    
                async for chunk in gen:
                    if chunk:
                        yield chunk
                if has_content:
                    return
            except Exception as e:
                logger.warning(f"Groq failed: {e}")

        # Если дошли сюда — все провайдеры и ключи упали
        logger.error(f"All AI providers and keys failed for user {user_id}")
        yield "\n[Ошибка: Все ИИ-сервисы временно недоступны. Попробуйте позже.]"


    async def _ask_stream_openrouter_model(self, user_id: int, content: str, model_id: str, external_history: Optional[str] = None, rag_context: str = "") -> AsyncGenerator[str, None]:
        """Внутренний метод для стриминга через конкретную модель OpenRouter."""
        try:
            messages = []
            system_msg = self.system_instruction or ""
            
            if rag_context:
                system_msg += f"\n\n### ДАННЫЕ ИЗ БАЗЫ ЗНАНИЙ (ИСПОЛЬЗУЙ ПРИ ОТВЕТЕ):\n{rag_context}\n"

            if system_msg:
                messages.append({"role": "system", "content": system_msg})
            
            if self.knowledge_base:
                links = self.knowledge_base.get_file_links()
                if links:
                    links_block = "\n### ССЫЛКИ НА ДОКУМЕНТЫ БАЗЫ ЗНАНИЙ:\n"
                    for fname, url in links.items():
                        links_block += f"- {fname}: {url}\n"
                    messages[0]["content"] += links_block

            if external_history and external_history.strip():
                clean_history = external_history[-10000:]
                messages.append({"role": "user", "content": f"Краткая история диалога:\n{clean_history}"})
                messages.append({"role": "assistant", "content": "Понял, учитываю историю."})

            messages.append({"role": "user", "content": content})

            response = await self.or_client.chat.completions.create(
                model=model_id,
                messages=messages,
                stream=True,
                temperature=0.7
            )

            full_reply = ""
            async for chunk in response:
                if chunk.choices[0].delta.content:
                    text = chunk.choices[0].delta.content
                    full_reply += text
                    yield text
        except Exception as e:
            raise e

    async def _ask_stream_groq(self, user_id: int, content: str, external_history: Optional[str] = None, rag_context: str = "") -> AsyncGenerator[str, None]:
        """Внутренний метод для стриминга через Groq (сверхбыстрый LPU)."""
        try:
            messages = []
            system_msg = self.system_instruction or ""
            
            if rag_context:
                system_msg += f"\n\n### ДАННЫЕ ИЗ БАЗЫ ЗНАНИЙ (ИСПОЛЬЗУЙ ПРИ ОТВЕТЕ):\n{rag_context}\n"

            if system_msg:
                messages.append({"role": "system", "content": system_msg})
            
            if self.knowledge_base:
                links = self.knowledge_base.get_file_links()
                if links:
                    links_block = "\n### ССЫЛКИ НА ДОКУМЕНТЫ БАЗЫ ЗНАНИЙ:\n"
                    for fname, url in links.items():
                        links_block += f"- {fname}: {url}\n"
                    messages[0]["content"] += links_block

            if external_history and external_history.strip():
                clean_history = external_history[-10000:]
                messages.append({"role": "user", "content": f"Краткая история диалога:\n{clean_history}"})
                messages.append({"role": "assistant", "content": "Понял, учитываю историю."})

            messages.append({"role": "user", "content": content})

            response = await self.groq_client.chat.completions.create(
                model=self.groq_model,
                messages=messages,
                stream=True,
                temperature=0.7
            )

            full_reply = ""
            async for chunk in response:
                if chunk.choices[0].delta.content:
                    text = chunk.choices[0].delta.content
                    full_reply += text
                    yield text
        except Exception as e:
            raise e

    async def _ask_stream_gemini_client(self, user_id: int, content: str, client: genai.Client, external_history: Optional[str] = None, rag_context: str = "") -> AsyncGenerator[str, None]:
        """Внутренний метод для стриминга через конкретного клиента Gemini."""
        # 1. Инъекция контекста из RAG (если есть)
        if rag_context:
            content = f"### ДАННЫЕ ИЗ БАЗЫ ЗНАНИЙ:\n{rag_context}\n\n### ВОПРОС ПОЛЬЗОВАТЕЛЯ:\n{content}"

        # 2. Инъекция истории из Таблицы
        history_injection = ""
        if external_history and external_history.strip():
            # Очистка истории от фраз-паразитов эскалации и системных логов
            clean_external_history = external_history[-15000:]
            bad_phrases = [
                "Передаю ваш запрос специалисту",
                "свяжется с вами в ближайшее время",
                "[SYSTEM: Продолжение диалога]",
                "[SYSTEM: Новая сессия]"
            ]
            for phrase in bad_phrases:
                clean_external_history = clean_external_history.replace(phrase, "")
            
            # Очищаем временную историю в памяти, если пришел свежий дамп из Таблицы
            # Это гарантирует, что Таблица — главный источник правды.
            self.clear_history(user_id)
            self._add_to_history(user_id, "user", f"Вот история наших предыдущих обсуждений (учитывай её, но не повторяй системные ошибки): {clean_external_history}")
            self._add_to_history(user_id, "model", "Поняла. Я вспомнила детали прошлых диалогов и готова продолжать общение.")

        # Добавляем сообщение пользователя в историю
        if content:
             self._add_to_history(user_id, "user", content)
        
        # Получаем всю историю для отправки
        history = self._get_or_create_history(user_id)
        
        # Использование инструментов из self.tools (уже содержат Web Search и get_promotions)
        tools = self.tools

        # Graceful degradation: если KnowledgeBase недоступен, продолжаем без кэша
        cache_name = None
        try:
            if self.knowledge_base:
                cache_name = await self.knowledge_base.get_cache_name()
        except Exception as e:
            logger.warning(f"⚠️ Failed to get cache_name (continuing without RAG): {e}")
            cache_name = None
        
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
            effective_system_instruction = self.system_instruction
            
            # Внедряем ссылки на документы базы знаний, чтобы ИИ мог их цитировать
            if self.knowledge_base:
                links = self.knowledge_base.get_file_links()
                if links:
                    logger.info(f"Adding {len(links)} document links to system instruction")
                    links_block = "\n### ССЫЛКИ НА ДОКУМЕНТЫ БАЗЫ ЗНАНИЙ (ДЛЯ ЦИТИРОВАНИЯ):\n"
                    for fname, url in links.items():
                        links_block += f"- {fname}: {url}\n"
                    links_block += "\n**ПРАВИЛО:** Если ты используешь данные из файла выше, в конце ответа ОБЯЗАТЕЛЬНО напиши: 'Подробнее см. в документе: [Название документа](ссылка)'."
                    effective_system_instruction += links_block

            config_params['system_instruction'] = effective_system_instruction
            config_params['tools'] = tools
            
            # Внедряем файлы из KnowledgeBase в историю, если кэш не используется (простой RAG)
            try:
                if self.knowledge_base:
                    active_files = await self.knowledge_base.get_active_files()
                    if active_files:
                        logger.info(f"Adding {len(active_files)} files to contents for RAG (No Cache mode)")
                        file_parts = []
                        for gf in active_files:
                            file_parts.append(types.Part.from_uri(
                                file_uri=gf.uri,
                                mime_type=gf.mime_type
                            ))
                        # Создаем временную копию истории для этого запроса
                        history_with_context = [
                            types.Content(role='user', parts=file_parts)
                        ] + history
                        history = history_with_context
            except Exception as e:
                logger.error(f"Error adding RAG files to contents: {e}")
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
                logger.info(f"Starting Gemini stream for user {user_id} (Attempt {attempt+1}/{MAX_RETRIES+1})")
                
                # Таймаут на инициализацию стрима (60 секунд)
                STREAM_INIT_TIMEOUT = 60.0
                try:
                    stream = await asyncio.wait_for(
                        client.aio.models.generate_content_stream(**generate_kwargs),
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
                error_str = str(e)
                # Проверка на ошибки кэша: истекший, невалидный, или устаревший API
                if ('CachedContent' in error_str and ('403' in error_str or 'PERMISSION_DENIED' in error_str)) or \
                   'google_search' in error_str or \
                   'not supported' in error_str.lower():
                    logger.warning(f"❌ Cache error or outdated API: {e}")
                    # Инвалидировать кэш в Knowledge Base
                    await self.knowledge_base.invalidate_cache()
                    # Пересоздать config БЕЗ кэша для повтора
                    config_params['system_instruction'] = self.system_instruction
                    config_params['tools'] = tools
                    if 'cached_content' in config_params:
                        del config_params['cached_content']
                    config = types.GenerateContentConfig(**config_params)
                    generate_kwargs['config'] = config
                
                if attempt < MAX_RETRIES:
                    # Exponential Backoff: 1s, 2s, 4s...
                    wait_time = (2 ** attempt) + 0.1
                    logger.info(f"🔄 Retrying Gemini in {wait_time}s")
                    await asyncio.sleep(wait_time) 
                    continue # Идем на следующий круг
                else:
                    # Все попытки для Gemini исчерпаны
                    logger.error(f"All {MAX_RETRIES+1} attempts failed for user {user_id}")
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
            
            # Архивация истории для "памяти"
            if self.memory_archiver:
                 asyncio.create_task(self.memory_archiver.archive_user_history(
                     user_id, 
                     self.user_histories.get(user_id, [])
                 ))

    async def ask(self, user_id: int, content: str, external_history: Optional[str] = None) -> Optional[str]:
        """Отправляет запрос в Gemini и возвращает полный ответ (через стриминг)."""
        full_reply_parts = []
        async for part in self.ask_stream(user_id, content, external_history):
            full_reply_parts.append(part)
        return "".join(full_reply_parts) if full_reply_parts else None

    async def _ask_stream_openrouter(self, user_id: int, content: str, external_history: Optional[str] = None) -> AsyncGenerator[str, None]:
        """Внутренний метод для стриминга через OpenRouter."""
        MAX_OR_RETRIES = len(self.or_models)
        full_reply = ""
        current_or_model = "unknown"
        
        for attempt in range(MAX_OR_RETRIES):
            try:
                messages = []
                if self.system_instruction:
                    messages.append({"role": "system", "content": self.system_instruction})
                
                # --- Rate Limiter (Basic) ---
                # Даем паузу перед запросами к OpenRouter чтобы не ловить 429
                # Особенно важно для бесплатных моделей
                last_req_time = getattr(self, '_last_request_time', 0)
                time_since_last = time.time() - last_req_time
                if time_since_last < 2.0: # Минимум 2 секунды между запросами
                    sleep_time = 2.0 - time_since_last
                    logger.info(f"Rate limit protection: sleeping {sleep_time:.2f}s")
                    await asyncio.sleep(sleep_time)
                self._last_request_time = time.time()
                # -----------------------------

                if self.knowledge_base:
                    links = self.knowledge_base.get_file_links()
                    if links:
                        links_block = "\n### ССЫЛКИ НА ДОКУМЕНТЫ БАЗЫ ЗНАНИЙ:\n"
                        for fname, url in links.items():
                            links_block += f"- {fname}: {url}\n"
                        messages[0]["content"] += links_block

                if external_history and external_history.strip():
                    clean_history = external_history[-3000:]
                    messages.append({"role": "user", "content": f"Краткая история диалога:\n{clean_history}"})
                    messages.append({"role": "assistant", "content": "Понял, учитываю историю."})

                messages.append({"role": "user", "content": content})

                current_or_model = self.or_models[self.current_or_model_index]
                logger.info(f"OpenRouter stream for user {user_id} with model {current_or_model} (Attempt {attempt+1}/{MAX_OR_RETRIES})")

                response = await self.or_client.chat.completions.create(
                    model=current_or_model,
                    messages=messages,
                    stream=True,
                    temperature=0.7
                )

                async for chunk in response:
                    if chunk.choices[0].delta.content:
                        text = chunk.choices[0].delta.content
                        full_reply += text
                        yield text
                
                if full_reply:
                    break
                else:
                    raise ValueError("Received empty response from OpenRouter model")

            except Exception as e:
                logger.error(f"OpenRouter Error with model {current_or_model}: {e}")
                if attempt < MAX_OR_RETRIES - 1:
                    logger.warning(f"Rotating OpenRouter index and retrying (attempt {attempt+1}/{MAX_OR_RETRIES})")
                    self.current_or_model_index = (self.current_or_model_index + 1) % len(self.or_models)
                    await asyncio.sleep(1) 
                else:
                    logger.error(f"All {MAX_OR_RETRIES} OpenRouter models failed")
                    raise e 

        if self.memory_archiver and full_reply:
            fake_history = [
                types.Content(role="user", parts=[types.Part(text=content)]),
                types.Content(role="model", parts=[types.Part(text=full_reply)])
            ]
            asyncio.create_task(self.memory_archiver.archive_user_history(user_id, fake_history))

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
