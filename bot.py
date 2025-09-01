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
import functools
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
import telegram
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from sheets_client import GoogleSheetsClient

# Импорты новых модулей
from config import SECTIONS, get_web_app_url, get_ticket_status, SUBSECTIONS
from auth_cache import auth_cache
from openai_client import openai_client
from mcp_context_v7 import mcp_context
from error_handler import safe_execute
from performance_monitor import monitor_performance
from validator import validator

# ✅ Загрузка .env файла
load_dotenv()
if not os.getenv('TELEGRAM_TOKEN') and os.path.exists('bot.env'):
    load_dotenv('bot.env', override=True)


# Helper to run blocking IO in a thread with timeout, retries and exponential backoff
async def run_blocking(func, *args, timeout: int = 15, retries: int = 3, backoff: float = 0.5, **kwargs):
    """Run a blocking function in a separate thread with timeout, retries and exponential backoff.

    Usage: await run_blocking(some_blocking_fn, arg1, arg2, timeout=10, retries=3, backoff=0.5)
    """
    if retries is None or retries < 1:
        retries = 1

    for attempt in range(1, retries + 1):
        try:
            call = functools.partial(func, *args, **kwargs)
            return await asyncio.wait_for(asyncio.to_thread(call), timeout=timeout)
        except asyncio.TimeoutError as te:
            logger.warning(f'Blocking call timed out (attempt {attempt}/{retries}): {te}')
            if attempt == retries:
                raise
            await asyncio.sleep(backoff * (2 ** (attempt - 1)))
        except Exception as e:
            logger.warning(f'Blocking call failed (attempt {attempt}/{retries}): {e}')
            if attempt == retries:
                raise
            await asyncio.sleep(backoff * (2 ** (attempt - 1)))

@safe_execute('menu_command')
@monitor_performance('menu_command')
async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /menu - показывает persistent keyboard с кнопкой личного кабинета"""
    # Показываем persistent keyboard с кнопкой личного кабинета
    persistent_keyboard = create_persistent_keyboard()
    await update.message.reply_text(
        '💼 Используйте кнопку "🚀 Личный кабинет" для быстрого доступа к личному кабинету:',
        reply_markup=persistent_keyboard
    )

@safe_execute('handle_menu_callback')
@monitor_performance('handle_menu_callback')
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
    """Проверяет, является ли пользователь админом, на основе переменной окружения."""
    admin_ids = os.getenv('ADMIN_TELEGRAM_ID', '')
    if not admin_ids:
        return False
    admin_list = [s.strip() for s in admin_ids.split(',') if s.strip()]
    return str(user_id) in admin_list

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

@monitor_performance('is_user_authorized')
async def is_user_authorized(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Проверяет авторизацию пользователя. Использует единый кэш для оптимизации."""
    # Сначала проверяем кэш
    cached_auth = auth_cache.is_user_authorized(user_id)
    if cached_auth is not None:
        logger.info(f'Using cached authorization for user {user_id}: {cached_auth}')
        return cached_auth
    
    # Получаем актуальные данные из Google Sheets
    try:
        authorized_ids = await run_blocking(get_authorized_ids)
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
        
    # Примечание: не выполняем операции UI/resize на этапе импорта модуля
    # (могут быть блокирующими у некоторых реализаций Worksheet). Размеры
    # будут применены безопасно в `main()`.
    except Exception as e:
        logger.error(f'Ошибка инициализации tickets GoogleSheetsClient: {e}')
else:
    logger.info('TICKETS_SHEET_URL не задан или credentials.json отсутствует — таблица обращений отключена')

@safe_execute('handle_callback_query')
@monitor_performance('handle_callback_query')
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
            telegram_id = await run_blocking(lambda r=row: tickets_client.sheet.cell(r, 4).value)
    except Exception:
        telegram_id = None
    if action == 'transfer':
        try:
            ok = await run_blocking(tickets_client.set_ticket_status, row, None, 'в работе')
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
                        await context.bot.send_message(chat_id=int(aid), text='Ваш вопрос переведен специалисту.')
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
            ok = await run_blocking(tickets_client.set_ticket_status, row, None, 'выполнено')
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
    
