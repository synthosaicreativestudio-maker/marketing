"""
Модуль аналитики объектов недвижимости.

Обрабатывает запросы аналитики из Mini App:
1. Принимает код объекта через web_app_data
2. Записывает запрос в лист "Очередь" Google Sheets
3. Запускает polling для отслеживания статуса
4. Отправляет результат в чат пользователя
"""

import logging
import json
import asyncio
import uuid
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from auth_service import AuthService
from error_handler import safe_handler

logger = logging.getLogger(__name__)

# Константы
QUEUE_SHEET_NAME = "Очередь"
POLL_INTERVAL_SEC = 15       # Интервал проверки статуса
POLL_MAX_ATTEMPTS = 40       # Максимум проверок (~10 минут)
ANALYTICS_TIMEOUT_SEC = 600  # Таймаут 10 минут


def register_analytics_handlers(application, auth_service: AuthService):
    """Регистрация обработчиков аналитики."""
    application.add_handler(CommandHandler("analytics", analytics_command_handler(auth_service)))
    logger.info("Модуль Analytics: обработчики зарегистрированы")


def analytics_command_handler(auth_service: AuthService):
    """
    Обработчик команды /analytics <код_объекта>.
    Альтернатива отправке через Mini App.
    """
    @safe_handler
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user

        # Проверка авторизации
        auth_status = await auth_service.get_user_auth_status(user.id)
        if not auth_status:
            await update.message.reply_text(
                "⚠️ Для доступа к аналитике необходимо авторизоваться.\n"
                "Нажмите /start для входа."
            )
            return

        # Получаем код объекта из аргументов
        if not context.args:
            await update.message.reply_text(
                "📊 *Аналитика объекта недвижимости*\n\n"
                "Использование: `/analytics КОД_ОБЪЕКТА`\n\n"
                "Или откройте Mini App → вкладка «Аналитика».",
                parse_mode="Markdown"
            )
            return

        object_code = context.args[0].strip()
        chat_id = update.effective_chat.id

        await _process_analytics_request(update, context, object_code, chat_id, user)

    return handler


