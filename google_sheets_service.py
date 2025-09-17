import gspread
from oauth2client.service_account import ServiceAccountCredentials
import logging
import os
from dotenv import load_dotenv

# Настройка логирования
logger = logging.getLogger(__name__)

class GoogleSheetsService:
    """
    Сервис для работы с Google Sheets.
    """
    def __init__(self):
        """
        Инициализирует клиент gspread для доступа к Google Sheets.
        """
        logger.info("Инициализация Google Sheets сервиса...")
        try:
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            logger.info("Попытка загрузки credentials.json...")
            creds = ServiceAccountCredentials.from_json_keyfile_name(
                'credentials.json', scope
            )
            logger.info("Попытка авторизации в Google Sheets...")
            self.client = gspread.authorize(creds)
            logger.info("Успешная аутентификация в Google Sheets.")
        except FileNotFoundError:
            logger.error("Файл credentials.json не найден.")
            self.client = None
        except Exception as e:
            logger.error(f"Ошибка аутентификации в Google Sheets: {e}")
            self.client = None

    def get_sheet_by_url(self, sheet_url: str):
        """
        Открывает таблицу по её URL.
        """
        if not self.client:
            logger.error("Клиент Google Sheets не инициализирован.")
            return None
        try:
            spreadsheet = self.client.open_by_url(sheet_url)
            logger.info(f"Успешно открыта таблица: {spreadsheet.title}")
            return spreadsheet
        except gspread.exceptions.SpreadsheetNotFound:
            logger.error(f"Таблица по URL {sheet_url} не найдена.")
            return None
        except Exception as e:
            logger.error(f"Не удалось открыть таблицу по URL {sheet_url}: {e}")
            return None
