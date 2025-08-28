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
import signal
import sys
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
import telegram
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from telegram import CallbackQuery
from sheets_client import GoogleSheetsClient

# Импорты новых модулей
from config import SECTIONS, get_web_app_url, get_ticket_status, SUBSECTIONS
from auth_cache import auth_cache
from openai_client import openai_client

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
        
        logger.info(f'Checking authorization for user {user_id}. Available IDs: {list(authorized_ids)[:5] if authorized_ids else []}')
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
        logger.info(f'Using cached authorized IDs: {list(cached_ids)[:5] if cached_ids else []}')
        return cached_ids
    
    # Обновляем кэш
    try:
        if not sheets_client or not sheets_client.sheet:
            logger.warning('Sheets client not available')
            return None
        ids = sheets_client.get_all_authorized_user_ids()
        logger.info(f'Retrieved {len(ids)} authorized IDs from sheets: {list(ids)[:5] if ids else []}')
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
        
        # Устанавливаем фиксированные размеры для колонки с обращений (колонка E: ширина 600px, высота строк 100px)
        if tickets_client and tickets_client.sheet:
            tickets_client.set_tickets_column_width(600, 100)
            logger.info('Установлены размеры: ширина 600px, высота 100px для колонки обращений')
    except Exception as e:
        logger.error(f'Ошибка инициализации tickets GoogleSheetsClient: {e}')
else:
    logger.info('TICKETS_SHEET_URL не задан или credentials.json отсутствует — таблица обращений отключена')

# Система мониторинга ответов операторов






