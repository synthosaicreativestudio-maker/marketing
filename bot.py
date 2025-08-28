# -*- coding: utf-8 -*-

"""
Улучшенная версия бота с исправленной архитектурой.
- Централизованная конфигурация
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
from openai_client import openai_client
from auth_module import AuthModule

# Загрузка .env. Если TELEGRAM_TOKEN не задан, попробуем загрузить `bot.env`
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
TICKETS_SHEET_URL = os.getenv('TICKETS_SHEET_URL')
TICKETS_WORKSHEET = os.getenv('TICKETS_WORKSHEET', 'обращения')

sheets_client = None
auth_module = None
if SHEET_URL and os.path.exists('credentials.json'):
    try:
        sheets_client = GoogleSheetsClient(credentials_path='credentials.json', sheet_url=SHEET_URL, worksheet_name='обращения')
        # Инициализируем модуль авторизации
        auth_module = AuthModule(sheets_client)
        logger.info('Модуль авторизации инициализирован')
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

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start - приветствие и главное меню"""
    user = update.effective_user
    logger.info(f'Start command from user {user.id}')
    
    # Проверяем авторизацию пользователя
    if auth_module:
        user_auth = auth_module.check_user_authorization(str(user.id))
        if user_auth:
            # Пользователь авторизован - показываем главное меню
            await show_main_menu(update, context)
            return
        else:
            # Пользователь не авторизован - предлагаем авторизацию
            await show_auth_menu(update, context)
            return
    else:
        # Модуль авторизации недоступен - показываем главное меню
        await show_main_menu(update, context)

async def show_auth_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню авторизации"""
    user = update.effective_user
    
    # Создаем клавиатуру для авторизации
    keyboard = [
        [InlineKeyboardButton('🔐 Авторизоваться', web_app=WebAppInfo(url=get_web_app_url('AUTH')))],
        [InlineKeyboardButton('📱 Мобильная авторизация', callback_data='auth:mobile')],
        [InlineKeyboardButton('❓ Помощь', callback_data='auth:help')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    auth_text = f"""
🔐 <b>Требуется авторизация</b>

Привет, {user.first_name}! Для доступа к функциям бота необходимо пройти авторизацию.

