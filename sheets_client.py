import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials

logger = logging.getLogger(__name__)

class GoogleSheetsClient:
    """A client to handle all interactions with the Google Sheet."""

    def __init__(self, credentials_path: str, sheet_url: str, worksheet_name: str):
        self.sheet = self._connect(credentials_path, sheet_url, worksheet_name)

    def _connect(self, credentials_path, sheet_url, worksheet_name):
        """Настраивает подключение к Google Sheets и возвращает рабочий лист."""
        try:
            scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
                     "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
            
            creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_path, scope)
            client = gspread.authorize(creds)
            
            logger.info(f"Connecting to sheet: {sheet_url}")
            logger.info(f"Looking for worksheet: {worksheet_name}")
            
            # Если имя листа не указано или не найдено, берем первый лист
            try:
                if worksheet_name:
                    sheet = client.open_by_url(sheet_url).worksheet(worksheet_name)
                    logger.info(f"Successfully connected to worksheet: {worksheet_name}")
                else:
                    sheet = client.open_by_url(sheet_url).get_worksheet(0)
                    logger.info("Connected to first worksheet (index 0)")
            except Exception as e:
                logger.warning(f"Failed to connect to worksheet '{worksheet_name}', trying first worksheet: {e}")
                sheet = client.open_by_url(sheet_url).get_worksheet(0)
                logger.info("Connected to first worksheet (index 0) as fallback")
            
            # Проверяем размер таблицы
            try:
                row_count = len(sheet.get_all_values())
                logger.info(f"Sheet has {row_count} rows")
                if row_count > 0:
                    first_row = sheet.row_values(1)
                    logger.info(f"First row (headers): {first_row}")
            except Exception as e:
                logger.warning(f"Could not get sheet info: {e}")
            
            logger.info("Successfully connected to Google Sheets.")
            return sheet
        except FileNotFoundError:
            logger.error(f"Файл {credentials_path} не найден! Убедитесь, что он лежит в той же папке, что и bot.py.")
            return None
        except Exception as e:
            logger.error(f"Ошибка при подключении к Google Sheets: {repr(e)}")
            return None

    def get_all_tickets(self):
        """Получает все обращения из таблицы"""
        if not self.sheet:
            return []
        
        try:
            # Получаем все данные
            all_values = self.sheet.get_all_values()
            if len(all_values) <= 1:  # Только заголовки или пустая таблица
                return []
            
            headers = all_values[0]
            tickets = []
            
            # Обрабатываем каждую строку данных
            for i, row in enumerate(all_values[1:], start=2):
                if len(row) >= len(headers):
                    ticket = {}
                    for j, header in enumerate(headers):
                        ticket[header] = row[j] if j < len(row) else ''
                    ticket['row'] = i
                    tickets.append(ticket)
            
            return tickets
            
        except Exception as e:
            logger.error(f"Error getting all tickets: {e}")
            return []

    def update_ticket_status(self, row: int, status: str):
        """Обновляет статус обращения"""
        if not self.sheet:
            return False
        
        try:
            # Находим колонку статуса
            headers = self.sheet.row_values(1)
            status_col = None
            for i, header in enumerate(headers):
                if 'статус' in header.lower():
                    status_col = i + 1
                    break
            
            if status_col:
                self.sheet.update_cell(row, status_col, status)
                logger.info(f"Updated ticket status in row {row} to {status}")
                return True
            else:
                logger.warning("Status column not found")
                return False
                
        except Exception as e:
            logger.error(f"Error updating ticket status: {e}")
            return False

    def add_operator_reply(self, row: int, reply: str):
        """Добавляет ответ оператора к обращению"""
        if not self.sheet:
            return False
        
        try:
            # Находим колонку ответа оператора
            headers = self.sheet.row_values(1)
            reply_col = None
            for i, header in enumerate(headers):
                if 'специалист_ответ' in header.lower() or 'ответ' in header.lower():
                    reply_col = i + 1
                    break
            
            if reply_col:
                self.sheet.update_cell(row, reply_col, reply)
                logger.info(f"Added operator reply to row {row}")
                return True
            else:
                logger.warning("Operator reply column not found")
                return False
                
        except Exception as e:
            logger.error(f"Error adding operator reply: {e}")
            return False

    def setup_ticket_formatting(self):
        """Настраивает форматирование для таблицы обращений"""
        if not self.sheet:
            return False
        
        try:
            # Устанавливаем ширину колонок
            self.sheet.set_column_width(5, 600)  # Колонка E (текст обращений)
            self.sheet.set_column_width(7, 400)  # Колонка G (ответ специалиста)
            
            # Устанавливаем высоту строк
            self.sheet.set_row_height(1, 100)  # Заголовок
            
            logger.info("Установлена ширина 600px для колонки E и 400px для колонки G, высота 100px для строк")
            return True
            
        except Exception as e:
            logger.error(f"Error setting up ticket formatting: {e}")
            return False
