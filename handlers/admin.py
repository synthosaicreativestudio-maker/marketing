import os
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from error_handler import safe_handler
from ai_service import AIService

logger = logging.getLogger(__name__)


def register_admin_handlers(application, ai_service: AIService):
    """Регистрация админ-команд."""
    application.add_handler(CommandHandler("rag_refresh", rag_refresh_handler(ai_service)))


def _is_admin(user_id: int) -> bool:
    admin_id = os.getenv("ADMIN_TELEGRAM_ID", "").strip()
    return admin_id.isdigit() and int(admin_id) == user_id


def rag_refresh_handler(ai_service: AIService):
    """Фабрика для команды /rag_refresh (ручная переиндексация RAG)."""
    @safe_handler
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        if not _is_admin(user.id):
            await update.message.reply_text("Команда доступна только администратору.")
            return

        await update.message.reply_text("Запускаю переиндексацию базы знаний. Это может занять несколько минут.")
        try:
            ok = await ai_service.refresh_knowledge_base()
            if ok:
                await update.message.reply_text("Переиндексация завершена.")
            else:
                await update.message.reply_text("Не удалось запустить переиндексацию (RAG недоступен).")
        except Exception as e:
            logger.error(f"/rag_refresh failed: {e}", exc_info=True)
            await update.message.reply_text("Ошибка при переиндексации. Проверьте логи.")

    return handler
