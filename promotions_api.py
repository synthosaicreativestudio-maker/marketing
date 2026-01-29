"""API для работы с акциями и событиями из Google Sheets"""
import logging
import os
import json
from typing import List, Dict
from datetime import datetime, date
from dotenv import load_dotenv

from sheets_gateway import AsyncGoogleSheetsGateway, SheetsNotConfiguredError, CircuitBreakerOpenError

# Загружаем переменные окружения
load_dotenv()

logger = logging.getLogger(__name__)

class PromotionsNotConfiguredError(Exception):
    """Ошибка конфигурации системы акций"""
    pass

def _get_promotions_client_and_sheet():
    """Получение клиента и листа для таблицы акций (синхронная функция для инициализации)"""
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
        logger.info(f"Connected to Promotions Spreadsheet: '{spreadsheet.title}'")
        
        sheet_name = os.environ.get('PROMOTIONS_SHEET_NAME', 'Sheet1')
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
            logger.info(f"Successfully opened worksheet: '{sheet_name}'")
        except Exception as e:
            logger.warning(f"Promotions worksheet '{sheet_name}' not found ({e}). Falling back to first sheet.")
            worksheet = spreadsheet.sheet1
            logger.info(f"Fallback to first worksheet: '{worksheet.title}'")

        # Debug: Log headers
        try:
            headers = worksheet.row_values(1)
            logger.info(f"Sheet Headers: {headers}")
        except Exception as e:
            logger.error(f"Could not read headers: {e}")

        return client, worksheet
    
    except ImportError as e:
        raise PromotionsNotConfiguredError(f'Import error: {e}')
    except Exception as e:
        logger.error(f"Failed to connect to Promotions Google Sheets: {e}")
        raise PromotionsNotConfiguredError(f'Promotions Google Sheets connection failed: {e}')

# Global cache for promotions
_promotions_cache = {
    'data': [],
    'timestamp': 0
}
CACHE_TTL = 300  # 5 minutes in seconds

async def get_active_promotions(gateway: AsyncGoogleSheetsGateway) -> List[Dict]:
    """
    Получает список активных акций из Google Sheets.
    Использует кэширование на 5 минут.
    
    Args:
        gateway: AsyncGoogleSheetsGateway для работы с Google Sheets
        
    Returns:
        List[Dict]: Список активных акций
    """
    global _promotions_cache
    
    current_time = datetime.now().timestamp()
    
    # Return cached data if valid
    if _promotions_cache['data'] and (current_time - _promotions_cache['timestamp'] < CACHE_TTL):
        logger.info("Возврат акций из кэша")
        return _promotions_cache['data']

    try:
        client = await gateway.authorize_client()
        sheet_id = os.environ.get('PROMOTIONS_SHEET_ID')
        if not sheet_id:
            logger.error("PROMOTIONS_SHEET_ID не задан")
            return []
            
        spreadsheet = await gateway.open_spreadsheet(client, sheet_id)
        sheet_name = os.environ.get('PROMOTIONS_SHEET_NAME', 'Sheet1')
        worksheet = await gateway.get_worksheet_async(spreadsheet, sheet_name)
        
        records = await gateway.get_all_records(worksheet)
        
        active_promotions = []
        
        for record in records:
            # Проверяем статус акции
            status = str(record.get('Статус', '')).strip()
            if status.lower() == 'активна':
                # Используем описание как название, если название пустое
                title = str(record.get('Название', '')).strip()
                description = str(record.get('Описание', '')).strip()
                start_date = str(record.get('Дата начала', '')).strip()
                end_date = str(record.get('Дата окончания', '')).strip()
                content = str(record.get('Контент', '')).strip()
                
                if not title or title == 'None' or title == '':
                    title = f"Акция {description}" if description and description != 'None' else "Акция без названия"
                
                # Создаем уникальный ID
                unique_id = f"{title}_{description}_{start_date}_{end_date}".replace(' ', '_').replace(':', '').replace('-', '')
                
                promotion = {
                    'id': unique_id,
                    'title': title,
                    'description': description if description and description != 'None' else "Описание отсутствует",
                    'status': status,
                    'start_date': start_date if start_date and start_date != 'None' else '',
                    'end_date': end_date if end_date and end_date != 'None' else ''
                }
                
                # Добавляем контент, если он есть
                if content and content != 'None' and content != '':
                    promotion['content'] = content
                
                # Добавляем акцию, если есть хотя бы название или описание
                if promotion['title'] and promotion['title'] != 'None':
                    active_promotions.append(promotion)
                    logger.info(f"Найдена активная акция: {promotion['title']}")
                else:
                    logger.warning(f"Пропущена акция без названия и описания (row data: {record})")
        
        logger.info(f"Всего найдено активных акций: {len(active_promotions)}")
        
        # Update cache
        _promotions_cache['data'] = active_promotions
        _promotions_cache['timestamp'] = current_time
        
        return active_promotions
        
    except (PromotionsNotConfiguredError, SheetsNotConfiguredError, CircuitBreakerOpenError) as e:
        logger.error(f"Система акций недоступна: {e}")
        # Return cached data if available even if expired in case of error
        if _promotions_cache['data']:
            logger.warning("Возврат устаревшего кэша из-за ошибки")
            return _promotions_cache['data']
        return []
    except Exception as e:
        logger.error(f"Ошибка при получении активных акций: {e}")
        # Return cached data if available even if expired in case of error
        if _promotions_cache['data']:
            logger.warning("Возврат устаревшего кэша из-за ошибки")
            return _promotions_cache['data']
        return []

