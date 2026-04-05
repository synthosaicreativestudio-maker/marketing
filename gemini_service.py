import os
import asyncio
import time
import logging
from typing import Dict, List, Optional, AsyncGenerator

from sheets_gateway import AsyncGoogleSheetsGateway
from structured_logging import log_llm_metrics
from drive_service import DriveService
from memory_archiver import MemoryArchiver

logger = logging.getLogger(__name__)

# Google GenAI SDK — ленивый импорт (установится через requirements.txt)
_genai = None
def _get_genai():
    global _genai
    if _genai is None:
        import google.genai as genai
        _genai = genai
    return _genai


class GeminiService:
    """Service to interact with Gemini API directly (no OpenClaw dependency)."""
    
    def __init__(self, promotions_gateway: Optional[AsyncGoogleSheetsGateway] = None) -> None:
        self.promotions_gateway = promotions_gateway
        self.user_histories: Dict[int, List[Dict[str, str]]] = {}
        self.system_prompt_path = os.getenv("SYSTEM_PROMPT_FILE", "system_prompt.txt")
        self.system_prompt_cache_path = os.getenv(
            "SYSTEM_PROMPT_CACHE_FILE",
            os.path.join("logs", "system_prompt_cache.txt"),
        )
        self.system_prompt_refresh_hours = int(
            os.getenv("SYSTEM_PROMPT_REFRESH_HOURS", "168") or 168
        )
        
        # Gemini API конфигурация
        self.api_key = os.getenv("GEMINI_API_KEY", os.getenv("PROXYAPI_KEY", ""))
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite")
        self.proxy_base_url = os.getenv("PROXYAPI_BASE_URL", "")  # US proxy для обхода блокировок
        
        self.client = None
        self._init_client()
        
        self.drive_service = DriveService()
        self.memory_archiver = MemoryArchiver(self.drive_service)
        
        self.system_prompt = ""
        self.system_prompt = self._load_prompt_from_disk()
        
        logger.info(
            f"GeminiService initialized: model={self.model_name}, "
            f"direct_api={bool(self.api_key)}, proxy={self.proxy_base_url or 'none'}"
        )

    def is_enabled(self) -> bool:
        return self.client is not None

    def _init_client(self):
        """Инициализирует Gemini клиент."""
        if not self.api_key:
            logger.warning("GEMINI_API_KEY не найден — AI сервис будет недоступен")
            return
            
        try:
            genai = _get_genai()
            from google.genai import types
            
            http_options = None
            if self.proxy_base_url:
                proxy_url = self.proxy_base_url.rstrip("/")
                # socks5/socks5h: используем как исходящий proxy transport.
                if proxy_url.startswith(("socks5://", "socks5h://")):
                    http_options = types.HttpOptions(
                        client_args={"proxy": proxy_url},
                        async_client_args={"proxy": proxy_url},
                    )
                else:
                    # http/https URL без socks трактуем как reverse-proxy endpoint
                    # для Gemini API (см. docs/GEMINI_PROXY_AMERICAN_SERVER.md).
                    http_options = types.HttpOptions(base_url=proxy_url)

            self.client = genai.Client(
                api_key=self.api_key,
                http_options=http_options,
            )
                
        except Exception as e:
            logger.error(f"Ошибка инициализации Gemini клиента: {e}")
            self.client = None
        
    async def initialize(self):
        """Initializes the service and downloads the dynamic system prompt."""
        await self.refresh_system_prompt(force=False)
        
    async def wait_for_ready(self):
        """Проверяет доступность клиента."""
        return self.client is not None

    def _build_gemini_contents(self, user_id: int, content: str, external_history: Optional[str]) -> list:
        """Формирует список contents для Gemini API из истории."""
        from google.genai import types
        
        history = self._get_or_create_history(user_id)
        contents = []
        
        # Добавляем внешнюю историю из CRM (если есть)
        if external_history and external_history.strip():
            history_text = external_history.strip()
            if len(history_text) > 3000:
                cut_index = history_text.find('\n', len(history_text) - 3000)
                if cut_index == -1:
                    cut_index = history_text.find('. ', len(history_text) - 3000)
                if cut_index != -1:
                    clean_history = history_text[cut_index:].strip()
                else:
                    clean_history = history_text[-3000:]
            else:
                clean_history = history_text
                
            # Краткая история для контекста
            contents.append(types.Content(
                role="user",
                parts=[types.Part(text=f"Краткая история диалога из CRM (справочно):\n{clean_history}")]
            ))
            contents.append(types.Content(
                role="model",
                parts=[types.Part(text="Принято, учла контекст.")]
            ))
        
        # Добавляем историю чата
        for msg in history:
            role = msg.get("role", "user")
            text = msg.get("content", "")
            if role == "user":
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part(text=text)]
                ))
            elif role == "assistant":
                contents.append(types.Content(
                    role="model",
                    parts=[types.Part(text=text)]
                ))
        
        # Текущее сообщение пользователя
        contents.append(types.Content(
            role="user",
            parts=[types.Part(text=content)]
        ))
        
        return contents

    # ------------------------------------------------------------------
    # Retry helpers (transient WARP/proxy failures)
    # ------------------------------------------------------------------
    _MAX_RETRIES = 3
    _RETRY_DELAYS = (3, 6, 12)  # seconds between attempts

    @staticmethod
    def _is_transient(exc: Exception) -> bool:
        """Return True if the error looks like a transient proxy/network glitch."""
        msg = str(exc).lower()
        transient_markers = (
            "connection",
            "connect",
            "timeout",
            "timed out",
            "reset by peer",
            "broken pipe",
            "eof",
            "socks",
            "proxy",
            "503",
            "unavailable",
            "temporarily",
        )
        return any(m in msg for m in transient_markers)

    async def ask_stream(self, user_id: int, content: str, external_history: Optional[str] = None, system_context: Optional[str] = None) -> AsyncGenerator[str, None]:
        """Main entrypoint for chat generation via Gemini API with streaming.

        Includes automatic retry (up to 3 attempts) for transient proxy failures
        so that short WARP tunnel drops don't immediately surface as errors.
        """
        llm_start_time = time.perf_counter()

        if not self.client:
            logger.error("Gemini клиент не инициализирован")
            yield "__ERROR__ Gemini API недоступен"
            return

        from google.genai import types

        # Собираем системный промпт
        full_system = self.system_prompt or "You are a helpful assistant."
        if system_context:
            full_system += "\n\n" + system_context

        # Формируем contents из истории
        contents = self._build_gemini_contents(user_id, content, external_history)

        # Настройки генерации
        config = types.GenerateContentConfig(
            temperature=0.7,
            top_p=0.95,
            max_output_tokens=2048,
            system_instruction=full_system,
        )

        for attempt in range(1, self._MAX_RETRIES + 1):
            try:
                # Streaming вызов
                full_reply = ""
                stream = await self.client.aio.models.generate_content_stream(
                    model=self.model_name,
                    contents=contents,
                    config=config,
                )
                async for chunk in stream:
                    if chunk.text:
                        full_reply += chunk.text
                        yield chunk.text

                # Update history
                if full_reply:
                    self._add_to_history(user_id, "user", content)
                    self._add_to_history(user_id, "assistant", full_reply)

                    llm_duration_ms = (time.perf_counter() - llm_start_time) * 1000
                    log_llm_metrics(
                        user_id=user_id,
                        model=self.model_name,
                        duration_ms=llm_duration_ms,
                        success=True,
                    )

                    if self.memory_archiver:
                        asyncio.create_task(
                            self.memory_archiver.archive_user_history(
                                user_id,
                                self.user_histories.get(user_id, []),
                            )
                        )
                else:
                    llm_duration_ms = (time.perf_counter() - llm_start_time) * 1000
                    log_llm_metrics(
                        user_id=user_id,
                        model=self.model_name,
                        duration_ms=llm_duration_ms,
                        success=False,
                    )
                return  # success — exit retry loop

            except Exception as e:
                if attempt < self._MAX_RETRIES and self._is_transient(e):
                    delay = self._RETRY_DELAYS[attempt - 1]
                    logger.warning(
                        "Gemini stream attempt %d/%d failed (transient): %s. "
                        "Retrying in %ds…",
                        attempt,
                        self._MAX_RETRIES,
                        e,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                # Non-transient or last attempt — propagate
                logger.error("Ошибка Gemini API stream: %s", e)
                llm_duration_ms = (time.perf_counter() - llm_start_time) * 1000
                log_llm_metrics(
                    user_id=user_id,
                    model=self.model_name,
                    duration_ms=llm_duration_ms,
                    success=False,
                )
                raise

    async def ask(self, user_id: int, content: str, external_history: Optional[str] = None, system_context: Optional[str] = None) -> Optional[str]:
        """Отправляет запрос (не-streaming) с retry для WARP."""
        if not self.client:
            logger.error("Gemini клиент не инициализирован")
            return None

        from google.genai import types

        full_system = self.system_prompt or "You are a helpful assistant."
        if system_context:
            full_system += "\n\n" + system_context

        contents = self._build_gemini_contents(user_id, content, external_history)

        config = types.GenerateContentConfig(
            temperature=0.7,
            top_p=0.95,
            max_output_tokens=2048,
            system_instruction=full_system,
        )

        for attempt in range(1, self._MAX_RETRIES + 1):
            try:
                response = await self.client.aio.models.generate_content(
                    model=self.model_name,
                    contents=contents,
                    config=config,
                )

                full_reply = response.text if response.text else ""

                if full_reply:
                    self._add_to_history(user_id, "user", content)
                    self._add_to_history(user_id, "assistant", full_reply)

                return full_reply if full_reply else None

            except Exception as e:
                if attempt < self._MAX_RETRIES and self._is_transient(e):
                    delay = self._RETRY_DELAYS[attempt - 1]
                    logger.warning(
                        "Gemini ask attempt %d/%d failed (transient): %s. "
                        "Retrying in %ds…",
                        attempt,
                        self._MAX_RETRIES,
                        e,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.error("Ошибка Gemini API (non-stream): %s", e)
                return None
        return None

    # --- History Management ---

    def _get_or_create_history(self, user_id: int) -> List[Dict[str, str]]:
        if user_id not in self.user_histories:
            self.user_histories[user_id] = []
        return self.user_histories[user_id]

    def _add_to_history(self, user_id: int, role: str, content: str) -> None:
        history = self._get_or_create_history(user_id)
        history.append({"role": role, "content": content})
        # Keep tail of 30 messages max
        if len(history) > 30:
            history[:] = history[-30:]

    def clear_history(self, user_id: int) -> None:
        """Очищает историю диалога для пользователя."""
        if user_id in self.user_histories:
            del self.user_histories[user_id]
            logger.info(f"Cleared chat history for user {user_id}")
            
    # --- Admin Dashboard Compatibility ---
    
    async def refresh_system_prompt(self, force: bool = False) -> bool:
        """Downloads the system prompt from Google Docs and applies it."""
        if not force:
            cached_prompt = self._load_cached_prompt_if_fresh()
            if cached_prompt:
                self.system_prompt = cached_prompt
                logger.info(
                    "System prompt loaded from cache (ttl=%sh).",
                    self.system_prompt_refresh_hours,
                )
                return True

        doc_id = (
            os.getenv("SYSTEM_PROMPT_DOC", "")
            or os.getenv("SYSTEM_PROMPT_DOC_ID", "")
            or os.getenv("SYSTEM_PROMPT_GOOGLE_DOC_ID", "")
        )
        if not doc_id or not self.drive_service:
            logger.warning("DriveService or system prompt doc ID missing, using local prompt cache.")
            self.system_prompt = self._load_prompt_from_disk(
                fallback=self.system_prompt or "You are a helpful assistant."
            )
            return True
            
        try:
            downloaded = await asyncio.to_thread(
                self.drive_service.download_file,
                file_id=doc_id,
                file_name="system_prompt.txt",
                mime_type="application/vnd.google-apps.document"
            )
            if downloaded:
                with open(downloaded, "r", encoding="utf-8") as f:
                    self.system_prompt = f.read()
                self._write_prompt_cache(self.system_prompt)
                logger.info("System prompt successfully refreshed from Google Docs.")
                return True
        except Exception as e:
            logger.error(f"Failed to refresh system prompt: {e}")

        fallback_prompt = self._load_prompt_from_disk(fallback=self.system_prompt)
        if fallback_prompt:
            self.system_prompt = fallback_prompt
            logger.warning("Using cached/local system prompt after refresh failure.")
            return True

        return False

    async def close(self) -> None:
        """Закрывает HTTP-клиент."""
        if self.client and hasattr(self.client, '_session') and self.client._session:
            await self.client._session.close()

    def _load_prompt_from_disk(self, fallback: str = "") -> str:
        for path in (self.system_prompt_cache_path, self.system_prompt_path):
            try:
                with open(path, "r", encoding="utf-8") as file_obj:
                    return file_obj.read()
            except Exception:
                continue
        return fallback

    def _load_cached_prompt_if_fresh(self) -> Optional[str]:
        try:
            if not os.path.exists(self.system_prompt_cache_path):
                return None
            age_seconds = time.time() - os.path.getmtime(self.system_prompt_cache_path)
            if age_seconds > self.system_prompt_refresh_hours * 3600:
                return None
            with open(self.system_prompt_cache_path, "r", encoding="utf-8") as file_obj:
                return file_obj.read()
        except Exception as exc:
            logger.debug("Failed to read prompt cache: %s", exc, exc_info=True)
            return None

    def _write_prompt_cache(self, content: str) -> None:
        try:
            cache_dir = os.path.dirname(self.system_prompt_cache_path)
            if cache_dir:
                os.makedirs(cache_dir, exist_ok=True)
            with open(self.system_prompt_cache_path, "w", encoding="utf-8") as file_obj:
                file_obj.write(content)
        except Exception as exc:
            logger.error("Failed to write prompt cache: %s", exc)
