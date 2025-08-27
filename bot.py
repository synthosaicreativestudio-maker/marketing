# -*- coding: utf-8 -*-

"""
Улучшенная версия бота с исправленной архитектурой.
- Централизованная конфигурация
- Единый кэш авторизации
- Кроссплатформенная блокировка процессов
- Оптимизированная работа с OpenAI
- Улучшенная обработка ошибок
"""

import logging
import os
import json
import time
import asyncio
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
import telegram
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from sheets_client import GoogleSheetsClient

# Импорты новых модулей
from config import SECTIONS, get_web_app_url, get_ticket_status, SUBSECTIONS
from auth_cache import auth_cache
from openai_client import openai_client
from process_lock import ProcessLock

# Загрузка .env. Если TELEGRAM_TOKEN не задан, попробуем загрузить `bot.env`

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /menu - показывает persistent keyboard с кнопкой личного кабинета"""
    # Показываем persistent keyboard с кнопкой личного кабинета
    persistent_keyboard = create_persistent_keyboard()
    await update.message.reply_text(
        '💼 Используйте кнопку "🚀 Личный кабинет" для быстрого доступа к личному кабинету:',
        reply_markup=persistent_keyboard
    )

async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if not data or not data.startswith('menu:'):
        await query.edit_message_text('Неподдерживаемое действие меню.')
        return
    section = data[5:]
    if section == 'Связаться со специалистом':
        await query.edit_message_text('Пожалуйста, опишите вашу проблему, и специалист свяжется с вами.')
    else:
        await query.edit_message_text(f'Вы выбрали раздел: {section}. Здесь вы можете задать вопрос или получить информацию.')
load_dotenv()
if not os.getenv('TELEGRAM_TOKEN') and os.path.exists('bot.env'):
    load_dotenv('bot.env', override=True)

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Google Sheets клиент
SHEET_URL = os.getenv('SHEET_URL')
WORKSHEET_NAME = os.getenv('WORKSHEET_NAME', 'список сотрудников для авторизации')
TICKETS_SHEET_URL = os.getenv('TICKETS_SHEET_URL')
TICKETS_WORKSHEET = os.getenv('TICKETS_WORKSHEET', 'обращения')

sheets_client = None
if SHEET_URL and os.path.exists('credentials.json'):
    try:
        sheets_client = GoogleSheetsClient(credentials_path='credentials.json', sheet_url=SHEET_URL, worksheet_name=WORKSHEET_NAME)
    except Exception as e:
        logger.error(f'Ошибка инициализации GoogleSheetsClient: {e}')
else:
    logger.info('SHEET_URL не задан или credentials.json отсутствует — Google Sheets отключён')
# Утилиты
def is_admin(user_id: int) -> bool:
    # Временно добавляем ваш ID для тестирования
    hardcoded_admins = ['284355186']  # Ваш ID из логов
    admin_ids = os.getenv('ADMIN_TELEGRAM_ID', '')
    admin_list = [s.strip() for s in admin_ids.split(',') if s.strip()]
    all_admins = hardcoded_admins + admin_list
    return str(user_id) in all_admins

def create_persistent_keyboard():
    """Создаёт постоянную reply клавиатуру с кнопкой menu, которая сразу открывает миниапп"""
    from telegram import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
    menu_url = get_web_app_url('SPA_MENU')
    return ReplyKeyboardMarkup(
        [[KeyboardButton('🚀 Личный кабинет', web_app=WebAppInfo(url=menu_url))]],
        resize_keyboard=True,
        one_time_keyboard=False
    )

def create_auth_button(url: str):
    """Создаёт кнопку для авторизации"""
    return [[InlineKeyboardButton('Авторизоваться', web_app=WebAppInfo(url=url))]]

async def is_user_authorized(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Проверяет авторизацию пользователя. Использует единый кэш для оптимизации."""
    # Сначала проверяем кэш
    cached_auth = auth_cache.is_user_authorized(user_id)
    if cached_auth is not None:
        logger.info(f'Using cached authorization for user {user_id}: {cached_auth}')
        return cached_auth
    
    # Получаем актуальные данные из Google Sheets
    try:
    authorized_ids = await asyncio.to_thread(get_authorized_ids)
    if authorized_ids is None:
        logger.warning(f'No access to sheets for user {user_id}')
        return False
        
    is_auth = str(user_id) in authorized_ids
        
        # Обновляем кэш
        auth_cache.set_user_authorized(user_id, is_auth)
        
    logger.info(f'User {user_id} authorization result: {is_auth}')
    return is_auth

    except Exception as e:
        logger.error(f'Error checking authorization for user {user_id}: {e}')
        return False


# Функции для работы с кэшем авторизации
def get_authorized_ids():
    """Возвращает множество строк с авторизованными Telegram ID или None, если Sheets недоступен."""
    cached_ids = auth_cache.get_authorized_ids()
    if cached_ids is not None:
        return cached_ids
    
    # Обновляем кэш
    try:
        if not sheets_client or not sheets_client.sheet:
            return None
        ids = sheets_client.get_all_authorized_user_ids()
        auth_cache.set_authorized_ids(set(str(i) for i in ids if i))
        return auth_cache.get_authorized_ids()
    except Exception as e:
        logger.error(f'Не удалось получить список авторизованных ID: {e}')
        return None

def refresh_authorized_cache():
    """Обновляет кэш авторизованных пользователей"""
    try:
        if sheets_client and sheets_client.sheet:
            ids = sheets_client.get_all_authorized_user_ids()
            auth_cache.set_authorized_ids(set(str(i) for i in ids if i))
    except Exception as e:
        logger.error(f'Ошибка при обновлении кэша авторизаций: {e}')

# Клиент для таблицы обращений (tickets)
tickets_client = None
if TICKETS_SHEET_URL and os.path.exists('credentials.json'):
    try:
        tickets_client = GoogleSheetsClient(credentials_path='credentials.json', sheet_url=TICKETS_SHEET_URL, worksheet_name=TICKETS_WORKSHEET)
        # Отладочная информация
        logger.info(f'DEBUG: tickets_client создан: {type(tickets_client)}')
        logger.info(f'DEBUG: tickets_client has extract_operator_replies: {hasattr(tickets_client, "extract_operator_replies")}')
        logger.info(f'DEBUG: tickets_client methods: {[method for method in dir(tickets_client) if not method.startswith("_")]}')
        
        # Устанавливаем фиксированные размеры для колонки с обращениями (колонка E: ширина 600px, высота строк 100px)
        if tickets_client and tickets_client.sheet:
            tickets_client.set_tickets_column_width(600, 100)
            logger.info('Установлены размеры: ширина 600px, высота 100px для колонки обращений')
    except Exception as e:
        logger.error(f'Ошибка инициализации tickets GoogleSheetsClient: {e}')
else:
    logger.info('TICKETS_SHEET_URL не задан или credentials.json отсутствует — таблица обращений отключена')

# Система мониторинга ответов операторов






