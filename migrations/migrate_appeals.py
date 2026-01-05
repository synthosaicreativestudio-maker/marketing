"""
Скрипт миграции обращений из Google Sheets в базу данных.
Переносит все существующие обращения из таблицы Google Sheets в SQLite БД.
"""
import os
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

# Импорты после загрузки .env
import gspread
from google.oauth2.service_account import Credentials
import json
from db.database import SessionLocal, init_db
from db.models import Appeal, AppealMessage

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_service_account():
    """Загружает данные Service Account из переменных окружения."""
    sa_json = os.environ.get('GCP_SA_JSON')
    sa_file = os.environ.get('GCP_SA_FILE')
    
    if sa_json:
        return json.loads(sa_json)
    elif sa_file and os.path.exists(sa_file):
        with open(sa_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        raise ValueError('Service account JSON not provided (GCP_SA_JSON or GCP_SA_FILE)')


def connect_to_sheets():
    """Подключается к Google Sheets таблице обращений."""
    try:
        sa_info = load_service_account()
        creds = Credentials.from_service_account_info(sa_info, scopes=[
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ])
        client = gspread.authorize(creds)
        
        sheet_id = os.environ.get('APPEALS_SHEET_ID')
        if not sheet_id:
            raise ValueError('APPEALS_SHEET_ID not provided')
        
        spreadsheet = client.open_by_key(sheet_id)
        sheet_name = os.environ.get('APPEALS_SHEET_NAME', 'обращения')
        
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
        except Exception:
            worksheet = spreadsheet.sheet1
            logger.warning(f"Лист '{sheet_name}' не найден, используется первый лист")
        
        logger.info(f"Подключено к таблице: {spreadsheet.title}, лист: {worksheet.title}")
        return worksheet
        
    except Exception as e:
        logger.error(f"Ошибка подключения к Google Sheets: {e}")
        raise


def parse_appeals_text(text: str) -> list:
    """
    Парсит текст обращений из Google Sheets в список сообщений.
    
    Формат в Google Sheets:
    2026-01-05 14:43:49: Пользователь: Привет
    2026-01-05 14:44:12: 🤖 ИИ: Ответ ИИ
    2026-01-05 14:45:30: 👨‍💼 СПЕЦИАЛИСТ: Ответ специалиста
    """
    if not text or not text.strip():
        return []
    
    messages = []
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Определяем тип сообщения по префиксу
        if '🤖 ИИ:' in line or 'ИИ:' in line:
            message_type = 'ai'
            # Убираем префикс даты и префикс ИИ
            parts = line.split(':', 2)
            if len(parts) >= 3:
                message_text = parts[2].strip()
            else:
                message_text = line.replace('🤖 ИИ:', '').replace('ИИ:', '').strip()
        elif '👨‍💼 СПЕЦИАЛИСТ:' in line or 'СПЕЦИАЛИСТ:' in line:
            message_type = 'specialist'
            # Убираем префикс даты и префикс специалиста
            parts = line.split(':', 2)
            if len(parts) >= 3:
                message_text = parts[2].strip()
            else:
                message_text = line.replace('👨‍💼 СПЕЦИАЛИСТ:', '').replace('СПЕЦИАЛИСТ:', '').strip()
        elif 'Пользователь:' in line:
            message_type = 'user'
            # Убираем префикс даты и "Пользователь:"
            parts = line.split(':', 2)
            if len(parts) >= 3:
                message_text = parts[2].strip()
            else:
                message_text = line.split('Пользователь:', 1)[-1].strip()
        else:
            # По умолчанию считаем сообщением пользователя
            message_type = 'user'
            # Пытаемся извлечь текст после даты
            if ':' in line:
                parts = line.split(':', 1)
                message_text = parts[-1].strip() if len(parts) > 1 else line
            else:
                message_text = line
        
        if message_text:
            # Пытаемся извлечь дату из начала строки
            created_at = None
            if len(line) >= 19 and line[4] == '-' and line[7] == '-':
                try:
                    date_str = line[:19]
                    created_at = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    created_at = datetime.utcnow()
            else:
                created_at = datetime.utcnow()
            
            messages.append({
                'type': message_type,
                'text': message_text,
                'created_at': created_at
            })
    
    return messages


def migrate_appeals():
    """Основная функция миграции."""
    logger.info("=" * 60)
    logger.info("Начало миграции обращений из Google Sheets в БД")
    logger.info("=" * 60)
    
    # Инициализация БД
    try:
        init_db()
        logger.info("База данных инициализирована")
    except Exception as e:
        logger.warning(f"База данных уже существует или ошибка: {e}")
    
    # Подключение к Google Sheets
    try:
        worksheet = connect_to_sheets()
    except Exception as e:
        logger.error(f"Не удалось подключиться к Google Sheets: {e}")
        return False
    
    # Подключение к БД
    db = SessionLocal()
    
    try:
        # Получаем все записи из Google Sheets
        logger.info("Загрузка данных из Google Sheets...")
        records = worksheet.get_all_records()
        logger.info(f"Найдено {len(records)} записей в Google Sheets")
        
        migrated_count = 0
        skipped_count = 0
        error_count = 0
        
        for i, record in enumerate(records, 1):
            try:
                telegram_id = record.get('telegram_id', '')
                if not telegram_id:
                    logger.warning(f"Запись {i}: пропущена (нет telegram_id)")
                    skipped_count += 1
                    continue
                
                telegram_id = int(telegram_id)
                
                # Проверяем, есть ли уже такое обращение в БД
                existing = db.query(Appeal).filter(
                    Appeal.telegram_id == telegram_id
                ).first()
                
                if existing:
                    logger.info(f"Запись {i}: обращение для telegram_id {telegram_id} уже существует, пропускаем")
                    skipped_count += 1
                    continue
                
                # Создаем обращение
                appeal = Appeal(
                    telegram_id=telegram_id,
                    partner_code=str(record.get('код', '') or ''),
                    phone=str(record.get('телефон', '') or ''),
                    fio=str(record.get('ФИО', '') or ''),
                    status=str(record.get('статус', 'новое') or 'новое').lower()
                )
                
                # Парсим дату создания из времени обновления
                updated_time = record.get('время_обновления', '')
                if updated_time:
                    try:
                        appeal.created_at = datetime.strptime(updated_time, '%Y-%m-%d %H:%M:%S')
                        appeal.updated_at = appeal.created_at
                    except ValueError:
                        pass
                
                db.add(appeal)
                db.flush()  # Получаем ID
                
                # Парсим и добавляем сообщения
                appeals_text = record.get('текст_обращений', '')
                if appeals_text:
                    messages = parse_appeals_text(appeals_text)
                    for msg_data in messages:
                        message = AppealMessage(
                            appeal_id=appeal.id,
                            message_type=msg_data['type'],
                            message_text=msg_data['text'],
                            created_at=msg_data['created_at']
                        )
                        db.add(message)
                
                # Обрабатываем ответ специалиста, если есть
                specialist_response = record.get('специалист_ответ', '')
                if specialist_response and specialist_response.strip():
                    # Добавляем как сообщение
                    message = AppealMessage(
                        appeal_id=appeal.id,
                        message_type='specialist',
                        message_text=f"👨‍💼 СПЕЦИАЛИСТ: {specialist_response.strip()}"
                    )
                    db.add(message)
                
                db.commit()
                migrated_count += 1
                logger.info(f"Запись {i}: мигрировано обращение для telegram_id {telegram_id} (ID: {appeal.id})")
                
            except Exception as e:
                logger.error(f"Запись {i}: ошибка миграции - {e}", exc_info=True)
                db.rollback()
                error_count += 1
                continue
        
        logger.info("=" * 60)
        logger.info("Миграция завершена!")
        logger.info(f"Успешно мигрировано: {migrated_count}")
        logger.info(f"Пропущено: {skipped_count}")
        logger.info(f"Ошибок: {error_count}")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"Критическая ошибка миграции: {e}", exc_info=True)
        db.rollback()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    success = migrate_appeals()
    sys.exit(0 if success else 1)
