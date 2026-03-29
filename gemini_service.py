import os
import asyncio
import time
import logging
import json
import httpx
from typing import Dict, List, Optional, AsyncGenerator

from sheets_gateway import AsyncGoogleSheetsGateway
from structured_logging import log_llm_metrics
from drive_service import DriveService
from memory_archiver import MemoryArchiver

logger = logging.getLogger(__name__)

class GeminiService:
    """Service to interact with the OpenClaw AI Engine (acting as the Core Brain)."""
    
    def __init__(self, promotions_gateway: Optional[AsyncGoogleSheetsGateway] = None) -> None:
        self.promotions_gateway = promotions_gateway
        self.user_histories: Dict[int, List[Dict[str, str]]] = {}
        self.openclaw_url = os.getenv("OPENCLAW_URL", "http://127.0.0.1:18789")
        self.openclaw_token = os.getenv("OPENCLAW_TOKEN", "default-token")
        
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

    async def ask_stream(self, user_id: int, content: str, external_history: Optional[str] = None) -> AsyncGenerator[str, None]:
        """Main entrypoint for chat generation via OpenClaw."""
        llm_start_time = time.perf_counter()
        
        history = self._get_or_create_history(user_id)
        
        # We prepend the dynamic system prompt to every chat request for OpenClaw to process natively
        messages = [{"role": "system", "content": self.system_prompt or "You are a helpful assistant."}]
        messages.extend(history.copy())
        
        if external_history and external_history.strip():
            clean_history = external_history[-3000:]
            messages.append({"role": "user", "content": f"Краткая история диалога из CRM (справочно):\n{clean_history}"})
            messages.append({"role": "assistant", "content": "Принято, учел контекст."})
            
        messages.append({"role": "user", "content": content})
        
        MAX_RETRIES = 2
        full_reply = ""
        
        for attempt in range(MAX_RETRIES):
            try:
                # We use httpx explicitly since the openai SDK doesn't always play well with custom chunking proxies
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
                
                async with httpx.AsyncClient(timeout=90.0) as client:
                    async with client.stream("POST", f"{self.openclaw_url}/v1/chat/completions", headers=headers, json=payload) as response:
                        response.raise_for_status()
                        
                        stream_buffer = ""
                        in_think = False
                        
                        async for line in response.aiter_lines():
                            if line.startswith("data:"):
                                line_data = line[5:].strip()
                                if line_data == "[DONE]":
                                    break
                                    
                                try:
                                    chunk = json.loads(line_data)
                                    if "choices" in chunk and len(chunk["choices"]) > 0:
                                        delta = chunk["choices"][0].get("delta", {})
                                        text = delta.get("content", "")
                                        if text:
                                            stream_buffer += text
                                            
                                            # Strip <think>...</think> from stream
                                            while True:
                                                if not in_think:
                                                    think_start = stream_buffer.find("<think>")
                                                    if think_start != -1:
                                                        safe_text = stream_buffer[:think_start]
                                                        if safe_text:
                                                            full_reply += safe_text
                                                            yield safe_text
                                                        stream_buffer = stream_buffer[think_start + 7:]
                                                        in_think = True
                                                        continue
                                                    
                                                    # Check if ending with partial start tag
                                                    partial_len = 0
                                                    for i in range(1, 8):
                                                        if stream_buffer.endswith("<think>"[:i]):
                                                            partial_len = i
                                                    
                                                    if partial_len > 0:
                                                        safe_text = stream_buffer[:-partial_len]
                                                        if safe_text:
                                                            full_reply += safe_text
                                                            yield safe_text
                                                        stream_buffer = stream_buffer[-partial_len:]
                                                    else:
                                                        if stream_buffer:
                                                            full_reply += stream_buffer
                                                            yield stream_buffer
                                                        stream_buffer = ""
                                                else:
                                                    think_end = stream_buffer.find("</think>")
                                                    if think_end != -1:
                                                        stream_buffer = stream_buffer[think_end + 8:]
                                                        in_think = False
                                                        continue
                                                    else:
                                                        # Fully inside think tag, wait for end
                                                        stream_buffer = ""
                                                break
                                except json.JSONDecodeError:
                                    continue
                                    
                        # After loop, yield any safely remaining non-think text
                        if not in_think and stream_buffer:
                            full_reply += stream_buffer
                            yield stream_buffer
                                    
                if full_reply:
                    break
                    
            except Exception as e:
                logger.error(f"Error communicating with OpenClaw Engine: {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(2)
                else:
                    raise e
                    
        # Update our simple linear memory
        if full_reply:
            self._add_to_history(user_id, "user", content)
            self._add_to_history(user_id, "assistant", full_reply)
            
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

    async def ask(self, user_id: int, content: str, external_history: Optional[str] = None) -> Optional[str]:
        """Отправляет запрос и возвращает итоговую строку."""
        full_reply_parts = []
        async for part in self.ask_stream(user_id, content, external_history):
            full_reply_parts.append(part)
        return "".join(full_reply_parts) if full_reply_parts else None

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
