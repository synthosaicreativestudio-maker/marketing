import os
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from error_handler import safe_handler
from ai_service import AIService

logger = logging.getLogger(__name__)


def register_admin_handlers(application, ai_service: AIService):
    """Р РµРіРёСЃС‚СЂР°С†РёСЏ Р°РґРјРёРЅ-РєРѕРјР°РЅРґ."""
    application.add_handler(CommandHandler("rag_refresh", rag_refresh_handler(ai_service)))


def _is_admin(user_id: int) -> bool:
    admin_id = os.getenv("ADMIN_TELEGRAM_ID", "").strip()
    return admin_id.isdigit() and int(admin_id) == user_id


def rag_refresh_handler(ai_service: AIService):
    """Р¤Р°Р±СЂРёРєР° РґР»СЏ РєРѕРјР°РЅРґС‹ /rag_refresh (СЂСѓС‡РЅР°СЏ РїРµСЂРµРёРЅРґРµРєСЃР°С†РёСЏ RAG)."""
    @safe_handler
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        if not _is_admin(user.id):
            await update.message.reply_text("РљРѕРјР°РЅРґР° РґРѕСЃС‚СѓРїРЅР° С‚РѕР»СЊРєРѕ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂСѓ.")
            return

        if os.getenv("RAG_DISABLED", "false").lower() in ("1", "true", "yes", "y"):
            await update.message.reply_text("RAG временно отключен. Переиндексация недоступна.")
            return

        await update.message.reply_text("Р—Р°РїСѓСЃРєР°СЋ РїРµСЂРµРёРЅРґРµРєСЃР°С†РёСЋ Р±Р°Р·С‹ Р·РЅР°РЅРёР№. Р­С‚Рѕ РјРѕР¶РµС‚ Р·Р°РЅСЏС‚СЊ РЅРµСЃРєРѕР»СЊРєРѕ РјРёРЅСѓС‚.")
        try:
            ok = await ai_service.refresh_knowledge_base()
            if ok:
                await update.message.reply_text("РџРµСЂРµРёРЅРґРµРєСЃР°С†РёСЏ Р·Р°РІРµСЂС€РµРЅР°.")
            else:
                await update.message.reply_text("РќРµ СѓРґР°Р»РѕСЃСЊ Р·Р°РїСѓСЃС‚РёС‚СЊ РїРµСЂРµРёРЅРґРµРєСЃР°С†РёСЋ (RAG РЅРµРґРѕСЃС‚СѓРїРµРЅ).")
        except Exception as e:
            logger.error(f"/rag_refresh failed: {e}", exc_info=True)
            await update.message.reply_text("РћС€РёР±РєР° РїСЂРё РїРµСЂРµРёРЅРґРµРєСЃР°С†РёРё. РџСЂРѕРІРµСЂСЊС‚Рµ Р»РѕРіРё.")

    return handler