async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data or ''
    # Кнопка вызова меню миниапп
    if data == 'show_menu':
        keyboard = [[InlineKeyboardButton(section, callback_data=f"menu:{section}")] for section in SECTIONS]
        await query.edit_message_text('Выберите интересующий раздел:', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    # Expected format: t:action:row
    parts = data.split(':')
    if len(parts) != 3 or parts[0] != 't':
        await query.edit_message_text('Неподдерживаемое действие.')
        return
    action = parts[1]
    try:
        row = int(parts[2])
    except Exception:
        await query.edit_message_text('Неверный идентификатор тикета.')
        return
    # Read telegram_id from sheet
    try:
        telegram_id = None
        if tickets_client and tickets_client.sheet:
            telegram_id = await asyncio.to_thread(lambda r: tickets_client.sheet.cell(r, 4).value, row)
    except Exception:
        telegram_id = None
    if action == 'transfer':
        try:
            ok = await asyncio.to_thread(tickets_client.set_ticket_status, row, None, 'в работе')
        except Exception as e:
            logger.error(f'Error setting ticket status to in progress: {e}')
            ok = False
        if ok:
            await query.edit_message_reply_markup(None)
            await query.edit_message_text('Тикет помечен как "в работе" и направлен специалистам.')
            # notify specialists/admins
            notified = set()
            admin_ids = [s.strip() for s in os.getenv('ADMIN_TELEGRAM_ID','').split(',') if s.strip()]
            for aid in admin_ids:
                if aid and aid not in notified:
                    try:
                        await context.bot.send_message(chat_id=int(aid), text=f'Ваш вопрос переведен специалисту.')
                        notified.add(aid)
                    except Exception as e:
                        logger.debug(f'Не удалось уведомить admin {aid}: {e}')
            try:
                auth_ids = get_authorized_ids() or set()
                for aid in auth_ids:
                    if aid and str(aid) != str(telegram_id) and aid not in notified:
                        try:
                            await context.bot.send_message(chat_id=int(aid), text=f'Новый тикет для специалиста (строка {row}).')
                            notified.add(aid)
                        except Exception as e:
                            logger.debug(f'Не удалось уведомить специалиста {aid}: {e}')
            except Exception:
                pass
        else:
            await query.edit_message_text('Не удалось изменить статус (ошибка записи).')
    elif action == 'done':
        try:
            ok = await asyncio.to_thread(tickets_client.set_ticket_status, row, None, 'выполнено')
        except Exception as e:
            logger.error(f'Error setting ticket status to done: {e}')
            ok = False
        if ok:
            await query.edit_message_reply_markup(None)
            await query.edit_message_text('Тикет помечен как выполнено.')
        else:
            await query.edit_message_text('Не удалось пометить тикет как выполнено.')
    else:
        await query.edit_message_text('Неизвестное действие.')
    

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message_id = update.message.message_id
    logger.info(f'Processing message {message_id} from user {user.id}: {update.message.text[:50]}...')
    
    persistent_keyboard = create_persistent_keyboard()
    
    if not await is_user_authorized(user.id, context):
        await update.message.reply_text('Вы не авторизованы. Сначала пройдите авторизацию.')
        return
    
    text = update.message.text
    
    # Убираем обработку команды menu, так как теперь используется WebApp кнопка
    
    # Логируем входящее сообщение пользователя
    try:
        if tickets_client and tickets_client.sheet:
            telegram_id = update.effective_user.id
            code = context.user_data.get('partner_code', '')
            phone = context.user_data.get('phone', '')
            fio = f"{update.effective_user.first_name or ''} {update.effective_user.last_name or ''}".strip()
            
            await asyncio.to_thread(
                tickets_client.upsert_ticket, 
                str(telegram_id), code, phone, fio, 
                text, 'в работе', 'user', False
            )
    except Exception as e:
        logger.error(f'Не удалось записать входящее сообщение в tickets: {e}')
    
    # Проверяем настройки OpenAI
    if not openai_client.is_available():
        await update.message.reply_text('OpenAI недоступен. Обратитесь к администратору.', reply_markup=persistent_keyboard)
        return

    # Делаем вызов OpenAI с retry/backoff
    retry = 0
    max_retry = openai_client.get_max_retry()
    backoff_base = openai_client.get_backoff_base()
    
    while True:
        try:
            # Получаем или создаем thread_id
            user_data = {
                'partner_code': context.user_data.get('partner_code', ''),
                'telegram_id': str(update.effective_user.id)
            }
            
            thread_id = await openai_client.get_or_create_thread(user_data)
            if not thread_id:
                await update.message.reply_text('Ошибка создания thread. Попробуйте позже.', reply_markup=persistent_keyboard)
                return
            
            # Отправляем сообщение в OpenAI Assistant
            logger.info(f'Sending message to OpenAI Assistant thread {thread_id}: {text[:100]}...')
            assistant_msg = await openai_client.send_message(thread_id, text)
            logger.info(f'Received response from Assistant: {assistant_msg[:100] if assistant_msg else "None"}...')
            
            if not assistant_msg:
                await update.message.reply_text('Ошибка получения ответа от ассистента. Попробуйте позже.', reply_markup=persistent_keyboard)
                return
            
            # Создаем кнопки для управления тикетом
            buttons = None
            try:
                code = context.user_data.get('partner_code', '')
                row = None
                if code and tickets_client:
                    row = tickets_client.find_row_by_code(code)
                if not row and tickets_client:
                    try:
                        cell = tickets_client.sheet.find(str(update.effective_user.id), in_column=4)
                        row = cell.row if cell else None
                    except Exception:
                        row = None
                
                if row:
                    # Создаем кнопки для управления тикетом
                    menu_url = get_web_app_url('SPA_MENU')
                    buttons = [
                        [InlineKeyboardButton('Перевести специалисту', callback_data=f't:transfer:{row}'), InlineKeyboardButton('Выполнено', callback_data=f't:done:{row}')],
                        [InlineKeyboardButton('Личный кабинет', web_app=WebAppInfo(url=menu_url))]
                    ]
            except Exception as e:
                logger.warning(f'Failed to create ticket buttons: {e}')
                buttons = None
            
            # Извлекаем текст из ответа ассистента
            def extract_text(obj):
                import collections.abc
                if obj is None:
                    return ''
                if isinstance(obj, str):
                    return obj
                if isinstance(obj, bytes):
                    try:
                        return obj.decode('utf-8')
                    except Exception:
                        return ''
                if isinstance(obj, collections.abc.Mapping):
                    parts = []
                    for v in obj.values():
                        t = extract_text(v)
                        if t:
                            parts.append(t)
                    return '\n'.join(parts)
                if isinstance(obj, collections.abc.Iterable) and not isinstance(obj, (str, bytes)):
                    parts = [extract_text(el) for el in obj]
                    return '\n'.join([p for p in parts if p])
                for attr in ['text', 'content', 'value', 'message', 'output_text']:
                    if hasattr(obj, attr):
                        val = getattr(obj, attr)
                        t = extract_text(val)
                        if t:
                            return t
                s = str(obj)
                if s.startswith('<') and s.endswith('>'):
                    return ''
                if s and s != repr(obj):
                    return s
                return ''
            
            assistant_msg = extract_text(assistant_msg)
            if not assistant_msg or not isinstance(assistant_msg, str):
                assistant_msg = 'Ошибка: не удалось получить текст ответа.'
            
            # Заменяем нежелательные паттерны
            assistant_msg = assistant_msg.replace('annotations value', 'Вера')
            logger.info(f'Sending response to user. Has buttons: {buttons is not None}. Message: {assistant_msg[:100]}...')
            logger.info(f'DEBUG: About to send message via reply_text')
            
            if buttons:
                # Send message with inline action buttons; persistent keyboard remains available to the user
                logger.info(f'DEBUG: Sending with buttons')
                await update.message.reply_text(assistant_msg, reply_markup=InlineKeyboardMarkup(buttons))
            else:
                logger.info(f'DEBUG: Sending with persistent keyboard')
                await update.message.reply_text(assistant_msg, reply_markup=persistent_keyboard)
            
            logger.info(f'DEBUG: Message sent successfully')
            
            # Логируем ответ ассистента в таблицу обращений
            try:
                if tickets_client and tickets_client.sheet:
                    telegram_id = update.effective_user.id
                    code = context.user_data.get('partner_code', '')
                    phone = context.user_data.get('phone', '')
                    fio = f"{update.effective_user.first_name or ''} {update.effective_user.last_name or ''}".strip()
                    
                    await asyncio.to_thread(
                        tickets_client.upsert_ticket, 
                        str(telegram_id), code, phone, fio, 
                        assistant_msg, 'в работе', 'assistant', False
                    )
            except Exception as e:
                logger.error(f'Не удалось записать ответ ассистента в tickets: {e}')
            
            break
            
        except Exception as e:
            retry += 1
            err_str = str(e)
            logger.warning(f'OpenAI Assistant request failed (attempt {retry}): {err_str}')
            if retry > max_retry:
                logger.exception(f'OpenAI Assistant failed after {retry} attempts; last error: {err_str}')
                await update.message.reply_text('Ошибка при обращении к ассистенту. Попробуйте позже.', reply_markup=persistent_keyboard)
                return
            wait = backoff_base * (2 ** (retry-1))
            await asyncio.sleep(wait)
    
    logger.info(f'Completed processing message {message_id} from user {user.id}')

# Обработчики
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f'/start от {user.id} ({user.first_name})')
    if await is_user_authorized(user.id, context):
        # Persistent меню с кнопкой личного кабинета
        persistent_keyboard = create_persistent_keyboard()
        await update.message.reply_text(
            'Вы уже авторизованы и готовы к работе!\nНажмите кнопку "🚀 Личный кабинет" чтобы открыть личный кабинет.',
            reply_markup=persistent_keyboard
        )
        return
    auth_url = get_web_app_url('MAIN')
    keyboard = create_auth_button(auth_url)
    await update.message.reply_text(f'Привет, {user.first_name}! Нажми кнопку чтобы авторизоваться.', reply_markup=InlineKeyboardMarkup(keyboard))

