"""
Сервис для работы с обращениями в Google Sheets.
Адаптирован под структуру листа 'обращения'.
"""

import logging
import datetime
from typing import Optional, List, Dict
from sheets_gateway import (
    _get_appeals_client_and_sheet,
    AsyncGoogleSheetsGateway,
    CircuitBreakerOpenError
)
from utils import mask_phone, mask_telegram_id, mask_fio

logger = logging.getLogger(__name__)


class AppealsService:
    """Сервис для работы с обращениями в листе 'обращения'."""
    
    def __init__(self, gateway: Optional[AsyncGoogleSheetsGateway] = None):
        """Инициализация сервиса обращений."""
        self.worksheet = None
        self.gateway = gateway or AsyncGoogleSheetsGateway(circuit_breaker_name='appeals')
        
        # Синхронная инициализация
        try:
            client, worksheet = _get_appeals_client_and_sheet()
            self.worksheet = worksheet
            if self.worksheet:
                logger.info(f"Лист 'обращения' найден: {self.worksheet.title}")
        except Exception as e:
            logger.error(f"Не удалось инициализировать лист 'обращения': {e}")

    def is_available(self) -> bool:
        """Проверяет доступность сервиса обращений."""
        return self.worksheet is not None and self.gateway is not None

    async def create_appeal(self, code: str, phone: str, fio: str, telegram_id: int, text: str) -> bool:
        """
        Создает или обновляет обращение в листе (накопление в одной ячейке).
        
        Args:
            code: код партнера
            phone: телефон партнера
            fio: ФИО партнера
            telegram_id: ID пользователя в Telegram
            text: текст обращения
            
        Returns:
            bool: True если обращение создано/обновлено успешно
        """
        if not self.is_available():
            logger.error("Сервис обращений недоступен")
            return False

        try:
            logger.info(f"Создание обращения для telegram_id={mask_telegram_id(telegram_id)}, code={code}, phone={mask_phone(phone)}, fio={mask_fio(fio)}")
            # Ищем существующую строку для этого telegram_id
            records = await self.gateway.get_all_records(self.worksheet)
            logger.info(f"Получено {len(records)} записей из таблицы обращений")
            existing_row = None
            
            for i, record in enumerate(records, start=2):  # start=2 потому что строка 1 - заголовки
                # Ищем telegram_id в колонке D (индекс 3 в массиве)
                record_telegram_id = str(record.get('telegram_id', ''))
                logger.info(f"Проверка записи {i}: telegram_id='{mask_telegram_id(record_telegram_id)}' vs '{mask_telegram_id(telegram_id)}'")
                if record_telegram_id == str(telegram_id):
                    existing_row = i
                    logger.info(f"Найдена существующая строка {i} для telegram_id {mask_telegram_id(telegram_id)}")
                    break
            
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            new_appeal = f"{timestamp}: {text}"
            
            if existing_row:
                # Обновляем существующую строку - накапливаем обращения в одной ячейке
                cell = await self.gateway.cell(self.worksheet, existing_row, 5)
                current_appeals = cell.value or ""  # колонка E
                
                # Добавляем новое обращение сверху
                if current_appeals.strip():
                    updated_appeals = f"{new_appeal}\n{current_appeals}"
                else:
                    updated_appeals = new_appeal
                
                # Очищаем старые обращения (>30 дней)
                updated_appeals = self._cleanup_old_appeals(updated_appeals)
                # Усечение под лимит Google Sheets
                updated_appeals = self._truncate_to_gs_limit(updated_appeals)
                
                # Обновляем ячейку с обращениями и время обновления через batch_update
                await self.gateway.batch_update(self.worksheet, [{
                    'range': f'E{existing_row}',
                    'values': [[updated_appeals]]
                }, {
                    'range': f'H{existing_row}',
                    'values': [[timestamp]]
                }])
                
                logger.info(f"Обновлено обращение для пользователя {mask_telegram_id(telegram_id)} (строка {existing_row})")
            else:
                # Создаем новую строку
                next_row = len(records) + 2  # +2 потому что records не включает заголовок
                logger.info(f"Создание новой строки {next_row} для telegram_id {mask_telegram_id(telegram_id)}")
                
                row_data = [
                    code,
                    phone,
                    fio,
                    telegram_id,  # telegram_id (колонка D)
                    self._truncate_to_gs_limit(new_appeal),  # текст_обращений (колонка E)
                    'Новое',  # статус (колонка F)
                    '',  # специалист_ответ (колонка G)
                    timestamp  # время_обновления (колонка H)
                ]
                
                logger.info(f"Данные для записи: {row_data}")
                await self.gateway.append_row(self.worksheet, row_data)
                
                # Устанавливаем заливку #f3cccc (светло-красный) для статуса "Новое"
                try:
                    logger.info(f"Попытка установить заливку #f3cccc для новой ячейки F{next_row}")
                    await self.gateway.format(self.worksheet, f'F{next_row}', {
                        "backgroundColor": {
                            "red": 0.95,    # #f3cccc
                            "green": 0.8,
                            "blue": 0.8
                        }
                    })
                    logger.info(f"Заливка успешно установлена для ячейки F{next_row}")
                except Exception as format_error:
                    logger.error(f"Ошибка при установке заливки для ячейки F{next_row}: {format_error}", exc_info=True)
                
                logger.info(f"Создано новое обращение для пользователя {mask_telegram_id(telegram_id)} (строка {next_row})")
            
            return True
            
        except CircuitBreakerOpenError as e:
            logger.warning(f"Circuit Breaker открыт для Appeals Service: {e}")
            return False
        except Exception as e:
            logger.error(f"Ошибка создания/обновления обращения: {e}")
            return False

    def _cleanup_old_appeals(self, appeals_text: str) -> str:
        """
        Очищает обращения старше 30 дней.
        
        Args:
            appeals_text: текст с обращениями
            
        Returns:
            str: очищенный текст
        """
        try:
            if not appeals_text.strip():
                return appeals_text
                
            cutoff_date = datetime.datetime.now() - datetime.timedelta(days=30)
            lines = appeals_text.split('\n')
            cleaned_lines = []
            
            for line in lines:
                if not line.strip():
                    continue
                    
                # Пытаемся извлечь дату из начала строки (формат: YYYY-MM-DD HH:MM:SS)
                try:
                    if len(line) >= 19 and line[4] == '-' and line[7] == '-':
                        date_str = line[:19]
                        appeal_date = datetime.datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                        
                        if appeal_date >= cutoff_date:
                            cleaned_lines.append(line)
                        else:
                            logger.debug(f"Удалено старое обращение: {line[:50]}...")
                    else:
                        # Если не удается распарсить дату, оставляем строку
                        cleaned_lines.append(line)
                except ValueError:
                    # Если ошибка парсинга даты, оставляем строку
                    cleaned_lines.append(line)
            
            return '\n'.join(cleaned_lines)
            
        except Exception as e:
            logger.error(f"Ошибка очистки старых обращений: {e}")
            return appeals_text

    def _truncate_to_gs_limit(self, text: str, limit: int = 25000) -> str:
        """
        Ограничивает длину текста для одной ячейки Google Sheets (лимит 50% от максимума = 25k символов).
        Сохраняем новые сообщения (в начале текста), добавляя пометку об усечении в конце.
        """
        try:
            if text is None:
                return ""
            if len(text) <= limit:
                return text
            suffix = "\n[...] (усечено до лимита Google Sheets)"
            keep = max(0, limit - len(suffix))
            # Берем первые символы (новые записи сверху), а не последние
            return text[:keep] + suffix
        except Exception:
            return text[:limit]

    async def get_raw_history(self, telegram_id: int) -> str:
        """
        Получает сырой текст всей истории переписки из всех ячеек 'текст_обращений' для данного пользователя.
        
        Args:
            telegram_id: ID пользователя в Telegram
            
        Returns:
            str: склеенный текст или пустая строка
        """
        if not self.is_available():
            return ""

        try:
            records = await self.gateway.get_all_records(self.worksheet)
            all_history = []
            
            for i, record in enumerate(records, start=2):
                if str(record.get('telegram_id', '')) == str(telegram_id):
                    history = record.get('текст_обращений', '')
                    if history.strip():
                        all_history.append(history)
            
            if not all_history:
                return ""
            
            # Склеиваем историю от новых к старым
            combined = "\n\n--- СЛЕДУЮЩИЙ БЛОК ИСТОРИИ ---\n\n".join(all_history)
            
            # ОГРАНИЧЕНИЕ: Берем только последние 5000 символов для экономии токенов и ускорения
            if len(combined) > 5000:
                combined = "[...] " + combined[-5000:]
                
            logger.info(f"Получена история для {mask_telegram_id(telegram_id)} (длина: {len(combined)})")
            return combined
            
        except Exception as e:
            logger.error(f"Ошибка получения истории из таблицы: {e}")
            return ""

    async def get_user_memory(self, telegram_id: int) -> str:
        """
        Получает краткий контекст/память о пользователе из колонки I.
        
        Args:
            telegram_id: ID пользователя в Telegram
            
        Returns:
            str: текст памяти или пустая строка
        """
        if not self.is_available():
            return ""

        try:
            records = await self.gateway.get_all_records(self.worksheet)
            
            for record in records:
                if str(record.get('telegram_id', '')) == str(telegram_id):
                    # Колонка I — 9-я по счету. В словаре record ключи по заголовкам.
                    # Если заголовка еще нет, record.get() вернет None.
                    return str(record.get('контекст_памяти', '')).strip()
            
            return ""
        except Exception as e:
            logger.error(f"Ошибка получения памяти из таблицы: {e}")
            return ""

    async def update_user_memory(self, telegram_id: int, memory_text: str) -> bool:
        """
        Обновляет долгосрочную память о пользователе в колонке I.
        
        Args:
            telegram_id: ID пользователя в Telegram
            memory_text: новый текст для сохранения
            
        Returns:
            bool: True если успешно
        """
        if not self.is_available():
            return False

        try:
            records = await self.gateway.get_all_records(self.worksheet)
            existing_row = None
            
            for i, record in enumerate(records, start=2):
                if str(record.get('telegram_id', '')) == str(telegram_id):
                    existing_row = i
                    break
            
            if existing_row:
                # Обновляем колонку I (9)
                truncated_memory = self._truncate_to_gs_limit(memory_text, limit=5000)
                await self.gateway.batch_update(self.worksheet, [{
                    'range': f'I{existing_row}',
                    'values': [[truncated_memory]]
                }])
                logger.info(f"Обновлена долгосрочная память для пользователя {mask_telegram_id(telegram_id)}")
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка обновления памяти: {e}")
            return False

    async def update_appeal_status(self, telegram_id: int, appeal_text: str, status: str, specialist_answer: str = '') -> bool:
        """
        Обновляет статус обращения.
        
        Args:
            telegram_id: ID пользователя в Telegram
            appeal_text: текст обращения для поиска
            status: новый статус
            specialist_answer: ответ специалиста (опционально)
            
        Returns:
            bool: True если обновление прошло успешно
        """
        if not self.is_available():
            logger.error("Сервис обращений недоступен")
            return False

        try:
            records = await self.gateway.get_all_records(self.worksheet)
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            for i, record in enumerate(records, start=2):  # start=2 потому что строка 1 - заголовки
                if (str(record.get('telegram_id', '')) == str(telegram_id) and 
                    record.get('текст_обращений', '') == appeal_text):
                    
                    # Обновляем статус и ответ специалиста
                    await self.gateway.update(self.worksheet, f'F{i}', [[status]])  # статус
                    if specialist_answer:
                        await self.gateway.update(self.worksheet, f'G{i}', [[specialist_answer]])  # специалист_ответ
                    await self.gateway.update(self.worksheet, f'H{i}', [[timestamp]])  # время_обновления
                    
                    logger.info(f"Обновлен статус обращения для пользователя {mask_telegram_id(telegram_id)}")
                    return True
            
            logger.warning(f"Обращение не найдено для пользователя {mask_telegram_id(telegram_id)}")
            return False
            
        except Exception as e:
            logger.error(f"Ошибка обновления статуса обращения: {e}")
            return False

    async def get_all_appeals(self, status: Optional[str] = None) -> List[Dict]:
        """
        Получает все обращения, опционально фильтруя по статусу.
        
        Args:
            status: статус для фильтрации (опционально)
            
        Returns:
            List[Dict]: список всех обращений
        """
        if not self.is_available():
            logger.error("Сервис обращений недоступен")
            return []

        try:
            records = await self.gateway.get_all_records(self.worksheet)
            
            if status:
                filtered_records = [r for r in records if r.get('статус', '').lower() == status.lower()]
                logger.info(f"Найдено {len(filtered_records)} обращений со статусом '{status}'")
                return filtered_records
            else:
                logger.info(f"Найдено {len(records)} обращений всего")
                return records
                
        except Exception as e:
            logger.error(f"Ошибка получения всех обращений: {e}")
            return []

    async def check_for_responses(self) -> List[Dict]:
        """
        Проверяет наличие новых ответов специалистов в колонке G.
        
        Returns:
            List[Dict]: список записей с новыми ответами для отправки
        """
        if not self.is_available():
            logger.error("Сервис обращений недоступен")
            return []

        try:
            records = await self.gateway.get_all_records(self.worksheet)
            responses_to_send = []
            
            for i, record in enumerate(records, start=2):  # start=2 потому что строка 1 - заголовки
                specialist_answer = record.get('специалист_ответ', '').strip()
                telegram_id = record.get('telegram_id', '')
                
                if specialist_answer and telegram_id:
                    responses_to_send.append({
                        'row': i,
                        'telegram_id': int(telegram_id),
                        'response': specialist_answer,
                        'code': record.get('код', ''),
                        'fio': record.get('ФИО', '')
                    })
            
            if responses_to_send:
                logger.info(f"Найдено {len(responses_to_send)} ответов для отправки")
            
            return responses_to_send
            
        except Exception as e:
            logger.error(f"Ошибка проверки ответов: {e}")
            return []

    async def check_for_resolved_status(self) -> List[Dict]:
        """
        Проверяет наличие обращений со статусом 'Решено', о которых еще не уведомлен пользователь.
        Определяет это по отсутствию системного сообщения о решении в тексте обращений.
        
        Returns:
            List[Dict]: список решенных обращений для уведомления
        """
        if not self.is_available():
            return []

        try:
            records = await self.gateway.get_all_records(self.worksheet)
            resolved_appeals = []
            
            for i, record in enumerate(records, start=2):
                status = str(record.get('статус', '')).strip().lower()
                appeals_text = str(record.get('текст_обращений', ''))
                telegram_id = record.get('telegram_id', '')
                
                # Если статус "решено" и в тексте нет маркера закрытия
                if status == 'решено' and telegram_id:
                    # Маркеры, которые мы добавляем при закрытии (проверяем оба варианта)
                    closing_markers = [
                        "✅ Ваше обращение решено",
                        "✅ Ваше обращение отмечено как решенное специалистом."
                    ]
                    
                    # Проверяем, есть ли хотя бы один маркер
                    has_marker = any(marker in appeals_text for marker in closing_markers)
                    
                    if not has_marker:
                        resolved_appeals.append({
                            'row': i,
                            'telegram_id': int(telegram_id),
                            'appeals_text': appeals_text
                        })
            
            if resolved_appeals:
                logger.info(f"Найдено {len(resolved_appeals)} решенных обращений для уведомления")
                
            return resolved_appeals
            
        except Exception as e:
            logger.error(f"Ошибка проверки решенных статусов: {e}")
            return []

    async def clear_response(self, row: int) -> bool:
        """
        Очищает ответ специалиста в указанной строке.
        
        Args:
            row: номер строки для очистки
            
        Returns:
            bool: True если очистка прошла успешно
        """
        if not self.is_available():
            logger.error("Сервис обращений недоступен")
            return False

        try:
            # Очищаем колонку G (специалист_ответ) - используем batch_update
            await self.gateway.batch_update(self.worksheet, [{
                'range': f'G{row}',
                'values': [['']]
            }])
            logger.info(f"Очищен ответ специалиста в строке {row}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка очистки ответа в строке {row}: {e}")
            return False

    async def has_records(self) -> bool:
        """
        Проверяет, есть ли записи в таблице.
        
        Returns:
            bool: True если есть записи
        """
        if not self.is_available():
            return False

        try:
            records = await self.gateway.get_all_records(self.worksheet)
            return len(records) > 0
        except Exception as e:
            logger.error(f"Ошибка проверки наличия записей: {e}")
            return False

    async def add_specialist_response(self, telegram_id: int, response_text: str) -> bool:
        """
        Добавляет ответ специалиста к существующим обращениям пользователя.
        
        Args:
            telegram_id: ID пользователя в Telegram
            response_text: текст ответа специалиста
            
        Returns:
            bool: True если ответ добавлен успешно
        """
        if not self.is_available():
            logger.error("Сервис обращений недоступен")
            return False

        try:
            # Ищем существующую строку для этого telegram_id
            records = await self.gateway.get_all_records(self.worksheet)
            existing_row = None
            
            for i, record in enumerate(records, start=2):  # start=2 потому что строка 1 - заголовки
                if str(record.get('telegram_id', '')) == str(telegram_id):
                    existing_row = i
                    break
            
            if existing_row:
                # Получаем текущие обращения
                cell = await self.gateway.cell(self.worksheet, existing_row, 5)
                current_appeals = cell.value or ""  # колонка E
                
                # Добавляем ответ специалиста сверху
                if current_appeals.strip():
                    updated_appeals = f"{response_text}\n{current_appeals}"
                else:
                    updated_appeals = response_text
                # Усечение под лимит Google Sheets
                updated_appeals = self._truncate_to_gs_limit(updated_appeals)
                
                # Обновляем ячейку с обращениями
                await self.gateway.batch_update(self.worksheet, [{
                    'range': f'E{existing_row}',
                    'values': [[updated_appeals]]
                }])
                
                logger.info(f"Ответ специалиста добавлен для пользователя {mask_telegram_id(telegram_id)} (строка {existing_row})")
                return True
            else:
                logger.warning(f"Не найдена строка для пользователя {mask_telegram_id(telegram_id)}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка добавления ответа специалиста: {e}")
            return False

    async def add_ai_response(self, telegram_id: int, response_text: str) -> bool:
        """
        Добавляет ответ ИИ к существующим обращениям пользователя и устанавливает статус "Ответ ИИ".
        
        Args:
            telegram_id: ID пользователя в Telegram
            response_text: текст ответа ИИ
            
        Returns:
            bool: True если ответ добавлен успешно
        """
        if not self.is_available():
            logger.error("Сервис обращений недоступен")
            return False

        try:
            # Ищем существующую строку для этого telegram_id
            records = await self.gateway.get_all_records(self.worksheet)
            existing_row = None
            
            for i, record in enumerate(records, start=2):  # start=2 потому что строка 1 - заголовки
                if str(record.get('telegram_id', '')) == str(telegram_id):
                    existing_row = i
                    break
            
            if existing_row:
                # Получаем текущие обращения
                cell = await self.gateway.cell(self.worksheet, existing_row, 5)
                current_appeals = cell.value or ""  # колонка E
                
                # Добавляем ответ ИИ сверху с префиксом
                ai_response = f"🤖 ИИ: {response_text}"
                if current_appeals.strip():
                    updated_appeals = f"{ai_response}\n{current_appeals}"
                else:
                    updated_appeals = ai_response
                # Усечение под лимит Google Sheets
                updated_appeals = self._truncate_to_gs_limit(updated_appeals)
                
                # Обновляем ячейку с обращениями и статус
                await self.gateway.batch_update(self.worksheet, [{
                    'range': f'E{existing_row}',
                    'values': [[updated_appeals]]
                }, {
                    'range': f'F{existing_row}',
                    'values': [['Ответ ИИ']]
                }])
                
                logger.info(f"Статус обновлен на 'Ответ ИИ' для строки {existing_row}")
                
                # Устанавливаем заливку #ffffff (белый) для статуса "Ответ ИИ"
                try:
                    logger.info(f"Попытка установить заливку для ячейки F{existing_row}")
                    await self.gateway.format(self.worksheet, f'F{existing_row}', {
                        "backgroundColor": {
                            "red": 1.0,    # #ffffff
                            "green": 1.0,
                            "blue": 1.0
                        }
                    })
                    logger.info(f"Заливка успешно установлена для ячейки F{existing_row}")
                except Exception as format_error:
                    logger.error(f"Ошибка при установке заливки для ячейки F{existing_row}: {format_error}", exc_info=True)
                    # Продолжаем выполнение, даже если форматирование не удалось
                
                logger.info(f"Ответ ИИ добавлен для пользователя {mask_telegram_id(telegram_id)} (строка {existing_row})")
                return True
            else:
                logger.warning(f"Не найдена строка для пользователя {mask_telegram_id(telegram_id)}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка добавления ответа ИИ: {e}")
            return False

    async def add_user_message(self, telegram_id: int, message_text: str) -> bool:
        """
        Гарантированно добавляет пользовательское сообщение в колонку E без изменения статуса.
        Используется как дополнительная страховка при режиме специалиста.
        """
        if not self.is_available():
            logger.error("Сервис обращений недоступен")
            return False

        try:
            records = await self.gateway.get_all_records(self.worksheet)
            existing_row = None
            for i, record in enumerate(records, start=2):
                if str(record.get('telegram_id', '')) == str(telegram_id):
                    existing_row = i
                    break

            if existing_row:
                cell = await self.gateway.cell(self.worksheet, existing_row, 5)
                current_appeals = cell.value or ""
                timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                user_line = f"{timestamp}: Пользователь: {message_text}"
                updated_appeals = f"{user_line}\n{current_appeals}" if current_appeals.strip() else user_line
                # Усечение под лимит Google Sheets
                updated_appeals = self._truncate_to_gs_limit(updated_appeals)
                await self.gateway.batch_update(self.worksheet, [
                    {'range': f'E{existing_row}', 'values': [[updated_appeals]]},
                    {'range': f'H{existing_row}', 'values': [[timestamp]]}
                ])
                logger.info(f"Сообщение пользователя добавлено (страховка) для {mask_telegram_id(telegram_id)} (строка {existing_row})")
                return True
            else:
                logger.warning(f"Строка пользователя не найдена для добавления сообщения (telegram_id={mask_telegram_id(telegram_id)})")
                return False
        except Exception as e:
            logger.error(f"Ошибка добавления пользовательского сообщения: {e}")
            return False

    async def set_status_escalated(self, telegram_id: int) -> bool:
        """
        Устанавливает статус обращения на 'Передано специалисту' с красной заливкой #f3cccc.
        
        Args:
            telegram_id: ID пользователя в Telegram
            
        Returns:
            bool: True если статус установлен успешно
        """
        if not self.is_available():
            logger.error("Сервис обращений недоступен")
            return False

        try:
            # Ищем существующую строку для этого telegram_id
            records = await self.gateway.get_all_records(self.worksheet)
            existing_row = None
            
            for i, record in enumerate(records, start=2):  # start=2 потому что строка 1 - заголовки
                if str(record.get('telegram_id', '')) == str(telegram_id):
                    existing_row = i
                    break
            
            if existing_row:
                # Устанавливаем статус "Передано специалисту" в колонке F (статус)
                await self.gateway.batch_update(self.worksheet, [{
                    'range': f'F{existing_row}',
                    'values': [['Передано специалисту']]
                }])
                
                logger.info(f"Статус обновлен на 'Передано специалисту' для строки {existing_row}")
                
                # Устанавливаем заливку #f3cccc (светло-красный) для колонки F
                try:
                    logger.info(f"Попытка установить заливку #f3cccc для ячейки F{existing_row}")
                    await self.gateway.format(self.worksheet, f'F{existing_row}', {
                        "backgroundColor": {
                            "red": 0.95,    # #f3cccc
                            "green": 0.8,
                            "blue": 0.8
                        }
                    })
                    logger.info(f"Заливка успешно установлена для ячейки F{existing_row}")
                except Exception as format_error:
                    logger.error(f"Ошибка при установке заливки для ячейки F{existing_row}: {format_error}", exc_info=True)
                
                logger.info(f"Статус установлен 'Передано специалисту' для пользователя {mask_telegram_id(telegram_id)} (строка {existing_row})")
                return True
            else:
                logger.warning(f"Не найдена строка для пользователя {mask_telegram_id(telegram_id)}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка установки статуса 'Передано специалисту': {e}")
            return False

    async def set_status_in_work(self, telegram_id: int) -> bool:
        """
        Устанавливает статус обращения на 'В работе' с заливкой #fff2cc.
        
        Args:
            telegram_id: ID пользователя в Telegram
            
        Returns:
            bool: True если статус установлен успешно
        """
        if not self.is_available():
            logger.error("Сервис обращений недоступен")
            return False

        try:
            # Ищем существующую строку для этого telegram_id
            records = await self.gateway.get_all_records(self.worksheet)
            existing_row = None
            
            for i, record in enumerate(records, start=2):  # start=2 потому что строка 1 - заголовки
                if str(record.get('telegram_id', '')) == str(telegram_id):
                    existing_row = i
                    break
            
            if existing_row:
                # Устанавливаем статус "В работе" в колонке F (статус)
                await self.gateway.batch_update(self.worksheet, [{
                    'range': f'F{existing_row}',
                    'values': [['В работе']]
                }])
                
                logger.info(f"Статус обновлен на 'В работе' для строки {existing_row}")
                
                # Устанавливаем заливку #fff2cc (светло-желтый) для колонки F
                try:
                    logger.info(f"Попытка установить заливку #fff2cc для ячейки F{existing_row}")
                    await self.gateway.format(self.worksheet, f'F{existing_row}', {
                        "backgroundColor": {
                            "red": 1.0,    # #fff2cc
                            "green": 0.95,
                            "blue": 0.8
                        }
                    })
                    logger.info(f"Заливка успешно установлена для ячейки F{existing_row}")
                except Exception as format_error:
                    logger.error(f"Ошибка при установке заливки для ячейки F{existing_row}: {format_error}", exc_info=True)
                
                logger.info(f"Статус установлен 'В работе' для пользователя {mask_telegram_id(telegram_id)} (строка {existing_row})")
                return True
            else:
                logger.warning(f"Не найдена строка для пользователя {mask_telegram_id(telegram_id)}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка при установке статуса 'В работе': {e}")
            return False

    async def set_status_resolved(self, telegram_id: int) -> bool:
        """
        Устанавливает статус обращения на 'Решено' с зелёной заливкой #d9ead3.
        
        Args:
            telegram_id: ID пользователя в Telegram
            
        Returns:
            bool: True если статус установлен успешно
        """
        if not self.is_available():
            logger.error("Сервис обращений недоступен")
            return False

        try:
            # Ищем существующую строку для этого telegram_id
            records = await self.gateway.get_all_records(self.worksheet)
            existing_row = None
            
            for i, record in enumerate(records, start=2):
                if str(record.get('telegram_id', '')) == str(telegram_id):
                    existing_row = i
                    break
            
            if existing_row:
                # Устанавливаем статус "Решено" в колонке F (статус)
                await self.gateway.batch_update(self.worksheet, [{
                    'range': f'F{existing_row}',
                    'values': [['Решено']]
                }])
                
                logger.info(f"Статус обновлен на 'Решено' для строки {existing_row}")
                
                # Зелёная заливка #d9ead3
                try:
                    logger.info(f"Попытка установить заливку #d9ead3 для ячейки F{existing_row}")
                    await self.gateway.format(self.worksheet, f'F{existing_row}', {
                        "backgroundColor": {
                            "red": 0.85,
                            "green": 0.92,
                            "blue": 0.83
                        }
                    })
                    logger.info(f"Заливка успешно установлена для ячейки F{existing_row}")
                except Exception as format_error:
                    logger.error(f"Ошибка при установке заливки для ячейки F{existing_row}: {format_error}", exc_info=True)
                
                logger.info(f"Статус установлен 'Решено' для пользователя {mask_telegram_id(telegram_id)} (строка {existing_row})")
                return True
            else:
                logger.warning(f"Не найдена строка для пользователя {mask_telegram_id(telegram_id)}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка при установке статуса 'Решено': {e}")
            return False

    async def get_appeal_status(self, telegram_id: int) -> str:
        """
        Получает статус обращения пользователя.
        
        Args:
            telegram_id: ID пользователя в Telegram
            
        Returns:
            str: статус обращения или 'новое' если не найден
        """
        if not self.is_available():
            logger.error("Сервис обращений недоступен")
            return 'новое'

        try:
            # Ищем существующую строку для этого telegram_id
            records = await self.gateway.get_all_records(self.worksheet)
            
            for i, record in enumerate(records, start=2):
                if str(record.get('telegram_id', '')) == str(telegram_id):
                    status = record.get('статус', 'новое')
                    logger.info(f"Найден статус для пользователя {mask_telegram_id(telegram_id)}: {status}")
                    # Авто-форматирование: применяем заливку в зависимости от статуса
                    try:
                        status_lower = str(status).strip().lower()
                        if status_lower == 'решено':
                            logger.info(f"Попытка установить заливку #d9ead3 для ячейки F{i} (статус: решено)")
                            await self.gateway.format(self.worksheet, f'F{i}', {
                                "backgroundColor": {
                                    "red": 0.85,
                                    "green": 0.92,
                                    "blue": 0.83
                                }
                            })
                            logger.info(f"Заливка успешно установлена для ячейки F{i}")
                        elif status_lower == 'в работе':
                            logger.info(f"Попытка установить заливку #fff2cc для ячейки F{i} (статус: в работе)")
                            await self.gateway.format(self.worksheet, f'F{i}', {
                                "backgroundColor": {
                                    "red": 1.0,
                                    "green": 0.95,
                                    "blue": 0.8
                                }
                            })
                            logger.info(f"Заливка успешно установлена для ячейки F{i}")
                    except Exception as e:
                        logger.error(f"Не удалось применить форматирование для строки {i}: {e}", exc_info=True)
                    return status
            
            logger.info(f"Статус для пользователя {mask_telegram_id(telegram_id)} не найден, возвращаем 'новое'")
            return 'новое'
                
        except Exception as e:
            logger.error(f"Ошибка получения статуса обращения: {e}")
            return 'новое'
