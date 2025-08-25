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

    def find_user_by_id(self, user_id: int) -> tuple[int, str] | None:
        """Finds a user by their Telegram ID in column E and returns their row and status from column D."""
        if not self.sheet: return None
        try:
            cell = self.sheet.find(str(user_id), in_column=5)
            if cell:
                status = self.sheet.cell(cell.row, 4).value
                # Проверяем, что статус именно "авторизован"
                if str(status).strip() == "авторизован":
                    return (cell.row, status)
                else:
                    logger.info(f"User {user_id} found but not authorized (status: {status})")
                    return None
        except Exception as e:
            logger.error(f"Error finding user by ID {user_id}: {e}")
        return None

    def find_user_by_credentials(self, code: str, phone: str) -> int | None:
        """Finds a user by partner code and phone, returns the row number if found."""
        if not self.sheet: 
            logger.error('Google Sheets not connected')
            return None
        try:
            logger.info(f'Searching for code={code}, phone={phone}')
            
            # Add timeout protection by limiting the search scope
            try:
                all_codes = self.sheet.col_values(1)  # Колонка A
                all_phones = self.sheet.col_values(3)  # Колонка C  
            except Exception as e:
                logger.error(f'Failed to fetch sheet data: {e}')
                return None
            
            logger.info(f'Found {len(all_codes)} codes, {len(all_phones)} phones')
            
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
                        
            logger.warning(f'No user found for code={code}, phone={phone}')
        except Exception as e:
            logger.error(f"Error finding user by credentials: {e}")
        return None

    def update_user_auth_status(self, row_to_update: int, user_id: int):
        """Updates the auth status and Telegram ID for a user in a specific row."""
        if not self.sheet: 
            logger.error('Google Sheets not connected')
            return
        try:
            logger.info(f'Updating auth status for row {row_to_update}, user_id {user_id}')
            
            # Обновляем колонку D (статус авторизации) и колонку E (Telegram ID)
            try:
                cells_to_update = [self.sheet.cell(row_to_update, 4), self.sheet.cell(row_to_update, 5)]
                cells_to_update[0].value = "авторизован"
                cells_to_update[1].value = str(user_id)  # Записываем реальный Telegram ID
                self.sheet.update_cells(cells_to_update)
                logger.info(f"Successfully updated auth status and Telegram ID {user_id} for row {row_to_update}.")
            except Exception as e:
                logger.error(f'Failed to update cells for row {row_to_update}: {e}')
                # Try alternative method
                try:
                    self.sheet.update_cell(row_to_update, 4, "авторизован")
                    self.sheet.update_cell(row_to_update, 5, str(user_id))
                    logger.info(f"Successfully updated auth status using alternative method for row {row_to_update}.")
                except Exception as e2:
                    logger.error(f'Alternative update method also failed: {e2}')
                    raise
        except Exception as e:
            logger.error(f"Error updating user auth status for row {row_to_update}: {e}")
            raise  # Re-raise to let the calling function handle it

    def get_all_statuses(self) -> list[str]:
        """Returns a list of all statuses from column D."""
        if not self.sheet: return []
        try:
            return self.sheet.col_values(4)
        except Exception as e:
            logger.error(f"Error getting all statuses: {e}")
            return []

    def get_all_authorized_user_ids(self) -> set[str]:
        """Returns a set of unique, non-empty Telegram IDs from column E for users with 'авторизован' status in column D."""
        if not self.sheet: return set()
        try:
            all_statuses = self.sheet.col_values(4)  # Колонка D - статусы авторизации
            all_ids = self.sheet.col_values(5)       # Колонка E - Telegram ID
            
            logger.info(f"DEBUG: Found {len(all_statuses)} statuses and {len(all_ids)} IDs")
            logger.info(f"DEBUG: Statuses (col D): {all_statuses[:5]}...")  # Первые 5 статусов
            logger.info(f"DEBUG: IDs (col E): {all_ids[:5]}...")           # Первые 5 ID
            
            authorized_ids = set()
            for i in range(1, min(len(all_statuses), len(all_ids))):  # Пропускаем заголовок
                status = str(all_statuses[i]).strip() if i < len(all_statuses) else ""
                user_id = str(all_ids[i]).strip() if i < len(all_ids) else ""
                
                logger.info(f"DEBUG: Row {i+1}: status='{status}', id='{user_id}'")
                
                if (status == "авторизован" and user_id):
                    authorized_ids.add(user_id)
                    logger.info(f"DEBUG: Added authorized user {user_id} from row {i+1}")
            
            logger.info(f"DEBUG: Total authorized users found: {len(authorized_ids)}")
            return authorized_ids
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
            
            # Применяем форматирование цвета
            try:
                if status.lower() in ('выполнено', 'completed', 'done'):
                    color = {'red': 0, 'green': 0.8, 'blue': 0}  # Зеленый
                elif status.lower() in ('в работе', 'work', 'open', 'in progress'):
                    color = {'red': 0.8, 'green': 0, 'blue': 0}  # Красный
                else:
                    color = {'red': 1, 'green': 1, 'blue': 1}  # Белый
                
                fmt_range = f'F{row}'
                self.sheet.format(fmt_range, {'backgroundColor': color})
                logger.info(f'Применено форматирование для статуса "{status}" в строке {row}')
            except Exception as e:
                logger.warning(f'Не удалось применить форматирование: {e}')
            
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
                # Обновляем tickets (колонка 5) добавляя новую запись вВЕРХ (новые сообщения сверху)
                current = self.sheet.cell(row, 5).value or ''
                if current:
                    updated = new_entry + '\n\n' + current  # Новое сообщение вверху
                else:
                    updated = new_entry
                self.sheet.update_cell(row, 5, updated)
                # Определяем новый статус с учетом предыдущего
                current_status = self.sheet.cell(row, 6).value or ''
                
                if sender_type == 'assistant' and handled:
                    new_status = 'выполнено'
                elif sender_type == 'specialist':
                    new_status = 'в работе'
                elif sender_type == 'user' and current_status.lower() in ('выполнено', 'completed', 'done'):
                    # Если пользователь пишет к выполненной задаче - возвращаем в работу
                    new_status = 'в работе'
                    logger.info(f'Статус изменен с "выполнено" на "в работе" для пользователя {telegram_id}')
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
                # Определяем строку (если мы добавили новую, ищем её снова)
                target_row = None
                if cell:
                    target_row = cell.row
                else:
                    # попробуем найти по telegram_id
                    try:
                        found_cell = self.sheet.find(str(telegram_id), in_column=4)
                        if found_cell:
                            target_row = found_cell.row
                    except Exception:
                        pass
                
                if target_row:
                    # Получаем актуальный статус из ячейки
                    current_status = self.sheet.cell(target_row, 6).value or ''
                    
                    if current_status.lower() in ('выполнено', 'completed', 'done'):
                        color = {'red': 0, 'green': 0.8, 'blue': 0}  # Зеленый для выполнено
                    elif current_status.lower() in ('в работе', 'work', 'open', 'in progress'):
                        color = {'red': 0.8, 'green': 0, 'blue': 0}  # Красный для в работе
                    else:
                        color = {'red': 1, 'green': 1, 'blue': 1}  # Белый для других статусов
                    
                    fmt_range = f'F{target_row}'
                    self.sheet.format(fmt_range, {'backgroundColor': color})
                    logger.info(f'Применено форматирование для статуса "{current_status}" в строке {target_row}')
            except Exception as e:
                logger.warning(f'Не удалось применить форматирование статуса: {e}')

        except Exception as e:
            logger.error(f'Error upserting ticket for {telegram_id}: {e}')
    
    def set_tickets_column_width(self, width_pixels: int = 600, row_height_pixels: int = 100):
        """Устанавливает фиксированную ширину для колонки E (обращения) и высоту строк."""
        if not self.sheet:
            logger.error('Sheet not connected')
            return False
        try:
            from gspread.utils import rowcol_to_a1
            import requests
            
            # Получаем ID таблицы и листа
            spreadsheet_id = self.sheet.spreadsheet.id
            sheet_id = self.sheet.id
            
            # Батч запрос для установки ширины колонки и высоты строк
            batch_update_request = {
                'requests': [
                    # Установка ширины колонки E
                    {
                        'updateDimensionProperties': {
                            'range': {
                                'sheetId': sheet_id,
                                'dimension': 'COLUMNS',
                                'startIndex': 4,  # Колонка E (счет с 0)
                                'endIndex': 5     # До колонки E включительно
                            },
                            'properties': {
                                'pixelSize': width_pixels
                            },
                            'fields': 'pixelSize'
                        }
                    },
                    # Установка высоты всех строк (начиная с строки 2, пропуская заголовок)
                    {
                        'updateDimensionProperties': {
                            'range': {
                                'sheetId': sheet_id,
                                'dimension': 'ROWS',
                                'startIndex': 1,   # Начинаем со 2-й строки (счет с 0)
                                'endIndex': 1000   # Охватываем до 1000 строк
                            },
                            'properties': {
                                'pixelSize': row_height_pixels
                            },
                            'fields': 'pixelSize'
                        }
                    }
                ]
            }
            
            # Отправляем batch update через gspread API
            self.sheet.spreadsheet.batch_update(batch_update_request)
            logger.info(f'Установлена ширина {width_pixels}px для колонки E и высота {row_height_pixels}px для строк')
            return True
            
        except Exception as e:
            logger.error(f'Ошибка при установке размеров: {e}')
            return False