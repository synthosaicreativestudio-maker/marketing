# -*- coding: utf-8 -*- 
"""
Переписанная и улучшенная версия бота с исправленной архитектурой.
- Централизованная конфигурация
- Классовая структура для инкапсуляции логики
- Улучшенная обработка ошибок и логирование
- Рефакторинг длинных функций
"""

import logging
import os
import asyncio
import functools
import nest_asyncio
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler

# Импорты модулей проекта
from config import (
    SECTIONS, get_web_app_url, get_ticket_status, SUBSECTIONS, validate_config,
    LOG_FILE, GOOGLE_CREDENTIALS_PATH, AUTH_WORKSHEET_NAME, TICKETS_WORKSHEET_NAME
)
from sheets_client import GoogleSheetsClient
from auth_cache import auth_cache
from openai_client import openai_client
from mcp_context_v7 import mcp_context
from error_handler import safe_execute
from performance_monitor import monitor_performance
from validator import validator

# Инициализируем nest_asyncio для совместимости
nest_asyncio.apply()

# Загрузка .env файла
load_dotenv()
if not os.getenv('TELEGRAM_TOKEN') and os.path.exists('bot.env'):
    load_dotenv('bot.env', override=True)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class Bot:
    """
    Основной класс бота, инкапсулирующий всю логику.
    """
    def __init__(self, token: str):
        """
        Инициализация бота.
        """
        self.token = token
        self.application = Application.builder().token(self.token).build()
        self.sheets_client = None
        self.tickets_client = None
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

    def _register_handlers(self):
        """
        Регистрация обработчиков команд и сообщений.
        """
        self.application.add_handler(CommandHandler('start', self.start))
        self.application.add_handler(CommandHandler('menu', self.menu_command))
        self.application.add_handler(CommandHandler('new_chat', self.new_chat))
        self.application.add_handler(CommandHandler('reply', self.reply_command))
        self.application.add_handler(CommandHandler('auth', self.auth_command))
        self.application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, self.web_app_data))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(CallbackQueryHandler(self.handle_callback_query))

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
                text=f'✉️ Ответ специалиста (код {code}):\n{text}'
            )
            logger.info(f"Ответ специалиста отправлен пользователю {telegram_id}")
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
                str(telegram_id), code, '', '', f'[ОТВЕТ СПЕЦИАЛИСТА] {text}', 'в работе', 'specialist', False
            )
            logger.info(f"Ответ специалиста залогирован для пользователя {telegram_id}")
        except Exception as e:
            logger.error(f"Не удалось залогировать ответ специалиста для пользователя {telegram_id}: {e}")
            raise


def main():
    """
    Основная функция для запуска бота.
    """
    logger.info("Starting Marketing Bot...")
    
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

if __name__ == '__main__':
    main()