def validate_payload(payload: dict) -> tuple[bool, str]:
    """Валидирует входящие данные от веб-приложения. Возвращает (валидно, сообщение об ошибке)."""
    logger.info(f'DEBUG: Validating payload: {payload}')
    
    if not isinstance(payload, dict):
        logger.warning(f'Payload is not a dict: {type(payload)}')
        return False, "Неверный формат данных"
    
    # Проверяем тип данных
    data_type = payload.get('type', '').strip()  # Очищаем от пробелов
    logger.info(f'DEBUG: Payload type detected: "{data_type}"')
    logger.info(f'DEBUG: All payload keys: {list(payload.keys())}')
    
    # Проверяем, что в payload есть section и webapp_url (для direct_webapp)
    if 'section' in payload and 'webapp_url' in payload and not data_type:
        logger.info('DEBUG: Detected direct_webapp payload without explicit type')
        data_type = 'direct_webapp'
    
    if data_type == 'menu_selection':
        logger.info('DEBUG: Processing menu_selection')
        # Проверяем данные выбора раздела
        section = payload.get('section')
        if not section or not isinstance(section, str):
            return False, "Не указан раздел меню"
        if section not in SECTIONS:
            return False, f"Неизвестный раздел: {section}"
        return True, ""
    
    elif data_type == 'subsection_selection':
        logger.info('DEBUG: Processing subsection_selection')
        # Проверяем данные выбора подраздела
        section = payload.get('section')
        subsection = payload.get('subsection')
        if not section or not isinstance(section, str):
            return False, "Не указан раздел"
        if not subsection or not isinstance(subsection, str):
            return False, "Не указан подраздел"
        if section in SUBSECTIONS and subsection not in SUBSECTIONS[section]:
            return False, f"Неизвестный подраздел: {subsection}"
        return True, ""
    
    elif data_type == 'back_to_main':
        logger.info('DEBUG: Processing back_to_main')
        # Никакой дополнительной валидации не требуется
        return True, ""
    
    elif data_type == 'direct_webapp':
        logger.info('DEBUG: Processing direct_webapp')
        # Проверяем данные для прямого открытия мини-приложения
        section = payload.get('section')
        webapp_url = payload.get('webapp_url')
        logger.info(f'DEBUG: direct_webapp section="{section}", webapp_url="{webapp_url}"')
        if not section or not isinstance(section, str):
            return False, "Не указан раздел"
        if not webapp_url or not isinstance(webapp_url, str):
            return False, "Не указан URL мини-приложения"
        logger.info('DEBUG: direct_webapp validation passed')
        return True, ""
    
    else:
        logger.info(f'DEBUG: Processing as authorization data (type="{data_type}")')
        # Проверяем данные авторизации
        code = payload.get('code')
        phone = payload.get('phone')
        
        logger.info(f'Auth validation: code={code}, phone={phone}')
        
        if not code or not isinstance(code, str):
            logger.warning(f'Invalid code: {code} (type: {type(code)})')
            return False, "Не указан код партнера"
        if not phone or not isinstance(phone, str):
            logger.warning(f'Invalid phone: {phone} (type: {type(phone)})')
            return False, "Не указан номер телефона"
        if len(code.strip()) < 3:
            logger.warning(f'Code too short: {code}')
            return False, "Код партнера слишком короткий"
        if len(phone.strip()) < 10:
            logger.warning(f'Phone too short: {phone}')
            return False, "Номер телефона слишком короткий"
        
        logger.info(f'Payload validation successful')
        return True, ""