async def perform_mobile_auth(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, code: str, phone: str):
    """Выполняет авторизацию пользователя по введенным данным"""
    user = query.from_user
    
    logger.info(f'🔐 Выполняем мобильную авторизацию для пользователя {user.id}: код={code}, телефон={phone[:3]}***')
    
    # Валидация телефона
    phone_digits = ''.join(filter(str.isdigit, phone))
    if len(phone_digits) != 11:
        await query.edit_message_text(
            '❌ <b>Неверный формат телефона!</b>\n\n'
            '📝 Введите 11 цифр без пробелов и символов\n\n'
            '💡 Пример: <code>89827701055</code>',
            parse_mode='HTML'
        )
        return
    
    # Отправляем подтверждение
    await query.edit_message_text('🔍 <b>Проверяю данные...</b>', parse_mode='HTML')
    
    # Проверяем доступность Google Sheets
    if not sheets_client or not sheets_client.sheet:
        logger.error('❌ Google Sheets client not available for mobile auth')
        await query.edit_message_text('❌ База недоступна. Свяжитесь с админом.')
        return
    
    try:
        # Выполняем проверку авторизации
        logger.info(f'🔍 Looking up credentials for mobile auth user {user.id}')
        row = await asyncio.to_thread(sheets_client.find_user_by_credentials, code, phone_digits)
        logger.info(f'✅ Mobile auth credentials lookup result for user {user.id}: row={row}')
        
        if row:
            # ✅ Успешная авторизация
            try:
                logger.info(f'🔄 Updating mobile auth status for user {user.id} in row {row}')
                await asyncio.to_thread(sheets_client.update_user_auth_status, row, user.id)
                
                # Обновляем данные пользователя в контексте
                context.user_data['is_authorized'] = True
                context.user_data['partner_code'] = code
                context.user_data['phone'] = phone_digits
                context.user_data['auth_timestamp'] = time.time()
                context.user_data['platform'] = {'platform': 'mobile_command'}
                
                # Очищаем данные мобильной авторизации
                context.user_data.pop('mobile_auth_state', None)
                context.user_data.pop('mobile_auth_code', None)
                context.user_data.pop('mobile_auth_phone', None)
                
                # Очищаем счетчик неудачных попыток
                auth_cache.clear_failed_attempts(user.id)
                
                # Обновляем глобальный кэш авторизованных пользователей
                await asyncio.to_thread(refresh_authorized_cache)
                
                logger.info(f'✅ Mobile authorization successful for user {user.id}')
                
                # Отправляем успешное сообщение
                await query.edit_message_text(
                    '✅ <b>Авторизация прошла успешно!</b>\n\n'
                    '🎉 Добро пожаловать в систему!',
                    parse_mode='HTML'
                )
                
                # Предлагаем открыть личный кабинет
                menu_url = get_web_app_url('SPA_MENU')
                keyboard = [[InlineKeyboardButton('🏠 Открыть личный кабинет', web_app=WebAppInfo(url=menu_url))]]
                await query.message.reply_text(
                    '💡 Откройте личный кабинет для выбора раздела:',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                
                # Добавляем постоянную клавиатуру
                persistent_keyboard = create_persistent_keyboard()
                await query.message.reply_text(
                    '💡 Совет: Используйте кнопку "🚀 Личный кабинет" для быстрого доступа',
                    reply_markup=persistent_keyboard
                )
                
            except Exception as e:
                logger.error(f'❌ Error updating mobile auth status for user {user.id}: {e}')
                await query.edit_message_text('❌ Ошибка при сохранении авторизации. Попробуйте позже.')
                return
        else:
            # ❌ Неудачная попытка авторизации
            is_blocked, block_duration = auth_cache.add_failed_attempt(user.id)
            attempts_left = auth_cache.get_attempts_left(user.id)
            
            logger.warning(f'❌ Failed mobile authorization attempt for user {user.id}. Attempts left: {attempts_left}')
            
            if is_blocked:
                hours = block_duration // 3600
                if hours > 24:
                    days = hours // 24
                    time_text = f"{days} дн{'я' if days < 5 else 'ей'}"
                else:
                    time_text = f"{hours} час{'а' if hours < 5 else 'ов'}"
                await query.edit_message_text(f'❌ Превышен лимит попыток авторизации. Доступ заблокирован на {time_text}.')
            else:
                # Предлагаем попробовать еще раз
                keyboard = [
                    [InlineKeyboardButton('🔄 Попробовать снова', callback_data='mobile_auth:code')],
                    [InlineKeyboardButton('❌ Отмена', callback_data='mobile_auth:cancel')]
                ]
                await query.edit_message_text(
                    f'❌ <b>Неверные данные или аккаунт неактивен</b>\n\n'
                    f'⚠️ Осталось попыток: {attempts_left}\n\n'
                    f'💡 Проверьте правильность ввода кода партнера и телефона из системы КОСМОС\n\n'
                    f'🔑 Введенный код: <code>{code}</code>\n'
                    f'📞 Введенный телефон: <code>{phone_digits}</code>',
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            
    except Exception as e:
        logger.error(f'❌ Error during mobile auth lookup for user {user.id}: {e}')
        await query.edit_message_text('❌ Ошибка проверки данных. Попробуйте позже.')

async def handle_mobile_auth_callback(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Обрабатывает callback'и мобильной авторизации"""
    user = query.from_user
    action = data.split(':', 1)[1]
    
    logger.info(f'📱 Мобильная авторизация callback от пользователя {user.id}: {action}')
    
    if action == 'code':
        # Запрашиваем ввод кода партнера
        await query.edit_message_text(
            '🔑 <b>Введите код партнера</b>\n\n'
            '📝 Отправьте код партнера из системы КОСМОС\n\n'
            '💡 Пример: <code>111098</code>',
            parse_mode='HTML'
        )
        # Сохраняем состояние в контексте
        context.user_data['mobile_auth_state'] = 'waiting_code'
        
    elif action == 'phone':
        # Запрашиваем ввод телефона
        await query.edit_message_text(
            '📞 <b>Введите номер телефона</b>\n\n'
            '📝 Отправьте номер телефона из системы КОСМОС\n\n'
            '💡 Пример: <code>89827701055</code>',
            parse_mode='HTML'
        )
        # Сохраняем состояние в контексте
        context.user_data['mobile_auth_state'] = 'waiting_phone'
        
    elif action == 'confirm':
        # Проверяем, есть ли все необходимые данные
        code = context.user_data.get('mobile_auth_code')
        phone = context.user_data.get('mobile_auth_phone')
        
        if not code or not phone:
            await query.edit_message_text(
                '❌ <b>Не все данные введены</b>\n\n'
                f'🔑 Код партнера: {code or "❌ не введен"}\n'
                f'📞 Телефон: {phone or "❌ не введен"}\n\n'
                '💡 Сначала введите код и телефон, затем подтвердите авторизацию',
                parse_mode='HTML'
            )
            return
        
        # Выполняем авторизацию
        await perform_mobile_auth(query, context, code, phone)
        
    elif action == 'cancel':
        # Отменяем авторизацию
        context.user_data.pop('mobile_auth_state', None)
        context.user_data.pop('mobile_auth_code', None)
        context.user_data.pop('mobile_auth_phone', None)
        
        await query.edit_message_text(
            '❌ <b>Авторизация отменена</b>\n\n'
            '💡 Для повторной авторизации используйте команду /mobile_auth',
            parse_mode='HTML'
        )

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data or ''
    
    # Обработка мобильной авторизации
    if data.startswith('mobile_auth:'):
        await handle_mobile_auth_callback(query, context, data)
        return
    
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
    

async def handle_mobile_auth_input(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    """Обрабатывает ввод данных для мобильной авторизации. Возвращает True, если сообщение обработано."""
    user = update.effective_user
    mobile_auth_state = context.user_data.get('mobile_auth_state')
    
    if not mobile_auth_state:
        return False
    
    logger.info(f'📱 Мобильная авторизация: состояние {mobile_auth_state} от пользователя {user.id}')
    
    if mobile_auth_state == 'waiting_code':
        # Ожидаем ввод кода партнера
        if text.isdigit() and len(text) >= 4:
            context.user_data['mobile_auth_code'] = text
            context.user_data['mobile_auth_state'] = 'waiting_phone'
            
            await update.message.reply_text(
                '✅ <b>Код партнера принят!</b>\n\n'
                f'🔑 Код: <code>{text}</code>\n\n'
                '📞 Теперь введите номер телефона из системы КОСМОС',
                parse_mode='HTML'
            )
            return True
        else:
            await update.message.reply_text(
                '❌ <b>Неверный формат кода!</b>\n\n'
                '📝 Код должен содержать только цифры (минимум 4 символа)\n\n'
                '💡 Пример: <code>111098</code>',
                parse_mode='HTML'
            )
            return True
    
    elif mobile_auth_state == 'waiting_phone':
        # Ожидаем ввод телефона
        phone_digits = ''.join(filter(str.isdigit, text))
        if len(phone_digits) == 11:
            context.user_data['mobile_auth_phone'] = phone_digits
            context.user_data['mobile_auth_state'] = 'ready'
            
            code = context.user_data.get('mobile_auth_code', '')
            
            # Создаем клавиатуру для подтверждения
            keyboard = [
                [InlineKeyboardButton('✅ Подтвердить авторизацию', callback_data='mobile_auth:confirm')],
                [InlineKeyboardButton('🔄 Ввести заново', callback_data='mobile_auth:code')],
                [InlineKeyboardButton('❌ Отмена', callback_data='mobile_auth:cancel')]
            ]
            
            await update.message.reply_text(
                '✅ <b>Телефон принят!</b>\n\n'
                f'🔑 Код партнера: <code>{code}</code>\n'
                f'📞 Телефон: <code>{phone_digits}</code>\n\n'
                '💡 Теперь подтвердите авторизацию',
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return True
        else:
            await update.message.reply_text(
                '❌ <b>Неверный формат телефона!</b>\n\n'
                '📝 Введите 11 цифр без пробелов и символов\n\n'
                '💡 Пример: <code>89827701055</code>',
                parse_mode='HTML'
            )
            return True
    
    return False

async def handle_text_auth(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    """Обрабатывает текстовые сообщения с данными авторизации. Возвращает True, если сообщение обработано."""
    user = update.effective_user
    
    import re
    
    # Проверяем различные форматы текстовой авторизации
    auth_patterns = [
        # "Авторизация код 111098 телефон 89827701055"
        r'авторизация\s+код\s+(\d+)\s+телефон\s+(\d+)',
        # "Код 111098 телефон 89827701055"
        r'код\s+(\d+)\s+телефон\s+(\d+)',
        # "111098 89827701055"
        r'^(\d+)\s+(\d{11})$',
        # "Код: 111098, Телефон: 89827701055"
        r'код:\s*(\d+).*?телефон:\s*(\d+)'
    ]
    
    for pattern in auth_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            code = match.group(1)
            phone = match.group(2)
            
            logger.info(f'🔐 Текстовая авторизация от пользователя {user.id}: код={code}, телефон={phone[:3]}***')
            
            # Валидация телефона
            phone_digits = ''.join(filter(str.isdigit, phone))
            if len(phone_digits) != 11:
                await update.message.reply_text('❌ Неверный формат телефона! Введите 11 цифр.')
                return True
            
            # Отправляем подтверждение
            await update.message.reply_text('🔍 Проверяю данные...')
            
            # Проверяем доступность Google Sheets
            if not sheets_client or not sheets_client.sheet:
                logger.error('❌ Google Sheets client not available for text auth')
                await update.message.reply_text('❌ База недоступна. Свяжитесь с админом.')
                return True
            
            try:
                # Выполняем проверку авторизации
                logger.info(f'🔍 Looking up credentials for text auth user {user.id}')
                row = await asyncio.to_thread(sheets_client.find_user_by_credentials, code, phone_digits)
                logger.info(f'✅ Text auth credentials lookup result for user {user.id}: row={row}')
                
                if row:
                    # ✅ Успешная авторизация
                    try:
                        logger.info(f'🔄 Updating text auth status for user {user.id} in row {row}')
                        await asyncio.to_thread(sheets_client.update_user_auth_status, row, user.id)
                        
                        # Обновляем данные пользователя в контексте
                        context.user_data['is_authorized'] = True
                        context.user_data['partner_code'] = code
                        context.user_data['phone'] = phone_digits
                        context.user_data['auth_timestamp'] = time.time()
                        context.user_data['platform'] = {'platform': 'text_message'}
                        
                        # Очищаем счетчик неудачных попыток
                        auth_cache.clear_failed_attempts(user.id)
                        
                        # Обновляем глобальный кэш авторизованных пользователей
                        await asyncio.to_thread(refresh_authorized_cache)
                        
                        logger.info(f'✅ Text authorization successful for user {user.id}')
                        
                        # Отправляем успешное сообщение
                        await update.message.reply_text('✅ Авторизация прошла успешно!')
                        
                        # Предлагаем открыть личный кабинет
                        menu_url = get_web_app_url('SPA_MENU')
                        keyboard = [[InlineKeyboardButton('🏠 Открыть личный кабинет', web_app=WebAppInfo(url=menu_url))]]
                        await update.message.reply_text(
                            '🎉 Добро пожаловать! Откройте личный кабинет для выбора раздела:',
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                        
                        # Добавляем постоянную клавиатуру
                        persistent_keyboard = create_persistent_keyboard()
                        await update.message.reply_text(
                            '💡 Совет: Используйте кнопку "🚀 Личный кабинет" для быстрого доступа',
                            reply_markup=persistent_keyboard
                        )
                        
                        return True
                        
                    except Exception as e:
                        logger.error(f'❌ Error updating text auth status for user {user.id}: {e}')
                        await update.message.reply_text('❌ Ошибка при сохранении авторизации. Попробуйте позже.')
                        return True
                else:
                    # ❌ Неудачная попытка авторизации
                    is_blocked, block_duration = auth_cache.add_failed_attempt(user.id)
                    attempts_left = auth_cache.get_attempts_left(user.id)
                    
                    logger.warning(f'❌ Failed text authorization attempt for user {user.id}. Attempts left: {attempts_left}')
                    
                    if is_blocked:
                        hours = block_duration // 3600
                        if hours > 24:
                            days = hours // 24
                            time_text = f"{days} дн{'я' if days < 5 else 'ей'}"
                        else:
                            time_text = f"{hours} час{'а' if hours < 5 else 'ов'}"
                        await update.message.reply_text(f'❌ Превышен лимит попыток авторизации. Доступ заблокирован на {time_text}.')
                    else:
                        await update.message.reply_text(
                            f'❌ Неверные данные или аккаунт неактивен.\n\n'
                            f'⚠️ Осталось попыток: {attempts_left}\n\n'
                            f'💡 Проверьте правильность ввода кода партнера и телефона из системы КОСМОС.\n\n'
                            f'📝 Форматы:\n'
                            f'• <code>/auth код телефон</code>\n'
                            f'• <code>Авторизация код 111098 телефон 89827701055</code>\n'
                            f'• <code>111098 89827701055</code>',
                            parse_mode='HTML'
                        )
                    return True
                
            except Exception as e:
                logger.error(f'❌ Error during text auth lookup for user {user.id}: {e}')
                await update.message.reply_text('❌ Ошибка проверки данных. Попробуйте позже.')
                return True
    
    # Сообщение не является авторизацией
    return False

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message_id = update.message.message_id
    text = update.message.text.strip()
    logger.info(f'Processing message {message_id} from user {user.id}: {text[:50]}...')
    
    persistent_keyboard = create_persistent_keyboard()
    
    # Проверяем, не является ли сообщение текстовой авторизацией
    if not await is_user_authorized(user.id, context):
        # Пытаемся обработать как текстовую авторизацию
        if await handle_text_auth(update, context, text):
            return
        
        # Проверяем, не является ли сообщение вводом данных для мобильной авторизации
        if await handle_mobile_auth_input(update, context, text):
            return
        else:
            await update.message.reply_text('Вы не авторизованы. Сначала пройдите авторизацию.')
            return
    
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
            if buttons:
                # Send message with inline action buttons; persistent keyboard remains available to the user
                await update.message.reply_text(assistant_msg, reply_markup=InlineKeyboardMarkup(buttons))
            else:
                await update.message.reply_text(assistant_msg, reply_markup=persistent_keyboard)
            
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
async def mobile_auth_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Специальная команда для мобильной авторизации: /mobile_auth"""
    user = update.effective_user
    logger.info(f'📱 Команда /mobile_auth от пользователя {user.id} ({user.first_name})')
    
    # Проверяем, не авторизован ли уже пользователь
    if await is_user_authorized(user.id, context):
        await update.message.reply_text('✅ Вы уже авторизованы в системе!')
        return
    
    # Создаем интерактивную клавиатуру для мобильной авторизации
    keyboard = [
        [InlineKeyboardButton('🔑 Ввести код партнера', callback_data='mobile_auth:code')],
        [InlineKeyboardButton('📞 Ввести телефон', callback_data='mobile_auth:phone')],
        [InlineKeyboardButton('✅ Подтвердить авторизацию', callback_data='mobile_auth:confirm')],
        [InlineKeyboardButton('❌ Отмена', callback_data='mobile_auth:cancel')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        '📱 <b>Мобильная авторизация</b>\n\n'
        '🔐 Для авторизации в системе выполните следующие шаги:\n\n'
        '1️⃣ <b>Введите код партнера</b> из системы КОСМОС\n'
        '2️⃣ <b>Введите номер телефона</b> из системы КОСМОС\n'
        '3️⃣ <b>Подтвердите авторизацию</b>\n\n'
        '💡 Используйте кнопки ниже для пошаговой авторизации',
        parse_mode='HTML',
        reply_markup=reply_markup
    )

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

async def auth_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для мобильной авторизации: /auth код телефон"""
    user = update.effective_user
    text = update.message.text.strip()
    
    logger.info(f'🔐 Команда /auth от пользователя {user.id}: {text}')
    
    # Проверяем, не авторизован ли уже пользователь
    if await is_user_authorized(user.id, context):
        await update.message.reply_text('✅ Вы уже авторизованы в системе!')
        return
    
    # Парсим команду: /auth код телефон
    parts = text.split()
    if len(parts) < 3:
        await update.message.reply_text(
            '❌ Неверный формат команды!\n\n'
            '💡 Используйте: <code>/auth код телефон</code>\n\n'
            '📝 Пример: <code>/auth 111098 89827701055</code>',
            parse_mode='HTML'
        )
        return
    
    # Извлекаем код и телефон
    code = parts[1].strip()
    phone = ''.join(parts[2:])  # Объединяем все части после кода как телефон
    
    logger.info(f'🔍 Мобильная авторизация: код={code}, телефон={phone[:3]}***')
    
    # Валидация телефона
    phone_digits = ''.join(filter(str.isdigit, phone))
    if len(phone_digits) != 11:
        await update.message.reply_text(
            '❌ Неверный формат телефона!\n\n'
            '💡 Введите 11 цифр без пробелов и символов\n\n'
            '📝 Пример: <code>/auth 111098 89827701055</code>',
            parse_mode='HTML'
        )
        return
    
    # Отправляем подтверждение
    await update.message.reply_text('🔍 Проверяю данные...')
    
    # Проверяем доступность Google Sheets
    if not sheets_client or not sheets_client.sheet:
        logger.error('❌ Google Sheets client not available for mobile authorization')
        await update.message.reply_text('❌ База недоступна. Свяжитесь с админом.')
        return
    
    # Выполняем проверку авторизации
    try:
        logger.info(f'🔍 Looking up credentials in Google Sheets for mobile user {user.id}')
        row = await asyncio.to_thread(sheets_client.find_user_by_credentials, code, phone_digits)
        logger.info(f'✅ Mobile credentials lookup result for user {user.id}: row={row}')
        
        if row:
            logger.info(f'🎯 Mobile user found in row {row}, checking current status...')
            # Получаем текущий статус пользователя
            current_status = await asyncio.to_thread(lambda: sheets_client.sheet.cell(row, 4).value)
            current_telegram_id = await asyncio.to_thread(lambda: sheets_client.sheet.cell(row, 5).value)
            logger.info(f'📊 Mobile current status: "{current_status}", Telegram ID: "{current_telegram_id}"')
            
            # Проверяем, не авторизован ли уже пользователь
            if str(current_status).strip() == "авторизован" and str(current_telegram_id).strip():
                logger.info(f'✅ Mobile user {user.id} already authorized in system')
                await update.message.reply_text('✅ Вы уже авторизованы в системе!')
                return
        else:
            logger.warning(f'❌ Mobile user not found with code={code}, phone={phone_digits[:3]}***')
        
    except Exception as e:
        logger.error(f'❌ Error during mobile credentials lookup for user {user.id}: {e}')
        await update.message.reply_text('❌ Ошибка проверки данных. Попробуйте позже.')
        return
    
    if row:
        # ✅ Успешная авторизация
        try:
            logger.info(f'🔄 Updating mobile auth status for user {user.id} in row {row}')
            await asyncio.to_thread(sheets_client.update_user_auth_status, row, user.id)
            
            # Обновляем данные пользователя в контексте
            context.user_data['is_authorized'] = True
            context.user_data['partner_code'] = code
            context.user_data['phone'] = phone_digits
            context.user_data['auth_timestamp'] = time.time()
            context.user_data['platform'] = {'platform': 'mobile_command'}
            
            # Очищаем счетчик неудачных попыток
            auth_cache.clear_failed_attempts(user.id)
            
            # Обновляем глобальный кэш авторизованных пользователей
            await asyncio.to_thread(refresh_authorized_cache)
            
            logger.info(f'✅ Mobile authorization successful for user {user.id}')
            
            # Отправляем успешное сообщение
            await update.message.reply_text('✅ Авторизация прошла успешно!')
            
            # Предлагаем открыть личный кабинет
            menu_url = get_web_app_url('SPA_MENU')
            keyboard = [[InlineKeyboardButton('🏠 Открыть личный кабинет', web_app=WebAppInfo(url=menu_url))]]
            await update.message.reply_text(
                '🎉 Добро пожаловать! Откройте личный кабинет для выбора раздела:',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            # Добавляем постоянную клавиатуру
            persistent_keyboard = create_persistent_keyboard()
            await update.message.reply_text(
                '💡 Совет: Используйте кнопку "🚀 Личный кабинет" для быстрого доступа',
                reply_markup=persistent_keyboard
            )
            
        except Exception as e:
            logger.error(f'❌ Error updating mobile auth status for user {user.id}: {e}')
            await update.message.reply_text('❌ Ошибка при сохранении авторизации. Попробуйте позже.')
            return
    else:
        # ❌ Неудачная попытка авторизации
        is_blocked, block_duration = auth_cache.add_failed_attempt(user.id)
        attempts_left = auth_cache.get_attempts_left(user.id)
        
        logger.warning(f'❌ Failed mobile authorization attempt for user {user.id}. Attempts left: {attempts_left}')
        
        if is_blocked:
            hours = block_duration // 3600
            if hours > 24:
                days = hours // 24
                time_text = f"{days} дн{'я' if days < 5 else 'ей'}"
            else:
                time_text = f"{hours} час{'а' if hours < 5 else 'ов'}"
            await update.message.reply_text(f'❌ Превышен лимит попыток авторизации. Доступ заблокирован на {time_text}.')
        else:
            # Предлагаем попробовать еще раз
            await update.message.reply_text(
                f'❌ Неверные данные или аккаунт неактивен.\n\n'
                f'⚠️ Осталось попыток: {attempts_left}\n\n'
                f'💡 Проверьте правильность ввода кода партнера и телефона из системы КОСМОС.\n\n'
                f'📝 Формат: <code>/auth код телефон</code>',
                parse_mode='HTML'
            )

def validate_payload(payload: dict) -> tuple[bool, str]:
    """Валидирует входящие данные от веб-приложения. Возвращает (валидно, сообщение об ошибке)."""
    
    if not isinstance(payload, dict):
        logger.warning(f'Payload is not a dict: {type(payload)}')
        return False, "Неверный формат данных"
    
    # Проверяем тип данных
    data_type = payload.get('type', '').strip()  # Очищаем от пробелов
    
    # Проверяем, что в payload есть section и webapp_url (для direct_webapp)
    if 'section' in payload and 'webapp_url' in payload and not data_type:
        data_type = 'direct_webapp'
    
    if data_type == 'menu_selection':
        # Проверяем данные выбора раздела
        section = payload.get('section')
        if not section or not isinstance(section, str):
            return False, "Не указан раздел меню"
        if section not in SECTIONS:
            return False, f"Неизвестный раздел: {section}"
        return True, ""
    
    elif data_type == 'subsection_selection':
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
        # Никакой дополнительной валидации не требуется
        return True, ""
    
    elif data_type == 'direct_webapp':
        # Проверяем данные для прямого открытия мини-приложения
        section = payload.get('section')
        webapp_url = payload.get('webapp_url')
        if not section or not isinstance(section, str):
            return False, "Не указан раздел"
        if not webapp_url or not isinstance(webapp_url, str):
            return False, "Не указан URL мини-приложения"
        return True, ""
    
    elif data_type == 'contact_specialist':
        # Никакой дополнительной валидации не требуется для contact_specialist
        return True, ""
    
    else:
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
    elif data_type == 'contact_specialist':
        logger.info(f'Routing to contact specialist handler')
        await handle_contact_specialist(update, context, payload)
    else:
        logger.info(f'Routing to authorization handler')
        await handle_authorization(update, context, payload)

async def handle_menu_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, payload: dict):
    """Обрабатывает выбор раздела меню от пользователя."""
    user = update.effective_user
    section = payload.get('section')
    
    # Проверяем авторизацию
    is_auth = await is_user_authorized(user.id, context)
    if not is_auth:
        logger.warning(f'User {user.id} not authorized for menu selection: {section}')
        await update.message.reply_text('❌ Вы не авторизованы. Сначала пройдите авторизацию.')
        return
    
    logger.info(f'User {user.id} selected menu section: {section}')
    
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
    
    # Проверяем авторизацию
    is_auth = await is_user_authorized(user.id, context)
    if not is_auth:
        logger.warning(f'User {user.id} not authorized for subsection selection: {section} → {subsection}')
        await update.message.reply_text('❌ Вы не авторизованы. Сначала пройдите авторизацию.')
        return

    logger.info(f'User {user.id} selected subsection: {section} → {subsection}')
    
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
    """Упрощенный универсальный обработчик авторизации для всех платформ."""
    user = update.effective_user
    
    # Логируем информацию о платформе пользователя
    platform_info = payload.get('platform', {})
    logger.info(f'🔐 Authorization attempt from user {user.id}')
    logger.info(f'📱 Platform info: {platform_info}')
    logger.info(f'📋 Full payload: {payload}')
    
    # Проверяем блокировку
    is_blocked, block_duration = auth_cache.is_user_blocked(user.id)
    if is_blocked:
        hours = block_duration // 3600
        if hours > 24:
            days = hours // 24
            time_text = f"{days} дн{'я' if days < 5 else 'ей'}"
        else:
            time_text = f"{hours} час{'а' if hours < 5 else 'ов'}"
        await update.message.reply_text(f'❌ Превышен лимит попыток авторизации. Доступ заблокирован на {time_text}.')
        return
    
    # Получаем данные авторизации
    code = payload.get('code', '').strip()
    phone = payload.get('phone', '').strip()
    
    logger.info(f'📝 Auth data received - code: "{code}", phone: "{phone}"')
    
    if not code or not phone:
        logger.warning(f'❌ Missing auth data from user {user.id}: code={bool(code)}, phone={bool(phone)}')
        await update.message.reply_text('❌ Необходимо указать код партнера и телефон.')
        return
    
    # Валидация телефона
    phone_digits = ''.join(filter(str.isdigit, phone))
    if len(phone_digits) != 11:
        logger.warning(f'❌ Invalid phone format from user {user.id}: {phone_digits}')
        await update.message.reply_text('❌ Неверный формат телефона. Введите 11 цифр.')
        return
    
    logger.info(f'🔍 Processing authorization: user_id={user.id}, code={code}, phone={phone_digits[:3]}***')
    
    # Отправляем подтверждение
    await update.message.reply_text('🔍 Проверяю данные...')
    
    # Проверяем доступность Google Sheets
    if not sheets_client or not sheets_client.sheet:
        logger.error('❌ Google Sheets client not available for authorization')
        await update.message.reply_text('❌ База недоступна. Свяжитесь с админом.')
        return
    
    # Выполняем проверку авторизации
    try:
        logger.info(f'🔍 Looking up credentials in Google Sheets for user {user.id}')
        row = await asyncio.to_thread(sheets_client.find_user_by_credentials, code, phone_digits)
        logger.info(f'✅ Credentials lookup result for user {user.id}: row={row}')
        
        if row:
            logger.info(f'🎯 User found in row {row}, checking current status...')
            # Получаем текущий статус пользователя
            current_status = await asyncio.to_thread(lambda: sheets_client.sheet.cell(row, 4).value)
            current_telegram_id = await asyncio.to_thread(lambda: sheets_client.sheet.cell(row, 5).value)
            logger.info(f'📊 Current status: "{current_status}", Telegram ID: "{current_telegram_id}"')
            
            # Проверяем, не авторизован ли уже пользователь
            if str(current_status).strip() == "авторизован" and str(current_telegram_id).strip():
                logger.info(f'✅ User {user.id} already authorized in system')
                await update.message.reply_text('✅ Вы уже авторизованы в системе!')
                return
        else:
            logger.warning(f'❌ User not found with code={code}, phone={phone_digits[:3]}***')
        
    except Exception as e:
        logger.error(f'❌ Error during credentials lookup for user {user.id}: {e}')
        await update.message.reply_text('❌ Ошибка проверки данных. Попробуйте позже.')
        return
    
    if row:
        # ✅ Успешная авторизация
        try:
            logger.info(f'🔄 Updating auth status for user {user.id} in row {row}')
            await asyncio.to_thread(sheets_client.update_user_auth_status, row, user.id)
            
            # Обновляем данные пользователя в контексте
            context.user_data['is_authorized'] = True
            context.user_data['partner_code'] = code
            context.user_data['phone'] = phone_digits
            context.user_data['auth_timestamp'] = time.time()
            context.user_data['platform'] = platform_info
            
            # Очищаем счетчик неудачных попыток
            auth_cache.clear_failed_attempts(user.id)
            
            # Обновляем глобальный кэш авторизованных пользователей
            await asyncio.to_thread(refresh_authorized_cache)
            
            logger.info(f'✅ Authorization successful for user {user.id} from platform: {platform_info.get("platform", "unknown")}')
            
            # Отправляем успешное сообщение
            await update.message.reply_text('✅ Авторизация прошла успешно!')
            
            # Предлагаем открыть личный кабинет
            menu_url = get_web_app_url('SPA_MENU')
            keyboard = [[InlineKeyboardButton('🏠 Открыть личный кабинет', web_app=WebAppInfo(url=menu_url))]]
            await update.message.reply_text(
                '🎉 Добро пожаловать! Откройте личный кабинет для выбора раздела:',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            # Добавляем постоянную клавиатуру
            persistent_keyboard = create_persistent_keyboard()
            await update.message.reply_text(
                '💡 Совет: Используйте кнопку "🚀 Личный кабинет" для быстрого доступа',
                reply_markup=persistent_keyboard
            )
            
        except Exception as e:
            logger.error(f'❌ Error updating auth status for user {user.id}: {e}')
            await update.message.reply_text('❌ Ошибка при сохранении авторизации. Попробуйте позже.')
            return
    else:
        # ❌ Неудачная попытка авторизации
        is_blocked, block_duration = auth_cache.add_failed_attempt(user.id)
        attempts_left = auth_cache.get_attempts_left(user.id)
        
        logger.warning(f'❌ Failed authorization attempt for user {user.id}. Attempts left: {attempts_left}')
        
        if is_blocked:
            hours = block_duration // 3600
            if hours > 24:
                days = hours // 24
                time_text = f"{days} дн{'я' if days < 5 else 'ей'}"
            else:
                time_text = f"{hours} час{'а' if hours < 5 else 'ов'}"
            await update.message.reply_text(f'❌ Превышен лимит попыток авторизации. Доступ заблокирован на {time_text}.')
        else:
            # Предлагаем попробовать еще раз
            auth_url = get_web_app_url('MAIN')
            keyboard = [[InlineKeyboardButton('🔄 Попробовать еще раз', web_app=WebAppInfo(url=auth_url))]]
            await update.message.reply_text(
                f'❌ Неверные данные или аккаунт неактивен.\n\n'
                f'⚠️ Осталось попыток: {attempts_left}\n\n'
                f'💡 Проверьте правильность ввода кода партнера и телефона из системы КОСМОС.',
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

async def test_auth_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тестирует авторизацию с данными из таблицы"""
    if not await is_admin(update.effective_user.id):
        await update.message.reply_text('❌ У вас нет прав для выполнения этой команды.')
        return
    
    await update.message.reply_text('🔍 Тестирую авторизацию...')
    
    try:
        # Получаем данные из таблицы
        all_values = sheets_client.sheet.get_all_values()
        if len(all_values) <= 1:
            await update.message.reply_text('❌ Таблица пустая или содержит только заголовки')
            return
        
        # Показываем доступных пользователей
        users_info = []
        for i, row_data in enumerate(all_values[1:], start=2):
            if len(row_data) >= 4:
                code = row_data[0] if row_data[0] else "пусто"
                phone = row_data[2] if len(row_data) > 2 and row_data[2] else "пусто"
                status = row_data[3] if len(row_data) > 3 and row_data[3] else "пусто"
                users_info.append(f"Строка {i}: код={code}, телефон={phone}, статус={status}")
        
        await update.message.reply_text('📋 Доступные пользователи:\n' + '\n'.join(users_info))
        
        # Тестируем авторизацию с первым пользователем
        if len(all_values) > 1:
            test_code = all_values[1][0]  # Первый пользователь
            test_phone = all_values[1][2] if len(all_values[1]) > 2 else ""
            
            if test_code and test_phone:
                await update.message.reply_text(f'🧪 Тестирую авторизацию с:\nКод: {test_code}\nТелефон: {test_phone}')
                
                # Имитируем авторизацию
                row = await asyncio.to_thread(sheets_client.find_user_by_credentials, test_code, test_phone)
                if row:
                    await update.message.reply_text(f'✅ Пользователь найден в строке {row}')
                    
                    # Авторизуем пользователя
                    await asyncio.to_thread(sheets_client.update_user_auth_status, row, update.effective_user.id)
                    await update.message.reply_text(f'✅ Пользователь {test_code} авторизован!')
                else:
                    await update.message.reply_text('❌ Пользователь не найден')
            else:
                await update.message.reply_text('❌ Недостаточно данных для тестирования')
        
    except Exception as e:
        logger.error(f'Error in test_auth_command: {e}')
        await update.message.reply_text(f'❌ Ошибка: {e}')

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

async def handle_contact_specialist(update: Update, context: ContextTypes.DEFAULT_TYPE, payload: dict):
    """Обрабатывает запрос на связь со специалистом."""
    user = update.effective_user
    
    # Проверяем авторизацию
    is_auth = await is_user_authorized(user.id, context)
    if not is_auth:
        logger.warning(f'User {user.id} not authorized for contact specialist request')
        await update.message.reply_text('❌ Вы не авторизованы. Сначала пройдите авторизацию.')
        return
    
    logger.info(f'User {user.id} requested contact with specialist')
    
    # Создаем тикет для связи со специалистом
    try:
        if tickets_client and tickets_client.sheet:
            telegram_id = str(user.id)
            code = context.user_data.get('partner_code', '')
            phone = context.user_data.get('phone', '')
            fio = f"{user.first_name or ''} {user.last_name or ''}".strip()
            
            ticket_text = "Запрос на связь со специалистом"
            
            await asyncio.to_thread(
                tickets_client.upsert_ticket, 
                telegram_id, code, phone, fio, 
                ticket_text, 'в работе', 'user', False
            )
            
            logger.info(f'Created contact specialist ticket for user {user.id}')
    except Exception as e:
        logger.error(f'Не удалось создать тикет для связи со специалистом: {e}')
    
    await update.message.reply_text('✅ Ваша заявка на связь со специалистом принята!\n\nМы свяжемся с вами в ближайшее время.')
    
    # Уведомляем администраторов
    try:
        admin_ids = [s.strip() for s in os.getenv('ADMIN_TELEGRAM_ID','').split(',') if s.strip()]
        for aid in admin_ids:
            try:
                await context.bot.send_message(
                    chat_id=int(aid), 
                    text=f'🆕 Запрос на связь со специалистом от {user.first_name or user.id}\n\n👤 ID: {user.id}'
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

# Запуск
def main():
    # Улучшенная блокировка через файл с проверкой PID
    lock_file = 'bot.lock'
    
    # Проверяем существующую блокировку
    if os.path.exists(lock_file):
        try:
            with open(lock_file, 'r') as f:
                stored_pid = f.read().strip()
            
            # Проверяем, действительно ли процесс с этим PID запущен
            if stored_pid.isdigit():
                pid = int(stored_pid)
                try:
                    # Проверяем, существует ли процесс
                    os.kill(pid, 0)  # Сигнал 0 не убивает процесс, только проверяет существование
                    logger.error(f'Бот уже запущен (PID: {pid})')
                    return
                except OSError:
                    # Процесс не существует, удаляем мертвую блокировку
                    logger.warning(f'Найдена мертвая блокировка (PID: {pid} не существует), удаляю...')
                    os.remove(lock_file)
        except Exception as e:
            logger.warning(f'Ошибка чтения файла блокировки: {e}, удаляю...')
            os.remove(lock_file)
    
    # Создаем новую блокировку
    with open(lock_file, 'w') as f:
        f.write(str(os.getpid()))
    
    logger.info(f'Создана блокировка для PID: {os.getpid()}')
    
    # Регистрируем обработчики сигналов для корректного завершения
    signal.signal(signal.SIGINT, cleanup_and_exit)   # Ctrl+C
    signal.signal(signal.SIGTERM, cleanup_and_exit)  # Сигнал завершения
    logger.info('Зарегистрированы обработчики сигналов завершения')
    
    try:
        token = os.getenv('TELEGRAM_TOKEN')
        if not token:
            logger.error('TELEGRAM_TOKEN не задан в .env')
            return
                        
        # Создаем Application с job_queue
        app = Application.builder().token(token).build()

        app.add_handler(CommandHandler('start', start))
        app.add_handler(CommandHandler('auth', auth_command))
        app.add_handler(CommandHandler('mobile_auth', mobile_auth_command))
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
        app.add_handler(CommandHandler('test_auth', test_auth_command))
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
    finally:
        # Очищаем блокировку при выходе
        if os.path.exists(lock_file):
            os.remove(lock_file)

# Функция для корректного завершения
def cleanup_and_exit(signum=None, frame=None):
    """Корректно завершает бота и очищает блокировку"""
    logger.info(f'Получен сигнал завершения {signum}, завершаю бота...')
    
    # Удаляем файл блокировки
    lock_file = 'bot.lock'
    if os.path.exists(lock_file):
        try:
            os.remove(lock_file)
            logger.info('Файл блокировки удален')
        except Exception as e:
            logger.error(f'Ошибка при удалении файла блокировки: {e}')
    
    sys.exit(0)

if __name__ == '__main__':
    main()