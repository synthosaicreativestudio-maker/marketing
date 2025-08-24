# -*- coding: utf-8 -*-

"""
Упрощённая и чистая версия бота.
- Загружает настройки из .env
- Проверяет подключение к OpenAI при старте
- Работает с Google Sheets через sheets_client.py
- Реализованы /start, обработка WebAppData, /new_chat и handle_message

Примечание: этот файл заменяет повреждённую версию. Если у вас есть кастомная логика — скажите, добавлю.
"""

import logging
import os
import json
import openai
import time
import asyncio
import math
import fcntl
from openai import OpenAI
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
import telegram
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from sheets_client import GoogleSheetsClient
from urllib.parse import urlencode

# Загрузка .env. Если TELEGRAM_TOKEN не задан, попробуем загрузить `bot.env` (у вас был такой файл).
import subprocess
SECTIONS = [
    'Агрегаторы',
    'Контент',
    'Финансы',
    'Технические проблемы',
    'Дизайн и материалы',
    'Регламенты и обучение',
    'Акции и мероприятия',
    'Аналитика',
    'Связаться со специалистом'
]

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Send a single Web App inline button that opens the mini‑app immediately.
    # Many Telegram clients open inline web_app buttons more reliably than reply keyboard buttons.
    web_app_base = os.getenv('WEB_APP_MENU_URL', os.getenv('WEB_APP_URL', 'https://synthosaicreativestudio-maker.github.io/marketing/'))
    main_button = InlineKeyboardButton('Открыть миниапп', web_app=WebAppInfo(url=web_app_base))
    # Optional: attach a secondary row with per-section deep-links (clients may show them as normal links)
    section_rows = []
    for section in SECTIONS:
        # Prefer fragment deep-linking (more reliable in Telegram clients)
        fragment = urlencode({'section': section})
        url = f"{web_app_base.rstrip('/')}#{fragment}"
        section_rows.append([InlineKeyboardButton(section, web_app=WebAppInfo(url=url))])
    keyboard = [[main_button]] + section_rows
    await update.message.reply_text('Нажмите кнопку ниже, чтобы открыть личный кабинет:', reply_markup=InlineKeyboardMarkup(keyboard))

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

# OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')
# Инициализируем клиент для новой версии openai-python
try:
    openai_client = OpenAI(api_key=openai.api_key)
except Exception:
    # fallback: инициализация без явного ключа (будет читать из env)
    openai_client = OpenAI()

def check_openai_connection() -> bool:
    if not openai.api_key:
        logger.error('OPENAI_API_KEY не задан в .env')
        return False
    try:
        # Try a lightweight chat completion to verify connectivity
        try:
            resp = openai_client.chat.completions.create(
                model=os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo'),
                messages=[{'role': 'system', 'content': 'ping'}],
                max_tokens=1
            )
            logger.info('OpenAI доступен (chat completions)')
            return True
        except Exception:
            # Fallback: try listing models (may work with low privileges)
            try:
                resp = openai_client._client.request('GET', '/v1/models')
                if getattr(resp, 'status_code', None) == 200 or getattr(resp, 'status', None) == 200:
                    logger.info('OpenAI доступен (models list)')
                    return True
            except Exception as e:
                logger.warning(f'OpenAI lightweight check fallback failed: {e}')
            raise
    except Exception as e:
        logger.error(f'OpenAI connection error: {e}')
        return False


def autopush_index() -> bool:
    """
    Автоматически коммитит и пушит все изменения в текущем git-репозитории.
    Возвращает True при успешном пуше, иначе False. Не бросает исключения наружу.
    """
    import subprocess
    import os
    repo_path = os.path.dirname(os.path.abspath(__file__))
    # If repository has no .git, skip
    if not os.path.exists(os.path.join(repo_path, '.git')):
        logger.info('.git не найден в репозитории, пропускаю autopush.')
        return False
    try:
        # Add all changes
        subprocess.run(['git', '-C', repo_path, 'add', '.'], check=True)
        try:
            subprocess.run(['git', '-C', repo_path, 'commit', '-m', 'Автоматический коммит изменений'], check=True)
        except subprocess.CalledProcessError:
            # nothing to commit
            logger.info('Нет изменений для коммита.')
            return True  # No changes is also success
        subprocess.run(['git', '-C', repo_path, 'push'], check=True)
        logger.info('autopush завершён успешно.')
        return True
    except Exception as e:
        logger.error(f'Ошибка autopush: {e}')
        return False


