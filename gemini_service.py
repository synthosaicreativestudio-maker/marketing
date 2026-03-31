import os
import asyncio
import time
import logging
import json
import re
import httpx
from typing import Any, Dict, List, Optional, AsyncGenerator

from sheets_gateway import AsyncGoogleSheetsGateway
from structured_logging import log_llm_metrics
from drive_service import DriveService
from memory_archiver import MemoryArchiver
from utils import sanitize_ai_text_plain

logger = logging.getLogger(__name__)

_OPENCLAW_TAG_FRAGMENT_RE = re.compile(
    r'^\s*</?(?:think(?:ing)?|thought|final(?:_answer)?)\s*>?\s*$',
    re.IGNORECASE,
)

# Inline-очистка: вырезает теги из чанка, СОХРАНЯЯ полезный текст рядом.
# Решает проблему когда Gemini Flash Lite шлёт "<think" как первый токен стрима.
_OPENCLAW_INLINE_TAG_RE = re.compile(
    r'</?(?:think(?:ing)?|thought|final(?:_answer)?)(?:\s*)>?',
    re.IGNORECASE,
)

class GeminiService:
    """Service to interact with the OpenClaw AI Engine (acting as the Core Brain)."""
    
    def __init__(self, promotions_gateway: Optional[AsyncGoogleSheetsGateway] = None) -> None:
        self.promotions_gateway = promotions_gateway
        self.user_histories: Dict[int, List[Dict[str, str]]] = {}
        self.openclaw_url = os.getenv("OPENCLAW_URL", "http://127.0.0.1:18789")
        self.openclaw_token = (
            os.getenv("OPENCLAW_GATEWAY_TOKEN")
            or os.getenv("OPENCLAW_TOKEN")
            or "default-token"
        )
        self._http_timeout = httpx.Timeout(connect=10.0, read=90.0, write=30.0, pool=10.0)
        self._http_limits = httpx.Limits(max_connections=10, max_keepalive_connections=5)
        self._http_client = httpx.AsyncClient(
            timeout=self._http_timeout,
            limits=self._http_limits,
            trust_env=False,
            headers={"Accept": "text/event-stream"},
        )
        
        # Tools (removed from Google SDK format, let OpenClaw handle its own native tools)
        self.tools = []
        
        self.drive_service = DriveService()
        
        self.memory_archiver = MemoryArchiver(self.drive_service)
        
        self.system_prompt = ""
        # Load local fallback immediately
        try:
            with open("system_prompt.txt", "r", encoding="utf-8") as f:
                 self.system_prompt = f.read()
        except Exception:
             pass
        
        logger.info(f"AI Service routing traffic directly to OpenClaw Node.js: {self.openclaw_url}")
        
    async def initialize(self):
        """Initializes the service and downloads the dynamic system prompt."""
        await self.refresh_system_prompt(force=True)
        
    async def wait_for_ready(self):
        """Immediately ready in this architecture."""
        return True

    async def ask_stream(
        self,
        user_id: int,
        content: str,
        external_history: Optional[str] = None,
        system_context: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Main entrypoint for chat generation via OpenClaw."""
        llm_start_time = time.perf_counter()
        
        messages = self._build_messages(
            user_id=user_id,
            content=content,
            external_history=external_history,
            system_context=system_context,
        )
        
        MAX_RETRIES = 2
        final_reply = ""
        
        for attempt in range(MAX_RETRIES):
            attempt_reply = ""
            yielded_any = False
            try:
                headers = {
                    "Authorization": f"Bearer {self.openclaw_token}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": "openclaw",
                    "messages": messages,
                    "stream": True,
                    "temperature": 0.7
                }
                
                async with self._http_client.stream(
                    "POST",
                    f"{self.openclaw_url}/v1/chat/completions",
                    headers=headers,
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue

                        line_data = line[5:].strip()
                        if line_data == "[DONE]":
                            break
                        
                        try:
                            chunk = json.loads(line_data)
                        except json.JSONDecodeError:
                            continue

                        text = self._extract_openclaw_text(chunk)
                        if not text:
                            continue

                        # Вырезаем reasoning-теги из чанка, сохраняя полезный текст.
                        # Gemini Flash Lite отправляет "<think" как первый токен —
                        # раньше весь чанк дропался, теряя начало ответа.
                        cleaned = _OPENCLAW_INLINE_TAG_RE.sub('', text)
                        if not cleaned or not cleaned.strip():
                            logger.debug("Filtered OpenClaw tag from chunk: %r → empty", text)
                            continue

                        attempt_reply += cleaned
                        yielded_any = True
                        yield cleaned

                if attempt_reply.strip():
                    final_reply = attempt_reply
                    break
                    
            except Exception as e:
                logger.error(f"Error communicating with OpenClaw Engine: {e}")
                if yielded_any:
                    # Уже отправили куски пользователю, повторная попытка только создаст дубли.
                    raise
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(2)
                else:
                    raise e
        
        if not final_reply.strip():
            final_reply = attempt_reply
                    
        # Update our simple linear memory — сохраняем только очищенный текст для истории
        clean_reply = sanitize_ai_text_plain(final_reply, ensure_emojis=True).strip()
        if clean_reply:
            self._add_to_history(user_id, "user", content)
            self._add_to_history(user_id, "assistant", clean_reply)
            
            # Log metrics
            llm_duration_ms = (time.perf_counter() - llm_start_time) * 1000
            log_llm_metrics(
                user_id=user_id,
                model="openclaw-engine",
                duration_ms=llm_duration_ms,
                success=True
            )
            
            # Archive asynchronously
            if self.memory_archiver:
                 asyncio.create_task(self.memory_archiver.archive_user_history(
                     user_id, 
                     self.user_histories.get(user_id, [])
                 ))
        else:
            logger.warning(
                "OpenClaw returned empty user-facing reply after sanitization "
                f"(raw_len={len(final_reply)})"
            )
            llm_duration_ms = (time.perf_counter() - llm_start_time) * 1000
            log_llm_metrics(
                user_id=user_id,
                model="openclaw-engine",
                duration_ms=llm_duration_ms,
                success=False
            )

    async def ask(
        self,
        user_id: int,
        content: str,
        external_history: Optional[str] = None,
        system_context: Optional[str] = None,
    ) -> Optional[str]:
        """Отправляет запрос без стрима и возвращает итоговую строку."""
        messages = self._build_messages(
            user_id=user_id,
            content=content,
            external_history=external_history,
            system_context=system_context,
        )

        try:
            headers = {
                "Authorization": f"Bearer {self.openclaw_token}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "openclaw",
                "messages": messages,
                "stream": False,
                "temperature": 0.7,
            }

            response = await self._http_client.post(
                f"{self.openclaw_url}/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            raw_reply = self._extract_openclaw_text(data)
            clean_reply = sanitize_ai_text_plain(raw_reply, ensure_emojis=True).strip()

            if clean_reply:
                self._add_to_history(user_id, "user", content)
                self._add_to_history(user_id, "assistant", clean_reply)
                return clean_reply

            logger.warning(
                "OpenClaw non-stream reply was empty after sanitization "
                f"(raw_len={len(raw_reply)})"
            )
            return None
        except Exception as e:
            logger.error(f"Error communicating with OpenClaw Engine (non-stream): {e}")
            return None

    # --- History Management ---

    def _get_or_create_history(self, user_id: int) -> List[Dict[str, str]]:
        if user_id not in self.user_histories:
            self.user_histories[user_id] = []
        return self.user_histories[user_id]

    def _build_messages(
        self,
        user_id: int,
        content: str,
        external_history: Optional[str] = None,
        system_context: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        history = self._get_or_create_history(user_id)

        # We prepend the dynamic system prompt to every chat request for OpenClaw to process natively
        prompt = self.system_prompt or "You are a helpful assistant."

        messages = [{"role": "system", "content": prompt}]
        if system_context and system_context.strip():
            messages.append({"role": "system", "content": system_context.strip()})

        if external_history and external_history.strip():
            # Находим безопасную границу обрезки (разрыв строки или точка)
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
            messages.append({
                "role": "system",
                "content": f"Краткая история диалога из CRM (справочно, не цитировать дословно):\n{clean_history}",
            })

        messages.extend(history.copy())
        messages.append({"role": "user", "content": content})
        return messages

    def _normalize_text_value(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            parts: List[str] = []
            for item in value:
                if isinstance(item, str):
                    parts.append(item)
                    continue
                if isinstance(item, dict):
                    for key in ("text", "content", "value"):
                        piece = item.get(key)
                        if isinstance(piece, str) and piece:
                            parts.append(piece)
                            break
            return "".join(parts)
        if isinstance(value, dict):
            for key in ("text", "content", "value"):
                piece = value.get(key)
                if isinstance(piece, str) and piece:
                    return piece
        return str(value)

    def _extract_openclaw_text(self, payload: Any) -> str:
        if not isinstance(payload, dict):
            return ""

        candidates: List[str] = []

        choices = payload.get("choices")
        if isinstance(choices, list) and choices:
            choice = choices[0] if isinstance(choices[0], dict) else {}

            delta = choice.get("delta")
            if isinstance(delta, dict):
                for key in ("content", "text", "response", "output"):
                    piece = self._normalize_text_value(delta.get(key))
                    if piece:
                        candidates.append(piece)

            message = choice.get("message")
            if isinstance(message, dict):
                for key in ("content", "text", "response", "output"):
                    piece = self._normalize_text_value(message.get(key))
                    if piece:
                        candidates.append(piece)

            for key in ("content", "text", "response", "output"):
                piece = self._normalize_text_value(choice.get(key))
                if piece:
                    candidates.append(piece)

        for key in ("content", "text", "response", "output", "message"):
            piece = self._normalize_text_value(payload.get(key))
            if piece:
                candidates.append(piece)

        text = "".join(candidates).strip()
        if not text and logger.isEnabledFor(logging.DEBUG):
            payload_keys = list(payload.keys())[:20]
            logger.debug(f"OpenClaw chunk without text. payload_keys={payload_keys}")
            if isinstance(choices, list) and choices and isinstance(choices[0], dict):
                choice0 = choices[0]
                logger.debug(f"OpenClaw choice keys={list(choice0.keys())[:20]}")
                delta = choice0.get("delta")
                if isinstance(delta, dict):
                    logger.debug(f"OpenClaw delta keys={list(delta.keys())[:20]}")
                message = choice0.get("message")
                if isinstance(message, dict):
                    logger.debug(f"OpenClaw message keys={list(message.keys())[:20]}")
        return text

    def _is_openclaw_tag_fragment(self, text: str) -> bool:
        if not text:
            return False
        return bool(_OPENCLAW_TAG_FRAGMENT_RE.match(text))

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

    async def close(self) -> None:
        """Закрывает сетевые ресурсы сервиса."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            
    # --- Admin Dashboard Compatibility ---
    
    async def refresh_system_prompt(self, force: bool = False) -> bool:
        """Downloads the system prompt from Google Docs and applies it for OpenClaw injection."""
        doc_id = os.getenv("SYSTEM_PROMPT_DOC", "") or os.getenv("SYSTEM_PROMPT_DOC_ID", "")
        if not doc_id or not self.drive_service:
            logger.warning("DriveService or SYSTEM_PROMPT_DOC_ID missing, reading local system_prompt.txt")
            try:
                with open("system_prompt.txt", "r", encoding="utf-8") as f:
                    self.system_prompt = f.read()
            except Exception:
                if not self.system_prompt:
                    self.system_prompt = "You are a helpful assistant."
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
                logger.info("System prompt successfully refreshed from Google Docs.")
                return True
        except Exception as e:
            logger.error(f"Failed to refresh system prompt: {e}")
            
        return False
