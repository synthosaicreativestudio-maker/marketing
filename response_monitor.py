"""
Сервис для мониторинга ответов специалистов и отправки их в Telegram.
"""

import logging
import asyncio
from typing import Optional
from telegram import Bot
from appeals_service import AppealsService

logger = logging.getLogger(__name__)


class ResponseMonitor:
    """Сервис для мониторинга и отправки ответов специалистов."""
    
    def __init__(self, appeals_service: AppealsService, bot_token: str):
        """
        Инициализация монитора ответов.
        
        Args:
            appeals_service: сервис для работы с обращениями
            bot_token: токен Telegram бота
        """
        self.appeals_service = appeals_service
        self.bot = Bot(token=bot_token)
        self.is_running = False
        self._task = None

    async def start_monitoring(self, interval_seconds: int = 60):
        """
        Запускает мониторинг ответов специалистов.
        
        Args:
            interval_seconds: интервал проверки в секундах (по умолчанию 60)
        """
        if self.is_running:
            logger.warning("Мониторинг уже запущен")
            return

        self.is_running = True
        logger.info(f"Запуск мониторинга ответов (интервал: {interval_seconds} сек)")
        
        self._task = asyncio.create_task(self._monitoring_loop(interval_seconds))

    async def stop_monitoring(self):
        """Останавливает мониторинг ответов."""
        if not self.is_running:
            return

        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("Мониторинг ответов остановлен")

    async def _monitoring_loop(self, interval_seconds: int):
        """Основной цикл мониторинга."""
        while self.is_running:
            try:
                # Проверяем только если есть записи в таблице
                if self.appeals_service.has_records():
                    await self._check_and_send_responses()
                else:
                    logger.debug("Нет записей в таблице, пропускаем проверку")
                
                # Ждем до следующей проверки
                await asyncio.sleep(interval_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка в цикле мониторинга: {e}")
                await asyncio.sleep(interval_seconds)  # Продолжаем работу при ошибке

    async def _check_and_send_responses(self):
        """Проверяет и отправляет ответы специалистов."""
        try:
            responses = self.appeals_service.check_for_responses()
            
            for response_data in responses:
                await self._send_response(response_data)
                
        except Exception as e:
            logger.error(f"Ошибка при проверке ответов: {e}")

    async def _send_response(self, response_data: dict):
        """
        Отправляет ответ специалиста пользователю.
        
        Args:
            response_data: данные ответа (row, telegram_id, response, code, fio)
        """
        try:
            telegram_id = response_data['telegram_id']
            response_text = response_data['response']
            fio = response_data.get('fio', '')
            code = response_data.get('code', '')
            
            # Формируем сообщение (без информации о пользователе)
            message = f"💬 Ответ от специалиста отдела маркетинга:\n\n{response_text}"
            
            # Отправляем сообщение
            await self.bot.send_message(
                chat_id=telegram_id,
                text=message
            )
            
            logger.info(f"Отправлен ответ пользователю {telegram_id}")
            
            # Логируем ответ специалиста в таблицу обращений
            try:
                # Формируем ответ с выделением для специалиста
                specialist_response = f"👨‍💼 СПЕЦИАЛИСТ: {response_text}"
                
                # Добавляем ответ специалиста к существующим обращениям
                self.appeals_service.add_specialist_response(
                    telegram_id=telegram_id,
                    response_text=specialist_response
                )
                logger.info(f"Ответ специалиста записан в таблицу для пользователя {telegram_id}")
            except Exception as e:
                logger.error(f"Ошибка записи ответа специалиста в таблицу: {e}")
            
            # Обновляем статус на "решено" и очищаем ответ
            try:
                # Устанавливаем статус "решено" 
                self.appeals_service.worksheet.batch_update([{
                    'range': f'F{response_data["row"]}',
                    'values': [['решено']]
                }])
                
                # Убираем заливку (устанавливаем белый цвет)
                self.appeals_service.worksheet.format(f'F{response_data["row"]}', {
                    "backgroundColor": {
                        "red": 1.0,
                        "green": 1.0,
                        "blue": 1.0
                    }
                })
                
                logger.info(f"Статус обновлен на 'решено' для строки {response_data['row']}")
            except Exception as e:
                logger.error(f"Ошибка обновления статуса: {e}")
            
            # Очищаем ответ в таблице
            self.appeals_service.clear_response(response_data['row'])
            
        except Exception as e:
            logger.error(f"Ошибка отправки ответа пользователю {response_data.get('telegram_id', 'unknown')}: {e}")

    async def send_test_response(self, telegram_id: int, test_message: str = "Тестовое сообщение от монитора ответов"):
        """
        Отправляет тестовое сообщение для проверки работы.
        
        Args:
            telegram_id: ID пользователя в Telegram
            test_message: тестовое сообщение
        """
        try:
            await self.bot.send_message(
                chat_id=telegram_id,
                text=f"🧪 {test_message}"
            )
            logger.info(f"Отправлено тестовое сообщение пользователю {telegram_id}")
        except Exception as e:
            logger.error(f"Ошибка отправки тестового сообщения: {e}")