async def web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает данные от веб-приложения. Определяет тип данных и направляет в соответствующий обработчик."""
    user = update.effective_user
    logger.info(f'Web app data received from user {user.id}')
    
    # Проверяем структуру update
    logger.info(f'Update structure: message={hasattr(update, "message")}, web_app_data={hasattr(update.message, "web_app_data") if hasattr(update, "message") else False}')
    
    if not hasattr(update, 'message') or not hasattr(update.message, 'web_app_data'):
        logger.error(f'No web_app_data in update: {update}')
        await update.message.reply_text('Ошибка: данные от Web App не получены')
        return
    
    try:
        raw_data = update.message.web_app_data.data
        logger.info(f'Raw web app data: {raw_data}')
        payload = json.loads(raw_data)
        logger.info(f'Parsed web app payload: {payload}')
    except Exception as e:
        logger.error(f'Failed to parse web app data: {e}')
        logger.error(f'Raw data was: {update.message.web_app_data.data if hasattr(update.message, "web_app_data") else "No web_app_data"}')
        await update.message.reply_text('Не удалось прочитать данные от Web App')
        return
    
    # Валидируем входящие данные
    is_valid, error_message = validate_payload(payload)
    if not is_valid:
        logger.warning(f'Invalid payload from user {user.id}: {error_message}')
        await update.message.reply_text(f'❌ Ошибка в данных: {error_message}')
        return
    
    # Определяем тип данных и направляем в соответствующий обработчик
    data_type = payload.get('type', '').strip()
    # Проверяем, что в payload есть section и webapp_url (для direct_webapp)
    if 'section' in payload and 'webapp_url' in payload and not data_type:
        data_type = 'direct_webapp'
        
    if data_type == 'menu_selection':
        logger.info(f'Routing to menu selection handler')
        await handle_menu_selection(update, context, payload)
    elif data_type == 'subsection_selection':
        logger.info(f'Routing to subsection selection handler')
        await handle_subsection_selection(update, context, payload)
    elif data_type == 'back_to_main':
        logger.info(f'Routing back to main menu')
        await handle_back_to_main(update, context)
    elif data_type == 'direct_webapp':
        logger.info(f'Routing to direct webapp handler')
        await handle_direct_webapp(update, context, payload)
    else:
        logger.info(f'Routing to authorization handler')
        await handle_authorization(update, context, payload)

async def handle_menu_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, payload: dict):
    """Обрабатывает выбор раздела меню от пользователя."""
        user = update.effective_user
    section = payload.get('section')
    
        if not await is_user_authorized(user.id, context):
            await update.message.reply_text('Вы не авторизованы. Сначала пройдите авторизацию.')
            return
    
    # Создаем тикет для раздела без подпунктов
        try:
            if tickets_client and tickets_client.sheet:
                telegram_id = str(user.id)
                code = context.user_data.get('partner_code', '')
                phone = context.user_data.get('phone', '')
                fio = f"{user.first_name or ''} {user.last_name or ''}".strip()
            
            await asyncio.to_thread(
                tickets_client.upsert_ticket, 
                telegram_id, code, phone, fio, 
                f"Запрос: {section}", 'в работе', 'user', False
            )
        except Exception as e:
            logger.error(f'Не удалось записать выбор раздела в tickets: {e}')
    
        await update.message.reply_text(f'Вы выбрали раздел: {section}. Мы получили вашу заявку и скоро свяжемся.')
    
    # Уведомляем администраторов
        try:
            admin_ids = [s.strip() for s in os.getenv('ADMIN_TELEGRAM_ID','').split(',') if s.strip()]
            for aid in admin_ids:
                try:
                    await context.bot.send_message(chat_id=int(aid), text=f'Пользователь {user.id} выбрал раздел: {section}')
                except Exception:
                    pass
        except Exception:
            pass

async def handle_subsection_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, payload: dict):
    """Обрабатывает выбор подраздела от пользователя."""
    user = update.effective_user
    section = payload.get('section')
    subsection = payload.get('subsection')
    
    # Убираем проверку авторизации для миниаппов
    # Пользователь уже авторизован в основном меню
    
    # Создаем тикет для выбранного подраздела
    try:
        if tickets_client and tickets_client.sheet:
            telegram_id = str(user.id)
            # Получаем данные из context или оставляем пустыми
            code = context.user_data.get('partner_code', '')
            phone = context.user_data.get('phone', '')
            fio = f"{user.first_name or ''} {user.last_name or ''}".strip()
            
            ticket_text = f"{section} → {subsection}"
            
            await asyncio.to_thread(
                tickets_client.upsert_ticket, 
                telegram_id, code, phone, fio, 
                ticket_text, 'в работе', 'user', False
            )
            
            logger.info(f'Created ticket for user {user.id}: {ticket_text}')
    except Exception as e:
        logger.error(f'Не удалось создать тикет для подраздела: {e}')
    
    await update.message.reply_text(f'✅ Ваша заявка принята\n\n📝 Раздел: {section}\n🔹 Подраздел: {subsection}\n\nМы свяжемся с вами в ближайшее время.')
    
    # Уведомляем администраторов
    try:
        admin_ids = [s.strip() for s in os.getenv('ADMIN_TELEGRAM_ID','').split(',') if s.strip()]
        for aid in admin_ids:
            try:
                await context.bot.send_message(
                    chat_id=int(aid), 
                    text=f'🆕 Новая заявка от {user.first_name or user.id}\n\n📝 {section} → {subsection}\n\n👤 ID: {user.id}'
                )
            except Exception:
                pass
    except Exception:
        pass

async def handle_back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает возврат в главное меню."""
    user = update.effective_user
    
    # Убираем проверку авторизации для навигации
    # Пользователь уже авторизован в основном меню
    
    # Открываем главное меню
    menu_url = get_web_app_url('SPA_MENU')
    keyboard = [[InlineKeyboardButton('🏠 Открыть личный кабинет', web_app=WebAppInfo(url=menu_url))]]
    await update.message.reply_text('Возвращаюсь в главное меню:', reply_markup=InlineKeyboardMarkup(keyboard))
    
    # Добавляем persistent keyboard
    persistent_keyboard = create_persistent_keyboard()
    await update.message.reply_text('Используйте кнопку "🚀 Личный кабинет" для быстрого доступа:', reply_markup=persistent_keyboard)

