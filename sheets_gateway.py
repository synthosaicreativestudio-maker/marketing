"""
Асинхронный шлюз для работы с Google Sheets API.
Единственная точка доступа к Google Sheets с retry логикой и Circuit Breaker.
"""
import logging
import asyncio
import json
import os
from pathlib import Path
from typing import List, Dict, Optional, Any, Callable
import gspread
from gspread.exceptions import APIError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
    RetryError
)
from requests.exceptions import ConnectionError, ReadTimeout
from dotenv import load_dotenv

from sheets_utils import (
    get_auth_circuit_breaker,
    get_appeals_circuit_breaker,
    get_promotions_circuit_breaker,
    CircuitBreakerOpenError
)

# Загружаем переменные окружения
load_dotenv()

logger = logging.getLogger(__name__)


class SheetsNotConfiguredError(Exception):
    """Ошибка конфигурации Google Sheets"""
    pass


def normalize_phone(phone: str) -> str:
    """Нормализация номера телефона к формату 8XXXXXXXXXX"""
    digits = ''.join(ch for ch in (phone or '') if ch.isdigit())
    if len(digits) == 10:
        return '8' + digits
    elif len(digits) == 11 and digits.startswith('7'):
        return '8' + digits[1:]
    elif len(digits) == 11 and digits.startswith('8'):
        return digits
    else:
        return digits


def _load_service_account():
    """Загрузка service account для Google Sheets"""
    sa_json = os.environ.get('GCP_SA_JSON')
    sa_file = os.environ.get('GCP_SA_FILE')
    
    if sa_json:
        try:
            return json.loads(sa_json)
        except Exception as e:
            raise ValueError('Invalid GCP_SA_JSON: ' + str(e)) from e
    
    if sa_file and Path(sa_file).exists():
        with Path(sa_file).open(encoding='utf-8') as f:
            return json.load(f)
    
    raise SheetsNotConfiguredError(
        'Service account JSON not provided (GCP_SA_JSON or GCP_SA_FILE)'
    )


def _get_client_and_sheet():
    """Получение клиента и листа Google Sheets (для инициализации)"""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        
        sa_info = _load_service_account()
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        creds = Credentials.from_service_account_info(sa_info, scopes=scopes)
        client = gspread.authorize(creds)
        
        sheet_id = os.environ.get('SHEET_ID')
        if not sheet_id:
            raise SheetsNotConfiguredError('SHEET_ID not provided')
        
        spreadsheet = client.open_by_key(sheet_id)
        sheet_name = os.environ.get('SHEET_NAME', 'Sheet1')
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
        except Exception as e:
            logger.warning(f"Worksheet '{sheet_name}' not found ({e}). Falling back to first sheet.")
            worksheet = spreadsheet.sheet1

        return client, worksheet
    
    except ImportError as e:
        raise SheetsNotConfiguredError(f'Import error: {e}')
    except Exception as e:
        logger.error(f"Failed to connect to Google Sheets: {e}")
        raise SheetsNotConfiguredError(f'Google Sheets connection failed: {e}')


def _get_appeals_client_and_sheet():
    """Получение клиента и листа для таблицы обращений (для инициализации)"""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        
        sa_info = _load_service_account()
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        creds = Credentials.from_service_account_info(sa_info, scopes=scopes)
        client = gspread.authorize(creds)
        
        sheet_id = os.environ.get('APPEALS_SHEET_ID')
        if not sheet_id:
            raise SheetsNotConfiguredError('APPEALS_SHEET_ID not provided')
        
        spreadsheet = client.open_by_key(sheet_id)
        sheet_name = os.environ.get('APPEALS_SHEET_NAME', 'обращения')
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
        except Exception as e:
            logger.warning(f"Appeals worksheet '{sheet_name}' not found ({e}). Falling back to first sheet.")
            worksheet = spreadsheet.sheet1

        return client, worksheet
    
    except ImportError as e:
        raise SheetsNotConfiguredError(f'Import error: {e}')
    except Exception as e:
        logger.error(f"Failed to connect to Appeals Google Sheets: {e}")
        raise SheetsNotConfiguredError(f'Appeals Google Sheets connection failed: {e}')


