# -*- coding: utf-8 -*- 
"""
Основной файл бота, который инициализирует все компоненты и запускает приложение.
"""

import logging
import os
import sys
import nest_asyncio
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler

# Импорты модулей проекта
from config import (
    SECTIONS, get_web_app_url, LOG_FILE, GOOGLE_CREDENTIALS_PATH, AUTH_WORKSHEET_NAME, TICKETS_WORKSHEET_NAME,
    SCALING_CONFIG, PROMOTIONS_CONFIG, PROMOTIONS_SHEET_URL
)
from sheets_client import GoogleSheetsClient
from promotions_client import PromotionsClient
from async_promotions_client import AsyncPromotionsClient
from error_handler import safe_execute
from validator import validator
from services.auth_service import AuthService
from services.promotions_service import PromotionsService
from services.ticket_service import TicketService
from auth_cache import auth_cache

nest_asyncio.apply()
load_dotenv()
if not os.getenv('TELEGRAM_TOKEN') and os.path.exists('bot.env'):
    load_dotenv('bot.env', override=True)

def setup_production_logging():
    app_logger = logging.getLogger('marketing_bot')
    app_logger.setLevel(logging.DEBUG)
    if app_logger.handlers: return app_logger
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    file_handler = logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - [%(levelname)s] - %(funcName)s:%(lineno)d - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    app_logger.addHandler(console_handler)
    app_logger.addHandler(file_handler)
    return app_logger

app_logger = setup_production_logging()
logger = logging.getLogger('marketing_bot.main')