def _create_or_get_thread(assistant_id: str, code: str | None = None, telegram_id: str | None = None) -> str | None:
    """Создаёт новый thread через OpenAI API и возвращает thread_id."""
    try:
        thread = openai_client.beta.threads.create()
        return thread.id
    except Exception as e:
        logger.error(f'Не удалось создать thread: {e}')
        return None


import time
def _send_message_in_thread(assistant_id: str, thread_id: str, text: str) -> str | None:
    """Добавляет сообщение, запускает ассистента, ждёт run, возвращает ответ ассистента."""
    if not assistant_id or not thread_id:
        return None
    try:
        # 1. Добавить сообщение пользователя
        openai_client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=text
        )
        # 2. Запустить ассистента
        run = openai_client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id
        )
        # 3. Ждать завершения run (polling)
        for _ in range(60):
            run_status = openai_client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id
            )
            if run_status.status == "completed":
                break
            elif run_status.status in ("failed", "cancelled", "expired"):
                logger.error(f'Run завершился с ошибкой: {run_status.status}')
                return None
            time.sleep(1)
        # 4. Получить все сообщения в thread
        messages = openai_client.beta.threads.messages.list(thread_id=thread_id)
        # 5. Найти последний ответ ассистента
        for msg in reversed(messages.data):
            if msg.role == "assistant":
                return msg.content[0].text.value if msg.content and hasattr(msg.content[0], 'text') and hasattr(msg.content[0].text, 'value') else str(msg.content)
        return None
    except Exception as e:
        logger.error(f'Ошибка при отправке сообщения в thread: {e}')
        return None

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
# Параметры производительности
MAX_OPENAI_CONCURRENT = int(os.getenv('MAX_OPENAI_CONCURRENT', '3'))
OPENAI_SEMAPHORE = asyncio.Semaphore(MAX_OPENAI_CONCURRENT)
# Утилиты
def is_admin(user_id: int) -> bool:
    admin_ids = os.getenv('ADMIN_TELEGRAM_ID', '')
    admin_list = [s.strip() for s in admin_ids.split(',') if s.strip()]
    return str(user_id) in admin_list