@safe_execute('handle_message')
@monitor_performance('handle_message')
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
            
            await run_blocking(
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
            
            # Get or create a thread via OpenAI client and also register it in local MCP context
            thread_id = await openai_client.get_or_create_thread(user_data)
            if thread_id:
                try:
                    mcp_context.register_thread(thread_id, user_data['telegram_id'])
                except Exception:
                    # non-fatal: context registration shouldn't break flow
                    logger.debug('Failed to register thread in MCP context')
            if not thread_id:
                await update.message.reply_text('Ошибка создания thread. Попробуйте позже.', reply_markup=persistent_keyboard)
                return
            
            # Отправляем сообщение в OpenAI Assistant
            logger.info(f'Sending message to OpenAI Assistant thread {thread_id}: {text[:100]}...')
            # Append user message to local MCP context before sending
            try:
                if thread_id:
                    mcp_context.append_message(thread_id, 'user', text)
            except Exception:
                logger.debug('Failed to append user message to MCP context')

            assistant_msg = await openai_client.send_message(thread_id, text)

            # Append assistant response to local MCP context (best-effort)
            try:
                if thread_id and assistant_msg:
                    mcp_context.append_message(thread_id, 'assistant', str(assistant_msg))
                    # prune to keep memory bounded
                    mcp_context.prune_thread(thread_id, keep=80)
            except Exception:
                logger.debug('Failed to append assistant message to MCP context')
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
                    row = await run_blocking(tickets_client.find_row_by_code, code)
                if not row and tickets_client:
                    try:
                        cell = await run_blocking(tickets_client.sheet.find, str(update.effective_user.id), in_column=4)
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
                # Если не удалось создать кнопки на основе строки, пытаемся найти строку по Telegram ID в фоне
                logger.warning(f'Failed to create ticket buttons during initial attempt: {e}')
                try:
                    cell = await run_blocking(tickets_client.sheet.find, str(update.effective_user.id), in_column=4)
                    row = cell.row if cell else None
                except Exception:
                    row = None
                if row:
                    try:
                        menu_url = get_web_app_url('SPA_MENU')
                        buttons = [
                            [InlineKeyboardButton('Перевести специалисту', callback_data=f't:transfer:{row}'), InlineKeyboardButton('Выполнено', callback_data=f't:done:{row}')],
                            [InlineKeyboardButton('Личный кабинет', web_app=WebAppInfo(url=menu_url))]
                        ]
                    except Exception as e2:
                        logger.warning(f'Failed to create ticket buttons after background lookup: {e2}')
                        buttons = None
                else:
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
            logger.info('DEBUG: About to send message via reply_text')
            
            if buttons:
                # Send message with inline action buttons; persistent keyboard remains available to the user
                logger.info('DEBUG: Sending with buttons')
                await update.message.reply_text(assistant_msg, reply_markup=InlineKeyboardMarkup(buttons))
            else:
                logger.info('DEBUG: Sending with persistent keyboard')
                await update.message.reply_text(assistant_msg, reply_markup=persistent_keyboard)
            
            logger.info('DEBUG: Message sent successfully')
            
            # Логируем ответ ассистента в таблицу обращений
            try:
                if tickets_client and tickets_client.sheet:
                    telegram_id = update.effective_user.id
                    code = context.user_data.get('partner_code', '')
                    phone = context.user_data.get('phone', '')
                    fio = f"{update.effective_user.first_name or ''} {update.effective_user.last_name or ''}".strip()
                    
                    await run_blocking(
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
@safe_execute('start')
@monitor_performance('start')
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

@safe_execute('web_app_data')
@monitor_performance('web_app_data')
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
    
    # Парсим JSON от веб-приложения
    is_valid_json, payload, error_message = validator.validate_web_app_data(update.message.web_app_data.data)
    if not is_valid_json:
        logger.error(f'Failed to parse web app data: {error_message}')
        await update.message.reply_text('Не удалось прочитать данные от Web App')
        return
    
    # Определяем тип данных и валидируем
    data_type = payload.get('type', '').strip()
    if 'section' in payload and 'webapp_url' in payload and not data_type:
        data_type = 'direct_webapp'

    is_valid = False
    error_message = "Неизвестный тип данных от веб-приложения."

    if data_type == 'menu_selection':
        is_valid, error_message = validator.validate_menu_selection(payload)
    
    elif data_type == 'subsection_selection':
        is_valid, error_message = validator.validate_subsection_selection(payload)

    elif data_type in ('back_to_main', 'direct_webapp'):
        is_valid = True
        error_message = ""

    else: # Валидация данных авторизации
        code = payload.get('code')
        phone = payload.get('phone')
        code_valid, code_error = validator.validate_partner_code(code)
        if not code_valid:
            error_message = code_error
        else:
            phone_valid, phone_error = validator.validate_phone(phone)
            if not phone_valid:
                error_message = phone_error
            else:
                is_valid = True

    if not is_valid:
        logger.warning(f'Invalid payload from user {user.id}: {error_message}')
        await update.message.reply_text(f'❌ Ошибка в данных: {error_message}')
        return
    
    # Направляем в соответствующий обработчик
    if data_type == 'menu_selection':
        logger.info('Routing to menu selection handler')
        await handle_menu_selection(update, context, payload)
    elif data_type == 'subsection_selection':
        logger.info('Routing to subsection selection handler')
        await handle_subsection_selection(update, context, payload)
    elif data_type == 'back_to_main':
        logger.info('Routing back to main menu')
        await handle_back_to_main(update, context)
    elif data_type == 'direct_webapp':
        logger.info('Routing to direct webapp handler')
        await handle_direct_webapp(update, context, payload)
    else:
        logger.info('Routing to authorization handler')
        await handle_authorization(update, context, payload)

@safe_execute('handle_menu_selection')
@monitor_performance('handle_menu_selection')
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

            await run_blocking(
                tickets_client.upsert_ticket, 
                telegram_id, code, phone, fio, 
                f'Запрос: {section}', 'в работе', 'user', False
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

@safe_execute('handle_subsection_selection')
@monitor_performance('handle_subsection_selection')
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

            await run_blocking(
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

@safe_execute('handle_back_to_main')
@monitor_performance('handle_back_to_main')
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

@safe_execute('handle_direct_webapp')
@monitor_performance('handle_direct_webapp')
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

@safe_execute('handle_authorization')
@monitor_performance('handle_authorization')
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
        logger.info('Looking up user credentials in Google Sheets...')
        row = await run_blocking(sheets_client.find_user_by_credentials, code, phone)
        logger.info(f'Credentials lookup result: row={row}')
    except Exception as e:
        logger.error(f'Error during credentials lookup: {e}')
        await update.message.reply_text('Ошибка проверки данных. Попробуйте позже.')
        return
    
    if row:
        # Успешная авторизация
        try:
            logger.info(f'Updating auth status for user {user.id} in row {row}')
            await run_blocking(sheets_client.update_user_auth_status, row, update.effective_user.id)
            
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

@safe_execute('new_chat')
@monitor_performance('new_chat')
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

@safe_execute('reply_command')
@monitor_performance('reply_command')
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
        row = await run_blocking(tickets_client.find_row_by_code, code)
        if not row:
            await update.message.reply_text(f'Тикет с кодом {code} не найден.')
            return

        # Читаем telegram_id из строки
        telegram_id = await run_blocking(lambda r=row: tickets_client.sheet.cell(r, 4).value)
        if not telegram_id:
            await update.message.reply_text(f'Telegram ID не найден для кода {code}.')
            return

        # 1. Записываем ответ в поле G (SPECIALIST_REPLY)
        success = await run_blocking(tickets_client.set_specialist_reply, str(telegram_id), reply_text)
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
        await run_blocking(
            tickets_client.upsert_ticket, 
            str(telegram_id), code, '', '', f'[ОТВЕТ СПЕЦИАЛИСТА] {reply_text}', 'в работе', 'specialist', False
        )
        
        # 4. Очищаем поле G (SPECIALIST_REPLY) после логирования
        logger.info(f'Очищаем поле G для пользователя {telegram_id}')
        await run_blocking(tickets_client.clear_specialist_reply, str(telegram_id))

        await update.message.reply_text(
            '✅ Ответ успешно отправлен!\n\n'
            f'👤 Пользователь: {telegram_id}\n'
            f'📝 Код: {code}\n'
            f'💬 Ответ: {reply_text[:100]}{