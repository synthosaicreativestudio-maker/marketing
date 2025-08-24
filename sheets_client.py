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
            
            # Если имя листа не указано или не найдено, берем первый лист
            try:
                if worksheet_name:
                    sheet = client.open_by_url(sheet_url).worksheet(worksheet_name)
                else:
                    sheet = client.open_by_url(sheet_url).get_worksheet(0)
            except Exception:
                sheet = client.open_by_url(sheet_url).get_worksheet(0)
            logger.info("Successfully connected to Google Sheets.")
            return sheet
        except FileNotFoundError:
            logger.error(f"Файл {credentials_path} не найден! Убедитесь, что он лежит в той же папке, что и bot.py.")
            return None
        except Exception as e:
            logger.error(f"Ошибка при подключении к Google Sheets: {repr(e)}")
            return None

    def find_user_by_id(self, user_id: int) -> tuple[int, str] | None:
        """Finds a user by their Telegram ID in column E and returns their row and status."""
        if not self.sheet: return None
        try:
            cell = self.sheet.find(str(user_id), in_column=5)
            if cell:
                status = self.sheet.cell(cell.row, 4).value
                return (cell.row, status)
        except Exception as e:
            logger.error(f"Error finding user by ID {user_id}: {e}")
        return None

    def find_user_by_credentials(self, code: str, phone: str) -> int | None:
        """Finds a user by partner code and phone, returns the row number if found."""
        if not self.sheet: return None
        try:
            logger.info(f'Searching for code={code}, phone={phone}')
            all_codes = self.sheet.col_values(1)
            all_phones = self.sheet.col_values(3)
            
            logger.info(f'Found {len(all_codes)} codes and {len(all_phones)} phones')
            
            # Начинаем с индекса 1 (пропускаем заголовок)
            for i in range(1, len(all_codes)):
                if i < len(all_phones) and all_codes[i]:
                    sheet_code = str(all_codes[i]).strip()
                    sheet_phone = str(all_phones[i]).strip() if i < len(all_phones) else ''
                    
                    # Очищаем телефон от всех символов кроме цифр
                    cleaned_sheet_phone = ''.join(filter(str.isdigit, sheet_phone))
                    cleaned_input_phone = ''.join(filter(str.isdigit, phone))
                    
                    logger.info(f'Row {i+1}: code="{sheet_code}" vs "{code}", phone="{cleaned_sheet_phone}" vs "{cleaned_input_phone}"')
                    
                    if sheet_code == code and cleaned_sheet_phone == cleaned_input_phone:
                        logger.info(f'MATCH FOUND at row {i+1}')
                        return i + 1  # Return the 1-based row index
                        
            logger.warning(f'No match found for code={code}, phone={phone}')
        except Exception as e:
            logger.error(f"Error finding user by credentials: {e}")
        return None

    def update_user_auth_status(self, row_to_update: int, user_id: int):
        """Updates the auth status and Telegram ID for a user in a specific row."""
        if not self.sheet: return
        try:
            cells_to_update = [self.sheet.cell(row_to_update, 4), self.sheet.cell(row_to_update, 5)]
            cells_to_update[0].value = "авторизован"
            cells_to_update[1].value = user_id
            self.sheet.update_cells(cells_to_update)
            logger.info(f"Successfully updated auth status for user {user_id} in row {row_to_update}.")
        except Exception as e:
            logger.error(f"Error updating user auth status for row {row_to_update}: {e}")

    def get_all_statuses(self) -> list[str]:
        """Returns a list of all statuses from column D."""
        if not self.sheet: return []
        try:
            return self.sheet.col_values(4)
        except Exception as e:
            logger.error(f"Error getting all statuses: {e}")
            return []

    def get_all_authorized_user_ids(self) -> set[str]:
        """Returns a set of unique, non-empty Telegram IDs from column E."""
        if not self.sheet: return set()
        try:
            all_ids = self.sheet.col_values(5)
            return set(filter(None, all_ids[1:]))
        except Exception as e:
            logger.error(f"Error getting all authorized user IDs: {e}")
            return set()

    def find_row_by_code(self, code: str) -> int | None:
        """Find a row by the unique code in column 1. Returns 1-based row index or None."""
        if not self.sheet:
            return None
        try:
            all_codes = self.sheet.col_values(1)
            # all_codes[0] is header; iterate starting from second element
            for idx, val in enumerate(all_codes[1:], start=2):
                if val and str(val).strip() == str(code).strip():
                    return idx
        except Exception as e:
            logger.error(f"Error finding row by code '{code}': {e}")
        return None

    def get_thread_id(self, row: int | None = None, code: str | None = None) -> str | None:
        """Return thread_id stored in column 8 for given row or code."""
        if not self.sheet:
            return None
        try:
            if row is None and code is not None:
                row = self.find_row_by_code(code)
            if not row:
                return None
            return self.sheet.cell(row, 8).value or None
        except Exception as e:
            logger.error(f"Error getting thread_id for row={row} code={code}: {e}")
            return None

    def set_thread_id(self, row: int | None = None, code: str | None = None, thread_id: str | None = None) -> bool:
        """Set thread_id in column 8 for given row or code."""
        if not self.sheet:
            return False
        try:
            if row is None and code is not None:
                row = self.find_row_by_code(code)
            if not row:
                logger.error(f"Cannot set thread_id; ticket not found for row={row} code={code}")
                return False
            self.sheet.update_cell(row, 8, thread_id or '')
            return True
        except Exception as e:
            logger.error(f"Error setting thread_id for row={row} code={code}: {e}")
            return False

    def set_ticket_status(self, row: int | None = None, code: str | None = None, status: str = 'в работе') -> bool:
        """Set status for a ticket by row or code. Updates last_updated timestamp. Returns True on success."""
        if not self.sheet:
            return False
        try:
            from datetime import datetime
            ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            if row is None and code is not None:
                row = self.find_row_by_code(code)
            if not row:
                logger.error(f"Cannot set status; ticket not found for row={row} code={code}")
                return False
            self.sheet.update_cell(row, 6, status)
            self.sheet.update_cell(row, 7, ts)
            return True
        except Exception as e:
            logger.error(f"Error setting ticket status for row={row} code={code}: {e}")
            return False

    # --- Ticket sheet helpers ---
    def upsert_ticket(self, telegram_id: str, code: str, phone: str, fio: str, text: str, status: str = 'в работе', sender_type: str = 'user', handled: bool = False):
        """Добавляет или обновляет запись обращения для пользователя в таблице обращений.
        Структура колонок (1-based): 1=code,2=phone,3=fio,4=telegram_id,5=tickets,6=status,7=last_updated
        Для одного и того же telegram_id записи объединяются в одну ячейку в колонке 5.
        """
        if not self.sheet:
            logger.error('Ticket sheet not connected')
            return
        try:
            # Prefer to locate the ticket by code (unique conversation id). If no code given,
            # fall back to telegram_id lookup in column 4.
            cell = None
            if code:
                try:
                    row = self.find_row_by_code(code)
                    if row:
                        # create a lightweight cell-like object by reading the telegram_id cell
                        try:
                            cell = self.sheet.cell(row, 4)
                        except Exception:
                            cell = None
                except Exception:
                    cell = None
            if not cell:
                try:
                    cell = self.sheet.find(str(telegram_id), in_column=4)
                except Exception:
                    cell = None

            from datetime import datetime
            ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            # Normalize sender label
            sender_label = 'Пользователь'
            if sender_type == 'assistant':
                sender_label = 'Ассистент'
            elif sender_type == 'specialist':
                sender_label = 'Специалист'
            new_entry = f"[{ts}] {sender_label}: {text}"

            if cell:
                row = cell.row
                # Обновляем tickets (колонка 5) добавляя новую запись как продолжение
                current = self.sheet.cell(row, 5).value or ''
                if current:
                    updated = current + '\n\n' + new_entry
                else:
                    updated = new_entry
                self.sheet.update_cell(row, 5, updated)
                # Determine status: assistant handled -> 'выполнено' if handled True;
                # specialist -> 'в работе'; otherwise use provided status.
                if sender_type == 'assistant' and handled:
                    new_status = 'выполнено'
                elif sender_type == 'specialist':
                    new_status = 'в работе'
                else:
                    new_status = status
                self.sheet.update_cell(row, 6, new_status)
                self.sheet.update_cell(row, 7, ts)
                # Также обновим code/phone/fio если пустые
                if not (self.sheet.cell(row,1).value):
                    self.sheet.update_cell(row,1, code or '')
                if not (self.sheet.cell(row,2).value):
                    self.sheet.update_cell(row,2, phone or '')
                if not (self.sheet.cell(row,3).value):
                    self.sheet.update_cell(row,3, fio or '')
            else:
                # Добавляем новую строку
                values = [code or '', phone or '', fio or '', str(telegram_id), new_entry, status, ts]
                self.sheet.append_row(values)

            # Форматирование статуса (красный для 'в работе', зелёный для 'выполнено')
            try:
                if status.lower() in ('в работе', 'work', 'open'):
                    color = {'red': 1, 'green': 0.0, 'blue': 0}
                else:
                    color = {'red': 0, 'green': 1, 'blue': 0}
                # Определяем строку (если мы добавили новую, ищем её снова)
                if not cell:
                    # попробуем найти по telegram_id
                    try:
                        cell = self.sheet.find(str(telegram_id), in_column=4)
                    except Exception:
                        cell = None
                if cell:
                    fmt_range = f'F{cell.row}'
                    self.sheet.format(fmt_range, {'backgroundColor': color})
            except Exception as e:
                logger.warning(f'Не удалось применить форматирование статуса: {e}')

        except Exception as e:
            logger.error(f'Error upserting ticket for {telegram_id}: {e}')