async def is_user_authorized(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    # Не используем кэш в context.user_data, всегда проверяем актуальные данные
    
    # Используем глобальный кэш авторизованных ID
    authorized_ids = get_authorized_ids()
    if authorized_ids is None:
        # Если нет доступа к sheets, возвращаем False
        return False
    is_auth = str(user_id) in authorized_ids
    # Обновляем кэш в контексте
    context.user_data['is_authorized'] = is_auth
    return is_auth


## --- СИСТЕМА БЛОКИРОВКИ АВТОРИЗАЦИИ ---
FAILED_AUTH_CACHE = {}  # {user_id: {'attempts': count, 'blocked_until': timestamp, 'block_count': total_blocks}}
MAX_AUTH_ATTEMPTS = 5
BLOCK_DURATIONS = [86400, 432000, 2592000]  # 1 день, 5 дней, 30 дней в секундах

def is_user_blocked(user_id: int) -> tuple[bool, int]:
    """Проверяет заблокирован ли пользователь. Возвращает (заблокирован, секунд до разблокировки)"""
    if user_id not in FAILED_AUTH_CACHE:
        return False, 0
    
    user_data = FAILED_AUTH_CACHE[user_id]
    blocked_until = user_data.get('blocked_until', 0)
    
    if blocked_until > time.time():
        return True, int(blocked_until - time.time())
    
    # Разблокирован - сбрасываем попытки
    if blocked_until > 0:
        user_data['attempts'] = 0
        user_data['blocked_until'] = 0
    
    return False, 0

def add_failed_attempt(user_id: int) -> tuple[bool, int]:
    """Добавляет неудачную попытку. Возвращает (заблокирован, секунд блокировки)"""
    if user_id not in FAILED_AUTH_CACHE:
        FAILED_AUTH_CACHE[user_id] = {'attempts': 0, 'blocked_until': 0, 'block_count': 0}
    
    user_data = FAILED_AUTH_CACHE[user_id]
    user_data['attempts'] += 1
    
    if user_data['attempts'] >= MAX_AUTH_ATTEMPTS:
        # Блокируем пользователя
        block_count = min(user_data['block_count'], len(BLOCK_DURATIONS) - 1)
        block_duration = BLOCK_DURATIONS[block_count]
        user_data['blocked_until'] = time.time() + block_duration
        user_data['block_count'] += 1
        user_data['attempts'] = 0
        return True, block_duration
    
    return False, 0

def clear_failed_attempts(user_id: int):
    """Очищает неудачные попытки при успешной авторизации"""
    if user_id in FAILED_AUTH_CACHE:
        FAILED_AUTH_CACHE[user_id]['attempts'] = 0
AUTH_CACHE = {'ids': set(), 'ts': 0}
AUTH_TTL = 30  # Сократил с 300 до 30 секунд для быстрого обновления

def get_authorized_ids():
    """Возвращает множество строк с авторизованными Telegram ID или None, если Sheets недоступен."""
    now = time.time()
    if AUTH_CACHE['ids'] and (now - AUTH_CACHE['ts'] < AUTH_TTL):
        return AUTH_CACHE['ids']
    # иначе обновляем
    try:
        if not sheets_client or not sheets_client.sheet:
            return None
        ids = sheets_client.get_all_authorized_user_ids()
        AUTH_CACHE['ids'] = set(str(i) for i in ids if i)
        AUTH_CACHE['ts'] = now
        return AUTH_CACHE['ids']
    except Exception as e:
        logger.error(f'Не удалось получить список авторизованных ID: {e}')
        return None

def refresh_authorized_cache():
    try:
        if sheets_client and sheets_client.sheet:
            ids = sheets_client.get_all_authorized_user_ids()
            AUTH_CACHE['ids'] = set(str(i) for i in ids if i)
            AUTH_CACHE['ts'] = time.time()
            logger.info(f'Кэш авторизованных пользователей обновлён: {len(AUTH_CACHE["ids"])} записей')
    except Exception as e:
        logger.error(f'Ошибка при обновлении кэша авторизаций: {e}')

# Клиент для таблицы обращений (tickets)
tickets_client = None
if TICKETS_SHEET_URL and os.path.exists('credentials.json'):
    try:
        tickets_client = GoogleSheetsClient(credentials_path='credentials.json', sheet_url=TICKETS_SHEET_URL, worksheet_name=TICKETS_WORKSHEET)
    except Exception as e:
        logger.error(f'Ошибка инициализации tickets GoogleSheetsClient: {e}')
else:
    logger.info('TICKETS_SHEET_URL не задан или credentials.json отсутствует — таблица обращений отключена')

# Обработчики
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f'/start от {user.id} ({user.first_name})')
    if await is_user_authorized(user.id, context):
        # Persistent меню с кнопкой /menu
        from telegram import ReplyKeyboardMarkup, KeyboardButton
        web_app_base = os.getenv('WEB_APP_URL', 'https://synthosaicreativestudio-maker.github.io/marketing/')
        kb_button = KeyboardButton('Личный кабинет', web_app=WebAppInfo(url=web_app_base))
        persistent_keyboard = ReplyKeyboardMarkup(
            [[kb_button]],
            resize_keyboard=True,
            one_time_keyboard=False
        )
        await update.message.reply_text(
            'Вы уже авторизованы и готовы к работе!\nНажмите кнопку ниже, чтобы открыть личный кабинет.',
            reply_markup=persistent_keyboard
        )
        return
    web_app_url = os.getenv('WEB_APP_URL', 'https://synthosaicreativestudio-maker.github.io/marketing/')
    keyboard = [[InlineKeyboardButton('Авторизоваться', web_app=WebAppInfo(url=web_app_url))]]
    await update.message.reply_text(f'Привет, {user.first_name}! Нажми кнопку чтобы авторизоваться.', reply_markup=InlineKeyboardMarkup(keyboard))

