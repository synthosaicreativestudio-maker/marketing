import os
import asyncio
import time
import logging
from typing import Dict, List, Optional, AsyncGenerator

from google import genai
from google.genai import types
from openai import AsyncOpenAI

# Импорты для инструментов
from promotions_api import get_promotions_json
from sheets_gateway import AsyncGoogleSheetsGateway
from structured_logging import log_llm_metrics
from memory_manager_sqlite import SQLiteMemoryManager


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
        
        logger.info(f"Found {len(gemini_keys)} Gemini API keys in environment.")
        logger.info(f"Proxy config: base_url={proxyapi_base_url}, key_present={bool(proxyapi_key)}")
        
        if not proxyapi_base_url:
            raise RuntimeError(
                "Proxy-only mode enforced: PROXYAPI_BASE_URL is required for Gemini access."
            )
        
        proxy_url = os.getenv("TINYPROXY_URL")
        if proxy_url:
            os.environ["HTTP_PROXY"] = proxy_url
            os.environ["HTTPS_PROXY"] = proxy_url
            logger.info("System-wide PROXY (TINYPROXY) activated for AI services")
        
        for key in gemini_keys:
            try:
                logger.info(f"Attempting to init Gemini client with key ...{key[-4:]}")
                if proxyapi_base_url:
                    # Вариант Б: через прокси-релей (например, ProxyAPI.ru)
                    api_version = os.getenv("PROXYAPI_VERSION", "v1beta")
                    client = genai.Client(
                        api_key=key,
                        http_options=types.HttpOptions(
                            api_version=api_version,
                            base_url=proxyapi_base_url if ("proxyapi.ru" in proxyapi_base_url.lower() or "relay" in proxyapi_base_url.lower()) else None
                        )
                    )
                else:
                    client = genai.Client(api_key=key)

                self.gemini_clients.append(client)
                logger.info(f"Gemini client initialized with key ...{key[-4:]}")
            except Exception as e:
                logger.error(f"CRITICAL: Failed to init Gemini client with key ...{key[-4:]}: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
        
        self.client = self.gemini_clients[0] if self.gemini_clients else None
        
        # Пул моделей Gemini с ротацией (приоритет: от мощной к легкой)
        gemini_models_str = os.getenv("GEMINI_MODELS", "gemini-3-flash-preview,gemini-2.5-flash,gemini-2.5-flash-lite,gemini-flash-latest")
        self.gemini_models = [m.strip() for m in gemini_models_str.split(",") if m.strip()]
        self.gemini_model = self.gemini_models[0] if self.gemini_models else os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.current_gemini_model_index = 0
        logger.info(f"Gemini models pool: {self.gemini_models}")
        

        # 2. OpenRouter — ОТКЛЮЧЕН (упрощение архитектуры)
        self.or_client = None
        self.or_api_key = None
        self.or_models = []
        logger.info("OpenRouter: DISABLED (simplified architecture)")
        
        # 3. Groq — ОТКЛЮЧЕН (упрощение архитектуры)
        self.groq_client = None
        self.groq_api_key = None
        self.groq_model = None
        logger.info("Groq: DISABLED (simplified architecture)")

        # 4. OpenAI — ОТКЛЮЧЕН (упрощение архитектуры)
        self.oa_client = None
        self.oa_api_key = None
        self.oa_model = None
        logger.info("OpenAI: DISABLED (simplified architecture)")


        
        # Загрузка системного промпта
        system_prompt_path = os.getenv("SYSTEM_PROMPT_FILE", "system_prompt.txt")
        self.system_instruction = None
        
        # Инициализация Knowledge Base (RAG)
        from drive_service import DriveService
        from knowledge_base import KnowledgeBase
        from memory_archiver import MemoryArchiver
        
        self.drive_service = DriveService()
        self.knowledge_base = KnowledgeBase(self.drive_service)
        # 5. Инициализация памяти SQLite
        try:
            from memory_manager_sqlite import SQLiteMemoryManager
            self.sqlite_memory = SQLiteMemoryManager()
            logger.info("SQLite Memory Manager integrated into GeminiService.")
        except Exception as e:
            logger.error(f"Failed to integrate SQLite Memory: {e}")
            self.sqlite_memory = None
        
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

1. **ИСТОЧНИКИ И ПРИОРИТЕТЫ (КРИТИЧНО):** 
   - СНАЧАЛА используй **Внутренние скрипты** из раздела "Скрипты и сценарии" основного промпта.
   - ЗАТЕМ используй **Базу Знаний (RAG)** из файлов, переданных в контексте. 
   - НИКОГДА не отказывай в предоставлении информации, если она есть во внутренних регламентах.

2. **ИНСТРУМЕНТЫ (TOOLS):** 
   - Если вопрос касается цен, акций, ипотеки - ТЫ ОБЯЗАН вызвать функцию `get_promotions`.
3. **ПОИСК КОНТАКТОВ:** 
   - Если пользователь просит контакт - СНАЧАЛА ищи в `system_prompt` (техподдержка), ЗАТЕМ в файле «Телефонный справочник сотрудников и партнеров компании.txt» (из БЗ), НО НИКОГДА не выводи ссылку на сам файл. Вместо этого всегда давай ссылку на актуальный онлайн-справочник: https://ecosystem.etagi.com/phonebook.
4. **ЗАЩИТА ССЫЛОК И АТРИБУЦИЯ:** 
   - Оформляй все ссылки СТРОГО через Markdown в формате: [Название](URL).
   - ЗАПРЕЩЕНО выводить "голые" URL-адреса в тексте (например, https://example.com).
   - ОБЯЗАТЕЛЬНО указывай источник информации (например: "Согласно базе знаний «Этажи»...").
5. **СТИЛЬ И ЭМОДЗИ:**
   - Используй Markdown (жирный текст) для акцентов.
   - Эмодзи: 2–5 в каждом ответе для создания живой и поддерживающей атмосферы.
   - Ты — дружелюбный наставник. Обращайся к пользователю по имени из [USER PROFILE] и поддерживай его.

ТЫ — продвинутый ассистент, работающий на базе знаний компании. Генерируй лучшие предложения, используя актуальные регламенты.

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
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash") 
        self.max_history_messages = 12  # Оптимально для быстрого скользящего окна (6 пар)
        
        # Кэш для акций (Simple TTL Cache)
        self._promotions_cache = None
        self._promotions_cache_time = 0
        self._promotions_cache_ttl = 600  # 10 минут
        
        # Tools (Google Search, etc) - будут загружены в initialize()
        self.tools = None

    async def initialize(self):
        """Async init for Knowledge Base with Rules and Tools."""
        # Активация инструментов (Google Search + Custom Functions)
        enable_search = os.getenv("ENABLE_GOOGLE_SEARCH", "false").lower() == "true"
        
        get_promotions_func = types.FunctionDeclaration(
            name="get_promotions",
            description="Получает список актуальных акций, скидок и ипотечных программ из Google Таблицы.",
            parameters=types.Schema(
                type="OBJECT",
                properties={}  # Нет входных параметров
            )
        )
        
        self.tools = []
        if enable_search:
            self.tools.append(types.Tool(google_search=types.GoogleSearch()))
            logger.info("Google Search tool activated in GeminiService.")
        else:
            logger.info("Google Search tool is DISABLED (via env).")
            
        self.tools.append(types.Tool(function_declarations=[get_promotions_func]))
        logger.info("'get_promotions' tool activated in GeminiService.")

        if self.knowledge_base:
            await self.knowledge_base.initialize()
            
            # Запускаем фоновое автообновление каждые 6 часов
            try:
                kb_refresh_hours = int(os.getenv("KB_REFRESH_HOURS", "12"))
            except ValueError:
                kb_refresh_hours = 12
            await self.knowledge_base.start_auto_refresh(interval_hours=kb_refresh_hours)
            
            # ПРИНУДИТЕЛЬНО запускаем первое обновление кэша с нашими правилами
            asyncio.create_task(self.knowledge_base.refresh_cache(
                system_instruction=self.system_instruction,
                tools=self.tools
            ))

    def is_enabled(self) -> bool:
        """Проверяет, доступен ли какой-либо ИИ-сервис."""
        return self.client is not None or self.or_client is not None or (hasattr(self, 'oa_client') and self.oa_client is not None)

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
                # 1. Query Expansion (Техника 3: Расширение запроса силами Gemini)
                # Генерируем расширенный запрос (синонимы) только если это не пустой контент
                search_query = content
                if content.strip() and len(content.split()) > 1:
                    try:
                        # Используем легкую модель для быстрой генерации синонимов
                        expansion_prompt = f"Действуй как эксперт по поиску. Напиши через пробел 3-4 синонима или связанных термина для поискового запроса: '{content}'. Пиши ТОЛЬКО термины. Например: 'продажа квартиры' -> 'реализация недвижимости выгрузка объектов'."
                        
                        # Делаем это отдельным быстрым вызовом (не стрим)
                        expansion_resp = await self.client.aio.models.generate_content(
                            model="gemini-2.0-flash-lite-preview-02-05", # Самая быстрая для этой задачи
                            contents=expansion_prompt,
                            config=types.GenerateContentConfig(temperature=0.0, max_output_tokens=50)
                        )
                        if expansion_resp.text:
                            search_query = f"{content} {expansion_resp.text.strip()}"
                            logger.info(f"Query expansion: '{content}' -> '{search_query}'")
                    except Exception as ex_err:
                        logger.warning(f"Query expansion failed (falling back to original): {ex_err}")
                
                # 2. Поиск с расширенным запросом
                # top_k увеличен до 10 (Техника: "Широкое окно"), window_size=2 (Техника 2: Sentence Window)
                rag_context = self.knowledge_base.get_relevant_context(search_query, top_k=10)
                
                if rag_context:
                    logger.info(f"Universal RAG: Found relevant context (len: {len(rag_context)})")
            except Exception as e:
                logger.error(f"Error getting RAG context: {e}")

        # --- MULTI-PROVIDER FALLBACK LOGIC (Priority: Gemini → OpenRouter → Groq) ---
        
        # 1. GEMINI PRIMARY (model rotation + key rotation)
        # Стратегия: пробуем все ключи с моделью #1, затем все ключи с моделью #2, и т.д.
        if self.gemini_clients and self.gemini_models:
            for model_idx, model_name in enumerate(self.gemini_models):
                for key_idx, client in enumerate(self.gemini_clients):
                    try:
                        logger.info(f"Trying Gemini Model '{model_name}' with Key #{key_idx+1}/{len(self.gemini_clients)}")
                        has_content = False
                        async for chunk in self._ask_stream_gemini_client(user_id, content, client, external_history, rag_context, model_name):
                            if chunk:
                                if not has_content:
                                    logger.info(f"✅ Gemini '{model_name}' + key #{key_idx+1} started responding")
                                    has_content = True
                                yield chunk
                        if has_content:
                            return
                    except Exception as e:
                        logger.warning(f"Gemini '{model_name}' + key #{key_idx+1} failed: {e}")
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

        # 4. OpenAI FINAL FALLBACK (If configured and not already tried via OR)
        if self.oa_client:
            try:
                logger.info(f"Trying OpenAI final fallback: {self.oa_model}")
                has_content = False
                messages = [
                    {"role": "system", "content": self.system_instruction},
                    {"role": "user", "content": f"### КОНТЕКСТ БАЗЫ ЗНАНИЙ:\n{rag_context}\n\n### ВОПРОС:\n{content}"}
                ]
                
                response = await self.oa_client.chat.completions.create(
                    model=self.oa_model,
                    messages=messages,
                    stream=True,
                    temperature=0.7
                )
                
                async for chunk in response:
                    text = chunk.choices[0].delta.content
                    if text:
                        if not has_content:
                            logger.info(f"✅ OpenAI {self.oa_model} started responding")
                            has_content = True
                        yield text
                
                if has_content:
                    return
            except Exception as e:
                logger.warning(f"OpenAI fallback failed: {e}")

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

    async def _ask_stream_openai(self, user_id: int, content: str, external_history: Optional[str] = None, rag_context: str = "") -> AsyncGenerator[str, None]:
        """Потоковая генерация ответа через OpenAI."""
        try:
            prompt = content
            if rag_context:
                prompt = f"Контекст из базы знаний:\n{rag_context}\n\nЗапрос пользователя: {content}"
            
            system_instruction = self.system_instruction
            messages = [{"role": "system", "content": system_instruction}]
            
            # Добавляем историю если есть
            if external_history:
                messages.append({"role": "system", "content": f"Предыдущий контекст: {external_history}"})
            
            messages.append({"role": "user", "content": prompt})

            response = await self.oa_client.chat.completions.create(
                model=self.oa_model,
                messages=messages,
                stream=True
            )

            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"Error in _ask_stream_openai: {e}")
            raise e

    async def _ask_stream_gemini_client(self, user_id: int, content: str, client: genai.Client, external_history: Optional[str] = None, rag_context: str = "", model_name: Optional[str] = None) -> AsyncGenerator[str, None]:
        """Внутренний метод для стриминга через конкретного клиента Gemini с указанной моделью."""
        # Метрики LLM: замер времени
        llm_start_time = time.perf_counter()
        
        # Используем переданную модель или дефолтную
        effective_model = model_name or self.gemini_model
        # 1. Инъекция контекста из RAG (если есть)
        structured_content = ""
        if rag_context:
            structured_content += f"### ДАННЫЕ ИЗ БАЗЫ ЗНАНИЙ (УРОВЕНЬ 2):\n{rag_context}\n\n"
        
        structured_content += f"### ВОПРОС ПОЛЬЗОВАТЕЛЯ:\n{content}"

        # 2. Инъекция истории
        # ПРИОРИТЕТ 1: Локальная память SQLite
        local_history = ""
        if self.sqlite_memory:
            try:
                local_history = await self.sqlite_memory.get_history_text(user_id)
                if local_history:
                    structured_content += f"### ИСТОРИЯ ПОСЛЕДНИХ СООБЩЕНИЙ (MEMORY):\n{local_history}\n\n"
                    logger.debug(f"Memory: injected local SQLite history for {user_id}")
            except Exception as e:
                logger.error(f"Error getting local history for user {user_id}: {e}")

        if not local_history and external_history and external_history.strip():
            # ПРИОРИТЕТ 2: Внешняя история (из Таблицы) — только если локальной нет
            # Оптимизация: инъектируем внешнюю историю только если внутренняя история пуста 
            # (содержит только 2 начальных сообщения: системное и подтверждение)
            history_exists = user_id in self.user_histories and len(self.user_histories[user_id]) > 2
            
            if not history_exists:
                logger.info(f"Injecting external history for user {user_id} (len: {len(external_history)})")
                # Внешняя история уже усечена в AppealsService до 5000 символов
                structured_content += f"### ИСТОРИЯ ПРЕДЫДУЩИХ ОБРАЩЕНИЙ:\n{external_history}\n\n"
                logger.debug(f"Memory: recovered context from External Table for {user_id}")
            else:
                logger.debug(f"Skipping external history injection for user {user_id} (internal history active)")

        # 3. Добавление текущего вопроса в SQLite ДО запроса (чтобы он был в памяти для след. раза)
        if self.sqlite_memory:
            try:
                asyncio.create_task(self.sqlite_memory.add_message(user_id, "user", content))
            except Exception as e:
                logger.error(f"Error adding message to SQLite for user {user_id}: {e}")

        # Добавляем сообщение пользователя в историю
        self._add_to_history(user_id, "user", structured_content)
        
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
            # Внедрение полных файлов отключено для предотвращения перегрузки API и таймаутов.
            # Вместо этого используется классический RAG (передача только релевантных фрагментов текста).
            pass

        else:
            config_params['cached_content'] = cache_name
        
        config = types.GenerateContentConfig(**config_params)
        generate_kwargs = {
            'model': effective_model,
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
                
                # Специфичная обработка ошибки квоты (429) - не ждать, если лимит исчерпан
                if '429' in error_str or 'RESOURCE_EXHAUSTED' in error_str:
                    logger.error(f"❌ Quota exceeded (429) for Gemini: {error_str}")
                    if attempt < MAX_RETRIES:
                        logger.warning("Quota hit, skipping backoff and trying next key/model immediately.")
                        # Мы НЕ ждем, так как 429 обычно не проходит за секунды
                        continue 
                    else:
                        raise e # Пробрасываем выше для перехода к OpenRouter

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
            
            # Сохраняем в SQLite (КРИТИЧНО для памяти)
            asyncio.create_task(self.sqlite_memory.add_message(user_id, "model", full_reply))
            
            # Метрики LLM: логируем время ответа
            llm_duration_ms = (time.perf_counter() - llm_start_time) * 1000
            log_llm_metrics(
                user_id=user_id,
                model=effective_model,
                duration_ms=llm_duration_ms,
                success=True
            )
            logger.info(f"Stream finished for user {user_id}, history updated. Sources: {len(grounding_sources)}, Duration: {llm_duration_ms:.0f}ms")
            
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
    async def wait_for_ready(self):
        """Ожидает инициализации базы знаний."""
        while self._initializing:
            await asyncio.sleep(0.5)
