import logging
import re
from typing import Optional, Tuple, Dict, Any
from sheets_client import GoogleSheetsClient

logger = logging.getLogger(__name__)

class AuthModule:
    """Модуль авторизации пользователей по коду партнера и телефону"""
    
    def __init__(self, sheets_client: GoogleSheetsClient):
        self.sheets_client = sheets_client
        self.auth_worksheet_name = 'список сотрудников для авторизации'
        
    def find_user_by_credentials(self, code: str, phone: str) -> Optional[Dict[str, Any]]:
        """
        Ищет пользователя по коду партнера и телефону
        
        Args:
            code: Код партнера
            phone: Номер телефона
            
        Returns:
            Dict с данными пользователя или None если не найден
        """
        try:
            logger.info(f'🔍 Поиск пользователя: код={code}, телефон={phone[:3]}***')
            
            # Получаем данные из таблицы авторизации
            if not self.sheets_client.sheet:
                logger.error('Google Sheets не подключен')
                return None
            
            # Получаем все данные
            all_values = self.sheets_client.sheet.get_all_values()
            if len(all_values) <= 1:
                logger.warning('Таблица пуста или содержит только заголовки')
                return None
            
            headers = all_values[0]
            data = all_values[1:]
            
            # Находим индексы нужных колонок
            code_col = self._find_column_index(headers, ['код партнера', 'код', 'partner_code'])
            phone_col = self._find_column_index(headers, ['телефон партнера', 'телефон', 'phone', 'phone_number'])
            status_col = self._find_column_index(headers, ['статус авторизации', 'статус', 'status'])
            telegram_col = self._find_column_index(headers, ['telegram id', 'telegram_id', 'telegram'])
            fio_col = self._find_column_index(headers, ['фио партнера', 'фио', 'fio', 'name'])
            
            if code_col == -1 or phone_col == -1:
                logger.error(f'Не найдены колонки: код={code_col}, телефон={phone_col}')
                return None
            
            # Очищаем телефон от всех символов кроме цифр
            cleaned_phone = ''.join(filter(str.isdigit, phone))
            
            # Ищем пользователя
            for i, row in enumerate(data):
                if len(row) > max(code_col, phone_col):
                    sheet_code = str(row[code_col]).strip()
                    sheet_phone = str(row[phone_col]).strip()
                    sheet_phone_cleaned = ''.join(filter(str.isdigit, sheet_phone))
                    
                    # Сравниваем код и телефон
                    if sheet_code == code and sheet_phone_cleaned == cleaned_phone:
                        user_data = {
                            'row': i + 2,  # +2 потому что индексы начинаются с 0 и пропускаем заголовок
                            'code': code,
                            'phone': phone,
                            'status': row[status_col] if status_col != -1 and len(row) > status_col else 'неизвестно',
                            'telegram_id': row[telegram_col] if telegram_col != -1 and len(row) > telegram_col else '',
                            'fio': row[fio_col] if fio_col != -1 and len(row) > fio_col else 'Неизвестно',
                            'headers': headers
                        }
                        
                        logger.info(f'✅ Пользователь найден в строке {user_data["row"]}: {user_data["fio"]}')
                        return user_data
            
            logger.warning(f'❌ Пользователь не найден: код={code}, телефон={phone}')
            return None
            
        except Exception as e:
            logger.error(f'❌ Ошибка поиска пользователя: {e}')
            return None
    
    def authorize_user(self, user_data: Dict[str, Any], telegram_id: str) -> bool:
        """
        Авторизует пользователя, обновляя статус и Telegram ID
        
        Args:
            user_data: Данные пользователя из find_user_by_credentials
            telegram_id: Telegram ID пользователя
            
        Returns:
            True если авторизация успешна, False в противном случае
        """
        try:
            if not user_data or 'row' not in user_data:
                logger.error('Некорректные данные пользователя для авторизации')
                return False
            
            row = user_data['row']
            headers = user_data['headers']
            
            logger.info(f'🔄 Авторизация пользователя {user_data["fio"]} в строке {row}')
            
            # Находим индексы колонок
            status_col = self._find_column_index(headers, ['статус авторизации', 'статус', 'status'])
            telegram_col = self._find_column_index(headers, ['telegram id', 'telegram_id', 'telegram'])
            
            if status_col == -1 or telegram_col == -1:
                logger.error(f'Не найдены колонки для обновления: статус={status_col}, telegram={telegram_col}')
                return False
            
            # Обновляем статус авторизации
            self.sheets_client.sheet.update_cell(row, status_col + 1, 'авторизован')
            logger.info(f'✅ Статус обновлен на "авторизован"')
            
            # Обновляем Telegram ID
            self.sheets_client.sheet.update_cell(row, telegram_col + 1, str(telegram_id))
            logger.info(f'✅ Telegram ID обновлен: {telegram_id}')
            
            logger.info(f'🎉 Пользователь {user_data["fio"]} успешно авторизован')
            return True
            
        except Exception as e:
            logger.error(f'❌ Ошибка авторизации пользователя: {e}')
            return False
    
    def check_user_authorization(self, telegram_id: str) -> Optional[Dict[str, Any]]:
        """
        Проверяет, авторизован ли пользователь
        
        Args:
            telegram_id: Telegram ID пользователя
            
        Returns:
            Dict с данными пользователя если авторизован, None в противном случае
        """
        try:
            if not self.sheets_client.sheet:
                return None
            
            # Получаем все данные
            all_values = self.sheets_client.sheet.get_all_values()
            if len(all_values) <= 1:
                return None
            
            headers = all_values[0]
            data = all_values[1:]
            
            # Находим колонки
            telegram_col = self._find_column_index(headers, ['telegram id', 'telegram_id', 'telegram'])
            status_col = self._find_column_index(headers, ['статус авторизации', 'статус', 'status'])
            fio_col = self._find_column_index(headers, ['фио партнера', 'фио', 'fio', 'name'])
            
            if telegram_col == -1 or status_col == -1:
                return None
            
            # Ищем пользователя по Telegram ID
            for i, row in enumerate(data):
                if len(row) > telegram_col and str(row[telegram_col]).strip() == str(telegram_id):
                    status = row[status_col] if status_col != -1 and len(row) > status_col else ''
                    
                    # Проверяем статус авторизации
                    if status and 'авторизован' in str(status).lower():
                        user_data = {
                            'row': i + 2,
                            'telegram_id': telegram_id,
                            'status': status,
                            'fio': row[fio_col] if fio_col != -1 and len(row) > fio_col else 'Неизвестно',
                            'is_authorized': True
                        }
                        logger.info(f'✅ Пользователь {user_data["fio"]} авторизован')
                        return user_data
            
            logger.info(f'❌ Пользователь с Telegram ID {telegram_id} не авторизован')
            return None
            
        except Exception as e:
            logger.error(f'❌ Ошибка проверки авторизации: {e}')
            return None
    
    def get_all_authorized_users(self) -> list:
        """
        Получает список всех авторизованных пользователей
        
        Returns:
            Список авторизованных пользователей
        """
        try:
            if not self.sheets_client.sheet:
                return []
            
            all_values = self.sheets_client.sheet.get_all_values()
            if len(all_values) <= 1:
                return []
            
            headers = all_values[0]
            data = all_values[1:]
            
            # Находим колонки
            status_col = self._find_column_index(headers, ['статус авторизации', 'статус', 'status'])
            telegram_col = self._find_column_index(headers, ['telegram id', 'telegram_id', 'telegram'])
            fio_col = self._find_column_index(headers, ['фио партнера', 'фио', 'fio', 'name'])
            code_col = self._find_column_index(headers, ['код партнера', 'код', 'partner_code'])
            
            authorized_users = []
            
            for i, row in enumerate(data):
                if len(row) > status_col:
                    status = row[status_col] if status_col != -1 else ''
                    telegram_id = row[telegram_col] if telegram_col != -1 and len(row) > telegram_col else ''
                    
                    # Проверяем статус авторизации и наличие Telegram ID
                    if status and 'авторизован' in str(status).lower() and telegram_id:
                        user_data = {
                            'row': i + 2,
                            'telegram_id': telegram_id,
                            'fio': row[fio_col] if fio_col != -1 and len(row) > fio_col else 'Неизвестно',
                            'code': row[code_col] if code_col != -1 and len(row) > code_col else '',
                            'status': status
                        }
                        authorized_users.append(user_data)
            
            logger.info(f'📊 Найдено {len(authorized_users)} авторизованных пользователей')
            return authorized_users
            
        except Exception as e:
            logger.error(f'❌ Ошибка получения авторизованных пользователей: {e}')
            return []
    
    def _find_column_index(self, headers: list, possible_names: list) -> int:
        """
        Находит индекс колонки по возможным названиям
        
        Args:
            headers: Заголовки таблицы
            possible_names: Возможные названия колонки
            
        Returns:
            Индекс колонки или -1 если не найдена
        """
        for i, header in enumerate(headers):
            header_lower = str(header).lower().strip()
            for name in possible_names:
                if name.lower() in header_lower:
                    return i
        return -1
    
    def validate_credentials(self, code: str, phone: str) -> Tuple[bool, str]:
        """
        Валидирует введенные данные
        
        Args:
            code: Код партнера
            phone: Номер телефона
            
        Returns:
            Tuple (is_valid, error_message)
        """
        # Проверяем код партнера
        if not code or not code.strip():
            return False, "Код партнера не может быть пустым"
        
        if not re.match(r'^\d+$', code.strip()):
            return False, "Код партнера должен содержать только цифры"
        
        # Проверяем телефон
        if not phone or not phone.strip():
            return False, "Номер телефона не может быть пустым"
        
        # Очищаем телефон от всех символов кроме цифр
        cleaned_phone = ''.join(filter(str.isdigit, phone))
        
        if len(cleaned_phone) < 10:
            return False, "Номер телефона должен содержать минимум 10 цифр"
        
        if len(cleaned_phone) > 15:
            return False, "Номер телефона слишком длинный"
        
        return True, ""