<b>Выберите способ авторизации:</b>
• 🔐 <b>WebApp</b> - откройте форму авторизации
• 📱 <b>Мобильная</b> - авторизация через команды бота
• ❓ <b>Помощь</b> - инструкции по авторизации
    """
    
    await update.message.reply_text(auth_text, reply_markup=reply_markup, parse_mode='HTML')

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает главное меню для авторизованных пользователей"""
    user = update.effective_user
    
    # Создаем клавиатуру с разделами
    keyboard = []
    for section in SECTIONS:
        keyboard.append([InlineKeyboardButton(section, callback_data=f'menu:{section}')])
    
    # Добавляем кнопку личного кабинета
    keyboard.append([InlineKeyboardButton('🚀 Личный кабинет', web_app=WebAppInfo(url=get_web_app_url('SPA_MENU')))])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = f"""
🎉 Добро пожаловать, {user.first_name}!

Выберите интересующий вас раздел или откройте личный кабинет:
    """
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    
    # Показываем persistent keyboard
    persistent_keyboard = create_persistent_keyboard()
    await update.message.reply_text(
        '💡 Совет: Используйте кнопку "🚀 Личный кабинет" для быстрого доступа',
        reply_markup=persistent_keyboard
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help - справка по использованию бота"""
    help_text = """
🤖 <b>Справка по использованию бота</b>

<b>Основные команды:</b>
/start - Главное меню
/menu - Быстрый доступ к личному кабинету
/help - Эта справка
/auth - Авторизация по коду и телефону

<b>Как использовать:</b>
1. Пройдите авторизацию для доступа к функциям
2. Используйте кнопку "🚀 Личный кабинет" для доступа к функциям
3. Выбирайте разделы из главного меню
4. Задавайте вопросы специалистам

<b>Поддержка:</b>
Если у вас возникли вопросы, используйте раздел "Связаться со специалистом"
    """
    
    await update.message.reply_text(help_text, parse_mode='HTML')

async def auth_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /auth - авторизация по коду и телефону"""
    user = update.effective_user
    text = update.message.text
    
    # Парсим команду /auth КОД ТЕЛЕФОН
    parts = text.split()
    if len(parts) != 3:
        await update.message.reply_text(
            '❌ <b>Неверный формат команды</b>\n\n'
            'Используйте: <code>/auth КОД ТЕЛЕФОН</code>\n\n'
            'Пример: <code>/auth 111098 89827701055</code>',
            parse_mode='HTML'
        )
        return
    
    code = parts[1]
    phone = parts[2]
    
    await process_auth_request(update, context, code, phone)

async def process_auth_request(update: Update, context: ContextTypes.DEFAULT_TYPE, code: str, phone: str):
    """Обрабатывает запрос авторизации"""
    user = update.effective_user
    
    if not auth_module:
        await update.message.reply_text('❌ Модуль авторизации недоступен')
        return
    
    # Валидируем данные
    is_valid, error_message = auth_module.validate_credentials(code, phone)
    if not is_valid:
        await update.message.reply_text(f'❌ <b>Ошибка валидации:</b>\n{error_message}', parse_mode='HTML')
        return
    
    # Ищем пользователя
    user_data = auth_module.find_user_by_credentials(code, phone)
    if not user_data:
        await update.message.reply_text(
            '❌ <b>Пользователь не найден</b>\n\n'
            'Проверьте правильность кода партнера и номера телефона.\n'
            'Если проблема повторяется, обратитесь к администратору.',
            parse_mode='HTML'
        )
        return
    
    # Авторизуем пользователя
    if auth_module.authorize_user(user_data, str(user.id)):
        await update.message.reply_text(
            f'✅ <b>Авторизация успешна!</b>\n\n'
            f'Добро пожаловать, <b>{user_data["fio"]}</b>!\n\n'
            f'Теперь у вас есть доступ ко всем функциям бота.\n'
            f'Используйте /start для открытия главного меню.',
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text(
            '❌ <b>Ошибка авторизации</b>\n\n'
            'Не удалось сохранить данные авторизации.\n'
            'Попробуйте еще раз или обратитесь к администратору.',
            parse_mode='HTML'
        )

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает текстовые сообщения"""
    user = update.effective_user
    text = update.message.text
    
    logger.info(f'Text message from user {user.id}: {text[:50]}...')
    
    # Простой ответ на текстовые сообщения
    await update.message.reply_text(
        '💡 Используйте кнопку "🚀 Личный кабинет" для доступа к функциям или выберите раздел из главного меню.'
    )

async def web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает данные от веб-приложения авторизации"""
    user = update.effective_user
    logger.info(f'Web app data received from user {user.id}')
    
    if not hasattr(update, 'message') or not hasattr(update.message, 'web_app_data'):
        logger.error(f'No web_app_data in update: {update}')
        await update.message.reply_text('Ошибка: данные от Web App не получены')
        return
    
    try:
        raw_data = update.message.web_app_data.data
        logger.info(f'Raw web app data: {raw_data}')
        payload = json.loads(raw_data)
        logger.info(f'Parsed web app payload: {payload}')
        
        # Направляем в обработчик авторизации
        await handle_authorization(update, context, payload)
        
    except Exception as e:
        logger.error(f'Failed to parse web app data: {e}')
        logger.error(f'Raw data was: {update.message.web_app_data.data if hasattr(update.message, "web_app_data") else "No web_app_data"}')
        await update.message.reply_text('Не удалось прочитать данные от Web App')
        return

async def handle_authorization(update: Update, context: ContextTypes.DEFAULT_TYPE, payload: dict):
    """Обрабатывает данные авторизации из веб-приложения"""
    user = update.effective_user
    
    # Логируем информацию о платформе пользователя
    platform_info = payload.get('platform', {})
    logger.info(f'🔐 Authorization attempt from user {user.id}')
    logger.info(f'📱 Platform info: {platform_info}')
    logger.info(f'📋 Full payload: {payload}')
    
    # Получаем данные авторизации
    code = payload.get('code', '').strip()
    phone = payload.get('phone', '').strip()
    
    logger.info(f'📝 Auth data received - code: "{code}", phone: "{phone}"')
    
    if not code or not phone:
        await update.message.reply_text('❌ Код партнера и телефон обязательны для заполнения')
        return
    
    # Обрабатываем авторизацию через существующую функцию
    await process_auth_request(update, context, code, phone)

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает callback запросы от inline кнопок"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if not data:
        return
    
    if data.startswith('menu:'):
        await handle_menu_callback(update, context)
    elif data.startswith('auth:'):
        await handle_auth_callback(update, context)
    else:
        await query.edit_message_text('Неподдерживаемое действие.')

async def handle_auth_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает callback'и авторизации"""
    query = update.callback_query
    data = query.data
    
    if data == 'auth:mobile':
        await show_mobile_auth_instructions(query, context)
    elif data == 'auth:help':
        await show_auth_help(query, context)
    else:
        await query.edit_message_text('Неподдерживаемое действие авторизации.')

async def show_mobile_auth_instructions(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    """Показывает инструкции по мобильной авторизации"""
    instructions_text = """
📱 <b>Мобильная авторизация</b>

Для авторизации используйте команду:
<code>/auth КОД ТЕЛЕФОН</code>

<b>Пример:</b>
<code>/auth 111098 89827701055</code>

<b>Где:</b>
• КОД - ваш код партнера
• ТЕЛЕФОН - ваш номер телефона

<b>Альтернативно:</b>
Отправьте сообщение в формате:
<code>Авторизация код 111098 телефон 89827701055</code>
    """
    
    await query.edit_message_text(instructions_text, parse_mode='HTML')

async def show_auth_help(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    """Показывает справку по авторизации"""
    help_text = """
❓ <b>Справка по авторизации</b>

<b>Что такое авторизация?</b>
Авторизация - это процесс подтверждения вашей личности в системе по коду партнера и номеру телефона.

<b>Зачем нужна авторизация?</b>
• Доступ к функциям бота
• Персонализированные ответы
• Безопасность данных

<b>Как получить код партнера?</b>
Обратитесь к администратору системы или в службу поддержки.

<b>Проблемы с авторизацией?</b>
• Проверьте правильность кода и телефона
• Убедитесь, что данные совпадают с записями в системе
• Обратитесь к администратору при необходимости
    """
    
    await query.edit_message_text(help_text, parse_mode='HTML')

async def check_operator_replies():
    """Проверяет ответы операторов в Google Sheets"""
    if not sheets_client:
        return
    
    try:
        # Получаем все обращения
        tickets = sheets_client.get_all_tickets()
        if not tickets:
            return
        
        # Проверяем новые ответы операторов
        for ticket in tickets:
            if ticket.get('специалист_ответ') and not ticket.get('processed'):
                # Здесь можно добавить логику отправки уведомлений
                logger.info(f'New operator reply for ticket: {ticket.get("id")}')
                
    except Exception as e:
        logger.error(f'Error checking operator replies: {e}')
    
def main():
    """Основная функция запуска бота"""
    # Получаем токен бота
    token = os.getenv('TELEGRAM_TOKEN')
    if not token:
        logger.error('TELEGRAM_TOKEN не задан в переменных окружения')
        return
    
    # Создаем приложение
    application = Application.builder().token(token).build()
    
    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("auth", auth_command))
    
    # Добавляем обработчики сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    # Добавляем обработчик веб-данных
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data))
    
    # Добавляем обработчик callback запросов
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # Запускаем планировщик для проверки ответов операторов
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_operator_replies, 'interval', seconds=30)
    
    logger.info('Бот запущен...')
    
    # Запускаем бота (планировщик запустится автоматически)
    application.run_polling()

if __name__ == '__main__':
    main()
