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
        from google.auth.service_account import Credentials
        
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
        worksheet = spreadsheet.worksheet(sheet_name)
        
        return client, worksheet
    
    except ImportError:
        raise SheetsNotConfiguredError('gspread not installed')
    except Exception as e:
        logger.error(f"Failed to connect to Google Sheets: {e}")
        raise SheetsNotConfiguredError(f'Google Sheets connection failed: {e}')


def find_row_by_partner_and_phone(partner_code: str, phone_norm: str) -> Optional[int]:
    """Поиск строки по коду партнера и телефону"""
    try:
        _, worksheet = _get_client_and_sheet()
        records = worksheet.get_all_records()
        
        for i, record in enumerate(records, start=2):  # start=2 because row 1 is header
            if (str(record.get('partner_code', '')) == partner_code and 
                normalize_phone(str(record.get('phone', ''))) == phone_norm):
                return i
        
        return None
    
    except SheetsNotConfiguredError:
        raise
    except Exception as e:
        logger.error(f"Error finding row: {e}")
        return None


def update_row_with_auth(row: int, telegram_id: int, status: str = 'authorized'):
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
