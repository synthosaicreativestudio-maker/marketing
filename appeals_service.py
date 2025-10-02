"""
Сервис для работы с обращениями в Google Sheets.
Адаптирован под структуру листа 'обращения'.
"""

import logging
import datetime
from typing import Optional, List, Dict
from sheets import _get_client_and_sheet, SheetsNotConfiguredError

logger = logging.getLogger(__name__)


class AppealsService:
    """Сервис для работы с обращениями в листе 'обращения'."""
    
    def __init__(self):
        """Инициализация сервиса обращений."""
        self.worksheet = None
        try:
            client, worksheet = _get_client_and_sheet()
            # Ищем лист 'обращения'
            spreadsheet = worksheet.spreadsheet
            for ws in spreadsheet.worksheets():
                if 'обращения' in ws.title.lower():
                    self.worksheet = ws
                    break
            
            if not self.worksheet:
                logger.critical("Лист 'обращения' не найден в таблице")
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
        Создает новое обращение в листе.
        
        Args:
            code: код партнера
            phone: телефон партнера
            fio: ФИО партнера
            telegram_id: ID пользователя в Telegram
            text: текст обращения
            
        Returns:
            bool: True если обращение создано успешно
        """
        if not self.is_available():
            logger.error("Сервис обращений недоступен")
            return False

        try:
            # Находим первую пустую строку
            all_values = self.worksheet.get_all_values()
            next_row = len(all_values) + 1
            
            # Подготавливаем данные для записи
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            row_data = [
                code,
                phone,
                fio,
                str(telegram_id),
                text,
                'новое',  # статус
                '',  # специалист_ответ (пустой)
                timestamp  # время_обновления
            ]
            
            # Записываем данные
            self.worksheet.append_row(row_data)
            
            logger.info(f"Создано обращение для пользователя {telegram_id} (код: {code})")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка создания обращения: {e}")
            return False

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
