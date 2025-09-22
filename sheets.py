"""Упрощенная работа с Google Sheets для MarketingBot"""
import json
import logging
import os
from pathlib import Path
from typing import Optional

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
    """Получение клиента и листа Google Sheets"""
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


def find_row_by_partner_and_phone(partner_code: str, phone_norm: str) -> Optional[int]:
    """Поиск строки по коду партнера и телефону.

    Поддерживаются заголовки как на английском, так и на русском:
    - English: 'partner_code', 'phone'
    - Russian: 'Код партнера', 'Телефон партнера'
    """
    try:
        _, worksheet = _get_client_and_sheet()
        records = worksheet.get_all_records()

        partner_code_str = str(partner_code).strip()

        for i, record in enumerate(records, start=2):  # start=2 because row 1 is header
            code_in_row = str(
                record.get('partner_code', record.get('Код партнера', ''))
            ).strip()
            phone_in_row = str(
                record.get('phone', record.get('Телефон партнера', ''))
            ).strip()

            if code_in_row == partner_code_str and normalize_phone(phone_in_row) == phone_norm:
                return i

        return None

    except SheetsNotConfiguredError:
        raise
    except Exception as e:
        logger.error(f"Error finding row: {e}")
        return None


def update_row_with_auth(row: int, telegram_id: int, status: str = 'авторизован'):
    """Обновление строки с данными авторизации"""
    try:
        _, worksheet = _get_client_and_sheet()
        
        # Обновляем колонки D (статус) и E (telegram_id)
        worksheet.update(f'D{row}', status)
        worksheet.update(f'E{row}', str(telegram_id))
        
        logger.info(f"Updated row {row} with status={status}, telegram_id={telegram_id}")
        
    except SheetsNotConfiguredError:
        raise
    except Exception as e:
        logger.error(f"Error updating row {row}: {e}")
        raise
