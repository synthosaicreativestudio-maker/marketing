import logging
import os
import datetime
from google_sheets_service import GoogleSheetsService

logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self, sheets_service: GoogleSheetsService):
        self.sheets_service = sheets_service
        self.sheet_url = os.getenv("SHEET_URL")
        self.spreadsheet = None
        self.sheet = None
        if self.sheet_url:
            self.spreadsheet = self.sheets_service.get_sheet_by_url(self.sheet_url)
            if self.spreadsheet:
                # Get the first worksheet from the spreadsheet
                self.sheet = self.spreadsheet.sheet1
        else:
            logger.error("SHEET_URL не найден в .env файле.")

    def find_and_update_user(self, partner_code: str, partner_phone: str, telegram_id: int) -> bool:
        """
        Ищет пользователя и обновляет его статус авторизации.
        """
        logger.info(f"Поиск пользователя: код={partner_code}, телефон={partner_phone}, telegram_id={telegram_id}")
        
        if not self.sheet:
            logger.error("Таблица авторизации не загружена.")
            return False
            
        try:
            logger.info("Получение всех записей из таблицы...")
            records = self.sheet.get_all_records()
            logger.info(f"Получено {len(records)} записей из таблицы")
            
            # Добавляем проверку на пустые данные
            if not partner_code or not partner_phone:
                logger.warning("Получены пустые данные для поиска пользователя")
                return False
            
            for i, row in enumerate(records):
                logger.info(f"Проверка записи {i+1}: {row}")
                
                # Колонки в таблице могут иметь разные названия, используем get()
                code_in_sheet = str(row.get('Код партнера', ''))
                phone_in_sheet = str(row.get('Телефон партнера', ''))
                
                logger.info(f"Сравнение: код в таблице='{code_in_sheet}' vs код из формы='{partner_code}'")

                # Нормализуем оба номера, оставляя только цифры
                normalized_phone_from_app = ''.join(filter(str.isdigit, partner_phone))
                normalized_phone_in_sheet = ''.join(filter(str.isdigit, phone_in_sheet))
                
                logger.info(f"Нормализованные телефоны: из формы='{normalized_phone_from_app}' vs из таблицы='{normalized_phone_in_sheet}'")

                # Убираем '7' или '8' в начале для унификации
                if normalized_phone_from_app.startswith('7') or normalized_phone_from_app.startswith('8'):
                    normalized_phone_from_app = normalized_phone_from_app[1:]
                
                if normalized_phone_in_sheet.startswith('7') or normalized_phone_in_sheet.startswith('8'):
                    normalized_phone_in_sheet = normalized_phone_in_sheet[1:]
                
                logger.info(f"Телефоны после нормализации: из формы='{normalized_phone_from_app}' vs из таблицы='{normalized_phone_in_sheet}'")

                if code_in_sheet == partner_code and normalized_phone_in_sheet == normalized_phone_from_app:
                    logger.info(f"Найдено совпадение в записи {i+1}")
                    row_index = i + 2
                    
                    logger.info(f"Обновление статуса в строке {row_index}")
                    self.sheet.update_cell(row_index, 4, "Авторизован") # Колонка D: Статус
                    self.sheet.update_cell(row_index, 5, telegram_id)   # Колонка E: Telegram ID
                    self.sheet.update_cell(row_index, 6, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")) # Колонка F: Дата
                    
                    logger.info(f"Пользователь с кодом {partner_code} успешно авторизован.")
                    return True
                else:
                    logger.info(f"Запись {i+1} не совпадает")
            
            logger.warning(f"Пользователь с кодом {partner_code} и телефоном {partner_phone} не найден.")
            return False
        except Exception as e:
            logger.error(f"Ошибка при поиске и обновлении пользователя: {e}")
            return False

    def get_user_auth_status(self, telegram_id: int) -> bool:
        """
        Проверяет статус авторизации пользователя по Telegram ID.
        """
        logger.info(f"Проверка статуса авторизации для пользователя {telegram_id}")
        
        if not self.sheet:
            logger.error("Таблица авторизации не загружена.")
            return False

        try:
            logger.info("Получение всех записей из таблицы для проверки статуса...")
            records = self.sheet.get_all_records()
            logger.info(f"Получено {len(records)} записей из таблицы для проверки статуса")
            
            for i, row in enumerate(records):
                logger.info(f"Проверка записи {i+1} для статуса: {row}")
                
                # Проверяем, есть ли 'Telegram ID' в строке и совпадает ли он
                telegram_id_in_sheet = row.get('Telegram ID')
                logger.info(f"Сравнение Telegram ID: в таблице='{telegram_id_in_sheet}' vs запрашиваемый='{telegram_id}'")
                
                if str(telegram_id_in_sheet) == str(telegram_id):
                    # Проверяем статус в колонке 'Статус'
                    status = row.get('Статус')
                    logger.info(f"Найден пользователь с Telegram ID {telegram_id}, статус: {status}")
                    result = status == "Авторизован"
                    logger.info(f"Результат проверки авторизации: {result}")
                    return result
                else:
                    logger.info(f"Запись {i+1} не соответствует запрашиваемому Telegram ID")
                    
            logger.info(f"Пользователь с Telegram ID {telegram_id} не найден в таблице")
            return False
        except Exception as e:
            logger.error(f"Ошибка при проверке статуса пользователя: {e}")
            return False
