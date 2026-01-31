import logging
import json
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from auth_service import AuthService
from error_handler import safe_handler
from promotions_api import get_promotions_json, is_promotions_available
from sheets_gateway import AsyncGoogleSheetsGateway

logger = logging.getLogger(__name__)

def register_promotions_handlers(application, auth_service: AuthService, promotions_gateway=None):
    """Регистрация обработчиков акций."""
    application.add_handler(CommandHandler("promotions", promotions_command_handler(auth_service, promotions_gateway)))

def promotions_command_handler(auth_service: AuthService, promotions_gateway=None):
    """Фабрика для команды /promotions."""
    @safe_handler
    async def handle_promotions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user

        if not await auth_service.get_user_auth_status(user.id):
            await update.message.reply_text("Для просмотра акций требуется авторизация.")
            return

        gateway = promotions_gateway or AsyncGoogleSheetsGateway(circuit_breaker_name='promotions')
        if not await is_promotions_available(gateway):
            await update.message.reply_text("Система акций временно недоступна.")
            return

        try:
            promotions_json = await get_promotions_json(gateway)
            await _send_promotions(update, promotions_json)
        except Exception as e:
            logger.error(f"Ошибка акций: {e}")
            await update.message.reply_text("Ошибка при получении акций.")

    return handle_promotions

async def handle_promotions_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Запрос акций из WebApp."""
    try:
        promotions_gateway = AsyncGoogleSheetsGateway(circuit_breaker_name='promotions')
        if not await is_promotions_available(promotions_gateway):
            await update.message.reply_text("Система акций временно недоступна.")
            return
        
        promotions_json = await get_promotions_json(promotions_gateway)
        await _send_promotions(update, promotions_json)
    except Exception as e:
        logger.error(f"Ошибка запроса акций из WebApp: {e}")

async def _send_promotions(update: Update, promotions_json: str):
    """Вспомогательная функция для форматирования и отправки акций."""
    promotions_data = json.loads(promotions_json)
    if not promotions_data:
        await update.message.reply_text("В данный момент активных акций нет.")
        return

    message = "🎉 **Активные акции и события:**\n\n"
    for i, p in enumerate(promotions_data, 1):
        message += f"{i}. **{p.get('title', 'Без названия')}**\n"
        message += f"   📅 {p.get('start_date', '')} - {p.get('end_date', '')}\n"
        message += f"   📝 {p.get('description', '')[:150]}\n\n"
    
    await update.message.reply_text(message, parse_mode='Markdown')
