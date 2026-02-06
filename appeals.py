import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from auth_service import AuthService
from appeals_service import AppealsService
from error_handler import safe_handler

logger = logging.getLogger(__name__)

def register_appeals_handlers(application, auth_service: AuthService, appeals_service: AppealsService):
    """Регистрация обработчиков обращений."""
    application.add_handler(CommandHandler("appeals", appeals_command_handler(auth_service, appeals_service)))

def appeals_command_handler(auth_service: AuthService, appeals_service: AppealsService):
    """Команда /appeals для просмотра истории."""
    @safe_handler
    async def handle_appeals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        
        if not await auth_service.get_user_auth_status(user.id):
            await update.message.reply_text("Для просмотра обращений требуется авторизация.")
            return

        if not appeals_service or not appeals_service.is_available():
            await update.message.reply_text("Сервис обращений временно недоступен.")
            return

        try:
            appeals = await appeals_service.get_user_appeals(user.id)
            if not appeals:
                await update.message.reply_text("У вас пока нет обращений.")
                return

            message = "📋 Ваши обращения:\n\n"
            for i, a in enumerate(appeals, 1):
                status = a.get('статус', 'неизвестно').lower()
                emoji = {'новое': '🆕', 'в обработке': '⏳', 'решено': '✅'}.get(status, '❓')
                
                message += f"{i}. {emoji} {status.upper()}\n"
                text = a.get('текст_обращений', '').split('\n')[:2]
                for line in text:
                    if line.strip():
                        message += f"   📝 {line[:70]}...\n"
                message += f"   🕒 {a.get('время_обновления', '')}\n\n"

            await update.message.reply_text(message)
        except Exception as e:
            logger.error(f"Ошибка /appeals: {e}")
            await update.message.reply_text("Ошибка при получении списка обращений.")
            
    return handle_appeals
