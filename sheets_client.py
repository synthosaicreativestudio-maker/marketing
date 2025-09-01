import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials
# Removed unused imports (previously: ErrorHandler, safe_execute)

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
                    
                    logger.info(f'Row {i+1}: code compare: "{sheet_code}" vs "{code}"')
                    logger.info(f'Row {i+1}: phone compare: "{cleaned_sheet_phone}" vs "{cleaned_input_phone}"')
                    
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
        """Return set of non-empty Telegram IDs from column E for users with 'авторизован' in column D."""
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
                logger.error(f"Cannot set thread_id - ticket not found for row={row} code={code}")
                return False
            self.sheet.update_cell(row, 8, thread_id or '')
            return True
        except Exception as e:
            logger.error(f"Error setting thread_id for row={row} code={code}: {e}")
            return False

    def set_ticket_status(self, row: int, code: str, status: str) -> bool:
        """Устанавливает статус тикета. Поддерживает как номер строки, так и код."""
        if not self.sheet:
            logger.error('Ticket sheet not connected')
            return False
        
        try:
            target_row = None
            
            if row and isinstance(row, int):
                # Используем номер строки
                if row > 0 and row <= len(self.sheet.get_all_values()):
                    target_row = row
                else:
                    logger.warning(f'Invalid row number: {row}')
                    return False
            elif code:
                # Ищем по коду
                found_row = self.find_row_by_code(code)
                if found_row:
                    target_row = found_row
                else:
                    logger.warning(f'Code {code} not found')
                    return False
            else:
                logger.warning('Neither row nor code provided')
                return False
            
            if target_row:
                # Обновляем статус в столбце F (новый индекс 6)
                self.sheet.update_cell(target_row, 6, status)
                
                # Обновляем время последнего обновления в столбце H (новый индекс 8)
                from datetime import datetime
                ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                self.sheet.update_cell(target_row, 8, ts)
                
                # Форматирование статуса
                try:
                    if status.lower() in ('выполнено', 'completed', 'done'):
                        color = {'red': 0, 'green': 0.8, 'blue': 0}  # Зеленый
                    elif status.lower() in ('в работе', 'work', 'open', 'in progress'):
                        color = {'red': 0.8, 'green': 0, 'blue': 0}  # Красный
                    elif status.lower() in ('ожидает', 'pending', 'waiting'):
                        color = {'red': 1, 'green': 0.6, 'blue': 0}  # Оранжевый
                    else:
                        color = {'red': 1, 'green': 1, 'blue': 1}  # Белый
                    
                    self.sheet.format(f'F{target_row}', {'backgroundColor': color})
                    logger.info(f'Status updated to "{status}" for row {target_row}')
                    
                except Exception as e:
                    logger.warning(f'Could not format status cell: {e}')
                
                return True
            
        except Exception as e:
            logger.error(f'Error setting ticket status: {e}')
        
        return False

    # --- Ticket sheet helpers ---
    def upsert_ticket(self, telegram_id: str, code: str, phone: str, fio: str, text: str,
                      status: str = 'в работе', sender_type: str = 'user', handled: bool = False):
        """Добавляет или обновляет запись обращения для пользователя в таблице обращений.
        НОВАЯ ЛОГИКА:
        - Новые обращения (новые пользователи) → новые строки
        - Старые обращения (существующие пользователи) → обновление в столбце E
        - Столбец G (SPECIALIST_REPLY) - временное поле для ответа специалиста
        """
        if not self.sheet:
            logger.error('Ticket sheet not connected')
            return
        
        try:
            from datetime import datetime
            ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            
            # Ищем существующую запись по telegram_id
            existing_row = None
            try:
                cell = self.sheet.find(str(telegram_id), in_column=4)  # колонка D
                if cell:
                    existing_row = cell.row
            except Exception:
                existing_row = None
            
            # Нормализуем метку отправителя
            sender_label = 'Пользователь'
            if sender_type == 'assistant':
                sender_label = 'Ассистент'
            elif sender_type == 'specialist':
                sender_label = 'Специалист'
            
            new_entry = f"[{ts}] {sender_label}: {text}"
            
            if existing_row:
                # ОБНОВЛЯЕМ существующую запись (старые обращения)
                # Обновляем столбец E (текст_обращений) - добавляем новое сообщение
                current_tickets = self.sheet.cell(existing_row, 5).value or ''
                if current_tickets:
                    updated_tickets = new_entry + '\n\n' + current_tickets  # Новое сверху
                else:
                    updated_tickets = new_entry
                
                self.sheet.update_cell(existing_row, 5, updated_tickets)
                
                # Обновляем статус: если это ответ специалиста - используем переданный статус,
                # если это повторное обращение пользователя - меняем на "в работе"
                if sender_type == 'specialist':
                    self.sheet.update_cell(existing_row, 6, status)
                    # НЕ очищаем поле G здесь - это делается отдельно после логирования
                elif sender_type == 'user':
                    # При повторном обращении пользователя меняем статус на "в работе"
                    current_status = self.sheet.cell(existing_row, 6).value or ''
                    if current_status.lower() in ('выполнено', 'completed', 'done'):
                        self.sheet.update_cell(existing_row, 6, 'в работе')
                        logger.info(
                            f'Status changed from "{current_status}" to "в работе" '
                            f'for user {telegram_id} (repeated)'
                        )
                
                # Обновляем время последнего обновления
                self.sheet.update_cell(existing_row, 8, ts)
                
                logger.info(f'Updated existing ticket for user {telegram_id} in row {existing_row}')
                
            else:
                # СОЗДАЕМ новую запись (новые обращения)
                # Столбец G (SPECIALIST_REPLY) остается пустым для ответа специалиста
                values = [
                    code or '',           # A - код партнера
                    phone or '',          # B - телефон
                    fio or '',            # C - ФИО
                    str(telegram_id),     # D - Telegram ID
                    new_entry,            # E - текст_обращений
                    status,               # F - статус
                    '',                   # G - поле для ответа специалиста (пустое)
                    ts                    # H - время последнего обновления
                ]
                
                self.sheet.append_row(values)
                logger.info(f'Created new ticket row for user {telegram_id}')
            
            # Форматирование статуса
            try:
                target_row = existing_row if existing_row else len(self.sheet.get_all_values())
                if target_row:
                    current_status = self.sheet.cell(target_row, 6).value or ''
                    
                    if current_status.lower() in ('выполнено', 'completed', 'done'):
                        color = {'red': 0, 'green': 0.8, 'blue': 0}  # Зеленый
                    elif current_status.lower() in ('в работе', 'work', 'open', 'in progress'):
                        color = {'red': 0.8, 'green': 0, 'blue': 0}  # Красный
                    elif current_status.lower() in ('ожидает', 'pending', 'waiting'):
                        color = {'red': 1, 'green': 0.6, 'blue': 0}  # Оранжевый
                    else:
                        color = {'red': 1, 'green': 1, 'blue': 1}  # Белый
                    
                    self.sheet.format(f'F{target_row}', {'backgroundColor': color})
                    
            except Exception as e:
                logger.warning(f'Could not format status cell: {e}')
                
        except Exception as e:
            logger.error(f'Error in upsert_ticket: {e}')
            raise
    
    def set_tickets_column_width(self, width_pixels: int, row_height_pixels: int) -> bool:
        """Устанавливает ширину колонок E и G, а также высоту строк для таблицы обращений"""
        if not self.sheet:
            logger.error('Ticket sheet not connected')
            return False
        
        try:
            # Some gspread Worksheet implementations don't implement UI helpers like
            # set_column_width / set_row_height. Detect support first and skip if
            # unavailable to avoid raising AttributeError repeatedly in logs.
            if hasattr(self.sheet, 'set_column_width'):
                try:
                    # Устанавливаем ширину колонки E (текст_обращений)
                    self.sheet.set_column_width(5, width_pixels)  # Колонка E
                    # Устанавливаем ширину колонки G (поле ответа специалиста)
                    self.sheet.set_column_width(7, 400)  # Колонка G
                except Exception as e:
                    logger.warning(f'Could not set column widths using worksheet methods: {e}')
            else:
                logger.info('Worksheet does not support set_column_width(); skipping column resize')

            if hasattr(self.sheet, 'set_row_height'):
                try:
                    # Устанавливаем высоту заголовка и всех строк с данными
                    self.sheet.set_row_height(1, row_height_pixels)  # Заголовок
                    all_values = self.sheet.get_all_values()
                    for row_num in range(2, len(all_values) + 1):
                        try:
                            self.sheet.set_row_height(row_num, row_height_pixels)
                        except Exception:
                            # Individual rows may fail; keep going
                            continue
                except Exception as e:
                    logger.warning(f'Could not set row heights using worksheet methods: {e}')
            else:
                logger.info('Worksheet does not support set_row_height(); skipping row height resize')

            logger.info(f'Column/row size operations completed (some operations may be no-ops on this worksheet)')
            return True
            
        except Exception as e:
            logger.warning(f'Ошибка при установке размеров (ignored): {e}')
            return False

    def setup_status_dropdown(self):
        """Настраивает выпадающий список статусов в столбце F для всех строк с данными"""
        if not self.sheet:
            logger.error('Ticket sheet not connected')
            return False
        
        try:
            # Получаем все значения для определения количества строк
            all_values = self.sheet.get_all_values()
            
            if len(all_values) <= 1:
                logger.info('Таблица пустая или содержит только заголовки, выпадающий список не нужен')
                return True
            
            # Список доступных статусов
            status_options = ['в работе', 'выполнено']
            
            # Настраиваем выпадающий список для каждой строки с данными (начиная со 2-й строки)
            for row_num in range(2, len(all_values) + 1):
                # Создаем правило валидации для выпадающего списка
                from gspread_formatting import DataValidationRule, BooleanCondition
                
                # Создаем правило для выпадающего списка
                rule = DataValidationRule(
                    BooleanCondition('ONE_OF_LIST', status_options),
                    showCustomUi=True,
                    strict=True
                )
                
                # Применяем правило к ячейке статуса (столбец F)
                self.sheet.set_data_validation(f'F{row_num}', rule)
            
            logger.info(f'Выпадающий список статусов настроен для {len(all_values) - 1} строк')
            return True
            
        except Exception as e:
            logger.error(f'Ошибка при настройке выпадающего списка статусов: {e}')
            return False

    def set_specialist_reply(self, telegram_id: str, reply_text: str, clear_after_send: bool = True):
        """Записывает ответ специалиста в поле G (SPECIALIST_REPLY) и отправляет пользователю.
        
        Args:
            telegram_id: ID пользователя в Telegram
            reply_text: Текст ответа специалиста
            clear_after_send: Очищать ли поле после отправки
        """
        if not self.sheet:
            logger.error('Ticket sheet not connected')
            return False
        
        try:
            # Ищем строку по telegram_id
            cell = self.sheet.find(str(telegram_id), in_column=4)  # колонка D
            if not cell:
                logger.warning(f'User {telegram_id} not found in tickets')
                return False
            
            row = cell.row
            
            # Записываем ответ в поле G (SPECIALIST_REPLY)
            self.sheet.update_cell(row, 7, reply_text)
            logger.info(f'Specialist reply written to row {row} for user {telegram_id}')
            
            return True
            
        except Exception as e:
            logger.error(f'Error setting specialist reply: {e}')
            return False
    
    def clear_specialist_reply(self, telegram_id: str):
        """Очищает поле ответа специалиста (столбец G) после отправки."""
        if not self.sheet:
            return False
        
        try:
            cell = self.sheet.find(str(telegram_id), in_column=4)
            if cell:
                self.sheet.update_cell(cell.row, 7, '')
                logger.info(f'Cleared specialist reply field for user {telegram_id}')
                return True
        except Exception as e:
            logger.error(f'Error clearing specialist reply: {e}')
        
        return False

    def update_tickets_headers(self):
        """Обновляет заголовки таблицы обращений в соответствии с новой структурой"""
        if not self.sheet:
            logger.error('Ticket sheet not connected')
            return False
        
        try:
            # Новые заголовки для обновленной структуры
            new_headers = [
                'код',                    # A - код партнера
                'телефон',                # B - телефон
                'ФИО',                    # C - ФИО
                'telegram_id',            # D - Telegram ID
                'текст_обращений',        # E - текст обращений (история)
                'статус',                 # F - статус (ручной выбор)
                'специалист_ответ',       # G - ответ специалиста (временное поле)
                'время_обновления'        # H - время последнего обновления
            ]
            
            # Обновляем заголовки
            for col_idx, header in enumerate(new_headers, start=1):
                self.sheet.update_cell(1, col_idx, header)
            
            logger.info('Заголовки таблицы обращений обновлены в соответствии с новой структурой')
            return True
            
        except Exception as e:
            logger.error(f'Ошибка при обновлении заголовков: {e}')
            return False

    def extract_operator_replies(self):
        """Извлекает все ответы операторов из поля G (специалист_ответ) для отправки пользователям"""
        if not self.sheet:
            logger.error('Ticket sheet not connected')
            return []
        
        try:
            # Получаем все значения из таблицы
            all_values = self.sheet.get_all_values()
            if len(all_values) < 2:  # Только заголовки или пустая таблица
                return []
            
            replies = []
            
            # Проходим по всем строкам с данными (начиная со 2-й строки)
            for row_idx, row in enumerate(all_values[1:], start=2):
                if len(row) < 7:  # Проверяем, что есть достаточно колонок
                    continue
                
                # Получаем данные из строки
                code = row[0] if len(row) > 0 else ''           # A - код
                telegram_id = row[3] if len(row) > 3 else ''    # D - telegram_id
                specialist_reply = row[6] if len(row) > 6 else ''  # G - специалист_ответ
                
                # Если есть ответ специалиста и код, добавляем в список
                if specialist_reply and specialist_reply.strip() and code and code.strip():
                    replies.append({
                        'telegram_id': telegram_id,
                        'reply_text': specialist_reply.strip(),
                        'code': code.strip(),
                        'row': row_idx
                    })
                    logger.info(f'Found specialist reply in row {row_idx}: {specialist_reply[:50]}...')
            
            logger.info(f'Extracted {len(replies)} specialist replies from field G')
            return replies
            
        except Exception as e:
            logger.error(f'Error extracting operator replies: {e}')
            return []