import httpx
import logging
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

class OpenClawClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token
        # КРИТИЧНО: НЕ использовать системный прокси для запросов к OpenClaw
        # HTTP_PROXY/HTTPS_PROXY из .env предназначены для Gemini API, а не для OpenClaw
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(90.0, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            proxy=None,  # Явно отключаем прокси
        )
        # Убираем прокси из переменных среды для этого клиента
        self.client._transport = httpx.AsyncHTTPTransport(
            retries=1,
            proxy=None,
        )

    async def ask(
        self,
        prompt: str,
        user_id: int,
        model: str = "openclaw:main",
        system_instruction: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """
        Отправляет запрос в OpenClaw через OpenAI-совместимый эндпоинт.
        Поддерживает system prompt и историю диалога.
        """
        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        messages = []

        # Системная инструкция (system prompt)
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})

        # История диалога (если есть)
        if history:
            messages.extend(history)

        # Текущий вопрос пользователя
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "user": str(user_id)
        }

        try:
            logger.info(f"Sending request to OpenClaw for user {user_id} (messages: {len(messages)}, system: {bool(system_instruction)})")
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
