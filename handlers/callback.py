import logging
from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler

from auth_service import AuthService
from appeals_service import AppealsService
from error_handler import safe_handler


logger = logging.getLogger(__name__)

def register_callback_handlers(application, auth_service, appeals_service):
    """Регистрация обработчиков callback-запросов."""
    application.add_handler(CallbackQueryHandler(callback_query_handler(auth_service, appeals_service)))

def callback_query_handler(auth_service: AuthService, appeals_service: AppealsService):
    """Обработчик нажатий на инлайн-кнопки."""
    @safe_handler
    async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        user = update.effective_user
        await query.answer()

        if not await auth_service.get_user_auth_status(user.id):
            await query.edit_message_text("Ошибка: требуется авторизация.")
            return

        if query.data == "contact_specialist":
            await _handle_specialist_request(query, user, auth_service, appeals_service)
            
    return handle_callback

async def _handle_specialist_request(query, user, auth_service, appeals_service):
    """Логика перехода к специалисту."""
    if not appeals_service or not appeals_service.is_available():
        await query.message.reply_text("Сервис временно недоступен.")
        return

    try:
        # Обновляем статус в таблице
        records = auth_service.worksheet.get_all_records()
        user_data = next((r for r in records if str(r.get('Telegram ID')) == str(user.id)), None)
        
        if user_data:
            await appeals_service.create_appeal(
                code=user_data.get('Код партнера', ''),
                phone=user_data.get('Телефон партнера', ''),
                fio=user_data.get('ФИО партнера', ''),
                telegram_id=user.id,
                text="[ЗАПРОС СПЕЦИАЛИСТА]"
            )
            # Ставим статус "В работе"
            await appeals_service.update_appeal_status(user.id, "В работе")
            
            await query.edit_message_text(
                "✅ Запрос принят. Специалист ответит вам в ближайшее время прямо здесь."
            )
        else:
            await query.message.reply_text("Ошибка: данные пользователя не найдены.")
    except Exception as e:
        logger.error(f"Ошибка при вызове специалиста: {e}")
        await query.message.reply_text("Произошла ошибка. Попробуйте еще раз.")
