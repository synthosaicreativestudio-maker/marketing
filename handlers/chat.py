import logging
import time
import asyncio
import os
import json
import re
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from auth_service import AuthService
from ai_service import AIService
from appeals_service import AppealsService
from error_handler import safe_handler
from utils import create_specialist_button, sanitize_ai_text_plain, sanitize_ai_text
from config import settings
from rate_limiter import check_rate_limit
from query_classifier import classify_query, QueryComplexity, should_use_rag, should_use_memory
from escalation_manager import (
    check_escalation, EscalationLevel, 
    get_clarification_message, get_escalation_success_message, reset_escalation
)

logger = logging.getLogger(__name__)

def register_chat_handlers(application, auth_service, ai_service, appeals_service, profile_manager=None):
    """Регистрация обработчиков чата."""
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.StatusUpdate.WEB_APP_DATA, 
        chat_handler(auth_service, ai_service, appeals_service, profile_manager)
    ))

    # Регистрация команды обновления базы знаний
    from telegram.ext import CommandHandler
    application.add_handler(CommandHandler(
        "refresh_kb", 
        refresh_kb_handler(ai_service)
    ))

def chat_handler(auth_service: AuthService, ai_service: AIService, appeals_service: AppealsService, profile_manager=None):
    """Основной обработчик общения с ИИ."""
    @safe_handler
    async def handle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        text = update.effective_message.text or ""
        
        # 0. Rate Limiting (защита от спама)
        allowed, remaining = check_rate_limit(user.id)
        if not allowed:
            await update.message.reply_text(
                "⚠️ Слишком много сообщений! Подождите минуту и попробуйте снова."
            )
            return
        
        # 1. Проверка авторизации
        auth_status = await auth_service.get_user_auth_status(user.id)
        if not auth_status:
            await update.message.reply_text("❌ Требуется авторизация. Нажмите /start.")
            return

        # 2. Логирование обращения в таблицу (если включено)
        if settings.ENABLE_APPEALS and appeals_service and appeals_service.is_available():
            asyncio.create_task(_create_appeal_entry(user, text, auth_service, appeals_service))

        # --- USER PROFILE: Update & Load ---
        profile_context = ""
        if profile_manager:
            try:
                # Update basic info from Telegram
                await profile_manager.update_profile(user.id, {
                    "first_name": user.first_name,
                    "username": user.username,
                    "last_seen": time.strftime("%Y-%m-%d %H:%M:%S")
                })
                profile_context = await profile_manager.get_system_context(user.id)
            except Exception as e:
                logger.error(f"Error handling profile for {user.id}: {e}")

        # 3. Классификация запроса
        complexity, reason = classify_query(text)

        # Короткий ответ на приветствие/благодарность без ИИ
        if reason == "greeting_or_acknowledgment":
            await update.message.reply_text(
                "Здравствуйте! Я Галина, помощник по маркетингу. Чем могу помочь? 🙂✨"
            )
            return

        # Быстрые короткие сообщения — считаем простыми (даже если с вопросом)
        if len(text.strip()) < 20 and complexity == QueryComplexity.MEDIUM:
            complexity, reason = QueryComplexity.SIMPLE, "short_message"

        # Уровень каскада 1–4 (5-й включается по эскалации)
        cascade_level = 1 if reason == "greeting_or_acknowledgment" and complexity == QueryComplexity.SIMPLE else \
                        2 if complexity == QueryComplexity.SIMPLE else \
                        3 if complexity == QueryComplexity.MEDIUM else 4

        logger.info(f"Query classified as {complexity.name} (reason: {reason}, level: {cascade_level}) for user {user.id}")

        # 4. Двухуровневая система эскалации
        escalation_level = check_escalation(user.id, text)
        force_escalation = False

        if escalation_level == EscalationLevel.CONFIRMED:
            # Для сложных запросов: отвечаем + эскалация (уровень 5)
            if complexity == QueryComplexity.COMPLEX:
                force_escalation = True
                cascade_level = 5
            else:
                # Немедленная эскалация — даём кнопку
                await update.message.reply_text(
                    get_escalation_success_message(),
                    reply_markup=create_specialist_button()
                )
                # Обновляем статус в таблице
                if appeals_service and appeals_service.is_available():
                    try:
                        await appeals_service.set_status(user.id, "Передано специалисту")
                    except Exception as e:
                        logger.error(f"Ошибка обновления статуса эскалации: {e}")
                reset_escalation(user.id)
                return
        elif escalation_level == EscalationLevel.CLARIFYING:
            # Уровень 1: Уточняем тему
            await update.message.reply_text(get_clarification_message())
            return

        # 5. Проверка режима специалиста (пассивный режим)
        if await _is_specialist_mode(user.id, appeals_service):
            return

        # 6. Проверка доступности ИИ
        if not ai_service or not ai_service.is_enabled() or not settings.ENABLE_AI_CHAT:
            await update.message.reply_text("Ассистент временно недоступен. Специалист ответит позже.")
            return

        # 7. Адаптация контекста в зависимости от уровня
        use_rag = cascade_level >= 3 and should_use_rag(complexity)
        if os.getenv("RAG_DISABLED", "false").lower() in ("1", "true", "yes", "y"):
            use_rag = False
        use_memory = cascade_level >= 4 and should_use_memory(complexity)

        # Для простых запросов не используем память
        if not use_memory:
            profile_context = ""

        # 8. Подготовка и стриминг ответа
        await _process_ai_response(
            update, context, ai_service, appeals_service, text,
            profile_context, complexity, use_rag, cascade_level, force_escalation
        )

    return handle_chat

