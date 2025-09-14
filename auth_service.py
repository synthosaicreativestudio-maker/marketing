import logging
import os
import datetime
from google_sheets_service import GoogleSheetsService

logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self, sheets_service: GoogleSheetsService):
        self.sheets_service = sheets_service
        self.sheet_url = os.getenv("SHEET_URL")
        self.sheet = None
        if self.sheet_url:
            self.sheet = self.sheets_service.get_sheet_by_url(self.sheet_url)
        else:
            logger.error("SHEET_URL не найден в .env файле.")

    def find_and_update_user(self, partner_code: str, partner_phone: str, telegram_id: int) -> bool:
        """
        Ищет пользователя и обновляет его статус авторизации.
        """
        if not self.sheet:
            logger.error("Таблица авторизации не загружена.")
            return False
            
        try:
            records = self.sheet.get_all_records()
            for i, row in enumerate(records):
                # Колонки в таблице могут иметь разные названия, используем get()
                code_in_sheet = str(row.get('Код партнера', ''))
                phone_in_sheet = str(row.get('Телефон партнера', ''))

                # Нормализуем оба номера, оставляя только цифры
                normalized_phone_from_app = ''.join(filter(str.isdigit, partner_phone))
                normalized_phone_in_sheet = ''.join(filter(str.isdigit, phone_in_sheet))

                # Убираем '7' или '8' в начале для унификации
                if normalized_phone_from_app.startswith('7') or normalized_phone_from_app.startswith('8'):
                    normalized_phone_from_app = normalized_phone_from_app[1:]
                
                if normalized_phone_in_sheet.startswith('7') or normalized_phone_in_sheet.startswith('8'):
                    normalized_phone_in_sheet = normalized_phone_in_sheet[1:]

                if code_in_sheet == partner_code and normalized_phone_in_sheet == normalized_phone_from_app:
                    row_index = i + 2
                    
                    self.sheet.update_cell(row_index, 4, "Авторизован") # Колонка D: Статус
                    self.sheet.update_cell(row_index, 5, telegram_id)   # Колонка E: Telegram ID
                    self.sheet.update_cell(row_index, 6, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")) # Колонка F: Дата
                    
                    logger.info(f"Пользователь с кодом {partner_code} успешно авторизован.")
                    return True
            
            logger.warning(f"Пользователь с кодом {partner_code} и телефоном {partner_phone} не найден.")
            return False
        except Exception as e:
            logger.error(f"Ошибка при поиске и обновлении пользователя: {e}")
            return False

    def get_user_auth_status(self, telegram_id: int) -> bool:
        """
        Проверяет статус авторизации пользователя по Telegram ID.
        """
        if not self.sheet:
            return False

        try:
            # Получаем все значения из 5-й колонки (E)
            telegram_ids = self.sheet.col_values(5)
            # Ищем индекс строки с нужным ID (начинаем с 1, так как 0 - заголовок)
            try:
                row_index = telegram_ids.index(str(telegram_id)) + 1
                # Проверяем статус в 4-й колонке (D) той же строки
                status = self.sheet.cell(row_index, 4).value
                return status == "Авторизован"
            except ValueError:
                # ID не найден в списке
                return False
        except Exception as e:
            logger.error(f"Ошибка при проверке статуса пользователя: {e}")
            return False