class Bot:
    def __init__(self, token: str):
        self.token = token
        from telegram.request import HTTPXRequest
        request = HTTPXRequest(connection_pool_size=8, read_timeout=60, write_timeout=60, connect_timeout=30, pool_timeout=30)
        self.application = Application.builder().token(self.token).request(request).build()
        self.sheets_client = None
        self.tickets_client = None
        self.promotions_client = None
        self.async_promotions_client = None
        self.auth_service = None
        self.promotions_service = None
        self.ticket_service = None
        self._register_handlers()

    async def _init_clients(self):
        # Auth client and service
        sheet_url = os.getenv('SHEET_URL')
        if sheet_url and os.path.exists(GOOGLE_CREDENTIALS_PATH):
            try:
                self.sheets_client = GoogleSheetsClient(credentials_path=GOOGLE_CREDENTIALS_PATH, sheet_url=sheet_url, worksheet_name=AUTH_WORKSHEET_NAME)
                logger.info("Auth Google Sheets client initialized.")
                self.auth_service = AuthService(self.sheets_client, self.run_blocking)
                logger.info("AuthService initialized.")
            except Exception as e:
                logger.error(f"Error initializing auth components: {e}")
        else:
            logger.info("Auth components disabled.")

        # Tickets client
        tickets_sheet_url = os.getenv('TICKETS_SHEET_URL')
        if tickets_sheet_url and os.path.exists(GOOGLE_CREDENTIALS_PATH):
            try:
                self.tickets_client = GoogleSheetsClient(credentials_path=GOOGLE_CREDENTIALS_PATH, sheet_url=tickets_sheet_url, worksheet_name=TICKETS_WORKSHEET_NAME)
                logger.info("Tickets Google Sheets client initialized.")
            except Exception as e:
                logger.error(f"Error initializing tickets client: {e}")
        else:
            logger.info("Tickets system disabled.")

        # Promotions client and service
        promotions_sheet_url = PROMOTIONS_SHEET_URL
        if promotions_sheet_url and os.path.exists(GOOGLE_CREDENTIALS_PATH):
            try:
                self.promotions_client = PromotionsClient(credentials_file=GOOGLE_CREDENTIALS_PATH, sheet_url=promotions_sheet_url)
                self.async_promotions_client = AsyncPromotionsClient(credentials_file=GOOGLE_CREDENTIALS_PATH, sheet_url=promotions_sheet_url)
                if self.async_promotions_client:
                    await self.async_promotions_client.connect()
                self.promotions_service = PromotionsService(self.auth_service, self.async_promotions_client, self.sheets_client, self.run_blocking, self.application.bot)
                logger.info("PromotionsService initialized.")
            except Exception as e:
                logger.error(f"Error creating promotion components: {e}")
        else:
            logger.info("Promotions system disabled.")

        # Ticket Service
        if self.tickets_client and self.auth_service:
            self.ticket_service = TicketService(self.auth_service, self.tickets_client, self.run_blocking)
            logger.info("TicketService initialized.")

    def _register_handlers(self):
        self.application.add_handler(CommandHandler('start', self.start))
        self.application.add_handler(CommandHandler('menu', self.menu_command))
        self.application.add_handler(CommandHandler('new_chat', self.new_chat))
        self.application.add_handler(CommandHandler('force_update', self.force_update_command))
        
        # Service-based handlers
        if self.auth_service:
            self.application.add_handler(CommandHandler('auth', lambda u, c: self.auth_service.auth_command_handler(u, c)))
        if self.promotions_service:
            self.application.add_handler(CommandHandler('test_promotions', lambda u, c: self.promotions_service.test_promotions_command(u, c)))
        if self.ticket_service:
            self.application.add_handler(CommandHandler('reply', lambda u, c: self.ticket_service.reply_command_handler(u, c)))

        self.application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, self.web_app_data))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(CallbackQueryHandler(self.handle_callback_query))
        
        job_queue = self.application.job_queue
        if job_queue:
            job_queue.run_repeating(self.monitor_specialist_replies, interval=SCALING_CONFIG['MONITORING_INTERVAL'], first=10)
            job_queue.run_repeating(self.cleanup_cache, interval=SCALING_CONFIG['CACHE_CLEANUP_INTERVAL'], first=300)
            if self.promotions_service:
                job_queue.run_repeating(self.promotions_service.monitor_new_promotions, interval=PROMOTIONS_CONFIG['MONITORING_INTERVAL'], first=30)
            logger.info("Scheduled jobs registered.")

    async def run(self):
        logger.info("Starting bot...")
        await self._init_clients()
        await self.application.run_polling()

    @staticmethod
    async def run_blocking(func, *args, **kwargs):
        # ... (implementation unchanged)
        pass

    @staticmethod
    def create_persistent_keyboard():
        menu_url = get_web_app_url('SPA_MENU')
        return ReplyKeyboardMarkup([[KeyboardButton('🚀 Личный кабинет', web_app=WebAppInfo(url=menu_url))]], resize_keyboard=True, one_time_keyboard=False)

    @safe_execute
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not self.auth_service:
            await update.message.reply_text('Сервис авторизации недоступен.')
            return
        if await self.auth_service.is_user_authorized(user.id):
            await update.message.reply_text('Вы уже авторизованы!', reply_markup=self.create_persistent_keyboard())
        else:
            keyboard = self.auth_service.create_auth_keyboard(get_web_app_url('MAIN'))
            await update.message.reply_text(f'Привет, {user.first_name}! Нажми кнопку для авторизации.', reply_markup=keyboard)

    @safe_execute
    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text('Используйте клавиатуру для навигации.', reply_markup=self.create_persistent_keyboard())

    @safe_execute
    async def force_update_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # ... (logic uses auth_service)
        pass

    @safe_execute
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.auth_service or not await self.auth_service.is_user_authorized(update.effective_user.id):
            await update.message.reply_text('Вы не авторизованы.')
            return
        if self.ticket_service:
            await self.ticket_service.handle_message(update, context)
        else:
            await update.message.reply_text("Сервис сообщений временно недоступен.")

    @safe_execute
    async def web_app_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        is_valid, payload, _ = validator.validate_web_app_data(update.message.web_app_data.data)
        if not is_valid: return

        data_type = payload.get('type', '')
        if data_type == 'get_promotions' and self.promotions_service:
            await self.promotions_service.handle_get_promotions_api(update, context, payload)
        elif data_type == 'auth_request' and self.auth_service:
            await self.auth_service.handle_auth_from_webapp(update, context, payload)
        # ... other webapp handlers

    @safe_execute
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        data = query.data or ''
        if not data: return

        if data.startswith('t:') and self.ticket_service:
            await self.ticket_service.handle_callback_query(query, context)
        elif (data.startswith('view_promotion:') or data == 'refresh_promotions') and self.promotions_service:
            await self.promotions_service.handle_callback_query(query, context)
        elif data == 'show_menu':
            keyboard = [[InlineKeyboardButton(section, callback_data=f"menu:{section}") for section in SECTIONS]]
            await query.edit_message_text('Выберите раздел:', reply_markup=InlineKeyboardMarkup(keyboard))

    async def cleanup_cache(self, context: ContextTypes.DEFAULT_TYPE):
        try:
            max_cache_size = SCALING_CONFIG['MAX_CACHE_SIZE']
            if len(auth_cache.user_cache) > max_cache_size:
                # ...
                auth_cache._save_to_file()
        except Exception as e:
            logger.error(f"Ошибка очистки кэша: {e}")

    async def monitor_specialist_replies(self, context: ContextTypes.DEFAULT_TYPE):
        if not self.ticket_service: return
        await self.ticket_service.monitor_specialist_replies(context)

def main():
    # ... (unchanged)
    pass

if __name__ == '__main__':
    main()