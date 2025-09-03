# -*- coding: utf-8 -*- 
"""
Переписанная и улучшенная версия бота с исправленной архитектурой.
- Централизованная конфигурация
- Классовая структура для инкапсуляции логики
- Улучшенная обработка ошибок и логирование
- Рефакторинг длинных функций
- Менеджер процессов для предотвращения множественных экземпляров
"""

import logging
import os
import sys
import asyncio
import functools
import nest_asyncio
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler

# Импорты модулей проекта
from config import (
    SECTIONS, get_web_app_url, get_ticket_status, SUBSECTIONS, validate_config,
    LOG_FILE, GOOGLE_CREDENTIALS_PATH, AUTH_WORKSHEET_NAME, TICKETS_WORKSHEET_NAME,
    SCALING_CONFIG, PROMOTIONS_CONFIG, PROMOTIONS_SHEET_URL
)
from sheets_client import GoogleSheetsClient
from promotions_client import PromotionsClient
from async_promotions_client import AsyncPromotionsClient
from auth_cache import auth_cache
from openai_client import openai_client
from mcp_context_v7 import mcp_context
from error_handler import safe_execute
from performance_monitor import monitor_performance
from validator import validator
# Process management is now handled by system service manager (systemd/launchd)

# Инициализируем nest_asyncio для совместимости
nest_asyncio.apply()

# Загрузка .env файла
load_dotenv()
if not os.getenv('TELEGRAM_TOKEN') and os.path.exists('bot.env'):
    load_dotenv('bot.env', override=True)

# Настройка логирования
def setup_production_logging():
    """
    Настраивает систему логирования производственного уровня.
    """
    # Создать корневой логгер для приложения
    app_logger = logging.getLogger('marketing_bot')
    app_logger.setLevel(logging.DEBUG)
    
    # Избегаем дублирования обработчиков при повторном вызове
    if app_logger.handlers:
        return app_logger
    
    # Создать обработчик для вывода в консоль
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # Создать обработчик для записи в файл
    file_handler = logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    
    # Создать форматер
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - [%(levelname)s] - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Применить форматер к обработчикам
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    
    # Добавить обработчики к логгеру
    app_logger.addHandler(console_handler)
    app_logger.addHandler(file_handler)
    
    return app_logger

# Инициализация логирования
app_logger = setup_production_logging()
logger = logging.getLogger('marketing_bot.main')