def _is_retryable_error(exception: Exception) -> bool:
    """
    Проверяет, является ли ошибка временной (требует retry).
    
    Args:
        exception: Исключение для проверки
        
    Returns:
        True если ошибка временная и требует retry
    """
    # Проверяем APIError с кодами ошибок
    if isinstance(exception, APIError):
        status_code = getattr(exception, 'response', {}).get('status', 0)
        # Retry для временных ошибок
        if status_code in [500, 502, 503, 504]:
            return True
        # Не retry для постоянных ошибок
        if status_code in [400, 401, 403, 404]:
            return False
    
    # Retry для сетевых ошибок
    if isinstance(exception, (ConnectionError, ReadTimeout)):
        return True
    
    # Проверяем строковое представление ошибки
    error_str = str(exception).lower()
    retryable_keywords = ['503', '502', '500', '504', 'unavailable', 'timeout', 'connection']
    if any(keyword in error_str for keyword in retryable_keywords):
        return True
    
    return False


def _should_not_retry(exception: Exception) -> bool:
    """
    Проверяет, не нужно ли делать retry (постоянные ошибки).
    
    Args:
        exception: Исключение для проверки
        
    Returns:
        True если ошибка постоянная и не требует retry
    """
    if isinstance(exception, APIError):
        status_code = getattr(exception, 'response', {}).get('status', 0)
        if status_code in [400, 401, 403, 404]:
            return True
    
    return False


