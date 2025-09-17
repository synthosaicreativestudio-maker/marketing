import logging
import os
import json
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters

from auth_service import AuthService

logger = logging.getLogger(__name__)

# Получаем URL веб-приложения из .env
WEB_APP_URL = os.getenv("WEB_APP_URL")


async def handle_auth_error(update: Update, message: str, show_retry_button: bool = False):
    """Отправляет сообщение об ошибке и, опционально, кнопку для повтора."""
    logger.info(f"WEB_APP_URL loaded from .env: {WEB_APP_URL}")
    if not WEB_APP_URL:
        logger.error("WEB_APP_URL is None or empty. Check your .env file.")
        await update.message.reply_text(
            "К сожалению, система авторизации временно недоступна. Пожалуйста, попробуйте позже."
        )
        return

    keyboard = []
    if show_retry_button:
        keyboard.append([InlineKeyboardButton("Повторить авторизацию", web_app=WebAppInfo(url=WEB_APP_URL))])
    
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    await update.message.reply_text(message, reply_markup=reply_markup)


def setup_handlers(application, auth_service: AuthService):
    """Регистрирует все обработчики в приложении."""
    application.add_handler(CommandHandler("start", start_command_handler(auth_service)))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_handler(auth_service)))

def start_command_handler(auth_service: AuthService):
    """Фабрика для создания обработчика /start с доступом к сервису авторизации."""
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        logger.info(f"Пользователь {user.id} ({user.first_name}) запустил команду /start.")

        # Проверка статуса авторизации
        if auth_service.get_user_auth_status(user.id):
            await update.message.reply_text(f"Добрый день, {user.first_name}! Вы уже авторизованы.")
            # TODO: Здесь можно добавить основное меню для авторизованных пользователей
        else:
            await handle_auth_error(
                update,
                f"Добрый день, {user.first_name}! Для продолжения работы вам необходимо авторизоваться.",
                show_retry_button=True,
            )
    return start

def web_app_data_handler(auth_service: AuthService):
    """Фабрика для создания обработчика данных из Mini App."""
    async def handle_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        await update.message.reply_text("Проверяю ваши данные...")
        
        try:
            data = json.loads(update.effective_message.web_app_data.data)
            logger.info(f"Получены данные из Web App от пользователя {user.id}: {data}")
            
            partner_code = data.get('partner_code')
            partner_phone = data.get('partner_phone')

            # Логика авторизации
            if auth_service.find_and_update_user(partner_code, partner_phone, user.id):
                await update.message.reply_text("Авторизация прошла успешно! Добро пожаловать.")
                # TODO: Показать основное меню
            else:
                await handle_auth_error(
                    update,
                    "Данные не найдены. Пожалуйста, проверьте код партнера и телефон и попробуйте снова.",
                    show_retry_button=True,
                )
        except json.JSONDecodeError:
            logger.error("Ошибка декодирования JSON из Web App.")
            await update.message.reply_text("Произошла ошибка при обработке данных. Попробуйте позже.")
        except Exception as e:
            logger.error(f"Непредвиденная ошибка в web_app_data_handler: {e}")
            await update.message.reply_text("Произошла внутренняя ошибка. Мы уже работаем над этим.")

    return handle_data