async def _create_appeal_entry(user, text, auth_service, appeals_service):
    """Фоновое создание записи в таблице обращений."""
    if not getattr(auth_service, 'worksheet', None):
        logger.debug("_create_appeal_entry: worksheet не инициализирован, пропуск")
        return
    try:
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

def _limit_sentences(text: str, max_sentences: int) -> str:
    if not text:
        return text
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    if len(parts) <= max_sentences:
        return text.strip()
    return " ".join(parts[:max_sentences]).strip()

def _wants_details(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in (
        "подроб", "инструкц", "пошаг", "шаг", "как сделать", "гайд",
        "полный", "детал", "опиши", "распиши", "пример", "шаблон"
    ))

def _wants_links(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in ("ссылка", "ссылки", "где найти", "дай ссылк", "кинь ссылк", "контакт", "телефон"))

async def _process_ai_response(update, context, ai_service, appeals_service, text, profile_context="", complexity=None, use_rag=True, cascade_level=2, force_escalation=False):
    """Стриминг ответа от ИИ с таймаутом и graceful degradation."""
    user = update.effective_user
    
    # Бизнес-правила ответа хранятся в системном промпте, здесь без переопределений.
    instruction = ""

    # Контекстуальное приветствие для средних и сложных
    if cascade_level >= 3:
        now = time.time()
        last = context.user_data.get('last_interaction_timestamp', 0)
        context.user_data['last_interaction_timestamp'] = now

        # Контекст профиля (без бизнес-правил формата/стиля)
        if user.first_name:
            instruction += f"\nИмя пользователя: {user.first_name}."
        instruction += profile_context
    
    # Для простых запросов не загружаем историю из таблицы
    table_history_task = None
    if complexity != QueryComplexity.SIMPLE and use_rag:
        table_history_task = asyncio.create_task(appeals_service.get_raw_history(user.id)) if appeals_service and appeals_service.is_available() else None
    
    status_msg = await update.message.reply_text("⏳ Галина печатает...")
    
    table_history = ""
    if table_history_task:
        try:
            table_history = await table_history_task
            if table_history:
                logger.info(f"Context recovered from Table for {user.id} (len: {len(table_history)})")
        except Exception as e:
            logger.error(f"Error recovering history from Table: {e}")

    full_response = ""
    last_update = 0
    STREAM_TOTAL_TIMEOUT = 120  # 2 минуты на весь ответ
    stream_start_time = time.time()

    try:
        async for chunk in ai_service.ask_stream(user.id, text + instruction, external_history=table_history):
            # Проверка таймаута вручную (совместимо с Python 3.10)
            if time.time() - stream_start_time > STREAM_TOTAL_TIMEOUT:
                raise asyncio.TimeoutError(f"Stream timeout after {STREAM_TOTAL_TIMEOUT}s")
            
            if chunk.startswith("__TOOL_CALL__"):
                continue
            
            full_response += chunk
            if (time.time() - last_update) > 1.5:
                display_text = sanitize_ai_text_plain(full_response, ensure_emojis=True)
                try:
                    display_text_truncated = display_text[:3900]
                    await status_msg.edit_text(display_text_truncated + " ▌")
                    last_update = time.time()
                except Exception as e:
                    logger.debug(f"edit_text during stream: {e}", exc_info=True)
        
        # Финализация
        is_esc = "[ESCALATE_ACTION]" in full_response
        clean_response = full_response.replace("[ESCALATE_ACTION]", "").strip()
        clean_response_plain = sanitize_ai_text_plain(clean_response, ensure_emojis=True)
        clean_response_html = sanitize_ai_text(clean_response, ensure_emojis=True)

        # Вариант A: не сокращаем ответы — отдаём полный сценарий

        # Эскалация для уровня 5
        if force_escalation and "[ESCALATE_ACTION]" not in full_response:
            is_esc = True
            clean_response_plain = f"{clean_response_plain}\n\nЕсли нужна помощь специалиста — передам."
            clean_response_html = sanitize_ai_text(clean_response_plain, ensure_emojis=True)

        markup = create_specialist_button() if is_esc else None
        
        # Разделение длинных сообщений (Telegram limit 4096)
        if len(clean_response_html) > 4096:
            # Разбиваем на части по 4000 символов для безопасности
            parts = [clean_response_plain[i:i+4000] for i in range(0, len(clean_response_plain), 4000)]
            
            # Первая часть редактирует сообщение с "печатает..."
            await status_msg.edit_text(parts[0], reply_markup=None if len(parts) > 1 else markup)
            
            # Остальные части отправляем новыми сообщениями
            for i, part in enumerate(parts[1:]):
                # Кнопки только к последнему сообщению
                current_markup = markup if i == len(parts) - 2 else None
                await update.message.reply_text(part, reply_markup=current_markup)
        else:
            # Штатный режим (короткое сообщение)
            await status_msg.edit_text(clean_response_html, reply_markup=markup, parse_mode="HTML")
        
        # Авто-эскалация для уровня 5
        if force_escalation and appeals_service and appeals_service.is_available():
            try:
                await appeals_service.set_status(user.id, "Передано специалисту")
            except Exception as e:
                logger.debug(f"force_escalation: {e}", exc_info=True)
            reset_escalation(user.id)

        # Фоновое логирование
        if settings.LOG_TO_SHEETS:
            asyncio.create_task(_safe_background_log(user.id, text, clean_response, appeals_service))
    
    except asyncio.TimeoutError:
        logger.error(f"Stream timeout ({STREAM_TOTAL_TIMEOUT}s) for user {user.id}")
        # Graceful degradation: предлагаем специалиста
        await status_msg.edit_text(
            "⚠️ Превышено время ожидания ответа. Специалист скоро ответит.",
            reply_markup=create_specialist_button()
        )
        # Автоматическая эскалация
        if appeals_service and appeals_service.is_available():
            try:
                await appeals_service.set_status(user.id, "Передано специалисту")
            except Exception:
                pass
            
    except Exception as e:
        logger.error(f"Ошибка стриминга ИИ: {e}")
        # Graceful degradation: предлагаем специалиста при любой ошибке
        await status_msg.edit_text(
            "⚠️ ИИ временно недоступен. Специалист скоро ответит.",
            reply_markup=create_specialist_button()
        )
        
        # ALERT ADMIN: Отправляем уведомление об ошибке
        from utils import alert_admin
        error_details = str(e)[:200]
        await alert_admin(
            context.bot,
            f"Ошибка AI Chat\nUser: {user.id}\nError: {error_details}",
            level="ERROR"
        )

        # Автоматическая эскалация
        if appeals_service and appeals_service.is_available():
            try:
                await appeals_service.set_status(user.id, "Передано специалисту")
            except Exception:
                pass

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

def refresh_kb_handler(ai_service: AIService):
    """Обработчик команды /refresh_kb."""
    @safe_handler
    async def handle_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        
        # Support multiple admin IDs (comma-separated)
        admin_ids_str = os.getenv("ADMIN_TELEGRAM_IDS", os.getenv("ADMIN_TELEGRAM_ID", ""))
        admin_ids = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip().isdigit()]
        
        if user_id not in admin_ids:
            await update.message.reply_text("⛔ У вас нет прав для выполнения этой команды.")
            return
            
        status_msg = await update.message.reply_text("🔄 Обновляю базу знаний... Это может занять пару минут.")
        
        try:
            success = await ai_service.refresh_knowledge_base()
            if success:
                # Даем немного времени на завершение фоновых задач загрузки в Gemini
                await update.message.reply_text("✅ База знаний успешно обновлена! Новые файлы теперь доступны ИИ.")
            else:
                await update.message.reply_text("❌ Ошибка при обновлении базы знаний (AIService не активен).")
        except Exception as e:
            logger.error(f"Error in refresh_kb_handler: {e}")
            await update.message.reply_text(f"❌ Произошла ошибка: {str(e)}")
        finally:
            try:
                await status_msg.delete()
            except Exception:
                pass

    return handle_refresh


