import os
import logging
import time
from typing import Dict, Optional

import httpx
from openai import OpenAI


logger = logging.getLogger(__name__)


class OpenAIService:
    """Thin wrapper around OpenAI Assistants Threads API for simple Q/A flows.

    Notes:
    - Maintains an in-memory map of user_id -> thread_id. This will reset on restart.
    - Expects OPENAI_API_KEY and OPENAI_ASSISTANT_ID in environment.
    """

    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        assistant_id = os.getenv("OPENAI_ASSISTANT_ID")
        proxy_url = os.getenv("OPENAI_PROXY_URL")

        if not api_key or not assistant_id:
            logger.warning(
                "OpenAIService disabled: missing OPENAI_API_KEY or OPENAI_ASSISTANT_ID"
            )
            self.client = None
            self.assistant_id = None
        else:
            # Настройка HTTP клиента с прокси, если указан
            http_client = None
            if proxy_url:
                logger.info(f"Using proxy for OpenAI API: {proxy_url.split('@')[1] if '@' in proxy_url else proxy_url}")
                http_client = httpx.Client(
                    proxy=proxy_url,
                    timeout=60.0
                )
            else:
                http_client = httpx.Client(timeout=60.0)
            
            self.client = OpenAI(api_key=api_key, http_client=http_client)
            self.assistant_id = assistant_id

        self.user_threads: Dict[int, str] = {}

    def is_enabled(self) -> bool:
        return self.client is not None and self.assistant_id is not None

    def _get_or_create_thread(self, user_id: int) -> Optional[str]:
        if not self.is_enabled():
            return None
        thread_id = self.user_threads.get(user_id)
        if thread_id:
            return thread_id
        thread = self.client.beta.threads.create()
        self.user_threads[user_id] = thread.id
        logger.info(f"Created new OpenAI thread for user {user_id}: {thread.id}")
        return thread.id

    def _wait_for_run(self, thread_id: str, run_id: str, timeout_sec: int = 60) -> Optional[str]:
        """Polls until run completes or times out; returns final status."""
        start = time.time()
        while time.time() - start < timeout_sec:
            run = self.client.beta.threads.runs.retrieve(
                thread_id=thread_id, run_id=run_id
            )
            if run.status in ("completed", "failed", "cancelled", "expired"):
                return run.status
            # ВАЖНО: Пауза, чтобы не сжечь CPU.
            # Допустимо только потому, что метод вызывается в run_in_executor.
            time.sleep(1)
        return None

    def ask(self, user_id: int, content: str) -> Optional[str]:
        """Send a message to user's thread and return the assistant's latest reply text."""
        if not self.is_enabled():
            return None

        thread_id = self._get_or_create_thread(user_id)
        if not thread_id:
            return None

        # Add user message
        self.client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=content,
        )

        # Create run
        run = self.client.beta.threads.runs.create(
            thread_id=thread_id, assistant_id=self.assistant_id
        )

        status = self._wait_for_run(thread_id, run.id)
        if status != "completed":
            logger.warning(f"OpenAI run did not complete (status={status}) for user {user_id}")
            return None

        # Read latest messages and return the most recent assistant response
        messages = self.client.beta.threads.messages.list(thread_id=thread_id, order="desc")
        for m in messages.data:
            if m.role == "assistant":
                # Extract first text segment
                for part in m.content:
                    if part.type == "text":
                        return part.text.value
        return None



