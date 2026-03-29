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
        self.drive_service.authenticate()
        
        self.memory_archiver = MemoryArchiver(self.drive_service)
        
        logger.info(f"AI Service routing traffic directly to OpenClaw Node.js: {self.openclaw_url}")
        
    async def initialize(self):
        """No intensive initialization needed as everything is offloaded to OpenClaw."""
        pass
        
    async def wait_for_ready(self):
        """Immediately ready in this architecture."""
        return True

    async def ask_stream(self, user_id: int, content: str, external_history: Optional[str] = None) -> AsyncGenerator[str, None]:
        """Main entrypoint for chat generation via OpenClaw."""
        llm_start_time = time.perf_counter()
        
        history = self._get_or_create_history(user_id)
        
        # In this architecture, we don't send the system prompt here. OpenClaw handles it.
        # However, we DO send context like external_history (e.g. from Sheets)
        
        messages = history.copy()
        
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
                                            full_reply += text
                                            yield text
                                except json.JSONDecodeError:
                                    continue
                                    
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
            
    # --- Stubs for Admin Dashboard Compatibility ---
    
    async def refresh_system_prompt(self, force: bool = False) -> bool:
        """Stub: The prompt is now strictly managed by OpenClaw Engine directly."""
        logger.info("refresh_system_prompt ignored as OpenClaw handles prompts.")
        return True
