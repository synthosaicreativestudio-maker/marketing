"""API для работы с акциями и событиями из Google Sheets"""
import logging
import os
import json
from typing import List, Dict, Optional
from datetime import datetime
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

logger = logging.getLogger(__name__)

class PromotionsNotConfiguredError(Exception):
    """Ошибка конфигурации системы акций"""
    pass

def _get_promotions_client_and_sheet():
    """Получение клиента и листа для таблицы акций"""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        
        # Используем ту же логику, что и в sheets.py
        sa_json = os.environ.get('GCP_SA_JSON')
        sa_file = os.environ.get('GCP_SA_FILE')
        
        if sa_json:
            sa_info = json.loads(sa_json)
        elif sa_file and os.path.exists(sa_file):
            with open(sa_file, 'r', encoding='utf-8') as f:
                sa_info = json.load(f)
        else:
            raise PromotionsNotConfiguredError(
                'Service account JSON not provided (GCP_SA_JSON or GCP_SA_FILE)'
            )
        
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        creds = Credentials.from_service_account_info(sa_info, scopes=scopes)
        client = gspread.authorize(creds)
        
        sheet_id = os.environ.get('PROMOTIONS_SHEET_ID')
        if not sheet_id:
            raise PromotionsNotConfiguredError('PROMOTIONS_SHEET_ID not provided')
        
        spreadsheet = client.open_by_key(sheet_id)
        sheet_name = os.environ.get('PROMOTIONS_SHEET_NAME', 'Sheet1')
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
        except Exception as e:
            logger.warning(f"Promotions worksheet '{sheet_name}' not found ({e}). Falling back to first sheet.")
            worksheet = spreadsheet.sheet1

        return client, worksheet
    
    except ImportError as e:
        raise PromotionsNotConfiguredError(f'Import error: {e}')
    except Exception as e:
        logger.error(f"Failed to connect to Promotions Google Sheets: {e}")
        raise PromotionsNotConfiguredError(f'Promotions Google Sheets connection failed: {e}')

def get_active_promotions() -> List[Dict]:
    """
    Получает список активных акций из Google Sheets.
    
    Returns:
        List[Dict]: Список активных акций с полями:
        - id: ID акции
        - title: Название акции
        - description: Описание акции
        - status: Статус акции
        - start_date: Дата начала
        - end_date: Дата окончания
    """
    try:
        _, worksheet = _get_promotions_client_and_sheet()
        records = worksheet.get_all_records()
        
        active_promotions = []
        
        for record in records:
            # Проверяем статус акции
            status = str(record.get('Статус', '')).strip()
            if status.lower() == 'активна':
                # Используем описание как название, если название пустое
                title = str(record.get('Название', '')).strip()
                description = str(record.get('Описание', '')).strip()
                
                if not title or title == 'None' or title == '':
                    title = f"Акция {description}" if description and description != 'None' else "Акция без названия"
                
                promotion = {
                    'id': str(record.get('ID акции', '')),
                    'title': title,
                    'description': description if description and description != 'None' else "Описание отсутствует",
                    'status': status,
                    'start_date': str(record.get('Дата начала', '')),
                    'end_date': str(record.get('Дата окончания', ''))
                }
                
                # Добавляем акцию, если есть хотя бы название или описание
                if promotion['title'] and promotion['title'] != 'None':
                    active_promotions.append(promotion)
                    logger.info(f"Найдена активная акция: {promotion['title']}")
        
        logger.info(f"Всего найдено активных акций: {len(active_promotions)}")
        return active_promotions
        
    except PromotionsNotConfiguredError:
        logger.error("Система акций не настроена")
        return []
    except Exception as e:
        logger.error(f"Ошибка при получении активных акций: {e}")
        return []

def get_promotions_json() -> str:
    """
    Возвращает активные акции в формате JSON для API.
    
    Returns:
        str: JSON строка с активными акциями
    """
    try:
        promotions = get_active_promotions()
        return json.dumps(promotions, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка при создании JSON акций: {e}")
        return json.dumps([], ensure_ascii=False)

def check_new_promotions() -> List[Dict]:
    """
    Проверяет наличие новых активных акций для отправки уведомлений.
    
    Returns:
        List[Dict]: Список новых активных акций
    """
    try:
        _, worksheet = _get_promotions_client_and_sheet()
        records = worksheet.get_all_records()
        
        new_promotions = []
        
        for record in records:
            # Проверяем статус акции
            status = str(record.get('Статус', '')).strip()
            if status.lower() == 'активна':
                # Проверяем, есть ли дата релиза (когда акция стала активной)
                release_date = str(record.get('Дата релиза', '')).strip()
                if release_date and release_date != 'None':
                    # Проверяем, что акция была опубликована сегодня
                    try:
                        from datetime import datetime, date
                        release_dt = datetime.strptime(release_date, '%d.%m.%Y').date()
                        today = date.today()
                        
                        if release_dt == today:
                                   promotion = {
                                       'id': str(record.get('ID акции', '')),
                                       'title': str(record.get('Название', '')),
                                       'description': str(record.get('Описание', '')),
                                       'status': status,
                                       'start_date': str(record.get('Дата начала', '')),
                                       'end_date': str(record.get('Дата окончания', '')),
                                       'release_date': release_date
                                   }
                            
                            if promotion['title'] and promotion['title'] != 'None':
                                new_promotions.append(promotion)
                                logger.info(f"Найдена новая акция: {promotion['title']} (релиз: {release_date})")
                    except ValueError as e:
                        logger.warning(f"Ошибка парсинга даты релиза '{release_date}': {e}")
                        continue
        
        logger.info(f"Всего найдено новых акций: {len(new_promotions)}")
        return new_promotions
        
    except PromotionsNotConfiguredError:
        logger.error("Система акций не настроена")
        return []
    except Exception as e:
        logger.error(f"Ошибка при проверке новых акций: {e}")
        return []

def is_promotions_available() -> bool:
    """
    Проверяет, доступна ли система акций.
    
    Returns:
        bool: True если система акций настроена и доступна
    """
    try:
        _get_promotions_client_and_sheet()
        return True
    except PromotionsNotConfiguredError:
        return False
    except Exception as e:
        logger.error(f"Ошибка проверки доступности системы акций: {e}")
        return False
