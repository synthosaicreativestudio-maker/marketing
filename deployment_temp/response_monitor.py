"""
Сервис для мониторинга ответов специалистов и отправки их в Telegram.
"""

import logging
import asyncio
from telegram import Bot
from appeals_service import AppealsService
from typing import Union

logger = logging.getLogger(__name__)


class ResponseMonitor:
    """Сервис для мониторинга и отправки ответов специалистов."""
    
    def __init__(self, appeals_service: Union[AppealsService, object], bot_token: str):
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
                if await self.appeals_service.has_records():
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
            # 1. Проверяем новые ответы в колонке G
            responses = await self.appeals_service.check_for_responses()
            
            for response_data in responses:
                await self._send_response(response_data)
                
                # Если в ответе есть триггер "решено", помечаем
                if self._is_resolved_response(response_data.get('response', '')):
                    await self._mark_as_resolved(response_data)

            # 2. Проверяем изменение статуса на "Решено" в колонке F (ручное изменение)
            await self._check_and_process_resolved_status()
                
        except Exception as e:
            logger.error(f"Ошибка при проверке ответов: {e}")

    async def _check_and_process_resolved_status(self):
        """Обрабатывает обращения, переведенные в статус 'Решено' вручную."""
        try:
            resolved_appeals = await self.appeals_service.check_for_resolved_status()
            
            for appeal in resolved_appeals:
                telegram_id = appeal['telegram_id']
                appeal['row']
                
                message = "✅ Ваше обращение отмечено как решенное специалистом."
                
                # ВАЖНО: Добавляем маркер ДО отправки уведомления, чтобы предотвратить повторную отправку
                # Используем add_specialist_response для добавления в историю
                try:
                    await self.appeals_service.add_specialist_response(
                        telegram_id=telegram_id,
                        response_text=message
                    )
                    logger.info(f"Маркер 'решено' добавлен в историю для пользователя {telegram_id}")
                except Exception as e:
                    logger.error(f"Ошибка добавления маркера для пользователя {telegram_id}: {e}")
                    # Продолжаем выполнение даже если не удалось добавить маркер
                
                # Отправляем уведомление
                try:
                    await self.bot.send_message(
                        chat_id=telegram_id,
                        text=message
                    )
                    logger.info(f"Уведомление о ручном решении отправлено пользователю {telegram_id}")
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления пользователю {telegram_id}: {e}")
                
        except Exception as e:
            logger.error(f"Ошибка обработки ручных решений: {e}")

    def _is_resolved_response(self, response_text: str) -> bool:
        """
        Проверяет, содержит ли ответ специалиста триггерные слова "решено".
        
        Args:
            response_text: текст ответа специалиста
            
        Returns:
            bool: True если найдены триггерные слова
        """
        if not response_text:
            return False
            
        text_lower = response_text.lower()
        
        # ВРЕМЕННО ОТКЛЮЧЕНО: только очень явные фразы
        # Триггерные фразы для определения "решено" (только явные указания)
        resolved_phrases = [
            'статус решено', 'отмечено как решенное', 'обработка завершена',
            'можно закрывать', 'закрывайте обращение', 'обращение закрыто'
        ]
        
        # Проверяем наличие триггерных фраз
        for phrase in resolved_phrases:
            if phrase in text_lower:
                logger.info(f"Найдена фраза 'решено': '{phrase}' в ответе: {response_text[:100]}...")
                return True
        
        # ВРЕМЕННО: логируем все ответы для диагностики
        logger.info(f"Ответ специалиста НЕ содержит фраз 'решено': '{response_text[:100]}...'")
        return False

    async def _mark_as_resolved(self, response_data: dict):
        """
        Отмечает обращение как решенное и уведомляет пользователя.
        
        Args:
            response_data: данные ответа
        """
        try:
            telegram_id = response_data['telegram_id']
            response_text = response_data['response']
            # fio and code are unused
            
            # Формируем сообщение о решении
            message = f"✅ Ваше обращение решено специалистом отдела маркетинга!\n\n{response_text}"
            
            # Отправляем сообщение
            await self.bot.send_message(
                chat_id=telegram_id,
                text=message
            )
            
            logger.info(f"Отправлено уведомление о решении пользователю {telegram_id}")
            
            # Статус меняется на "решено" только при явном указании триггерных фраз
            logger.info(f"Обращение помечено как решенное по триггерным фразам для строки {response_data['row']}")
            
            # Очищаем ответ в таблице
            await self.appeals_service.clear_response(response_data['row'])
            
        except Exception as e:
            logger.error(f"Ошибка обработки решения для пользователя {response_data.get('telegram_id', 'unknown')}: {e}")

    async def _send_response(self, response_data: dict):
        """
        Отправляет ответ специалиста пользователю.
        
        Args:
            response_data: данные ответа (row, telegram_id, response, code, fio)
        """
        try:
            telegram_id = response_data['telegram_id']
            response_text = response_data['response']
            # fio and code are unused
            
            # Формируем сообщение (без информации о пользователе)
            message = f"💬 Ответ от специалиста отдела маркетинга:\n\n{response_text}"
            
            # Отправляем сообщение
            await self.bot.send_message(
                chat_id=telegram_id,
                text=message
            )
            
            logger.info(f"Отправлен ответ пользователю {telegram_id}")
            
            # Устанавливаем статус "В работе" при первом ответе специалиста
            try:
                success = await self.appeals_service.set_status_in_work(telegram_id)
                if success:
                    logger.info(f"Статус установлен 'В работе' для пользователя {telegram_id}")
                else:
                    logger.warning(f"Не удалось установить статус 'В работе' для пользователя {telegram_id}")
            except Exception as e:
                logger.error(f"Ошибка при установке статуса 'В работе': {e}")
            
            # Логируем ответ специалиста в таблицу обращений
            try:
                # Формируем ответ с выделением для специалиста
                specialist_response = f"👨‍💼 СПЕЦИАЛИСТ: {response_text}"
                
                # Добавляем ответ специалиста к существующим обращениям
                await self.appeals_service.add_specialist_response(
                    telegram_id,
                    specialist_response
                )
                logger.info(f"Ответ специалиста записан в таблицу для пользователя {telegram_id}")
            except Exception as e:
                logger.error(f"Ошибка записи ответа специалиста в таблицу: {e}")
            
            # НЕ меняем статус автоматически - только при явном указании специалиста
            logger.info(f"Ответ специалиста записан для строки {response_data['row']}, статус остается без изменений")
            
            # Очищаем ответ в таблице
            await self.appeals_service.clear_response(response_data['row'])
            
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
