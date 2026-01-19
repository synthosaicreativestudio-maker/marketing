import logging
import time
import asyncio
import os
import json
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from auth_service import AuthService
from ai_service import AIService
from appeals_service import AppealsService
from error_handler import safe_handler
from utils import create_specialist_button, _is_user_escalation_request
from config import settings

logger = logging.getLogger(__name__)

def register_chat_handlers(application, auth_service, ai_service, appeals_service):
    """Регистрация обработчиков чата."""
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.StatusUpdate.WEB_APP_DATA, 
        chat_handler(auth_service, ai_service, appeals_service)
    ))

def chat_handler(auth_service: AuthService, ai_service: AIService, appeals_service: AppealsService):
    """Основной обработчик общения с ИИ."""
    @safe_handler
    async def handle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        text = update.effective_message.text or ""
        
        # 1. Проверка авторизации
        auth_status = await auth_service.get_user_auth_status(user.id)
        if not auth_status:
            await update.message.reply_text("❌ Требуется авторизация. Нажмите /start.")
            return

        # 2. Логирование обращения в таблицу (если включено)
        if settings.ENABLE_APPEALS and appeals_service and appeals_service.is_available():
            asyncio.create_task(_create_appeal_entry(user, text, auth_service, appeals_service))

        # 3. Проверка на запрос специалиста
        if _is_user_escalation_request(text):
            await update.message.reply_text(
                "Ваш запрос передан специалисту. Ожидайте ответа.",
                reply_markup=create_specialist_button()
            )
            return

        # 4. Проверка режима специалиста (пассивный режим)
        if await _is_specialist_mode(user.id, appeals_service):
            return

        # 5. Проверка доступности ИИ
        if not ai_service or not ai_service.is_enabled() or not settings.ENABLE_AI_CHAT:
            await update.message.reply_text("Ассистент временно недоступен. Специалист ответит позже.")
            return

        # 6. Подготовка контекста и стриминг
        await _process_ai_response(update, context, ai_service, appeals_service, text)

    return handle_chat

async def _create_appeal_entry(user, text, auth_service, appeals_service):
    """Фоновое создание записи в таблице обращений."""
    try:
        # Упрощенное получение данных (для Phase 2 можно оптимизировать кешированием)
        records = await auth_service.gateway.get_all_records(auth_service.worksheet)
        user_data = next((r for r in records if str(r.get('Telegram ID')) == str(user.id)), None)
        
        if user_data:
            await appeals_service.create_appeal(
                code=user_data.get('Код партнера', ''),
                phone=user_data.get('Телефон партнера', ''),
                fio=user_data.get('ФИО партнера', ''),
                telegram_id=user.id,
                text=f"Пользователь: {text}"
            )
    except Exception as e:
        logger.error(f"Ошибка создания обращения в чате: {e}")

async def _is_specialist_mode(user_id, appeals_service):
    """Проверка, не общается ли пользователь уже с человеком."""
    if not appeals_service or not appeals_service.is_available():
        return False
    try:
        status = await appeals_service.get_appeal_status(user_id)
        status = str(status or '').lower()
        return "в работе" in status or "передано" in status
    except Exception as e:
        logger.debug(f"_is_specialist_mode: {e}", exc_info=True)
        return False

async def _process_ai_response(update, context, ai_service, appeals_service, text):
    """Стриминг ответа от ИИ."""
    user = update.effective_user
    
    # Контекстуальное приветствие
    now = time.time()
    last = context.user_data.get('last_interaction_timestamp', 0)
    context.user_data['last_interaction_timestamp'] = now
    
    instruction = "\n\n[SYSTEM: Продолжение диалога]" if (now - last) < 28800 else "\n\n[SYSTEM: Новая сессия]"
    
    status_msg = await update.message.reply_text("⏳ *Синта печатает...*", parse_mode='Markdown')
    
    full_response = ""
    last_update = 0
    
    try:
        async for chunk in ai_service.ask_stream(user.id, text + instruction):
            if chunk.startswith("__TOOL_CALL__"):
                continue
            
            full_response += chunk
            if (time.time() - last_update) > 1.5:
                try:
                    await status_msg.edit_text(full_response[:3900] + " ▌", parse_mode='Markdown')
                    last_update = time.time()
                except Exception as e:
                    # При ошибке парсинга Markdown пробуем без форматирования
                    if "Can't parse entities" in str(e) or "parse" in str(e).lower():
                        try:
                            await status_msg.edit_text(full_response[:3900] + " ▌", parse_mode=None)
                            last_update = time.time()
                        except Exception as inner:
                            logger.debug(f"Fallback edit_text (parse_mode=None): {inner}", exc_info=True)
                    else:
                        logger.debug(f"edit_text during stream: {e}", exc_info=True)
        
        # Финализация
        is_esc = "[ESCALATE_ACTION]" in full_response
        clean_response = full_response.replace("[ESCALATE_ACTION]", "").strip()
        markup = create_specialist_button() if is_esc else None
        
        # Пытаемся отправить с Markdown, при ошибке парсинга - без форматирования
        try:
            await status_msg.edit_text(clean_response, reply_markup=markup, parse_mode='Markdown')
        except Exception as parse_error:
            if "Can't parse entities" in str(parse_error) or "parse" in str(parse_error).lower():
                logger.warning(f"Markdown parsing error, sending as plain text: {parse_error}")
                # Отправляем без Markdown форматирования
                await status_msg.edit_text(clean_response, reply_markup=markup, parse_mode=None)
            else:
                raise
        
        # Фоновое логирование
        if settings.LOG_TO_SHEETS:
            asyncio.create_task(_safe_background_log(user.id, text, clean_response, appeals_service))
            
    except Exception as e:
        logger.error(f"Ошибка стриминга ИИ: {e}")
        await status_msg.edit_text("⚠️ Ошибка связи с ИИ. Попробуйте позже.")

async def _safe_background_log(user_id, text, reply, appeals_service):
    """Логирование диалога."""
    # Локально
    if settings.LOG_TO_LOCAL_FILE:
        try:
            os.makedirs("logs", exist_ok=True)
            with open("logs/chat_history.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps({"uid": user_id, "q": text, "a": reply}, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.debug(f"_safe_background_log (local file): {e}", exc_info=True)

    # В таблицу
    if appeals_service and appeals_service.is_available():
        try:
            await appeals_service.add_user_message(user_id, text)
            await appeals_service.add_ai_response(user_id, reply)
        except Exception as e:
            logger.debug(f"_safe_background_log (Sheets): {e}", exc_info=True)
