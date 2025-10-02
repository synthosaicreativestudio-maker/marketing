"""
Сервис для работы с обращениями в Google Sheets.
Адаптирован под структуру листа 'обращения'.
"""

import logging
import datetime
from typing import Optional, List, Dict
from sheets import _get_appeals_client_and_sheet, SheetsNotConfiguredError

logger = logging.getLogger(__name__)


class AppealsService:
    """Сервис для работы с обращениями в листе 'обращения'."""
    
    def __init__(self):
        """Инициализация сервиса обращений."""
        self.worksheet = None
        try:
            client, worksheet = _get_appeals_client_and_sheet()
            self.worksheet = worksheet
            
            if not self.worksheet:
                logger.critical("Не удалось подключиться к таблице обращений")
            else:
                logger.info(f"Лист 'обращения' найден: {self.worksheet.title}")
                
        except SheetsNotConfiguredError as e:
            logger.critical(f"Sheets не сконфигурирован: {e}")
        except Exception as e:
            logger.critical(f"Не удалось инициализировать доступ к листу 'обращения': {e}")

    def is_available(self) -> bool:
        """Проверяет доступность сервиса обращений."""
        return self.worksheet is not None

    def create_appeal(self, code: str, phone: str, fio: str, telegram_id: int, text: str) -> bool:
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
            logger.info(f"Создание обращения для telegram_id={telegram_id}, code={code}, phone={phone}, fio={fio}")
            # Ищем существующую строку для этого telegram_id
            records = self.worksheet.get_all_records()
            logger.info(f"Получено {len(records)} записей из таблицы обращений")
            existing_row = None
            
            for i, record in enumerate(records, start=2):  # start=2 потому что строка 1 - заголовки
                record_telegram_id = str(record.get('telegram_id', ''))
                logger.info(f"Проверка записи {i}: telegram_id='{record_telegram_id}' vs '{telegram_id}'")
                if record_telegram_id == str(telegram_id):
                    existing_row = i
                    logger.info(f"Найдена существующая строка {i} для telegram_id {telegram_id}")
                    break
            
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            new_appeal = f"{timestamp}: {text}"
            
            if existing_row:
                # Обновляем существующую строку
                current_appeals = self.worksheet.cell(existing_row, 5).value or ""  # колонка E
                
                # Добавляем новое обращение сверху
                if current_appeals.strip():
                    updated_appeals = f"{new_appeal}\n{current_appeals}"
                else:
                    updated_appeals = new_appeal
                
                # Очищаем старые обращения (>30 дней)
                updated_appeals = self._cleanup_old_appeals(updated_appeals)
                
                # Обновляем ячейку с обращениями и время обновления через batch_update
                self.worksheet.batch_update([{
                    'range': f'E{existing_row}',
                    'values': [[updated_appeals]]
                }, {
                    'range': f'H{existing_row}',
                    'values': [[timestamp]]
                }])
                
                logger.info(f"Обновлено обращение для пользователя {telegram_id} (строка {existing_row})")
            else:
                # Создаем новую строку
                next_row = len(records) + 2  # +2 потому что records не включает заголовок
                logger.info(f"Создание новой строки {next_row} для telegram_id {telegram_id}")
                
                row_data = [
                    code,
                    phone,
                    fio,
                    str(telegram_id),
                    new_appeal,  # текст_обращений
                    'новое',  # статус
                    '',  # специалист_ответ (пустой)
                    timestamp  # время_обновления
                ]
                
                logger.info(f"Данные для записи: {row_data}")
                self.worksheet.append_row(row_data)
                logger.info(f"Создано новое обращение для пользователя {telegram_id} (строка {next_row})")
            
            return True
            
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

    def get_user_appeals(self, telegram_id: int) -> List[Dict]:
        """
        Получает все обращения пользователя.
        
        Args:
            telegram_id: ID пользователя в Telegram
            
        Returns:
            List[Dict]: список обращений пользователя
        """
        if not self.is_available():
            logger.error("Сервис обращений недоступен")
            return []

        try:
            records = self.worksheet.get_all_records()
            user_appeals = []
            
            for record in records:
                if str(record.get('telegram_id', '')) == str(telegram_id):
                    user_appeals.append(record)
            
            logger.info(f"Найдено {len(user_appeals)} обращений для пользователя {telegram_id}")
            return user_appeals
            
        except Exception as e:
            logger.error(f"Ошибка получения обращений пользователя: {e}")
            return []

    def update_appeal_status(self, telegram_id: int, appeal_text: str, status: str, specialist_answer: str = '') -> bool:
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
            records = self.worksheet.get_all_records()
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            for i, record in enumerate(records, start=2):  # start=2 потому что строка 1 - заголовки
                if (str(record.get('telegram_id', '')) == str(telegram_id) and 
                    record.get('текст_обращений', '') == appeal_text):
                    
                    # Обновляем статус и ответ специалиста
                    self.worksheet.update(f'F{i}', status)  # статус
                    if specialist_answer:
                        self.worksheet.update(f'G{i}', specialist_answer)  # специалист_ответ
                    self.worksheet.update(f'H{i}', timestamp)  # время_обновления
                    
                    logger.info(f"Обновлен статус обращения для пользователя {telegram_id}")
                    return True
            
            logger.warning(f"Обращение не найдено для пользователя {telegram_id}")
            return False
            
        except Exception as e:
            logger.error(f"Ошибка обновления статуса обращения: {e}")
            return False

    def get_all_appeals(self, status: Optional[str] = None) -> List[Dict]:
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
            records = self.worksheet.get_all_records()
            
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

    def check_for_responses(self) -> List[Dict]:
        """
        Проверяет наличие новых ответов специалистов в колонке G.
        
        Returns:
            List[Dict]: список записей с новыми ответами для отправки
        """
        if not self.is_available():
            logger.error("Сервис обращений недоступен")
            return []

        try:
            records = self.worksheet.get_all_records()
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

    def clear_response(self, row: int) -> bool:
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
            self.worksheet.batch_update([{
                'range': f'G{row}',
                'values': [['']]
            }])
            logger.info(f"Очищен ответ специалиста в строке {row}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка очистки ответа в строке {row}: {e}")
            return False

    def has_records(self) -> bool:
        """
        Проверяет, есть ли записи в таблице.
        
        Returns:
            bool: True если есть записи
        """
        if not self.is_available():
            return False

        try:
            records = self.worksheet.get_all_records()
            return len(records) > 0
        except Exception as e:
            logger.error(f"Ошибка проверки наличия записей: {e}")
            return False

    def add_specialist_response(self, telegram_id: int, response_text: str) -> bool:
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
            records = self.worksheet.get_all_records()
            existing_row = None
            
            for i, record in enumerate(records, start=2):  # start=2 потому что строка 1 - заголовки
                if str(record.get('telegram_id', '')) == str(telegram_id):
                    existing_row = i
                    break
            
            if existing_row:
                # Получаем текущие обращения
                current_appeals = self.worksheet.cell(existing_row, 5).value or ""  # колонка E
                
                # Добавляем ответ специалиста сверху
                if current_appeals.strip():
                    updated_appeals = f"{response_text}\n{current_appeals}"
                else:
                    updated_appeals = response_text
                
                # Обновляем ячейку с обращениями
                self.worksheet.batch_update([{
                    'range': f'E{existing_row}',
                    'values': [[updated_appeals]]
                }])
                
                logger.info(f"Ответ специалиста добавлен для пользователя {telegram_id} (строка {existing_row})")
                return True
            else:
                logger.warning(f"Не найдена строка для пользователя {telegram_id}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка добавления ответа специалиста: {e}")
            return False

    def set_status_in_work(self, telegram_id: int) -> bool:
        """
        Устанавливает статус обращения на 'в работе' с заливкой #f4cccc.
        
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
            records = self.worksheet.get_all_records()
            existing_row = None
            
            for i, record in enumerate(records, start=2):  # start=2 потому что строка 1 - заголовки
                if str(record.get('telegram_id', '')) == str(telegram_id):
                    existing_row = i
                    break
            
            if existing_row:
                # Устанавливаем статус "в работе" в колонке F
                self.worksheet.batch_update([{
                    'range': f'F{existing_row}',
                    'values': [['в работе']]
                }])
                
                # Устанавливаем заливку #f4cccc для колонки F
                self.worksheet.format(f'F{existing_row}', {
                    "backgroundColor": {
                        "red": 0.956,
                        "green": 0.8,
                        "blue": 0.8
                    }
                })
                
                logger.info(f"Статус установлен 'в работе' для пользователя {telegram_id} (строка {existing_row})")
                return True
            else:
                logger.warning(f"Не найдена строка для пользователя {telegram_id}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка установки статуса 'в работе': {e}")
            return False
