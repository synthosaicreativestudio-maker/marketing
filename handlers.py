import logging
import os
import json
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from auth_service import AuthService

logger = logging.getLogger(__name__)

# Получаем URL веб-приложения из .env
WEB_APP_URL = os.getenv("WEB_APP_URL")

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
            keyboard = [
                [InlineKeyboardButton("Авторизоваться", web_app=WebAppInfo(url=WEB_APP_URL))]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"Добрый день, {user.first_name}! Для продолжения работы вам необходимо авторизоваться.",
                reply_markup=reply_markup,
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
                keyboard = [[InlineKeyboardButton("Повторить авторизацию", web_app=WebAppInfo(url=WEB_APP_URL))]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    "Данные не найдены. Пожалуйста, проверьте код партнера и телефон и попробуйте снова.",
                    reply_markup=reply_markup
                )
        except json.JSONDecodeError:
            logger.error("Ошибка декодирования JSON из Web App.")
            await update.message.reply_text("Произошла ошибка при обработке данных. Попробуйте позже.")
        except Exception as e:
            logger.error(f"Непредвиденная ошибка в web_app_data_handler: {e}")
            await update.message.reply_text("Произошла внутренняя ошибка. Мы уже работаем над этим.")

    return handle_data