async def handle_direct_webapp(update: Update, context: ContextTypes.DEFAULT_TYPE, payload: dict):
    """Обрабатывает прямое открытие мини-приложения без промежуточных кнопок."""
    user = update.effective_user
    section = payload.get('section')
    webapp_url = payload.get('webapp_url')
    
    # Убираем проверку авторизации для прямого перехода в миниаппы
    # Авторизация уже была пройдена в основном меню
    
    if not section or not webapp_url:
        await update.message.reply_text('❗️ Ошибка: не указан раздел или URL мини-приложения.')
        return

    # Открываем мини-приложение напрямую
    keyboard = [[InlineKeyboardButton(f'📝 Открыть {section}', web_app=WebAppInfo(url=webapp_url))]]
    await update.message.reply_text(f'💼 Открываю раздел: {section}', reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_authorization(update: Update, context: ContextTypes.DEFAULT_TYPE, payload: dict):
    """Обрабатывает данные авторизации от пользователя."""
    user = update.effective_user
    
    # Проверяем блокировку
    is_blocked, seconds_left = auth_cache.is_user_blocked(user.id)
    if is_blocked:
        hours = seconds_left // 3600
        minutes = (seconds_left % 3600) // 60
        if hours > 24:
            days = hours // 24
            time_text = f"{days} дн{'я' if days < 5 else 'ей'}"
        elif hours > 0:
            time_text = f"{hours} час{'а' if hours < 5 else 'ов'}"
        else:
            time_text = f"{minutes} минут"
        await update.message.reply_text(f'❌ Авторизация заблокирована на {time_text}.')
        return
    
    code = payload.get('code')
    phone = payload.get('phone')
    
    if not code or not phone:
        await update.message.reply_text('❌ Необходимо указать код партнера и телефон.')
        return
    
    logger.info(f'Authorization attempt: code={code}, phone={phone[-4:] if phone else None}***')
    
    # Отправляем подтверждение
    await update.message.reply_text('Проверяю данные...')
    
    # Проверяем доступность Google Sheets
    if not sheets_client or not sheets_client.sheet:
        logger.error('Google Sheets client not available')
        await update.message.reply_text('База недоступна. Свяжитесь с админом.')
        return
    
    # Выполняем проверку авторизации
    try:
        logger.info(f'Looking up user credentials in Google Sheets...')
        row = await asyncio.to_thread(sheets_client.find_user_by_credentials, code, phone)
        logger.info(f'Credentials lookup result: row={row}')
    except Exception as e:
        logger.error(f'Error during credentials lookup: {e}')
        await update.message.reply_text('Ошибка проверки данных. Попробуйте позже.')
        return
    
    if row:
        # Успешная авторизация
        try:
            logger.info(f'Updating auth status for user {user.id} in row {row}')
            await asyncio.to_thread(sheets_client.update_user_auth_status, row, update.effective_user.id)
            
            # Обновляем данные пользователя
            context.user_data['is_authorized'] = True
            context.user_data['partner_code'] = code
            context.user_data['phone'] = phone
            context.user_data['auth_timestamp'] = time.time()
            
            auth_cache.clear_failed_attempts(user.id)
            
            logger.info(f'Authorization successful for user {user.id}')
            await update.message.reply_text('✅ Авторизация прошла успешно!')
            
            # Показываем кнопку для открытия личного кабинета
            web_app_base = get_web_app_url('SPA_MENU')
            menu_url = web_app_base
            await update.message.reply_text(
                'Откройте личный кабинет для выбора раздела, или напишите в чат',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Личный кабинет', web_app=WebAppInfo(url=menu_url))]])
            )
            
            # Добавляем постоянную reply клавиатуру с кнопкой menu
            persistent_keyboard = create_persistent_keyboard()
            await update.message.reply_text(
                'Используйте кнопку "menu" для быстрого доступа к личному кабинету',
                reply_markup=persistent_keyboard
            )
            
        except Exception as e:
            logger.error(f'Error updating auth status: {e}')
            await update.message.reply_text('Ошибка при сохранении авторизации. Попробуйте позже.')
            return
    else:
        # Неудачная попытка авторизации
        is_blocked, block_duration = auth_cache.add_failed_attempt(user.id)
        attempts_left = auth_cache.get_attempts_left(user.id)
        
        if is_blocked:
            hours = block_duration // 3600
            if hours > 24:
                days = hours // 24
                time_text = f"{days} дн{'я' if days < 5 else 'ей'}"
            else:
                time_text = f"{hours} час{'а' if hours < 5 else 'ов'}"
            await update.message.reply_text(f'❌ Превышен лимит попыток авторизации. Авторизация заблокирована на {time_text}.')
        else:
            web_app_url = get_web_app_url('MAIN')
            keyboard = create_auth_button(web_app_url)
            await update.message.reply_text(
                f'❌ Неверные данные или аккаунт неактивен.\nОсталось попыток: {attempts_left}',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

async def new_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Очищаем все данные пользователя
    context.user_data.clear()
    
    logger.info(f'/new_chat от {user.id} - кэш очищен')
    
    # Проверяем авторизацию заново
    if await is_user_authorized(user.id, context):
        persistent_keyboard = create_persistent_keyboard()
        await update.message.reply_text(
            'История диалога сброшена. Вы авторизованы и можете продолжить работу.',
            reply_markup=persistent_keyboard
        )
    else:
        await update.message.reply_text('История диалога сброшена. Для работы требуется авторизация.')
        # Показываем кнопку авторизации
        web_app_url = get_web_app_url('MAIN')
        keyboard = [[InlineKeyboardButton('Авторизоваться', web_app=WebAppInfo(url=web_app_url))]]
        await update.message.reply_text('Нажмите кнопку для авторизации:', reply_markup=InlineKeyboardMarkup(keyboard))

async def reply_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Специалист отвечает: /reply <код> <текст ответа>
    НОВАЯ ЛОГИКА:
    1. Записывает ответ в поле G (SPECIALIST_REPLY)
    2. Отправляет ответ пользователю в Telegram
    3. Очищает поле G после отправки
    4. Логирует ответ в столбец E (текст_обращений)
    """
    user = update.effective_user
    # Только авторизованные специалисты/админы
    if not await is_user_authorized(user.id, context) and not is_admin(user.id):
        await update.message.reply_text('Недостаточно прав для выполнения этой команды.')
        return
    
    args = context.args
    if len(args) < 2:
        await update.message.reply_text('Использование: /reply <код> <текст ответа>')
        return
    
    code = args[0]
    reply_text = ' '.join(args[1:])
    
    try:
        if not tickets_client or not tickets_client.sheet:
            await update.message.reply_text('Tickets sheet не доступен.')
            return
        
        # Ищем тикет по коду
        row = await asyncio.to_thread(tickets_client.find_row_by_code, code)
        if not row:
            await update.message.reply_text(f'Тикет с кодом {code} не найден.')
            return
        
        # Читаем telegram_id из строки
        telegram_id = await asyncio.to_thread(lambda r: tickets_client.sheet.cell(r, 4).value, row)
        if not telegram_id:
            await update.message.reply_text(f'Telegram ID не найден для кода {code}.')
            return
        
        # 1. Записываем ответ в поле G (SPECIALIST_REPLY)
        success = await asyncio.to_thread(tickets_client.set_specialist_reply, str(telegram_id), reply_text)
        if not success:
            await update.message.reply_text('Ошибка при записи ответа в поле специалиста.')
            return
        
        logger.info(f'Ответ специалиста записан в поле G для пользователя {telegram_id}')
        
        # 2. Отправляем ответ пользователю в Telegram
        try:
            await context.bot.send_message(
                chat_id=int(telegram_id), 
                text=f'✉️ Ответ специалиста (код {code}):\n{reply_text}'
            )
            logger.info(f'Ответ специалиста отправлен пользователю {telegram_id}')
            except Exception as e:
                logger.error(f'Не удалось отправить сообщение пользователю {telegram_id}: {e}')
            await update.message.reply_text('Ответ записан, но не удалось отправить пользователю.')
            return
        
        # 3. Логируем ответ в столбец E (текст_обращений) через upsert_ticket
        # Добавляем ответ специалиста в историю обращений
        logger.info(f'Логируем ответ специалиста в историю для пользователя {telegram_id}')
        await asyncio.to_thread(
            tickets_client.upsert_ticket, 
            str(telegram_id), code, '', '', f'[ОТВЕТ СПЕЦИАЛИСТА] {reply_text}', 'в работе', 'specialist', False
        )
        
        # 4. Очищаем поле G (SPECIALIST_REPLY) после логирования
        logger.info(f'Очищаем поле G для пользователя {telegram_id}')
        await asyncio.to_thread(tickets_client.clear_specialist_reply, str(telegram_id))
        
        await update.message.reply_text(
            f'✅ Ответ успешно отправлен!\n\n'
            f'👤 Пользователь: {telegram_id}\n'
            f'📝 Код: {code}\n'
            f'💬 Ответ: {reply_text[:100]}{"..." if len(reply_text) > 100 else ""}'
        )
        
    except Exception as e:
        logger.error(f'Ошибка в /reply: {e}')
        await update.message.reply_text('Ошибка при отправке ответа.')

async def monitor_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для проверки статуса мониторинга ответов оператора"""
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text('Недостаточно прав для этой команды.')
        return
    
    status_info = []
    status_info.append(f'🔍 Мониторинг ответов оператора:')
    status_info.append(f'📄 Таблица: {"\u2705 Подключена" if tickets_client else "\u274c Недоступна"}')
    status_info.append(f'📊 Мониторинг: Отключен')
    
    await update.message.reply_text('\n'.join(status_info))

async def test_monitor_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для ручного теста мониторинга"""
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text('Недостаточно прав для этой команды.')
        return
    
    await update.message.reply_text('🔄 Запускаю проверку ответов оператора...')
    
    try:

        await update.message.reply_text('✅ Проверка завершена (мониторинг временно отключен)')
    except Exception as e:
        logger.error(f'Ошибка в тесте мониторинга: {e}')
        await update.message.reply_text(f'❌ Ошибка: {e}')

async def send_keyboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для принудительной отправки persistent keyboard"""
    user = update.effective_user
    
    # Проверяем авторизацию
    auth_status = await is_user_authorized(user.id, context)
    logger.info(f'User {user.id} authorization check: {auth_status}')
    
    if auth_status:
        persistent_keyboard = create_persistent_keyboard()
        await update.message.reply_text(
            f'✅ Вы авторизованы!\n'
            f'👤 ID: {user.id}\n'
            f'👍 Reply клавиатура отправлена!\n'
            f'🔍 Посмотрите вниз экрана рядом с полем ввода.',
            reply_markup=persistent_keyboard
        )
        # Отправляем ещё одну клавиатуру чтобы точно появилась
        await update.message.reply_text('⚡️ Повторно отправляю клавиатуру...', reply_markup=persistent_keyboard)
    else:
        await update.message.reply_text(
            f'❌ Вы не авторизованы!\n'
            f'👤 ID: {user.id}\n'
            f'⚠️ Сначала пройдите авторизацию через /start'
        )

async def reset_keyboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для полного сброса и установки клавиатуры"""
    user = update.effective_user
    
    # Сначала убираем все клавиатуры
    from telegram import ReplyKeyboardRemove
    await update.message.reply_text('🗑️ Очищаю клавиатуру...', reply_markup=ReplyKeyboardRemove())
    
    # Проверяем авторизацию
    if await is_user_authorized(user.id, context):
        # Устанавливаем новую клавиатуру
        persistent_keyboard = create_persistent_keyboard()
        await update.message.reply_text(
            '✨ Клавиатура сброшена и установлена заново!\n'
            '🔍 Проверьте нижний левый угол экрана',
            reply_markup=persistent_keyboard
        )
    else:
        await update.message.reply_text('❌ Нужна авторизация. Напишите /start')

async def setstatus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Позволяет админу/специалисту установить статус: /setstatus <код|row> <статус>
    НОВЫЕ СТАТУСЫ: в работе, выполнено, ожидает, приостановлено, отменено, ожидает ответа пользователя
    """
    user = update.effective_user
    if not await is_user_authorized(user.id, context) and not is_admin(user.id):
        await update.message.reply_text('Недостаточно прав для изменения статуса.')
        return
    
    if len(context.args) < 2:
        await update.message.reply_text('Использование: /setstatus <код> <статус>')
        return
    
    key = context.args[0]
    status = ' '.join(context.args[1:])
    
    # Проверяем корректность статуса
    valid_statuses = ['в работе', 'выполнено']
    if status.lower() not in [s.lower() for s in valid_statuses]:
        await update.message.reply_text(
            f'❌ Некорректный статус: {status}\n\n'
            f'✅ Доступные статусы:\n'
            f'• в работе\n'
            f'• выполнено'
        )
        return
    
    try:
        # Пытаемся интерпретировать ключ как номер строки
        row = None
        if key.isdigit():
            row = int(key)
        
        # Выгружаем set_ticket_status в поток
        success = await asyncio.to_thread(tickets_client.set_ticket_status, row, (None if row else key), status)
        
        if success:
            await update.message.reply_text(
                f'✅ Статус обновлен!\n\n'
                f'🔑 Ключ: {key}\n'
                f'📊 Новый статус: {status}\n'
                f'👤 Специалист: {user.first_name or user.id}'
            )
        else:
            await update.message.reply_text('❌ Не удалось обновить статус (тикет не найден или ошибка).')
            
    except Exception as e:
        logger.error(f'Ошибка в /setstatus: {e}')
        await update.message.reply_text('❌ Ошибка при обновлении статуса.')

async def fix_telegram_id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для исправления Telegram ID в таблице"""
    user = update.effective_user
    
    if not sheets_client or not sheets_client.sheet:
        await update.message.reply_text('База недоступна.')
        return
    
    try:
        # Run worker in thread
        updated_count = await asyncio.to_thread(_fix_telegram_id_worker, user.id)
        if updated_count == 0:
            await update.message.reply_text('Не найдено авторизованных пользователей или обновлений не требовалось.')
            return
        await update.message.reply_text(
            f'🔧 Обновлено {updated_count} записей.\n'
            f'🆔 Ваш Telegram ID: {user.id}\n'
            f'✅ Проверьте авторизацию командой /check_auth'
        )
        # refresh cache in thread
        await asyncio.to_thread(refresh_authorized_cache)
    except Exception as e:
        logger.error(f'Ошибка в fix_telegram_id: {e}')
        await update.message.reply_text('Ошибка при обновлении Telegram ID.')

async def set_column_width_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для установки ширины колонок обращений (колонка E и G) и высоты строк"""
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text('Недостаточно прав для выполнения этой команды.')
        return
    
    args = context.args
    if len(args) != 2:
        await update.message.reply_text('Использование: /set_column_width <ширина_колонки_E> <высота_строк>')
        return
    
    try:
        width = int(args[0])
        height = int(args[1])
        
        if width < 50 or width > 1000:
            await update.message.reply_text('Ширина колонки должна быть от 50 до 1000 пикселей.')
            return
            
        if height < 30 or height > 300:
            await update.message.reply_text('Высота строк должна быть от 30 до 300 пикселей.')
            return
            
    except ValueError:
        await update.message.reply_text('Некорректные числа. Укажите ширину и высоту в пикселях.')
        return
    
    try:
        if not tickets_client or not tickets_client.sheet:
            await update.message.reply_text('Таблица обращений недоступна.')
            return
        
        success = await asyncio.to_thread(tickets_client.set_tickets_column_width, width, height)
        if success:
            await update.message.reply_text(
                f'✅ Установлены размеры:\n'
                f'📏 Колонка E (текст_обращений): {width}px\n'
                f'📏 Колонка G (специалист_ответ): 400px\n'
                f'📏 Высота строк: {height}px'
            )
        else:
            await update.message.reply_text('❗️ Ошибка при установке размеров')
        
    except Exception as e:
        logger.error(f'Ошибка в /set_column_width: {e}')
        await update.message.reply_text('Ошибка при установке размеров.')

async def setup_dropdown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для настройки выпадающего списка статусов в столбце F"""
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text('Недостаточно прав для выполнения этой команды.')
        return
    
    try:
        if not tickets_client or not tickets_client.sheet:
            await update.message.reply_text('Tickets sheet не доступен.')
            return
        
        # Выгружаем setup_status_dropdown в поток
        success = await asyncio.to_thread(tickets_client.setup_status_dropdown)
        
        if success:
            await update.message.reply_text(
                f'✅ Выпадающий список статусов настроен!\n\n'
                f'📋 Доступные статусы:\n'
                f'• в работе\n'
                f'• выполнено\n\n'
                f'📍 Применено к столбцу F (статус)'
            )
        else:
            await update.message.reply_text('❌ Не удалось настроить выпадающий список.')
            
    except Exception as e:
        logger.error(f'Ошибка в /setup_dropdown: {e}')
        await update.message.reply_text('❌ Ошибка при настройке выпадающего списка.')

async def check_auth_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для проверки авторизации пользователя"""
    user = update.effective_user
    
    # Проверяем авторизацию
    is_auth = await is_user_authorized(user.id, context)
    
    authorized_ids = get_authorized_ids()
    
    # Добавляем отладочную информацию о Google Sheets
    sheets_info = "❌ Недоступно"
    if sheets_client and sheets_client.sheet:
        try:
            def _read_sample():
                auth_statuses = sheets_client.sheet.col_values(4)[:10]
                telegram_ids = sheets_client.sheet.col_values(5)[:10]
                return auth_statuses, telegram_ids
            auth_statuses, telegram_ids = await asyncio.to_thread(_read_sample)
            sheets_info = f"✅ Подключено\nСтатусы (D): {auth_statuses}\nTelegram ID (E): {telegram_ids}"
        except Exception as e:
            sheets_info = f"⚠️ Ошибка чтения: {e}"
    
    await update.message.reply_text(
        f'🔍 Проверка авторизации:\n'
        f'🆔 Ваш ID: {user.id}\n'
        f'✅ Авторизован: {"Да" if is_auth else "Нет"}\n'
        f'📊 Количество авторизованных: {len(authorized_ids) if authorized_ids else 0}\n'
        f'📊 Авторизованные ID: {list(authorized_ids)[:5] if authorized_ids else []}{"..." if authorized_ids and len(authorized_ids) > 5 else ""}\n'
        f'📋 Google Sheets: {sheets_info}'
    )

async def push_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для очистки кэша авторизаций и принудительного обновления"""
    user = update.effective_user
    
    # Очищаем кэш в контексте пользователя
    if 'is_authorized' in context.user_data:
        del context.user_data['is_authorized']
    if 'auth_timestamp' in context.user_data:
        del context.user_data['auth_timestamp']
    
    logger.info(f'/push от {user.id} - кэш авторизаций очищен')
    
    # Проверяем авторизацию заново
    if await is_user_authorized(user.id, context):
        persistent_keyboard = create_persistent_keyboard()
        await update.message.reply_text('Кэш очищен. Вы авторизованы.', reply_markup=persistent_keyboard)
    else:
        await update.message.reply_text('Кэш очищен. Требуется авторизация.')
        # Показываем кнопку авторизации
        web_app_url = get_web_app_url('MAIN')
        keyboard = create_auth_button(web_app_url)
        await update.message.reply_text('Нажмите кнопку для авторизации:', reply_markup=InlineKeyboardMarkup(keyboard))

async def table_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для просмотра структуры обновленной таблицы обращений"""
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text('Недостаточно прав для этой команды.')
        return
    
    try:
        if not tickets_client or not tickets_client.sheet:
            await update.message.reply_text('❌ Таблица обращений недоступна.')
            return
        
        # Получаем информацию о таблице
        all_values = await asyncio.to_thread(tickets_client.sheet.get_all_values)
        row_count = len(all_values)
        
        info_text = [
            '📊 **СТРУКТУРА ТАБЛИЦЫ ОБРАЩЕНИЙ**',
            '',
            '🔹 **Колонки:**',
            '• A - Код партнера',
            '• B - Телефон',
            '• C - ФИО',
            '• D - Telegram ID',
            '• E - Текст обращений (история)',
            '• F - Статус (ручной выбор)',
            '• G - Ответ специалиста (временное поле)',
            '• H - Время последнего обновления',
            '',
            f'📈 **Всего строк:** {row_count}',
            f'📋 **Заголовки:** {row_count > 0}',
            '',
            '🎯 **НОВАЯ ЛОГИКА:**',
            '• Новые обращения → новые строки',
            '• Старые обращения → обновление в столбце E',
            '• Поле G очищается после отправки ответа',
            '• Статусы выбираются специалистом вручную'
        ]
        
        await update.message.reply_text('\n'.join(info_text))
        
    except Exception as e:
        logger.error(f'Ошибка в /table_info: {e}')
        await update.message.reply_text('❌ Ошибка при получении информации о таблице.')

async def check_operator_replies(context: ContextTypes.DEFAULT_TYPE):
    """Проверяет ответы операторов в поле G и отправляет их пользователям"""
    if not tickets_client or not tickets_client.sheet:
        logger.warning('Tickets sheet не доступен для проверки ответов')
        return
    
    try:
        # Отладочная информация
        logger.info(f'DEBUG: tickets_client type: {type(tickets_client)}')
        logger.info(f'DEBUG: tickets_client has extract_operator_replies: {hasattr(tickets_client, "extract_operator_replies")}')
        logger.info(f'DEBUG: tickets_client methods: {[method for method in dir(tickets_client) if not method.startswith("_")]}')
        
        # Получаем все ответы операторов из поля G
        replies = await asyncio.to_thread(tickets_client.extract_operator_replies)
        if not replies:
        return
        
        for reply in replies:
            telegram_id = reply.get('telegram_id')
            reply_text = reply.get('reply_text')
            code = reply.get('code')
            
            if not all([telegram_id, reply_text, code]):
                continue
            
            try:
                # Отправляем ответ пользователю
                await context.bot.send_message(
                    chat_id=telegram_id,
                    text=f"📋 **Ответ специалиста по обращению {code}:**\n\n{reply_text}"
                )
                
                # Логируем ответ в историю обращений (столбец E)
                await asyncio.to_thread(
                    tickets_client.upsert_ticket,
                    str(telegram_id), code, '', '', f'[ОТВЕТ СПЕЦИАЛИСТА] {reply_text}', 'в работе', 'specialist', False
                )
                
                # Очищаем поле G после обработки
                await asyncio.to_thread(tickets_client.clear_specialist_reply, str(telegram_id))
                
                logger.info(f'Ответ специалиста отправлен пользователю {telegram_id} и записан в историю')
                
        except Exception as e:
                logger.error(f'Ошибка при отправке ответа пользователю {telegram_id}: {e}')
                
                    except Exception as e:
        logger.error(f'Ошибка при проверке ответов операторов: {e}')

async def update_headers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для обновления заголовков таблицы обращений в соответствии с новой структурой"""
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text('Недостаточно прав для выполнения этой команды.')
        return
    
    try:
        if not tickets_client or not tickets_client.sheet:
            await update.message.reply_text('❌ Таблица обращений недоступна.')
        return

        await update.message.reply_text('🔄 Обновляю заголовки таблицы...')
        
        # Обновляем заголовки в потоке
        success = await asyncio.to_thread(tickets_client.update_tickets_headers)
        
        if success:
            await update.message.reply_text(
                '✅ Заголовки таблицы обновлены!\n\n'
                '📊 Новая структура:\n'
                '• A - код партнера\n'
                '• B - телефон\n'
                '• C - ФИО\n'
                '• D - telegram_id\n'
                '• E - текст_обращений (история)\n'
                '• F - статус (в работе/выполнено)\n'
                '• G - специалист_ответ (временное поле)\n'
                '• H - время_обновления\n\n'
                '🔄 ЛОГИКА РАБОТЫ:\n'
                '• Специалист пишет ответ в G\n'
                '• Бот отправляет пользователю\n'
                '• Очищает поле G\n'
                '• Логирует ответ в столбец E'
            )
        else:
            await update.message.reply_text('❌ Ошибка при обновлении заголовков.')
        
            except Exception as e:
        logger.error(f'Ошибка в /update_headers: {e}')
        await update.message.reply_text('❌ Ошибка при обновлении заголовков.')

def _fix_telegram_id_worker(new_id: int) -> int:
    """Worker to run in thread: find rows with status 'авторизован' and update column 5 with new_id."""
    try:
        all_statuses = sheets_client.sheet.col_values(4)
        found_rows = []
        for i, status in enumerate(all_statuses[1:], start=2):  # skip header
            if status and str(status).strip() == 'авторизован':
                found_rows.append(i)
        updated_count = 0
        for row in found_rows:
            current_id = sheets_client.sheet.cell(row, 5).value
            if current_id != str(new_id):
                sheets_client.sheet.update_cell(row, 5, str(new_id))
                updated_count += 1
        return updated_count
                except Exception:
        return 0

# Запуск
def main():
    # Prevent multiple instances
    lock_file = 'bot.lock'
    try:
        with ProcessLock(lock_file) as lock:
        logger.info('Successfully acquired lock, starting bot...')
    
    try:
        token = os.getenv('TELEGRAM_TOKEN')
        if not token:
            logger.error('TELEGRAM_TOKEN не задан в .env')
            return
                        
                # Создаем Application с job_queue
        app = Application.builder().token(token).build()

        app.add_handler(CommandHandler('start', start))
        app.add_handler(CommandHandler('new_chat', new_chat))
        app.add_handler(CommandHandler('reply', reply_command))
        app.add_handler(CommandHandler('setstatus', setstatus_command))
        app.add_handler(CommandHandler('push', push_command))
        app.add_handler(CommandHandler('check_auth', check_auth_command))
        app.add_handler(CommandHandler('fix_telegram_id', fix_telegram_id_command))
                app.add_handler(CommandHandler('set_column_width', set_column_width_command))
                app.add_handler(CommandHandler('setup_dropdown', setup_dropdown_command))
                app.add_handler(CommandHandler('monitor_status', monitor_status_command))
                app.add_handler(CommandHandler('test_monitor', test_monitor_command))
                app.add_handler(CommandHandler('send_keyboard', send_keyboard_command))
                app.add_handler(CommandHandler('reset_keyboard', reset_keyboard_command))
                app.add_handler(CommandHandler('table_info', table_info_command))
                app.add_handler(CommandHandler('update_headers', update_headers_command))
        app.add_handler(CallbackQueryHandler(handle_callback_query))
        app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_handler(CommandHandler('menu', menu_command))
        app.add_handler(CallbackQueryHandler(handle_menu_callback, pattern=r'^menu:'))
                        
                # Запускаем мониторинг ответов оператора
                job_queue = app.job_queue
                if job_queue and tickets_client:
                    job_queue.run_repeating(
                        check_operator_replies,
                        interval=30,  # каждые 30 секунд
                        first=10      # первый запуск через 10 секунд
                    )
                    logger.info('Запущен мониторинг ответов оператора (каждые 30 сек)')
                        
        logger.info('Бот запущен...')
                        
                # Global error handler
        async def _global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
            err = getattr(context, 'error', None)
            try:
                if isinstance(err, telegram.error.Conflict):
                    logger.warning(f'GetUpdates conflict (caught in error handler): {err} — sleeping briefly and will let polling retry.')
                    await asyncio.sleep(5)
                    return
            except Exception:
                logger.exception('Error in global error handler')
            logger.exception(f'Unhandled exception in update handling: {err}')

        app.add_error_handler(_global_error_handler)

                # Run polling with retry/backoff
        retry_delay = 3
        while True:
            try:
                app.run_polling(drop_pending_updates=True)
                break
            except telegram.error.Conflict as e:
                logger.error(f'GetUpdates conflict detected (outer loop): {e}. Retrying in {retry_delay}s...')
                time.sleep(retry_delay)
                retry_delay = min(60, retry_delay * 2)
                continue
            except Exception as e:
                logger.exception(f'Unexpected error in polling loop: {e}')
                break
                                
        except Exception as e:
                logger.error(f'Error starting bot: {e}')
                return
    except Exception as e:
        logger.error(f'Error acquiring lock: {e}')
        return

if __name__ == '__main__':
    main()