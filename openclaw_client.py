import httpx
import os
import logging
import asyncio
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class OpenClawClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )

    async def ask(self, prompt: str, user_id: int, model: str = "openclaw:main") -> str:
        """
        Отправляет запрос в OpenClaw через OpenAI-совместимый эндпоинт.
        """
        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "user": str(user_id)
        }
        
        try:
            logger.info(f"Sending request to OpenClaw for user {user_id}")
            response = await self.client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            answer = data["choices"][0]["message"]["content"]
            logger.info(f"Received response from OpenClaw: {len(answer)} chars")
            return answer
        except httpx.HTTPStatusError as e:
            logger.error(f"OpenClaw HTTP error {e.response.status_code}: {e.response.text}")
            return f"Ошибка ИИ (Статус {e.response.status_code})"
        except Exception as e:
            logger.error(f"OpenClaw connection error: {e}")
            return f"Ошибка связи с ИИ: {e}"

    async def close(self):
        await self.client.aclose()
