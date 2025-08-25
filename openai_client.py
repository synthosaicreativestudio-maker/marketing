"""
Модуль для работы с OpenAI API
Централизованная логика работы с ассистентами
"""

import os
import time
import logging
import asyncio
from typing import Optional, Dict, Any
from openai import OpenAI
from config import OPENAI_CONFIG

logger = logging.getLogger(__name__)

class OpenAIClient:
    """Клиент для работы с OpenAI API"""
    
    def __init__(self):
        self.client = None
        self.assistant_id = None
        self.semaphore = asyncio.Semaphore(OPENAI_CONFIG['MAX_CONCURRENT'])
        self._initialize_client()
    
    def _initialize_client(self):
        """Инициализирует OpenAI клиент"""
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            logger.error('OPENAI_API_KEY не задан в .env')
            return
        
        try:
            self.client = OpenAI(api_key=api_key)
            self.assistant_id = os.getenv('OPENAI_ASSISTANT_ID')
            if not self.assistant_id:
                logger.warning('OPENAI_ASSISTANT_ID не задан')
            
            logger.info('OpenAI клиент инициализирован')
        except Exception as e:
            logger.error(f'Ошибка инициализации OpenAI клиента: {e}')
    
    def is_available(self) -> bool:
        """Проверяет доступность OpenAI API"""
        if not self.client:
            return False
        
        try:
            # Легкая проверка через models endpoint
            response = self.client.models.list()
            return True
        except Exception as e:
            logger.warning(f'OpenAI API недоступен: {e}')
            return False
    
    async def create_thread(self) -> Optional[str]:
        """Создает новый thread"""
        if not self.client:
            return None
        
        try:
            async with self.semaphore:
                thread = await asyncio.to_thread(
                    self.client.beta.threads.create
                )
                return thread.id
        except Exception as e:
            logger.error(f'Ошибка создания thread: {e}')
            return None
    
    async def send_message(self, thread_id: str, text: str, max_wait: int = 60) -> Optional[str]:
        """Отправляет сообщение в thread и получает ответ"""
        if not self.client or not self.assistant_id:
            return None
        
        try:
            async with self.semaphore:
                # 1. Добавляем сообщение пользователя
                await asyncio.to_thread(
                    self.client.beta.threads.messages.create,
                    thread_id=thread_id,
                    role="user",
                    content=text
                )
                
                # 2. Запускаем ассистента
                run = await asyncio.to_thread(
                    self.client.beta.threads.runs.create,
                    thread_id=thread_id,
                    assistant_id=self.assistant_id
                )
                
                # 3. Ждем завершения
                response = await self._wait_for_run_completion(thread_id, run.id, max_wait)
                if not response:
                    return None
                
                # 4. Получаем ответ
                return await self._extract_assistant_response(thread_id)
                
        except Exception as e:
            logger.error(f'Ошибка отправки сообщения: {e}')
            return None
    
    async def _wait_for_run_completion(self, thread_id: str, run_id: str, max_wait: int) -> bool:
        """Ждет завершения run"""
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            try:
                run_status = await asyncio.to_thread(
                    self.client.beta.threads.runs.retrieve,
                    thread_id=thread_id,
                    run_id=run_id
                )
                
                if run_status.status == "completed":
                    return True
                elif run_status.status in ("failed", "cancelled", "expired"):
                    logger.error(f'Run завершился с ошибкой: {run_status.status}')
                    return False
                
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f'Ошибка проверки статуса run: {e}')
                return False
        
        logger.error(f'Run не завершился за {max_wait} секунд')
        return False
    
    async def _extract_assistant_response(self, thread_id: str) -> Optional[str]:
        """Извлекает ответ ассистента из thread"""
        try:
            messages = await asyncio.to_thread(
                self.client.beta.threads.messages.list,
                thread_id=thread_id
            )
            
            # Ищем последний ответ ассистента
            for msg in reversed(messages.data):
                if msg.role == "assistant":
                    if msg.content and hasattr(msg.content[0], 'text'):
                        return msg.content[0].text.value
                    elif msg.content:
                        return str(msg.content)
            
            return None
            
        except Exception as e:
            logger.error(f'Ошибка извлечения ответа: {e}')
            return None
    
    async def get_or_create_thread(self, user_data: Dict[str, Any]) -> Optional[str]:
        """Получает существующий thread или создает новый"""
        # TODO: Реализовать поиск существующего thread по user_data
        # Пока просто создаем новый
        return await self.create_thread()
    
    def get_model(self) -> str:
        """Получает модель для использования"""
        return os.getenv('OPENAI_MODEL', OPENAI_CONFIG['DEFAULT_MODEL'])
    
    def get_max_retry(self) -> int:
        """Получает максимальное количество попыток"""
        return OPENAI_CONFIG['MAX_RETRY']
    
    def get_backoff_base(self) -> float:
        """Получает базовый коэффициент задержки"""
        return OPENAI_CONFIG['BACKOFF_BASE']

# Глобальный экземпляр клиента
openai_client = OpenAIClient()