async def handle_analytics_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик данных из Mini App (action: analytics_request).
    Вызывается из web_app_data_handler в auth.py.
    """
    user = update.effective_user
    web_app_data = update.effective_message.web_app_data.data
    data = json.loads(web_app_data)

    object_code = data.get("object_code", "").strip()
    chat_id = update.effective_chat.id

    if not object_code:
        await update.message.reply_text("⚠️ Код объекта не указан.")
        return

    await _process_analytics_request(update, context, object_code, chat_id, user)


async def _process_analytics_request(update, context, object_code: str, chat_id: int, user) -> None:
    """Общая логика обработки запроса аналитики."""
    request_id = str(uuid.uuid4())[:8]

    # Подтверждение пользователю
    status_msg = await update.message.reply_text(
        f"📊 Запрос на анализ объекта `{object_code}` принят.\n"
        f"⏳ Обработка займёт 1–3 минуты.\n"
        f"Номер запроса: `{request_id}`",
        parse_mode="Markdown"
    )

    # Записываем в очередь Google Sheets
    try:
        queue_row = await _add_to_queue(
            context, request_id, object_code, chat_id, user
        )

        if not queue_row:
            await status_msg.edit_text(
                "❌ Не удалось добавить запрос в очередь.\n"
                "Попробуйте позже или обратитесь к администратору."
            )
            return

        # Запускаем polling в фоне
        asyncio.create_task(
            _poll_for_result(context, request_id, object_code, chat_id, status_msg)
        )

    except Exception as e:
        logger.error(f"Ошибка обработки аналитики: {e}", exc_info=True)
        await status_msg.edit_text(
            f"❌ Ошибка при создании запроса: {str(e)[:200]}\n"
            f"Попробуйте позже."
        )


async def _add_to_queue(context, request_id: str, object_code: str, chat_id: int, user) -> bool:
    """Добавляет запрос в лист 'Очередь' Google Sheets."""
    try:
        from sheets_gateway import AsyncGoogleSheetsGateway

        gateway = AsyncGoogleSheetsGateway(circuit_breaker_name='analytics')
        worksheet = await _get_queue_worksheet(gateway)

        if not worksheet:
            logger.error("Лист 'Очередь' не найден")
            return False

        now = datetime.now().isoformat()
        username = f"{user.first_name or ''} {user.last_name or ''}".strip()
        if user.username:
            username += f" (@{user.username})"

        row = [
            request_id,       # id
            now,               # created_at
            object_code,       # object_code
            str(chat_id),      # chat_id
            username,          # user
            "NEW",             # status
            "",                # started_at
            "",                # finished_at
            0,                 # tries
            "",                # error
            "",                # result_text
            "",                # eta_sec
        ]

        await gateway.append_row(worksheet, row)
        logger.info(f"Запрос {request_id} добавлен в очередь: код={object_code}, chat_id={chat_id}")
        return True

    except Exception as e:
        logger.error(f"Ошибка записи в очередь: {e}", exc_info=True)
        return False


async def _poll_for_result(
    context,
    request_id: str,
    object_code: str,
    chat_id: int,
    status_msg
) -> None:
    """
    Polling листа 'Очередь' для получения результата.
    Проверяет каждые POLL_INTERVAL_SEC секунд.
    """
    from sheets_gateway import AsyncGoogleSheetsGateway

    gateway = AsyncGoogleSheetsGateway(circuit_breaker_name='analytics')

    for attempt in range(POLL_MAX_ATTEMPTS):
        await asyncio.sleep(POLL_INTERVAL_SEC)

        try:
            worksheet = await _get_queue_worksheet(gateway)
            if not worksheet:
                continue

            # Читаем все записи (без кэша — нужны свежие данные)
            records = await gateway.get_all_records(worksheet, use_cache=False)

            # Ищем наш запрос по ID
            target = None
            for record in records:
                if str(record.get("id", "")).strip() == request_id:
                    target = record
                    break

            if not target:
                logger.warning(f"Запрос {request_id} не найден в очереди (попытка {attempt + 1})")
                continue

            status = str(target.get("status", "")).strip().upper()

            if status == "DONE":
                result_text = target.get("result_text", "")
                if result_text:
                    # Разбиваем длинный текст на части (Telegram лимит 4096 символов)
                    await _send_result(context, chat_id, object_code, result_text)
                    try:
                        await status_msg.edit_text(
                            f"✅ Анализ объекта `{object_code}` завершён!",
                            parse_mode="Markdown"
                        )
                    except Exception:
                        pass
                else:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"⚠️ Анализ объекта `{object_code}` завершён, но результат пуст.",
                        parse_mode="Markdown"
                    )
                return

            elif status == "ERROR":
                error_msg = target.get("error", "Неизвестная ошибка")
                try:
                    await status_msg.edit_text(
                        f"❌ Ошибка анализа объекта `{object_code}`:\n{error_msg[:500]}",
                        parse_mode="Markdown"
                    )
                except Exception:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"❌ Ошибка анализа объекта `{object_code}`:\n{error_msg[:500]}",
                        parse_mode="Markdown"
                    )
                return

            elif status == "PROCESSING" and attempt == 5:
                # Промежуточное обновление через ~75 секунд
                try:
                    await status_msg.edit_text(
                        f"📊 Объект `{object_code}` — анализ выполняется...\n"
                        f"⏳ Осталось ~1-2 минуты.",
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Ошибка polling (попытка {attempt + 1}): {e}")
            continue

    # Таймаут — результат не получен
    try:
        await status_msg.edit_text(
            f"⏰ Время ожидания анализа объекта `{object_code}` истекло.\n"
            f"Запрос остаётся в очереди и будет обработан.\n"
            f"Номер запроса: `{request_id}`",
            parse_mode="Markdown"
        )
    except Exception:
        pass


async def _send_result(context, chat_id: int, object_code: str, result_text: str) -> None:
    """Отправляет результат анализа в чат, разбивая при необходимости."""
    MAX_MSG_LEN = 4000  # Предел Telegram ~4096, оставляем запас

    header = f"📊 *Анализ объекта {object_code}*\n\n"
    full_text = header + result_text

    if len(full_text) <= MAX_MSG_LEN:
        await context.bot.send_message(
            chat_id=chat_id,
            text=full_text,
            parse_mode="Markdown"
        )
    else:
        # Разбиваем на части
        chunks = []
        text = result_text
        while text:
            if len(text) <= MAX_MSG_LEN - len(header):
                chunks.append(text)
                break
            # Ищем перенос строки для красивого разбиения
            split_pos = text.rfind('\n', 0, MAX_MSG_LEN - len(header))
            if split_pos == -1:
                split_pos = MAX_MSG_LEN - len(header)
            chunks.append(text[:split_pos])
            text = text[split_pos:].lstrip('\n')

        for i, chunk in enumerate(chunks):
            prefix = header if i == 0 else f"📊 *Продолжение ({i + 1}/{len(chunks)})*\n\n"
            await context.bot.send_message(
                chat_id=chat_id,
                text=prefix + chunk,
                parse_mode="Markdown"
            )
            await asyncio.sleep(0.5)  # Пауза между сообщениями


async def _get_queue_worksheet(gateway):
    """Получает worksheet 'Очередь' из таблицы аналитики."""
    import os
    import gspread
    from google.oauth2.service_account import Credentials

    try:
        analytics_sheet_id = os.environ.get("ANALYTICS_SHEET_ID")
        if not analytics_sheet_id:
            logger.error("ANALYTICS_SHEET_ID не задан в .env")
            return None

        sa_file = os.environ.get("GCP_SA_FILE", "credentials.json")

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file(sa_file, scopes=scopes)
        client = gspread.authorize(creds)

        spreadsheet = client.open_by_key(analytics_sheet_id)
        worksheet = spreadsheet.worksheet(QUEUE_SHEET_NAME)
        return worksheet

    except Exception as e:
        logger.error(f"Ошибка подключения к листу 'Очередь': {e}", exc_info=True)
        return None