class AsyncGoogleSheetsGateway:
    """
    Асинхронный шлюз для работы с Google Sheets API.
    
    Все методы gspread выполняются через run_in_executor для предотвращения
    блокировки event loop. Retry логика реализована через tenacity.
    Circuit Breaker интегрирован для защиты от каскадных ошибок.
    """
    
    def __init__(self, circuit_breaker_name: str = 'auth'):
        """
        Инициализация Gateway.
        
        Args:
            circuit_breaker_name: Имя Circuit Breaker ('auth', 'appeals', 'promotions')
        """
        self.circuit_breaker_name = circuit_breaker_name
        self._get_circuit_breaker()
        self._loop = None
    
    def _get_circuit_breaker(self):
        """Получает соответствующий Circuit Breaker."""
        if self.circuit_breaker_name == 'auth':
            self.circuit_breaker = get_auth_circuit_breaker()
        elif self.circuit_breaker_name == 'appeals':
            self.circuit_breaker = get_appeals_circuit_breaker()
        elif self.circuit_breaker_name == 'promotions':
            self.circuit_breaker = get_promotions_circuit_breaker()
        else:
            # По умолчанию используем auth
            self.circuit_breaker = get_auth_circuit_breaker()
    
    def _get_loop(self):
        """Получает текущий event loop."""
        if self._loop is None:
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        return self._loop
    
    def _retry_exec(self, func: Callable, *args, **kwargs) -> Any:
        """
        Выполняет функцию с retry логикой через tenacity.
        
        Args:
            func: Функция для выполнения
            *args: Позиционные аргументы
            **kwargs: Именованные аргументы
            
        Returns:
            Результат выполнения функции
            
        Raises:
            Exception: Если все попытки исчерпаны
        """
        @retry(
            stop=stop_after_attempt(5),
            wait=wait_exponential(min=2, max=30),
            retry=retry_if_exception(_is_retryable_error),
            reraise=True
        )
        def _execute():
            # Проверяем Circuit Breaker перед выполнением
            try:
                return self.circuit_breaker.call(func, *args, **kwargs)
            except CircuitBreakerOpenError as e:
                logger.warning(f"Circuit Breaker открыт: {e}")
                raise
        
        try:
            return _execute()
        except RetryError as e:
            # Все попытки исчерпаны
            logger.error(f"Все попытки retry исчерпаны для {func.__name__}: {e.last_attempt.exception()}")
            raise e.last_attempt.exception() from e
        except Exception as e:
            # Постоянные ошибки (400, 401, 403, 404) пробрасываем сразу
            if _should_not_retry(e):
                logger.error(f"Постоянная ошибка, не повторяем: {e}")
            raise
    
    async def _run_in_executor(self, func: Callable, *args, **kwargs) -> Any:
        """
        Запускает синхронную функцию в executor для предотвращения блокировки event loop.
        
        Args:
            func: Синхронная функция для выполнения
            *args: Позиционные аргументы
            **kwargs: Именованные аргументы
            
        Returns:
            Результат выполнения функции
        """
        loop = self._get_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._retry_exec(func, *args, **kwargs)
        )
    
    async def get_all_records(self, worksheet: gspread.Worksheet) -> List[Dict]:
        """
        Получает все записи из worksheet.
        
        Args:
            worksheet: Worksheet объект из gspread
            
        Returns:
            Список словарей с данными записей
        """
        return await self._run_in_executor(worksheet.get_all_records)
    
    async def append_row(self, worksheet: gspread.Worksheet, values: List[Any]) -> None:
        """
        Добавляет строку в worksheet.
        
        Args:
            worksheet: Worksheet объект из gspread
            values: Список значений для строки
        """
        await self._run_in_executor(worksheet.append_row, values)
    
    async def update(self, worksheet: gspread.Worksheet, range_name: str, values: List[List[Any]]) -> None:
        """
        Обновляет диапазон ячеек в worksheet.
        
        Args:
            worksheet: Worksheet объект из gspread
            range_name: Имя диапазона (например, 'A1:B2')
            values: Двумерный список значений
        """
        await self._run_in_executor(worksheet.update, range_name, values)
    
    async def update_cell(self, worksheet: gspread.Worksheet, row: int, col: int, value: Any) -> None:
        """
        Обновляет одну ячейку в worksheet.
        
        Args:
            worksheet: Worksheet объект из gspread
            row: Номер строки (начиная с 1)
            col: Номер колонки (начиная с 1)
            value: Значение для ячейки
        """
        await self._run_in_executor(worksheet.update_cell, row, col, value)
    
    async def find(self, worksheet: gspread.Worksheet, query: str, in_row: Optional[int] = None, in_column: Optional[int] = None) -> Optional[gspread.Cell]:
        """
        Находит ячейку по запросу.
        
        Args:
            worksheet: Worksheet объект из gspread
            query: Текст для поиска
            in_row: Ограничение поиска строкой (опционально)
            in_column: Ограничение поиска колонкой (опционально)
            
        Returns:
            Cell объект или None если не найдено
        """
        return await self._run_in_executor(worksheet.find, query, in_row, in_column)
    
    async def findall(self, worksheet: gspread.Worksheet, query: str) -> List[gspread.Cell]:
        """
        Находит все ячейки по запросу.
        
        Args:
            worksheet: Worksheet объект из gspread
            query: Текст для поиска
            
        Returns:
            Список Cell объектов
        """
        return await self._run_in_executor(worksheet.findall, query)
    
    async def row_values(self, worksheet: gspread.Worksheet, row: int) -> List[str]:
        """
        Получает значения строки.
        
        Args:
            worksheet: Worksheet объект из gspread
            row: Номер строки (начиная с 1)
            
        Returns:
            Список значений строки
        """
        return await self._run_in_executor(worksheet.row_values, row)
    
    async def col_values(self, worksheet: gspread.Worksheet, col: int) -> List[str]:
        """
        Получает значения колонки.
        
        Args:
            worksheet: Worksheet объект из gspread
            col: Номер колонки (начиная с 1)
            
        Returns:
            Список значений колонки
        """
        return await self._run_in_executor(worksheet.col_values, col)
    
    async def get_worksheet(self, spreadsheet: gspread.Spreadsheet, sheet_name: str) -> gspread.Worksheet:
        """
        Получает worksheet по имени.
        
        Args:
            spreadsheet: Spreadsheet объект из gspread
            sheet_name: Имя листа
            
        Returns:
            Worksheet объект
        """
        return await self._run_in_executor(spreadsheet.worksheet, sheet_name)
    
    async def batch_update(self, worksheet: gspread.Worksheet, data: List[Dict]) -> None:
        """
        Пакетное обновление ячеек.
        
        Args:
            worksheet: Worksheet объект из gspread
            data: Список словарей с данными для обновления
        """
        await self._run_in_executor(worksheet.batch_update, data)
    
    async def format(self, worksheet: gspread.Worksheet, range_name: str, format_dict: Dict) -> None:
        """
        Форматирует диапазон ячеек.
        
        Args:
            worksheet: Worksheet объект из gspread
            range_name: Имя диапазона
            format_dict: Словарь с параметрами форматирования
        """
        await self._run_in_executor(worksheet.format, range_name, format_dict)

    async def cell(self, worksheet: gspread.Worksheet, row: int, col: int) -> gspread.Cell:
        """
        Получает значение ячейки.
        
        Args:
            worksheet: Worksheet объект из gspread
            row: Номер строки (начиная с 1)
            col: Номер колонки (начиная с 1)
            
        Returns:
            Cell объект
        """
        return await self._run_in_executor(worksheet.cell, row, col)