class Bot:
    """
    Основной класс бота, инкапсулирующий всю логику.
    """
    def __init__(self, token: str):
        """
        Инициализация бота.
        """
        self.token = token
        
        # Создаем HTTP клиент с увеличенными таймаутами для медленного соединения
        from telegram.request import HTTPXRequest
        request = HTTPXRequest(
            connection_pool_size=8,
            read_timeout=60,  # Увеличиваем с 5 до 60 секунд
            write_timeout=60,  # Увеличиваем с 5 до 60 секунд
            connect_timeout=30,  # Увеличиваем с 5 до 30 секунд
            pool_timeout=30  # Увеличиваем с 1 до 30 секунд
        )
        
        self.application = Application.builder().token(self.token).request(request).build()
        self.sheets_client = None
        self.tickets_client = None
        self.promotions_client = None
        self.async_promotions_client = None
        self._init_clients()
        self._register_handlers()

    def _init_clients(self):
        """
        Инициализация клиентов для Google Sheets.
        """
        sheet_url = os.getenv('SHEET_URL')
        if sheet_url and os.path.exists(GOOGLE_CREDENTIALS_PATH):
            try:
                self.sheets_client = GoogleSheetsClient(
                    credentials_path=GOOGLE_CREDENTIALS_PATH,
                    sheet_url=sheet_url,
                    worksheet_name=AUTH_WORKSHEET_NAME
                )
                logger.info("Google Sheets client для авторизации успешно инициализирован.")
            except Exception as e:
                logger.error(f"Ошибка инициализации GoogleSheetsClient для авторизации: {e}")
        else:
            logger.info("SHEET_URL не задан или credentials.json отсутствует — Google Sheets для авторизации отключён.")

        tickets_sheet_url = os.getenv('TICKETS_SHEET_URL')
        if tickets_sheet_url and os.path.exists(GOOGLE_CREDENTIALS_PATH):
            try:
                self.tickets_client = GoogleSheetsClient(
                    credentials_path=GOOGLE_CREDENTIALS_PATH,
                    sheet_url=tickets_sheet_url,
                    worksheet_name=TICKETS_WORKSHEET_NAME
                )
                logger.info("Google Sheets client для тикетов успешно инициализирован.")
            except Exception as e:
                logger.error(f"Ошибка инициализации GoogleSheetsClient для тикетов: {e}")
        else:
            logger.info("TICKETS_SHEET_URL не задан или credentials.json отсутствует — таблица обращений отключена.")

        # Инициализация клиента акций
        promotions_sheet_url = PROMOTIONS_SHEET_URL
        if promotions_sheet_url and os.path.exists(GOOGLE_CREDENTIALS_PATH):
            try:
                # Создаем синхронный клиент для обратной совместимости
                self.promotions_client = PromotionsClient(
                    credentials_file=GOOGLE_CREDENTIALS_PATH,
                    sheet_url=promotions_sheet_url
                )
                
                # Создаем асинхронный клиент для новых операций
                self.async_promotions_client = AsyncPromotionsClient(
                    credentials_file=GOOGLE_CREDENTIALS_PATH,
                    sheet_url=promotions_sheet_url
                )
                
                logger.info("Клиенты акций созданы, подключение будет выполнено при запуске.")
            except Exception as e:
                logger.error(f"Ошибка создания клиентов акций: {e}")
                self.promotions_client = None
                self.async_promotions_client = None
        else:
            logger.info("PROMOTIONS_SHEET_URL не задан или credentials.json отсутствует — таблица акций отключена.")

    def _register_handlers(self):
        """
        Регистрация обработчиков команд и сообщений.
        """
        self.application.add_handler(CommandHandler('start', self.start))
        self.application.add_handler(CommandHandler('menu', self.menu_command))
        self.application.add_handler(CommandHandler('new_chat', self.new_chat))
        self.application.add_handler(CommandHandler('reply', self.reply_command))
        self.application.add_handler(CommandHandler('auth', self.auth_command))
        self.application.add_handler(CommandHandler('force_update', self.force_update_command))  # Новая команда
        self.application.add_handler(CommandHandler('test_promotions', self.test_promotions_command))  # Тестовая команда
        self.application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, self.web_app_data))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(CallbackQueryHandler(self.handle_callback_query))
        
        # Добавляем периодическую задачу мониторинга ответов специалистов
        job_queue = self.application.job_queue
        if job_queue:
            # Используем конфигурацию масштабирования
            monitoring_interval = SCALING_CONFIG['MONITORING_INTERVAL']
            job_queue.run_repeating(
                self.monitor_specialist_replies,
                interval=monitoring_interval,  # Конфигурируемый интервал
                first=10,     # Первая проверка через 10 секунд после запуска
                name='monitor_specialist_replies'
            )
            
            # Добавляем задачу очистки кэша
            cache_cleanup_interval = SCALING_CONFIG['CACHE_CLEANUP_INTERVAL']
            job_queue.run_repeating(
                self.cleanup_cache,
                interval=cache_cleanup_interval,
                first=300,  # Первая очистка через 5 минут
                name='cleanup_cache'
            )
            
            logger.info(f"🔄 Запущен мониторинг ответов специалистов (каждые {monitoring_interval} секунд)")
            logger.info(f"🧹 Запущена очистка кэша (каждые {cache_cleanup_interval // 60} минут)")
            
            # Добавляем мониторинг новых акций
            promotions_monitoring_interval = PROMOTIONS_CONFIG['MONITORING_INTERVAL']
            job_queue.run_repeating(
                self.monitor_new_promotions,
                interval=promotions_monitoring_interval,
                first=30,  # Первая проверка через 30 секунд
                name='monitor_new_promotions'
            )
            logger.info(f"🎉 Запущен мониторинг новых акций (каждые {promotions_monitoring_interval} секунд)")

    async def run(self):
        """
        Запуск бота.
        """
        logger.info("Бот запускается...")
        await self.application.run_polling()

    @staticmethod
    async def run_blocking(func, *args, timeout: int = 15, retries: int = 3, backoff: float = 0.5, **kwargs):
        """
        Запускает блокирующую функцию в отдельном потоке с таймаутом и ретраями.
        """
        if retries is None or retries < 1:
            retries = 1

        for attempt in range(1, retries + 1):
            try:
                call = functools.partial(func, *args, **kwargs)
                return await asyncio.wait_for(asyncio.to_thread(call), timeout=timeout)
            except asyncio.TimeoutError as te:
                logger.warning(f"Блокирующий вызов превысил таймаут (попытка {attempt}/{retries}): {te}")
                if attempt == retries:
                    raise
                await asyncio.sleep(backoff * (2 ** (attempt - 1)))
            except Exception as e:
                logger.warning(f"Блокирующий вызов не удался (попытка {attempt}/{retries}): {e}")
                if attempt == retries:
                    raise
                await asyncio.sleep(backoff * (2 ** (attempt - 1)))

    @staticmethod
    def is_admin(user_id: int) -> bool:
        """
        Проверяет, является ли пользователь админом.
        """
        admin_ids = os.getenv('ADMIN_TELEGRAM_ID', '')
        if not admin_ids:
            return False
        admin_list = [s.strip() for s in admin_ids.split(',') if s.strip()]
        return str(user_id) in admin_list

    @staticmethod
    def create_persistent_keyboard():
        """
        Создает постоянную клавиатуру с кнопкой для открытия личного кабинета.
        """
        menu_url = get_web_app_url('SPA_MENU')
        return ReplyKeyboardMarkup(
            [[KeyboardButton('🚀 Личный кабинет', web_app=WebAppInfo(url=menu_url))]],
            resize_keyboard=True,
            one_time_keyboard=False
        )

    @staticmethod
    def create_auth_keyboard(url: str):
        """
        Создает клавиатуру для авторизации с KeyboardButton для корректной работы sendData().
        """
        return ReplyKeyboardMarkup(
            [[KeyboardButton('🔐 Авторизоваться', web_app=WebAppInfo(url=url))]],
            resize_keyboard=True,
            one_time_keyboard=False
        )

    async def is_user_authorized(self, user_id: int) -> bool:
        """
        Проверяет авторизацию пользователя с использованием кэша.
        """
        cached_auth = auth_cache.is_user_authorized(user_id)
        if cached_auth is not None:
            logger.info(f"Используется кэшированный статус авторизации для пользователя {user_id}: {cached_auth}")
            return cached_auth

        try:
            authorized_ids = await self.run_blocking(self.get_authorized_ids)
            if authorized_ids is None:
                logger.warning(f"Нет доступа к таблице для пользователя {user_id}")
                return False

            is_auth = str(user_id) in authorized_ids
            auth_cache.set_user_authorized(user_id, is_auth)
            logger.info(f"Результат авторизации для пользователя {user_id}: {is_auth}")
            return is_auth
        except Exception as e:
            logger.error(f"Ошибка проверки авторизации для пользователя {user_id}: {e}")
            return False

    def get_authorized_ids(self):
        """
        Возвращает множество ID авторизованных пользователей.
        """
        cached_ids = auth_cache.get_authorized_ids()
        if cached_ids is not None:
            return cached_ids

        try:
            if not self.sheets_client or not self.sheets_client.sheet:
                return None
            ids = self.sheets_client.get_all_authorized_user_ids()
            auth_cache.set_authorized_ids(set(str(i) for i in ids if i))
            return auth_cache.get_authorized_ids()
        except Exception as e:
            logger.error(f"Не удалось получить список авторизованных ID: {e}")
            return None

    @safe_execute('start')
    @monitor_performance('start')
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Обработчик команды /start.
        """
        user = update.effective_user
        logger.info(f"/start от {user.id} ({user.first_name})")
        if await self.is_user_authorized(user.id):
            persistent_keyboard = self.create_persistent_keyboard()
            await update.message.reply_text(
                'Вы уже авторизованы и готовы к работе!\nНажмите кнопку "🚀 Личный кабинет" чтобы открыть личный кабинет.',
                reply_markup=persistent_keyboard
            )
        else:
            auth_url = get_web_app_url('MAIN')
            keyboard = self.create_auth_keyboard(auth_url)
            await update.message.reply_text(
                f'Привет, {user.first_name}! Нажми кнопку "🔐 Авторизоваться" чтобы авторизоваться.',
                reply_markup=keyboard
            )

    @safe_execute('menu_command')
    @monitor_performance('menu_command')
    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Обработчик команды /menu.
        """
        persistent_keyboard = self.create_persistent_keyboard()
        await update.message.reply_text(
            '💼 Используйте кнопку "🚀 Личный кабинет" для быстрого доступа к личному кабинету:',
            reply_markup=persistent_keyboard
        )

    @safe_execute('force_update_command')
    @monitor_performance('force_update_command')
    async def force_update_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Принудительное обновление интерфейса для решения проблем кэширования.
        """
        user = update.effective_user
        logger.info(f"/force_update от {user.id} ({user.first_name})")
        
        if await self.is_user_authorized(user.id):
            # Для авторизованных пользователей
            persistent_keyboard = self.create_persistent_keyboard()
            await update.message.reply_text(
                '✅ Интерфейс обновлен! Теперь вы видите обновленную клавиатуру.\n'
                'Нажмите кнопку "🚀 Личный кабинет" для доступа к функциям.',
                reply_markup=persistent_keyboard
            )
        else:
            # Для неавторизованных пользователей
            auth_url = get_web_app_url('MAIN')
            keyboard = self.create_auth_keyboard(auth_url)
            await update.message.reply_text(
                '✅ Интерфейс обновлен! Теперь вы видите обновленную клавиатуру.\n'
                'Нажмите кнопку "🔐 Авторизоваться" для авторизации.',
                reply_markup=keyboard
            )

    @safe_execute('auth_command')
    @monitor_performance('auth_command')
    async def auth_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Обработчик команды /auth для авторизации через чат.
        Формат: /auth <код_партнера> <телефон>
        """
        user = update.effective_user
        args = context.args
        
        logger.info(f"Команда /auth от пользователя {user.id} с аргументами: {args}")
        
        # Проверяем количество аргументов
        if len(args) != 2:
            await update.message.reply_text(
                '❌ Неверный формат команды.\n\n'
                '📝 Правильный формат:\n'
                '`/auth <код_партнера> <телефон>`\n\n'
                '📍 Пример:\n'
                '`/auth PARTNER123 89991234567`',
                parse_mode='Markdown'
            )
            return
        
        code = args[0].strip()
        phone = args[1].strip()
        
        # Валидация кода партнера
        if not code or len(code) < 3:
            await update.message.reply_text('❌ Код партнера должен содержать минимум 3 символа.')
            return
        
        # Валидация телефона
        phone_digits = ''.join(filter(str.isdigit, phone))
        if len(phone_digits) not in [10, 11]:
            await update.message.reply_text(
                '❌ Некорректный номер телефона.\n\n'
                '📱 Допустимые форматы:\n'
                '• `89991234567` (11 цифр)\n'
                '• `9991234567` (10 цифр)',
                parse_mode='Markdown'
            )
            return
        
        # Нормализуем телефон до 11 цифр
        if len(phone_digits) == 10:
            phone_digits = '8' + phone_digits
        
        # Проверяем блокировку попыток авторизации
        is_blocked, seconds_left = auth_cache.is_user_blocked(user.id)
        if is_blocked:
            time_text = self._format_block_time(seconds_left)
            await update.message.reply_text(f'❌ Авторизация заблокирована на {time_text}.')
            return
        
        await update.message.reply_text('🔍 Проверяю данные авторизации...')
        
        # Проверяем доступность Google Sheets
        if not self.sheets_client or not self.sheets_client.sheet:
            logger.error('Google Sheets client не доступен для команды /auth')
            await update.message.reply_text('❌ База данных недоступна. Обратитесь к администратору.')
            return
        
        try:
            # Ищем пользователя в таблице по коду и телефону
            row = await self.run_blocking(self.sheets_client.find_user_by_credentials, code, phone_digits)
        except Exception as e:
            logger.error(f"Ошибка при проверке данных авторизации: {e}")
            await update.message.reply_text('❌ Ошибка при проверке данных. Попробуйте позже.')
            return
        
        if row:
            # Успешная авторизация
            await self._handle_successful_authorization(update, context, row, code, phone_digits)
        else:
            # Неудачная авторизация
            await self._handle_failed_authorization(update, context)

    @safe_execute('handle_message')
    @monitor_performance('handle_message')
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Обработчик текстовых сообщений.
        """
        user = update.effective_user
        message_id = update.message.message_id
        logger.info(f"Обработка сообщения {message_id} от пользователя {user.id}: {update.message.text[:50]}...")

        if not await self.is_user_authorized(user.id):
            await update.message.reply_text('Вы не авторизованы. Сначала пройдите авторизацию.')
            return

        await self._log_incoming_message(update, context)

        if not openai_client.is_available():
            await update.message.reply_text('OpenAI недоступен. Обратитесь к администратору.', reply_markup=self.create_persistent_keyboard())
            return

        try:
            assistant_msg = await self._get_openai_response(update, context)
            if not assistant_msg:
                await update.message.reply_text('Ошибка получения ответа от ассистента. Попробуйте позже.', reply_markup=self.create_persistent_keyboard())
                return

            buttons = await self._create_ticket_buttons(update, context)
            assistant_msg = self._extract_text_from_response(assistant_msg)

            await self._send_response(update, assistant_msg, buttons)
            await self._log_assistant_response(update, context, assistant_msg)

        except Exception as e:
            logger.exception(f"Ошибка при обработке сообщения: {e}")
            await update.message.reply_text('Произошла ошибка при обработке вашего сообщения. Попробуйте позже.', reply_markup=self.create_persistent_keyboard())

    async def _log_incoming_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Логирует входящее сообщение в таблицу тикетов.
        """
        try:
            if self.tickets_client and self.tickets_client.sheet:
                user = update.effective_user
                telegram_id = str(user.id)
                code = context.user_data.get('partner_code', '')
                phone = context.user_data.get('phone', '')
                fio = f"{user.first_name or ''} {user.last_name or ''}".strip()
                text = update.message.text

                await self.run_blocking(
                    self.tickets_client.upsert_ticket,
                    telegram_id, code, phone, fio,
                    text, 'в работе', 'user', False
                )
        except Exception as e:
            logger.error(f"Не удалось записать входящее сообщение в tickets: {e}")

    async def _get_openai_response(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> str | None:
        """
        Получает ответ от OpenAI Assistant.
        """
        user = update.effective_user
        text = update.message.text
        user_data = {
            'partner_code': context.user_data.get('partner_code', ''),
            'telegram_id': str(user.id)
        }

        thread_id = await openai_client.get_or_create_thread(user_data)
        if not thread_id:
            logger.error("Не удалось создать или получить thread_id для OpenAI.")
            return None

        try:
            mcp_context.register_thread(thread_id, user_data['telegram_id'])
            mcp_context.append_message(thread_id, 'user', text)
        except Exception as e:
            logger.debug(f"Не удалось зарегистрировать или добавить сообщение в MCP контекст: {e}")

        assistant_msg = await openai_client.send_message(thread_id, text)

        try:
            if assistant_msg:
                mcp_context.append_message(thread_id, 'assistant', str(assistant_msg))
                mcp_context.prune_thread(thread_id, keep=80)
        except Exception as e:
            logger.debug(f"Не удалось добавить сообщение ассистента в MCP контекст: {e}")

        return assistant_msg

    async def _create_ticket_buttons(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> list | None:
        """
        Создает инлайн-кнопки для управления тикетом.
        """
        try:
            user = update.effective_user
            code = context.user_data.get('partner_code', '')
            row = None
            if code and self.tickets_client:
                row = await self.run_blocking(self.tickets_client.find_row_by_code, code)
            if not row and self.tickets_client:
                cell = await self.run_blocking(self.tickets_client.sheet.find, str(user.id), in_column=4)
                row = cell.row if cell else None

            if row:
                menu_url = get_web_app_url('SPA_MENU')
                return [
                    [InlineKeyboardButton('Перевести специалисту', callback_data=f't:transfer:{row}'), InlineKeyboardButton('Выполнено', callback_data=f't:done:{row}')],
                    [InlineKeyboardButton('Личный кабинет', web_app=WebAppInfo(url=menu_url))]
                ]
        except Exception as e:
            logger.warning(f"Не удалось создать кнопки для тикета: {e}")
        return None

    def _extract_text_from_response(self, response: any) -> str:
        """
        Извлекает текст из ответа ассистента.
        """
        import collections.abc
        if response is None:
            return ''
        if isinstance(response, str):
            return response
        if isinstance(response, bytes):
            try:
                return response.decode('utf-8')
            except Exception:
                return ''
        if isinstance(response, collections.abc.Mapping):
            parts = []
            for v in response.values():
                t = self._extract_text_from_response(v)
                if t:
                    parts.append(t)
            return '\n'.join(parts)
        if isinstance(response, collections.abc.Iterable) and not isinstance(response, (str, bytes)):
            parts = [self._extract_text_from_response(el) for el in response]
            return '\n'.join([p for p in parts if p])
        for attr in ['text', 'content', 'value', 'message', 'output_text']:
            if hasattr(response, attr):
                val = getattr(response, attr)
                t = self._extract_text_from_response(val)
                if t:
                    return t
        s = str(response)
        if s.startswith('<') and s.endswith('>'):
            return ''
        if s and s != repr(response):
            return s
        return ''

    async def _send_response(self, update: Update, text: str, buttons: list | None):
        """
        Отправляет ответ пользователю.
        """
        # Remove any potential annotation artifacts from OpenAI response
        if 'annotations value' in text:
            text = text.replace('annotations value', '')
        logger.info(f"Отправка ответа пользователю. Наличие кнопок: {buttons is not None}. Сообщение: {text[:100]}...")
        reply_markup = InlineKeyboardMarkup(buttons) if buttons else self.create_persistent_keyboard()
        await update.message.reply_text(text, reply_markup=reply_markup)

    async def _log_assistant_response(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """
        Логирует ответ ассистента в таблицу тикетов.
        """
        try:
            if self.tickets_client and self.tickets_client.sheet:
                user = update.effective_user
                telegram_id = str(user.id)
                code = context.user_data.get('partner_code', '')
                phone = context.user_data.get('phone', '')
                fio = f"{user.first_name or ''} {user.last_name or ''}".strip()

                await self.run_blocking(
                    self.tickets_client.upsert_ticket,
                    telegram_id, code, phone, fio,
                    text, 'в работе', 'assistant', False
                )
        except Exception as e:
            logger.error(f"Не удалось записать ответ ассистента в tickets: {e}")

    @safe_execute('web_app_data')
    @monitor_performance('web_app_data')
    async def web_app_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Обработчик данных от веб-приложения.
        """
        user = update.effective_user
        logger.info(f"📱 Получены данные от WebApp от пользователя {user.id} ({user.first_name})")

        # Проверяем наличие web_app_data
        if not hasattr(update, 'message') or not hasattr(update.message, 'web_app_data'):
            logger.error(f"❌ Нет web_app_data в обновлении: {update}")
            await update.message.reply_text('❌ Ошибка: данные от Web App не получены')
            return

        # Логируем сырые данные
        raw_data = update.message.web_app_data.data
        logger.info(f"📄 Сырые данные WebApp: {raw_data}")

        # Валидация JSON
        is_valid_json, payload, error_message = validator.validate_web_app_data(raw_data)
        if not is_valid_json:
            logger.error(f"❌ Не удалось разобрать JSON: {error_message}")
            await update.message.reply_text('❌ Не удалось прочитать данные от Web App')
            return

        logger.info(f"✅ JSON парсинг успешен: {payload}")

        # Определяем тип данных
        data_type = payload.get('type', '').strip()
        if 'section' in payload and 'webapp_url' in payload and not data_type:
            data_type = 'direct_webapp'
            
        logger.info(f"🏷️ Тип данных: '{data_type}'")

        # Находим обработчик
        handler = self._get_web_app_handler(data_type)
        if handler:
            logger.info(f"🏹 Найден обработчик: {handler.__name__}")
            await handler(update, context, payload)
        else:
            logger.info(f"🔄 Обработчик не найден, используем обработчик авторизации")
            await self._handle_authorization(update, context, payload)

    def _get_web_app_handler(self, data_type: str):
        """
        Возвращает обработчик для указанного типа данных от веб-приложения.
        """
        return {
            'menu_selection': self._handle_menu_selection,
            'subsection_selection': self._handle_subsection_selection,
            'back_to_main': self._handle_back_to_main,
            'direct_webapp': self._handle_direct_webapp,
            'auth_request': self._handle_authorization,
            'get_promotions': self._handle_get_promotions_api,
        }.get(data_type)

    async def _handle_menu_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE, payload: dict):
        """
        Обрабатывает выбор раздела меню.
        """
        user = update.effective_user
        section = payload.get('section')
        if not await self.is_user_authorized(user.id):
            await update.message.reply_text('Вы не авторизованы. Сначала пройдите авторизацию.')
            return

        try:
            if self.tickets_client and self.tickets_client.sheet:
                telegram_id = str(user.id)
                code = context.user_data.get('partner_code', '')
                phone = context.user_data.get('phone', '')
                fio = f"{user.first_name or ''} {user.last_name or ''}".strip()

                await self.run_blocking(
                    self.tickets_client.upsert_ticket,
                    telegram_id, code, phone, fio,
                    f'Запрос: {section}', 'в работе', 'user', False
                )
        except Exception as e:
            logger.error(f"Не удалось записать выбор раздела в tickets: {e}")

        await update.message.reply_text(f'Вы выбрали раздел: {section}. Мы получили вашу заявку и скоро свяжемся.')
        await self._notify_admins(context, f'Пользователь {user.id} выбрал раздел: {section}')

    async def _handle_subsection_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE, payload: dict):
        """
        Обрабатывает выбор подраздела.
        """
        user = update.effective_user
        section = payload.get('section')
        subsection = payload.get('subsection')
        
        # Отладочная информация
        logger.info(f"📋 Subsection selection from user {user.id}: section='{section}', subsection='{subsection}'")
        logger.info(f"📋 Full payload: {payload}")

        # Примечание: Акции теперь обрабатываются прямо в SPA меню, 
        # не требуют специальной обработки в боте

        try:
            if self.tickets_client and self.tickets_client.sheet:
                telegram_id = str(user.id)
                code = context.user_data.get('partner_code', '')
                phone = context.user_data.get('phone', '')
                fio = f"{user.first_name or ''} {user.last_name or ''}".strip()
                ticket_text = f"{section} → {subsection}"

                await self.run_blocking(
                    self.tickets_client.upsert_ticket,
                    telegram_id, code, phone, fio,
                    ticket_text, 'в работе', 'user', False
                )
                logger.info(f"Создан тикет для пользователя {user.id}: {ticket_text}")
        except Exception as e:
            logger.error(f"Не удалось создать тикет для подраздела: {e}")

        await update.message.reply_text(f'✅ Ваша заявка принята\n\n📝 Раздел: {section}\n🔹 Подраздел: {subsection}\n\nМы свяжемся с вами в ближайшее время.')
        await self._notify_admins(context, f'🆕 Новая заявка от {user.first_name or user.id}\n\n📝 {section} → {subsection}\n\n👤 ID: {user.id}')

    async def _handle_promotions_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Обрабатывает запрос на просмотр акций.
        """
        user = update.effective_user
        
        try:
            # Проверяем подключение к таблице акций
            if not self.promotions_client:
                await update.message.reply_text('🎉 Актуальных акций пока нет\n\nСледите за обновлениями! Мы обязательно сообщим о новых предложениях.')
                return
            
            # Подключаемся к таблице если не подключены
            if not self.promotions_client.sheet:
                connected = await self.run_blocking(self.promotions_client.connect)
                if not connected:
                    await update.message.reply_text('🎉 Актуальных акций пока нет\n\nСледите за обновлениями! Мы обязательно сообщим о новых предложениях.')
                    return
            
            # Получаем активные акции
            active_promotions = await self.run_blocking(self.promotions_client.get_active_promotions)
            
            if not active_promotions:
                await update.message.reply_text('🎉 Актуальных акций пока нет\n\nСледите за обновлениями! Мы обязательно сообщим о новых предложениях.')
                return
            
            # Формируем сообщение с актуальными акциями
            message_parts = ['🎉 Актуальные акции:']
            
            for i, promotion in enumerate(active_promotions[:5], 1):  # Показываем максимум 5 акций
                name = promotion.get('name', 'Без названия')
                description = promotion.get('description', '')
                status = promotion.get('ui_status', 'unknown')
                start_date = promotion.get('start_date')
                end_date = promotion.get('end_date')
                
                # Определяем эмодзи статуса
                status_emoji = {
                    'active': '🟢',
                    'published': '🟡', 
                    'finished': '🔴'
                }.get(status, '⚪')
                
                # Определяем текст статуса
                status_text = {
                    'active': 'Активна',
                    'published': 'Опубликована',
                    'finished': 'Завершена'
                }.get(status, 'Неизвестно')
                
                promotion_text = f'\n{i}. {status_emoji} **{name}** ({status_text})'
                
                # Добавляем описание если есть (обрезаем до 100 символов)
                if description:
                    short_desc = description[:100] + '...' if len(description) > 100 else description
                    promotion_text += f'\n   {short_desc}'
                
                # Добавляем даты если есть
                if start_date and end_date:
                    promotion_text += f'\n   📅 {start_date.strftime("%d.%m.%Y")} - {end_date.strftime("%d.%m.%Y")}'
                elif start_date:
                    promotion_text += f'\n   📅 Начало: {start_date.strftime("%d.%m.%Y")}'
                
                message_parts.append(promotion_text)
            
            # Добавляем информацию о дополнительных акциях
            if len(active_promotions) > 5:
                message_parts.append(f'\n... и еще {len(active_promotions) - 5} акций')
            
            message_parts.append('\n💡 Подробности уточняйте у специалистов отдела маркетинга')
            
            final_message = '\n'.join(message_parts)
            
            # Отправляем сообщение с акциями
            await update.message.reply_text(final_message, parse_mode='Markdown')
            
            # Логируем запрос акций как тикет
            try:
                if self.tickets_client and self.tickets_client.sheet:
                    telegram_id = str(user.id)
                    code = context.user_data.get('partner_code', '')
                    phone = context.user_data.get('phone', '')
                    fio = f"{user.first_name or ''} {user.last_name or ''}".strip()
                    ticket_text = f"Акции и мероприятия → Акции (просмотр {len(active_promotions)} акций)"

                    await self.run_blocking(
                        self.tickets_client.upsert_ticket,
                        telegram_id, code, phone, fio,
                        ticket_text, 'выполнено', 'user', False
                    )
            except Exception as e:
                logger.error(f"Не удалось залогировать просмотр акций: {e}")
                
        except Exception as e:
            logger.error(f"Ошибка при обработке запроса акций: {e}")
            await update.message.reply_text('🎉 Актуальных акций пока нет\n\nСледите за обновлениями! Мы обязательно сообщим о новых предложениях.')

    async def _handle_promotions_webapp_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Обрабатывает запрос на открытие страницы акций в мини-приложении.
        """
        user = update.effective_user
        logger.info(f"🎉 Promotions webapp request from user {user.id}")
        
        try:
            # Логируем запрос акций как тикет
            if self.tickets_client and self.tickets_client.sheet:
                telegram_id = str(user.id)
                code = context.user_data.get('partner_code', '')
                phone = context.user_data.get('phone', '')
                fio = f"{user.first_name or ''} {user.last_name or ''}".strip()
                ticket_text = f"Акции и мероприятия → Акции (открытие страницы)"

                await self.run_blocking(
                    self.tickets_client.upsert_ticket,
                    telegram_id, code, phone, fio,
                    ticket_text, 'выполнено', 'user', False
                )
            
            # Создаём URL для страницы акций
            promotions_url = get_web_app_url('SPA_MENU').replace('spa_menu.html', 'promotions.html')
            
            # Открываем страницу акций
            keyboard = [[InlineKeyboardButton('🎉 Открыть акции', web_app=WebAppInfo(url=promotions_url))]]
            await update.message.reply_text('🎉 Открываю страницу акций...', 
                                           reply_markup=InlineKeyboardMarkup(keyboard))
                
        except Exception as e:
            logger.error(f"Ошибка при открытии страницы акций: {e}")
            await update.message.reply_text('🎉 Ошибка при открытии страницы акций')

    async def _handle_get_promotions_api(self, update: Update, context: ContextTypes.DEFAULT_TYPE, payload: dict):
        """
        Обрабатывает API запрос на получение акций для мини-приложения.
        """
        user = update.effective_user
        logger.info(f"📱 API запрос акций от пользователя {user.id} ({user.first_name})")
        
        try:
            # Проверяем подключение к таблице акций
            if not self.async_promotions_client:
                logger.warning("Асинхронный клиент акций не инициализирован")
                await self._send_promotions_response(update, [])
                return
            
            # Подключаемся к таблице если не подключены
            if not self.async_promotions_client.sheet:
                connected = await self.async_promotions_client.connect()
                if not connected:
                    logger.warning("Не удалось подключиться к таблице акций")
                    await self._send_promotions_response(update, [])
                    return
            
            # Получаем активные акции асинхронно
            active_promotions = await self.async_promotions_client.get_active_promotions()
            
            logger.info(f"📋 Получено {len(active_promotions)} активных акций для мини-приложения")
            await self._send_promotions_response(update, active_promotions)
                
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке API запроса акций: {e}")
            await self._send_promotions_response(update, [])
    
    async def _send_promotions_response(self, update: Update, promotions: list):
        """
        Отправляет ответ с акциями в мини-приложение.
        """
        try:
            # Формируем JSON ответ для мини-приложения
            response_data = {
                'type': 'promotions_response',
                'promotions': promotions,
                'timestamp': datetime.now().isoformat(),
                'count': len(promotions)
            }
            
            # Отправляем данные через WebApp
            await update.message.reply_text(
                f"📱 Данные акций отправлены в мини-приложение\n\n"
                f"🎉 Найдено {len(promotions)} активных акций",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "🔄 Обновить акции", 
                        web_app=WebAppInfo(url=WEB_APP_URLS['SPA_MENU'])
                    )
                ]])
            )
            
            logger.info(f"✅ Отправлен ответ с {len(promotions)} акциями в мини-приложение")
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки ответа акций: {e}")
            await update.message.reply_text('❌ Ошибка при отправке данных акций')

    @safe_execute('test_promotions_command')
    @monitor_performance('test_promotions_command')
    async def test_promotions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Тестовая команда для проверки функциональности акций.
        """
        user = update.effective_user
        logger.info(f"/test_promotions от {user.id} ({user.first_name})")
        
        if not await self.is_user_authorized(user.id):
            await update.message.reply_text('Вы не авторизованы. Сначала пройдите авторизацию.')
            return
            
        await update.message.reply_text('🔍 Тестирую подключение к таблице акций...')
        
        try:
            # Проверяем асинхронный клиент акций
            if not self.async_promotions_client:
                await update.message.reply_text('❌ Асинхронный клиент акций не инициализирован')
                return
            
            # Подключаемся к таблице
            if not self.async_promotions_client.sheet:
                connected = await self.async_promotions_client.connect()
                if not connected:
                    await update.message.reply_text('❌ Не удалось подключиться к таблице акций')
                    return
            
            # Проверяем новые акции асинхронно
            new_promotions = await self.async_promotions_client.get_new_published_promotions()
            active_promotions = await self.async_promotions_client.get_active_promotions()
            
            result_text = f'''✅ Подключение к таблице акций работает!

📊 Статистика:
🆕 Новых для уведомления: {len(new_promotions)}
🎯 Активных всего: {len(active_promotions)}

⏰ Мониторинг: каждые 5 минут
🔄 Последняя проверка: прошла успешно'''
            
            if new_promotions:
                result_text += f"\n\n🎉 Новые акции:\n"
                for promo in new_promotions[:3]:
                    name = promo.get('name', 'Без названия')
                    result_text += f"• {name}\n"
            
            await update.message.reply_text(result_text)
            
        except Exception as e:
            logger.error(f"Ошибка в тесте акций: {e}")
            await update.message.reply_text(f'❌ Ошибка при тестировании: {str(e)}')

    async def _handle_back_to_main(self, update: Update, context: ContextTypes.DEFAULT_TYPE, payload: dict):
        """
        Обрабатывает возврат в главное меню.
        """
        menu_url = get_web_app_url('SPA_MENU')
        keyboard = [[InlineKeyboardButton('🏠 Открыть личный кабинет', web_app=WebAppInfo(url=menu_url))]]
        await update.message.reply_text('Возвращаюсь в главное меню:', reply_markup=InlineKeyboardMarkup(keyboard))
        await update.message.reply_text('Используйте кнопку "menu" для быстрого доступа:', reply_markup=self.create_persistent_keyboard())

    async def _handle_direct_webapp(self, update: Update, context: ContextTypes.DEFAULT_TYPE, payload: dict):
        """
        Обрабатывает прямое открытие мини-приложения.
        """
        section = payload.get('section')
        webapp_url = payload.get('webapp_url')

        if not section or not webapp_url:
            await update.message.reply_text('❗️ Ошибка: не указан раздел или URL мини-приложения.')
            return

        keyboard = [[InlineKeyboardButton(f'📝 Открыть {section}', web_app=WebAppInfo(url=webapp_url))]]
        await update.message.reply_text(f'💼 Открываю раздел: {section}', reply_markup=InlineKeyboardMarkup(keyboard))

    async def _handle_authorization(self, update: Update, context: ContextTypes.DEFAULT_TYPE, payload: dict):
        """
        Обрабатывает данные авторизации.
        """
        user = update.effective_user
        is_blocked, seconds_left = auth_cache.is_user_blocked(user.id)
        if is_blocked:
            time_text = self._format_block_time(seconds_left)
            await update.message.reply_text(f'❌ Авторизация заблокирована на {time_text}.')
            return

        code = payload.get('code')
        phone = payload.get('phone')

        if not code or not phone:
            await update.message.reply_text('❌ Необходимо указать код партнера и телефон.')
            return

        await update.message.reply_text('Проверяю данные...')

        if not self.sheets_client or not self.sheets_client.sheet:
            logger.error('Google Sheets client not available')
            await update.message.reply_text('База недоступна. Свяжитесь с админом.')
            return

        try:
            row = await self.run_blocking(self.sheets_client.find_user_by_credentials, code, phone)
        except Exception as e:
            logger.error(f"Ошибка проверки данных: {e}")
            await update.message.reply_text('Ошибка проверки данных. Попробуйте позже.')
            return

        if row:
            await self._handle_successful_authorization(update, context, row, code, phone)
        else:
            await self._handle_failed_authorization(update, context)

    def _format_block_time(self, seconds: int) -> str:
        """
        Форматирует время блокировки в человекочитаемый вид.
        """
        hours = seconds // 3600
        if hours > 24:
            days = hours // 24
            return f"{days} дн{'я' if days < 5 else 'ей'}"
        if hours > 0:
            return f"{hours} час{'а' if hours < 5 else 'ов'}"
        minutes = (seconds % 3600) // 60
        return f"{minutes} минут"

    async def _handle_successful_authorization(self, update: Update, context: ContextTypes.DEFAULT_TYPE, row: int, code: str, phone: str):
        """
        Обрабатывает успешную авторизацию.
        """
        user = update.effective_user
        try:
            await self.run_blocking(self.sheets_client.update_user_auth_status, row, user.id)
            context.user_data['is_authorized'] = True
            context.user_data['partner_code'] = code
            context.user_data['phone'] = phone
            auth_cache.clear_failed_attempts(user.id)
            logger.info(f"Авторизация для пользователя {user.id} прошла успешно.")
            await update.message.reply_text('✅ Авторизация прошла успешно!')
            menu_url = get_web_app_url('SPA_MENU')
            await update.message.reply_text(
                'Откройте личный кабинет для выбора раздела, или напишите в чат',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Личный кабинет', web_app=WebAppInfo(url=menu_url))]])
            )
            await update.message.reply_text(
                'Используйте кнопку "menu" для быстрого доступа к личному кабинету',
                reply_markup=self.create_persistent_keyboard()
            )
        except Exception as e:
            logger.error(f"Ошибка при сохранении авторизации: {e}")
            await update.message.reply_text('Ошибка при сохранении авторизации. Попробуйте позже.')

    async def _handle_failed_authorization(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Обрабатывает неудачную попытку авторизации.
        """
        user = update.effective_user
        is_blocked, block_duration = auth_cache.add_failed_attempt(user.id)
        if is_blocked:
            time_text = self._format_block_time(block_duration)
            await update.message.reply_text(f'❌ Авторизация заблокирована на {time_text}.')
        else:
            attempts_left = auth_cache.get_attempts_left(user.id)
            web_app_url = get_web_app_url('MAIN')
            keyboard = self.create_auth_keyboard(web_app_url)
            await update.message.reply_text(
                f'❌ Неверные данные или аккаунт неактивен.\nОсталось попыток: {attempts_left}',
                reply_markup=keyboard
            )

    async def _notify_admins(self, context: ContextTypes.DEFAULT_TYPE, text: str):
        """
        Уведомляет администраторов.
        """
        admin_ids_str = os.getenv('ADMIN_TELEGRAM_ID', '')
        if not admin_ids_str.strip():
            logger.warning('No admin IDs configured')
            return
            
        # Remove duplicates and invalid IDs
        admin_ids = list(set([s.strip() for s in admin_ids_str.split(',') if s.strip().isdigit()]))
        
        for aid in admin_ids:
            try:
                await context.bot.send_message(chat_id=int(aid), text=text)
                logger.debug(f'Notified admin {aid}')
            except Exception as e:
                logger.warning(f"Не удалось уведомить админа {aid}: {e}")


    @safe_execute('handle_callback_query')
    @monitor_performance('handle_callback_query')
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Обработчик колбэк-запросов от инлайн-кнопок.
        """
        query = update.callback_query
        await query.answer()
        data = query.data or ''

        if data.startswith('t:'):
            await self._handle_ticket_action(query, context, data)
        elif data == 'show_menu':
            keyboard = [[InlineKeyboardButton(section, callback_data=f"menu:{section}")] for section in SECTIONS]
            await query.edit_message_text('Выберите интересующий раздел:', reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.edit_message_text('Неподдерживаемое действие.')

    async def _handle_ticket_action(self, query, context: ContextTypes.DEFAULT_TYPE, data: str):
        """
        Обрабатывает действия с тикетами.
        """
        parts = data.split(':')
        if len(parts) != 3:
            await query.edit_message_text('Некорректный формат действия с тикетом.')
            return

        action = parts[1]
        try:
            row = int(parts[2])
        except (ValueError, IndexError):
            await query.edit_message_text('Неверный идентификатор тикета.')
            return

        if action == 'transfer':
            await self._transfer_ticket(query, context, row)
        elif action == 'done':
            await self._mark_ticket_as_done(query, row)
        else:
            await query.edit_message_text('Неизвестное действие с тикетом.')

    async def _transfer_ticket(self, query, context: ContextTypes.DEFAULT_TYPE, row: int):
        """
        Переводит тикет специалисту.
        """
        try:
            ok = await self.run_blocking(self.tickets_client.set_ticket_status, row, None, 'в работе')
            if ok:
                await query.edit_message_reply_markup(None)
                await query.edit_message_text('Тикет помечен как "в работе" и направлен специалистам.')
                await self._notify_specialists(context, row)
            else:
                await query.edit_message_text('Не удалось изменить статус (ошибка записи).')
        except Exception as e:
            logger.error(f"Ошибка при переводе тикета специалисту: {e}")
            await query.edit_message_text('Произошла ошибка при переводе тикета.')

    async def _mark_ticket_as_done(self, query, row: int):
        """
        Помечает тикет как выполненный.
        """
        try:
            ok = await self.run_blocking(self.tickets_client.set_ticket_status, row, None, 'выполнено')
            if ok:
                await query.edit_message_reply_markup(None)
                await query.edit_message_text('Тикет помечен как выполнено.')
            else:
                await query.edit_message_text('Не удалось пометить тикет как выполнено.')
        except Exception as e:
            logger.error(f"Ошибка при пометке тикета как выполненного: {e}")
            await query.edit_message_text('Произошла ошибка при обновлении статуса тикета.')

    async def _notify_specialists(self, context: ContextTypes.DEFAULT_TYPE, row: int):
        """
        Уведомляет специалистов о новом тикете.
        """
        try:
            telegram_id = None
            if self.tickets_client and self.tickets_client.sheet:
                telegram_id = await self.run_blocking(lambda r=row: self.tickets_client.sheet.cell(r, 4).value)

            notified = set()
            
            # Получаем список админов с валидацией
            admin_ids_str = os.getenv('ADMIN_TELEGRAM_ID', '')
            admin_ids = list(set([s.strip() for s in admin_ids_str.split(',') if s.strip().isdigit()]))
            
            for aid in admin_ids:
                if aid and aid not in notified:
                    try:
                        await context.bot.send_message(chat_id=int(aid), text='Ваш вопрос переведен специалисту.')
                        notified.add(aid)
                        logger.debug(f'Notified admin {aid} about ticket transfer')
                    except Exception as e:
                        logger.debug(f"Не удалось уведомить админа {aid}: {e}")

            # Получаем список авторизованных пользователей
            auth_ids = self.get_authorized_ids() or set()
            for aid in auth_ids:
                if aid and str(aid) != str(telegram_id) and aid not in notified and str(aid).isdigit():
                    try:
                        await context.bot.send_message(chat_id=int(aid), text=f'Новый тикет для специалиста (строка {row}).')
                        notified.add(aid)
                        logger.debug(f'Notified specialist {aid} about new ticket')
                    except Exception as e:
                        logger.debug(f"Не удалось уведомить специалиста {aid}: {e}")
                        
            logger.info(f'Notified {len(notified)} users about ticket in row {row}')
        except Exception as e:
            logger.error(f"Ошибка при уведомлении специалистов: {e}")


    @safe_execute('new_chat')
    @monitor_performance('new_chat')
    async def new_chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Обработчик команды /new_chat.
        """
        user = update.effective_user
        context.user_data.clear()
        logger.info(f"/new_chat от {user.id} - кэш очищен")
        await self.start(update, context)


    @safe_execute('reply_command')
    @monitor_performance('reply_command')
    async def reply_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Обработчик команды /reply.
        """
        user = update.effective_user
        if not await self.is_user_authorized(user.id) and not self.is_admin(user.id):
            await update.message.reply_text('Недостаточно прав для выполнения этой команды.')
            return

        args = context.args
        if len(args) < 2:
            await update.message.reply_text('Использование: /reply <код> <текст ответа>')
            return

        code = args[0]
        reply_text = ' '.join(args[1:])

        try:
            row, telegram_id = await self._find_ticket_by_code(code)
            if not row:
                await update.message.reply_text(f'Тикет с кодом {code} не найден.')
                return

            if not telegram_id:
                await update.message.reply_text(f'Telegram ID не найден для кода {code}.')
                return

            success = await self.run_blocking(self.tickets_client.set_specialist_reply, str(telegram_id), reply_text)
            if not success:
                await update.message.reply_text('Ошибка при записи ответа в поле специалиста.')
                return

            await self._send_reply_to_user(context, telegram_id, code, reply_text)
            await self._log_specialist_reply(telegram_id, code, reply_text)
            await self.run_blocking(self.tickets_client.clear_specialist_reply, str(telegram_id))

            await update.message.reply_text(
                '✅ Ответ успешно отправлен!\n\n' 
                f'👤 Пользователь: {telegram_id}\n' 
                f'📝 Код: {code}\n' 
                f'💬 Ответ: {reply_text[:100]}'
            )

        except Exception as e:
            logger.error(f"Ошибка при выполнении команды /reply: {e}")
            await update.message.reply_text('Произошла ошибка при отправке ответа.')

    async def _find_ticket_by_code(self, code: str) -> tuple[int | None, str | None]:
        """
        Находит тикет по коду и возвращает номер строки и telegram_id.
        """
        if not self.tickets_client or not self.tickets_client.sheet:
            return None, None

        row = await self.run_blocking(self.tickets_client.find_row_by_code, code)
        if not row:
            return None, None

        telegram_id = await self.run_blocking(lambda r=row: self.tickets_client.sheet.cell(r, 4).value)
        return row, telegram_id

    async def _send_reply_to_user(self, context: ContextTypes.DEFAULT_TYPE, telegram_id: str, code: str, text: str):
        """
        Отправляет ответ пользователю.
        """
        try:
            await context.bot.send_message(
                chat_id=int(telegram_id),
                text=f'Отдел маркетинга:\n{text}'
            )
            logger.info(f"Ответ отдела маркетинга отправлен пользователю {telegram_id}")
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение пользователю {telegram_id}: {e}")
            raise

    async def _log_specialist_reply(self, telegram_id: str, code: str, text: str):
        """
        Логирует ответ специалиста в таблицу.
        """
        try:
            await self.run_blocking(
                self.tickets_client.upsert_ticket, 
                str(telegram_id), code, '', '', f'[ОТВЕТ ОТДЕЛА МАРКЕТИНГА] {text}', 'в работе', 'specialist', False
            )
            logger.info(f"Ответ отдела маркетинга залогирован для пользователя {telegram_id}")
        except Exception as e:
            logger.error(f"Не удалось залогировать ответ специалиста для пользователя {telegram_id}: {e}")
            raise

    async def cleanup_cache(self, context: ContextTypes.DEFAULT_TYPE):
        """
        Периодическая очистка кэша для масштабируемости.
        """
        try:
            max_cache_size = SCALING_CONFIG['MAX_CACHE_SIZE']
            
            # Очищаем старые записи кэша
            if len(auth_cache.user_cache) > max_cache_size:
                # Удаляем самые старые записи
                sorted_items = sorted(
                    auth_cache.user_cache.items(),
                    key=lambda x: x[1].get('auth_timestamp', 0)
                )
                
                # Оставляем 80% от максимального размера
                keep_count = int(max_cache_size * 0.8)
                items_to_remove = sorted_items[:-keep_count]
                
                for user_id, _ in items_to_remove:
                    del auth_cache.user_cache[user_id]
                
                logger.info(f"🧹 Очищен кэш: удалено {len(items_to_remove)} старых записей, осталось {len(auth_cache.user_cache)}")
                
                # Сохраняем обновленный кэш
                auth_cache._save_to_file()
                
        except Exception as e:
            logger.error(f"❌ Ошибка при очистке кэша: {e}")

    async def monitor_new_promotions(self, context: ContextTypes.DEFAULT_TYPE):
        """
        Мониторинг новых опубликованных акций для отправки уведомлений.
        """
        if not self.async_promotions_client:
            return
            
        try:
            # Подключаемся к таблице если не подключены
            if not self.async_promotions_client.sheet:
                connected = await self.async_promotions_client.connect()
                if not connected:
                    logger.warning("Не удалось подключиться к таблице акций")
                    return
            
            # Получаем новые опубликованные акции асинхронно
            new_promotions = await self.async_promotions_client.get_new_published_promotions()
            
            if not new_promotions:
                return
                
            logger.info(f"🎉 Найдено {len(new_promotions)} новых акций для уведомления")
            
            # Получаем всех авторизованных пользователей
            authorized_users = await self.get_authorized_users()
            
            if not authorized_users:
                logger.warning("Нет авторизованных пользователей для отправки уведомлений об акциях")
                return
            
            # Отправляем уведомления для каждой акции
            for promotion in new_promotions:
                try:
                    await self._send_promotion_notification(context, promotion, authorized_users)
                    
                    # Помечаем уведомление как отправленное асинхронно
                    await self.async_promotions_client.mark_notification_sent(promotion['row'])
                    
                    # Небольшая пауза между уведомлениями
                    await asyncio.sleep(PROMOTIONS_CONFIG['NOTIFICATION_DELAY'])
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка при отправке уведомления об акции '{promotion.get('name', 'Unknown')}': {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"❌ Ошибка в мониторинге новых акций: {e}")
    
    async def _send_promotion_notification(self, context: ContextTypes.DEFAULT_TYPE, promotion: dict, authorized_users: list):
        """
        Отправляет уведомление о новой акции всем авторизованным пользователям.
        """
        try:
            # Формируем текст уведомления
            name = promotion.get('name', 'Новая акция')
            description = promotion.get('description', '')
            start_date = promotion.get('start_date')
            end_date = promotion.get('end_date')
            
            # Обрезаем описание если слишком длинное
            max_desc_length = PROMOTIONS_CONFIG['MAX_DESCRIPTION_LENGTH']
            if description and len(description) > max_desc_length:
                description = description[:max_desc_length] + '...'
            
            # Формируем период действия
            period_text = ''
            if start_date and end_date:
                period_text = f"📅 Действует: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}"
            elif start_date:
                period_text = f"📅 Начало: {start_date.strftime('%d.%m.%Y')}"
            
            message_text = f"""🎉 Новая акция опубликована!

📢 {name}
{period_text}

{description if description else 'Подробности в личном кабинете'}

👀 Посмотреть подробнее ↓"""
            
            # Создаем кнопку для просмотра акций (ведет прямо в раздел акций)
            spa_menu_url = get_web_app_url('SPA_MENU') + '?section=promotions'
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    '👀 Ознакомиться подробнее', 
                    web_app=WebAppInfo(url=spa_menu_url)
                )
            ]])
            
            # Отправляем уведомления всем авторизованным пользователям
            sent_count = 0
            failed_count = 0
            
            for user in authorized_users:
                telegram_id = user.get('telegram_id')
                if not telegram_id:
                    continue
                    
                try:
                    await context.bot.send_message(
                        chat_id=int(telegram_id),
                        text=message_text,
                        reply_markup=keyboard
                    )
                    sent_count += 1
                    
                except Exception as e:
                    logger.warning(f"Не удалось отправить уведомление пользователю {telegram_id}: {e}")
                    failed_count += 1
                    
                # Небольшая пауза между отправками
                await asyncio.sleep(0.1)
            
            logger.info(f"✅ Уведомление об акции '{name}' отправлено: {sent_count} успешно, {failed_count} ошибок")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке уведомления об акции: {e}")
            raise
    
    async def get_authorized_users(self) -> list:
        """
        Получает список всех авторизованных пользователей для отправки уведомлений.
        """
        try:
            if not self.sheets_client:
                logger.error("sheets_client не инициализирован")
                return []
            
            # Получаем авторизованных пользователей из кэша или из таблицы
            logger.debug("🔍 Вызываем sheets_client.get_authorized_users_batch()")
            raw_data = await self.run_blocking(self.sheets_client.get_authorized_users_batch)
            
            logger.debug(f"📊 Получены сырые данные: тип={type(raw_data)}, длина={len(raw_data) if hasattr(raw_data, '__len__') else 'N/A'}")
            
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Обработка случая JSON-строки
            if isinstance(raw_data, str):
                logger.warning(f"⚠️ Получена строка вместо словаря. Попытка десериализации JSON...")
                try:
                    import json
                    authorized_users_dict = json.loads(raw_data)
                    logger.info(f"✅ Успешно десериализован JSON: {type(authorized_users_dict)}")
                except json.JSONDecodeError as e:
                    logger.error(f"❌ Не удалось декодировать JSON: {e}")
                    logger.error(f"❌ Проблемные данные: {raw_data[:200]}...")
                    return []
                except Exception as e:
                    logger.error(f"❌ Неожиданная ошибка при десериализации: {e}")
                    return []
            elif isinstance(raw_data, dict):
                logger.debug("✅ Получен корректный словарь")
                authorized_users_dict = raw_data
            else:
                logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Неожиданный тип данных: {type(raw_data)}")
                logger.error(f"❌ Содержимое: {raw_data}")
                return []
            
            logger.debug(f"Словарь пользователей содержит {len(authorized_users_dict)} записей")
            
            # Преобразуем словарь в список объектов с telegram_id
            users_with_telegram = []
            for telegram_id, user_data in authorized_users_dict.items():
                logger.debug(f"Обрабатываем пользователя {telegram_id}: тип данных={type(user_data)}, данные={user_data}")
                
                # Дополнительная проверка типов
                if not isinstance(user_data, dict):
                    logger.warning(f"ПРОПУСК: Пользователь {telegram_id} имеет данные неправильного типа ({type(user_data)}): {user_data}")
                    continue
                    
                user_obj = {
                    'telegram_id': telegram_id,
                    'code': user_data.get('code', ''),
                    'phone': user_data.get('phone', ''),
                    'fio': user_data.get('fio', '')
                }
                users_with_telegram.append(user_obj)
            
            logger.info(f"📋 Найдено {len(users_with_telegram)} авторизованных пользователей с Telegram ID")
            return users_with_telegram
            
        except Exception as e:
            logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА в get_authorized_users: {e}")
            import traceback
            logger.error(f"Полный traceback: {traceback.format_exc()}")
            
            # Попытаемся получить данные повторно с дополнительным логированием
            try:
                logger.error("🔍 Попытка повторного получения данных...")
                test_data = await self.run_blocking(self.sheets_client.get_authorized_users_batch)
                logger.error(f"Повторные данные: тип={type(test_data)}, количество={len(test_data) if hasattr(test_data, '__len__') else 'N/A'}")
                if hasattr(test_data, 'items'):
                    for i, (k, v) in enumerate(test_data.items()):
                        if i < 3:  # Показываем только первые 3
                            logger.error(f"Ключ {i}: {k} -> Тип значения: {type(v)}, Значение: {v}")
            except Exception as e2:
                logger.error(f"Ошибка при повторном получении: {e2}")
            
            return []

    async def monitor_specialist_replies(self, context: ContextTypes.DEFAULT_TYPE):
        """
        Периодическая проверка поля 'специалист_ответ' в таблице для автоматической отправки ответов.
        """
        if not self.tickets_client:
            return
            
        try:
            # Извлекаем все ответы специалистов из поля G
            replies = await self.run_blocking(self.tickets_client.extract_operator_replies)
            
            if not replies:
                # Не логируем, чтобы не спамить
                return
                
            logger.info(f"📬 Найдено {len(replies)} ответов специалистов для обработки")
            
            # Обрабатываем каждый ответ
            for reply in replies:
                telegram_id = reply.get('telegram_id', '')
                reply_text = reply.get('reply_text', '')
                code = reply.get('code', '')
                row = reply.get('row', 0)
                
                if not telegram_id or not reply_text or not code:
                    logger.warning(f"Неполные данные в ответе: telegram_id={telegram_id}, code={code}")
                    continue
                
                try:
                    # Отправляем ответ пользователю
                    await self._send_reply_to_user(context, telegram_id, code, reply_text)
                    
                    # Логируем ответ в столбец E (история)
                    await self._log_specialist_reply(telegram_id, code, reply_text)
                    
                    # Очищаем поле G после успешной отправки
                    await self.run_blocking(self.tickets_client.clear_specialist_reply, telegram_id)
                    
                    logger.info(f"✅ Ответ отдела маркетинга успешно обработан: код={code}, telegram_id={telegram_id}")
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка при обработке ответа специалиста: код={code}, telegram_id={telegram_id}, ошибка: {e}")
                    # Продолжаем обработку остальных ответов
                    continue
                    
        except Exception as e:
            logger.error(f"❌ Ошибка в мониторинге ответов специалистов: {e}")


def main():
    """
    Основная функция для запуска бота.
    """
    logger.info("Starting Marketing Bot...")
    
    # System service manager (systemd/launchd) guarantees single instance
    # No need for manual process lock management
    
    # Комплексная валидация конфигурации
    logger.info("Validating configuration...")
    
    # Проверяем переменные окружения
    env_valid, env_errors = validator.validate_environment()
    if not env_valid:
        logger.critical("Ошибки переменных окружения:")
        for error in env_errors:
            logger.critical(f"  - {error}")
        return
    
    # Проверяем конфигурацию проекта
    is_valid, errors = validate_config()
    if not is_valid:
        logger.critical("Ошибки конфигурации:")
        for error in errors:
            logger.critical(f"  - {error}")
        return
    
    # Проверяем наличие обязательных файлов
    required_files = ['credentials.json']
    missing_files = [f for f in required_files if not os.path.exists(f)]
    if missing_files:
        logger.critical(f"Отсутствуют обязательные файлы: {missing_files}")
        return

    # Проверяем токен
    token = os.getenv('TELEGRAM_TOKEN')
    if not token:
        logger.critical("TELEGRAM_TOKEN не найден! Бот не может быть запущен.")
        return
    
    # Проверяем состояние внешних сервисов
    logger.info("Checking external services...")
    
    # Проверяем OpenAI
    if openai_client.is_available():
        logger.info("✓ OpenAI API доступен")
    else:
        logger.warning("⚠ OpenAI API недоступен - AI функции отключены")
    
    logger.info("✓ Configuration validation completed successfully")
    
    # Инициализация и запуск бота
    try:
        bot = Bot(token)
        logger.info("✓ Bot instance created successfully")
        
        # Очистка старых данных MCP контекста
        from mcp_context_v7 import mcp_context
        mcp_context.cleanup_and_save()
        logger.info("✓ MCP context initialized")
        
        logger.info("🚀 Starting bot polling...")
        asyncio.run(bot.run())
        
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.critical(f"❌ Critical error during bot startup: {e}")
        raise
    finally:
        logger.info("🧹 Bot shutdown completed")

if __name__ == '__main__':
    main()