async def web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        payload = json.loads(update.message.web_app_data.data)
    except Exception:
        await update.message.reply_text('Не удалось прочитать данные от Web App')
        return
    # Support two kinds of payloads from the WebApp:
    # 1) Authorization payload with {code, phone}
    # 2) Menu selection payload with {type: 'menu_selection', section: '...'}
    if isinstance(payload, dict) and payload.get('type') == 'menu_selection':
        section = payload.get('section')
        user = update.effective_user
        if not await is_user_authorized(user.id, context):
            await update.message.reply_text('Вы не авторизованы. Сначала пройдите авторизацию.')
            return
        # Log selection as a ticket in the Обращения sheet (if available)
        try:
            if tickets_client and tickets_client.sheet:
                telegram_id = str(user.id)
                code = context.user_data.get('partner_code', '')
                phone = context.user_data.get('phone', '')
                fio = f"{user.first_name or ''} {user.last_name or ''}".strip()
                tickets_client.upsert_ticket(telegram_id=telegram_id, code=code, phone=phone, fio=fio, text=f"Запрос: {section}", sender_type='user', handled=False)
        except Exception as e:
            logger.error(f'Не удалось записать выбор раздела в tickets: {e}')
        await update.message.reply_text(f'Вы выбрали раздел: {section}. Мы получили вашу заявку и скоро свяжемся.')
        # Optionally notify admins
        try:
            admin_ids = [s.strip() for s in os.getenv('ADMIN_TELEGRAM_ID','').split(',') if s.strip()]
            for aid in admin_ids:
                try:
                    await context.bot.send_message(chat_id=int(aid), text=f'Пользователь {user.id} выбрал раздел: {section}')
                except Exception:
                    pass
        except Exception:
            pass
        return

    # Otherwise treat as authorization payload
    user = update.effective_user
    
    # Проверяем блокировку
    is_blocked, seconds_left = is_user_blocked(user.id)
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
    await update.message.reply_text('Проверяю данные...')
    if not sheets_client or not sheets_client.sheet:
        await update.message.reply_text('База недоступна. Свяжитесь с админом.')
        return
    row = sheets_client.find_user_by_credentials(code, phone)
    if row:
        sheets_client.update_user_auth_status(row, update.effective_user.id)
        context.user_data['is_authorized'] = True
        context.user_data['partner_code'] = code
        context.user_data['phone'] = phone
        clear_failed_attempts(user.id)  # Очищаем неудачные попытки
        await update.message.reply_text('✅ Авторизация прошла успешно!')
        # Показываем кнопку для открытия мини-аппа сразу после авторизации (открывает второй экран меню)
        web_app_base = os.getenv('WEB_APP_MENU_URL', os.getenv('WEB_APP_URL', 'https://synthosaicreativestudio-maker.github.io/marketing/'))
        menu_url = f"{web_app_base.rstrip('/')}#view=menu2"
        await update.message.reply_text(
            '✅ Авторизация прошла успешно! Откройте личный кабинет для выбора раздела',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Личный кабинет', web_app=WebAppInfo(url=menu_url))]])
        )
    else:
        # Неудачная попытка
        is_blocked, block_duration = add_failed_attempt(user.id)
        attempts_left = MAX_AUTH_ATTEMPTS - (FAILED_AUTH_CACHE[user.id]['attempts'] if user.id in FAILED_AUTH_CACHE else 0)
        
        if is_blocked:
            hours = block_duration // 3600
            if hours > 24:
                days = hours // 24
                time_text = f"{days} дн{'я' if days < 5 else 'ей'}"
            else:
                time_text = f"{hours} час{'а' if hours < 5 else 'ов'}"
            await update.message.reply_text(f'❌ Превышен лимит попыток авторизации. Авторизация заблокирована на {time_text}.')
        else:
            web_app_url = os.getenv('WEB_APP_URL', 'https://synthosaicreativestudio-maker.github.io/marketing/')
            keyboard = [[InlineKeyboardButton('Повторить авторизацию', web_app=WebAppInfo(url=web_app_url))]]
            await update.message.reply_text(
                f'❌ Неверные данные или аккаунт неактивен.\nОсталось попыток: {attempts_left}',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

async def new_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Очищаем все данные пользователя, включая кэш авторизации
    context.user_data.clear()
    refresh_authorized_cache()  # Принудительно обновляем кэш авторизованных пользователей
    
    logger.info(f'/new_chat от {user.id} - кэш очищен')
    
    # Проверяем авторизацию заново
    if await is_user_authorized(user.id, context):
        await update.message.reply_text('История диалога сброшена. Вы авторизованы и можете продолжить работу.')
    else:
        await update.message.reply_text('История диалога сброшена. Для работы требуется авторизация.')
        # Показываем кнопку авторизации
        web_app_url = os.getenv('WEB_APP_URL', 'https://synthosaicreativestudio-maker.github.io/marketing/')
        keyboard = [[InlineKeyboardButton('Авторизоваться', web_app=WebAppInfo(url=web_app_url))]]
        await update.message.reply_text('Нажмите кнопку для авторизации:', reply_markup=InlineKeyboardMarkup(keyboard))


async def reply_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Specialist can reply using: /reply <код> <текст ответа>
    This will append the specialist's reply to the same ticket cell and forward the message to the user with that code.
    """
    user = update.effective_user
    # Only allow authorized specialists/admins
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
        # find the ticket row by code and append specialist message
        if not tickets_client or not tickets_client.sheet:
            await update.message.reply_text('Tickets sheet не доступен.')
            return
        row = tickets_client.find_row_by_code(code)
        if not row:
            await update.message.reply_text(f'Тикет с кодом {code} не найден.')
            return
        # Append to ticket cell as specialist
        # We will read telegram_id from the row to forward the message
        telegram_id = tickets_client.sheet.cell(row, 4).value
        tickets_client.upsert_ticket(telegram_id=str(telegram_id), code=code, phone='', fio='', text=reply_text, sender_type='specialist', handled=False)
        # Forward message to user (if telegram_id present)
        if telegram_id:
            try:
                await context.bot.send_message(chat_id=int(telegram_id), text=f'Ответ специалиста (код {code}):\n{reply_text}')
            except Exception as e:
                logger.error(f'Не удалось отправить сообщение пользователю {telegram_id}: {e}')
        await update.message.reply_text('Ответ добавлен в тикет и отправлен пользователю.')
    except Exception as e:
        logger.error(f'Ошибка в /reply: {e}')
        await update.message.reply_text('Ошибка при добавлении ответа.')


async def setstatus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allow admin/specialist to set status: /setstatus <код|row> <статус>"""
    user = update.effective_user
    if not await is_user_authorized(user.id, context) and not is_admin(user.id):
        await update.message.reply_text('Недостаточно прав для изменения статуса.')
        return
    if len(context.args) < 2:
        await update.message.reply_text('Использование: /setstatus <код> <статус>')
        return
    key = context.args[0]
    status = ' '.join(context.args[1:])
    try:
        # Try interpret key as integer row index
        row = None
        if key.isdigit():
            row = int(key)
        success = tickets_client.set_ticket_status(row=row, code=(None if row else key), status=status)
        if success:
            await update.message.reply_text(f'Статус для {key} обновлен на "{status}"')
        else:
            await update.message.reply_text('Не удалось обновить статус (тикет не найден или ошибка).')
    except Exception as e:
        logger.error(f'Ошибка в /setstatus: {e}')
        await update.message.reply_text('Ошибка при обновлении статуса.')


async def push_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для очистки кэша авторизаций и принудительного обновления"""
    user = update.effective_user
    
    # Очищаем глобальный кэш авторизаций
    AUTH_CACHE['ids'] = set()
    AUTH_CACHE['ts'] = 0
    
    # Принудительно обновляем кэш
    refresh_authorized_cache()
    
    logger.info(f'/push от {user.id} - кэш авторизаций очищен и обновлен')
    
    # Проверяем авторизацию заново
    if await is_user_authorized(user.id, context):
        await update.message.reply_text('Кэш очищен. Вы авторизованы.')
    else:
        await update.message.reply_text('Кэш очищен. Требуется авторизация.')
        # Показываем кнопку авторизации
        web_app_url = os.getenv('WEB_APP_URL', 'https://synthosaicreativestudio-maker.github.io/marketing/')
        keyboard = [[InlineKeyboardButton('Авторизоваться', web_app=WebAppInfo(url=web_app_url))]]
        await update.message.reply_text('Нажмите кнопку для авторизации:', reply_markup=InlineKeyboardMarkup(keyboard))


def _get_ticket_row_by_code_or_telegram(code: str | None, telegram_id: str | None) -> int | None:
    try:
        if code:
            row = tickets_client.find_row_by_code(code)
            if row:
                return row
        if telegram_id:
            try:
                cell = tickets_client.sheet.find(str(telegram_id), in_column=4)
                if cell:
                    return cell.row
            except Exception:
                return None
    except Exception:
        return None
    return None


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
        telegram_id = tickets_client.sheet.cell(row, 4).value
    except Exception:
        telegram_id = None
    if action == 'transfer':
        ok = tickets_client.set_ticket_status(row=row, status='в работе')
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
        ok = tickets_client.set_ticket_status(row=row, status='выполнено')
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
    
    from telegram import ReplyKeyboardMarkup, KeyboardButton
    persistent_keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton('Личный кабинет')]],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    if not await is_user_authorized(user.id, context):
        await update.message.reply_text('Вы не авторизованы. Сначала пройдите авторизацию.')
        return
    text = update.message.text
    # Если пользователь нажал на persistent кнопку
    if text.strip().lower() == 'личный кабинет':
        # Build Web App buttons so the user opens the mini‑app directly (deep link to a section)
        web_app_base = os.getenv('WEB_APP_URL', 'https://synthosaicreativestudio-maker.github.io/marketing/')
        keyboard = []
        for section in SECTIONS:
            params = urlencode({'section': section})
            url = f"{web_app_base.rstrip('/')}?{params}"
            keyboard.append([InlineKeyboardButton(section, web_app=WebAppInfo(url=url))])
        keyboard.append([InlineKeyboardButton('Открыть миниапп', web_app=WebAppInfo(url=web_app_base))])
        # Send inline WebApp menu; the persistent ReplyKeyboardMarkup remains available on client
        await update.message.reply_text('Откройте личный кабинет для выбора раздела', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    # Простая реализация: отправляем запрос только в OpenAI Assistant
    if not openai.api_key:
        await update.message.reply_text('OpenAI ключ не настроен. Обратитесь к администратору.', reply_markup=persistent_keyboard)
        return
    
    assistant_id = os.getenv('OPENAI_ASSISTANT_ID')
    if not assistant_id:
        await update.message.reply_text('OpenAI Assistant не настроен. Обратитесь к администратору.', reply_markup=persistent_keyboard)
        return

    # Делать вызов OpenAI с семафором и retry/backoff
    async with OPENAI_SEMAPHORE:
        retry = 0
        max_retry = int(os.getenv('OPENAI_MAX_RETRY', '2'))
        backoff_base = float(os.getenv('OPENAI_BACKOFF_BASE', '0.8'))
        while True:
            try:
                assistant_msg = None
                # Используем только OpenAI Assistant API
                if assistant_id and tickets_client and tickets_client.sheet:
                    code = context.user_data.get('partner_code', '')
                    telegram_id = str(update.effective_user.id)
                    thread_id = tickets_client.get_thread_id(code=code) if code else tickets_client.get_thread_id(row=None, code=None)
                    if not thread_id:
                        thread_id = _create_or_get_thread(assistant_id=assistant_id, code=code or None, telegram_id=telegram_id)
                        if thread_id:
                            try:
                                tickets_client.upsert_ticket(telegram_id=telegram_id, code=code, phone=context.user_data.get('phone',''), fio=f"{update.effective_user.first_name or ''} {update.effective_user.last_name or ''}".strip(), text=text, status='в работе')
                                row = tickets_client.find_row_by_code(code) if code else None
                                tickets_client.set_thread_id(row=row, code=code or None, thread_id=thread_id)
                            except Exception as e:
                                logger.debug(f'Не удалось сохранить thread_id в таблицу: {e}')
                    if thread_id:
                        logger.info(f'Sending message to OpenAI Assistant thread {thread_id}: {text[:100]}...')
                        assistant_msg = _send_message_in_thread(assistant_id=assistant_id, thread_id=thread_id, text=text)
                        logger.info(f'Received response from Assistant: {assistant_msg[:100] if assistant_msg else "None"}...')
                
                if not assistant_msg:
                    await update.message.reply_text('Ошибка получения ответа от ассистента. Попробуйте позже.', reply_markup=persistent_keyboard)
                    return
                    
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
        if not locals().get('assistant_msg'):
            logger.error('OpenAI Assistant не вернул ответ')
            await update.message.reply_text('Ассистент не ответил. Попробуйте ещё раз.', reply_markup=persistent_keyboard)
            return
        
        # OpenAI Assistant управляет своей историей, не нужно сохранять в context.user_data
        buttons = None
        try:
            code = context.user_data.get('partner_code', '')
            row = tickets_client.find_row_by_code(code) if code else None
            if not row:
                try:
                    cell = tickets_client.sheet.find(str(update.effective_user.id), in_column=4)
                    row = cell.row if cell else None
                except Exception:
                    row = None
            if row:
                # Создаем кнопку для личного кабинета
                web_app_base = os.getenv('WEB_APP_URL', 'https://synthosaicreativestudio-maker.github.io/marketing/')
                menu_url = f"{web_app_base.rstrip('/')}#view=menu2"
                buttons = [
                    [InlineKeyboardButton('Перевести специалисту', callback_data=f't:transfer:{row}'), InlineKeyboardButton('Выполнено', callback_data=f't:done:{row}')],
                    [InlineKeyboardButton('Личный кабинет', web_app=WebAppInfo(url=menu_url))]
                ]
        except Exception:
            buttons = None
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
        
        # Replace unwanted text patterns
        assistant_msg = assistant_msg.replace('annotations value', 'Вера')
        logger.info(f'Sending response to user. Has buttons: {buttons is not None}. Message: {assistant_msg[:100]}...')
        if buttons:
            # Send message with inline action buttons; persistent keyboard remains available to the user
            await update.message.reply_text(assistant_msg, reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await update.message.reply_text(assistant_msg, reply_markup=persistent_keyboard)
        # Always log to Обращения sheet via tickets_client
        try:
            if tickets_client and tickets_client.sheet:
                telegram_id = update.effective_user.id
                code = context.user_data.get('partner_code', '')
                phone = context.user_data.get('phone', '')
                fio = f"{update.effective_user.first_name or ''} {update.effective_user.last_name or ''}".strip()
                tickets_client.upsert_ticket(telegram_id=str(telegram_id), code=code, phone=phone, fio=fio, text=assistant_msg, sender_type='assistant', handled=False)
        except Exception as e:
            logger.error(f'Не удалось записать ответ ассистента в tickets: {e}')
    
    logger.info(f'Completed processing message {message_id} from user {user.id}')

# Запуск
def main():
    # Prevent multiple instances
    lock_file = 'bot.lock'
    try:
        lock_fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR)
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        logger.info('Successfully acquired lock, starting bot...')
    except (OSError, IOError) as e:
        logger.error(f'Another bot instance is already running or cannot acquire lock: {e}')
        return
    
    try:
        token = os.getenv('TELEGRAM_TOKEN')
        if not token:
            logger.error('TELEGRAM_TOKEN не задан в .env')
            return
        if not check_openai_connection():
            logger.error('OpenAI не доступен — прерывание старта бота')
            return
        app = Application.builder().token(token).build()
        app.add_handler(CommandHandler('start', start))
        app.add_handler(CommandHandler('new_chat', new_chat))
        app.add_handler(CommandHandler('reply', reply_command))
        app.add_handler(CommandHandler('setstatus', setstatus_command))
        app.add_handler(CommandHandler('push', push_command))
        app.add_handler(CallbackQueryHandler(handle_callback_query))
        app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_handler(CommandHandler('menu', menu_command))
        app.add_handler(CallbackQueryHandler(handle_menu_callback, pattern=r'^menu:'))
        logger.info('Бот запущен...')
        # Global error handler to catch exceptions produced inside the Application's network loop.
        # The library logs exceptions if no error handler is registered; that leads to noisy 409 logs.
        async def _global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
            err = getattr(context, 'error', None)
            try:
                if isinstance(err, telegram.error.Conflict):
                    # Conflict means another client is currently calling getUpdates for the same token.
                    logger.warning(f'GetUpdates conflict (caught in error handler): {err} — sleeping briefly and will let polling retry.')
                    # Small sleep to avoid busy-looping; the outer polling loop will handle longer backoff.
                    await asyncio.sleep(5)
                    return
            except Exception:
                # If something unexpected happens while handling the error, log it and continue.
                logger.exception('Error in global error handler')
            # For all other errors, log full traceback so maintainers can inspect.
            logger.exception(f'Unhandled exception in update handling: {err}')

        # Register the handler so the Application doesn't print uncaught exceptions for every getUpdates conflict.
        app.add_error_handler(_global_error_handler)

        # Run polling with drop_pending_updates to clear any pending updates and reduce chance of immediate conflicts.
        # Keep an outer retry/backoff to cope with remote clients that may briefly hold getUpdates.
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
    finally:
        # Cleanup lock file
        try:
            os.close(lock_fd)
            os.unlink(lock_file)
            logger.info('Lock file cleaned up')
        except Exception as e:
            logger.warning(f'Failed to cleanup lock file: {e}')

if __name__ == '__main__':
    main()