async def get_promotions_json(gateway: AsyncGoogleSheetsGateway) -> str:
    """
    Возвращает активные акции в формате JSON для API.
    
    Args:
        gateway: AsyncGoogleSheetsGateway для работы с Google Sheets
    
    Returns:
        str: JSON строка с активными акциями
    """
    try:
        promotions = await get_active_promotions(gateway)
        return json.dumps(promotions, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка при создании JSON акций: {e}")
        return json.dumps([], ensure_ascii=False)

async def check_new_promotions(gateway: AsyncGoogleSheetsGateway) -> List[Dict]:
    """
    Проверяет наличие новых активных акций для отправки уведомлений.
    
    Args:
        gateway: AsyncGoogleSheetsGateway для работы с Google Sheets
    
    Returns:
        List[Dict]: Список новых активных акций
    """
    try:
        client = await gateway.authorize_client()
        sheet_id = os.environ.get('PROMOTIONS_SHEET_ID')
        if not sheet_id:
            return []
            
        spreadsheet = await gateway.open_spreadsheet(client, sheet_id)
        sheet_name = os.environ.get('PROMOTIONS_SHEET_NAME', 'Sheet1')
        worksheet = await gateway.get_worksheet_async(spreadsheet, sheet_name)
        
        # Получаем заголовки для определения индекса колонки статуса
        headers = await gateway.row_values(worksheet, 1)
        status_col_name = 'NOTIFICATION_STATUS'
        
        try:
            status_col_index = headers.index(status_col_name) + 1
        except ValueError:
            # Если колонки нет, считаем, что это следующая за последней
            status_col_index = len(headers) + 1
            # Добавим заголовок, если его нет (чтобы get_all_records видел колонку)
            await gateway.update_cell(worksheet, 1, status_col_index, status_col_name)
            logger.info(f"Добавлена колонка {status_col_name} в таблицу акций (индекс {status_col_index})")
        
        records = await gateway.get_all_records(worksheet)
        
        new_promotions = []
        
        # Используем enumerate для отслеживания индекса строки (row_index)
        # Данные начинаются со 2-й строки
        for i, record in enumerate(records, start=2):
            # Шаг 1: Проверка статуса (Дедупликация)
            notification_status = str(record.get(status_col_name, '')).strip()
            if notification_status == 'SENT':
                continue # Пропускаем, уже отправляли
                
            # Проверяем статус акции (Активна ли она вообще)
            status = str(record.get('Статус', '')).strip()
            if status.lower() == 'активна':
                # Проверяем дату релиза
                release_date = str(record.get('Дата релиза', '')).strip()
                if release_date and release_date != 'None':
                    try:
                        release_dt = datetime.strptime(release_date, '%d.%m.%Y').date()
                        today = date.today()
                        
                        # Мы отправляем только сегодняшние или будущие, если они еще не SENT
                        if release_dt <= today:
                            title = str(record.get('Название', '')).strip()
                            description = str(record.get('Описание', '')).strip()
                            start_date = str(record.get('Дата начала', ''))
                            end_date = str(record.get('Дата окончания', ''))
                            content = str(record.get('Контент', '')).strip()
                            link = str(record.get('Ссылка', '')).strip()
                            
                            if not title or title == 'None' or title == '':
                                title = f"Акция {description}" if description and description != 'None' else "Акция без названия"
                            
                            unique_id = f"{title}_{description}_{start_date}_{end_date}".replace(' ', '_').replace(':', '').replace('-', '')
                            
                            promotion = {
                                'id': unique_id,
                                'title': title,
                                'description': description if description and description != 'None' else "Описание отсутствует",
                                'status': status,
                                'start_date': start_date,
                                'end_date': end_date,
                                'release_date': release_date,
                                'link': link,
                                'row_index': i, # Сохраняем индекс для последующей пометки SENT
                                'status_col_index': status_col_index
                            }
                            
                            # Добавляем контент
                            if content and content != 'None' and content != '':
                                promotion['content'] = content
                            
                            if promotion['title'] and promotion['title'] != 'None':
                                new_promotions.append(promotion)
                                logger.info(f"Найдена новая акция для рассылки: {promotion['title']} (строка {i})")
                    except ValueError as e:
                        logger.warning(f"Ошибка парсинга даты релиза '{release_date}' в строке {i}: {e}")
                        continue
        
        logger.info(f"Всего найдено новых акций для отправки: {len(new_promotions)}")
        return new_promotions
        
    except (PromotionsNotConfiguredError, SheetsNotConfiguredError, CircuitBreakerOpenError) as e:
        logger.error(f"Система акций недоступна: {e}")
        return []
    except Exception as e:
        logger.error(f"Ошибка при проверке новых акций: {e}")
        return []

async def is_promotions_available(gateway: AsyncGoogleSheetsGateway) -> bool:
    """
    Проверяет, доступна ли система акций.
    
    Args:
        gateway: AsyncGoogleSheetsGateway для работы с Google Sheets
    
    Returns:
        bool: True если система акций настроена и доступна
    """
    try:
        if not gateway:
             # Fallback to sync method if gateway not provided (legacy)
            _get_promotions_client_and_sheet()
            return True

        client = await gateway.authorize_client()
        sheet_id = os.environ.get('PROMOTIONS_SHEET_ID')
        if not sheet_id:
            return False
            
        # Just check if we can open the spreadsheet
        await gateway.open_spreadsheet(client, sheet_id)
        return True
    except (PromotionsNotConfiguredError, SheetsNotConfiguredError, CircuitBreakerOpenError):
        return False
    except Exception as e:
        logger.error(f"Ошибка проверки доступности системы акций: {e}")
        return False
