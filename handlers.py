import logging
import os
import json
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters

from auth_service import AuthService

logger = logging.getLogger(__name__)

# Получаем URL веб-приложения из .env
WEB_APP_URL = os.getenv("WEB_APP_URL")

# Проверка наличия WEB_APP_URL
if not WEB_APP_URL:
    logger.critical("WEB_APP_URL не найден в .env файле. Кнопка авторизации будет недоступна.")

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
            if WEB_APP_URL:
                keyboard = [
                    [InlineKeyboardButton("Авторизоваться", web_app=WebAppInfo(url=WEB_APP_URL))]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    f"Добрый день, {user.first_name}! Для продолжения работы вам необходимо авторизоваться.",
                    reply_markup=reply_markup,
                )
            else:
                logger.error("WEB_APP_URL не задан, кнопка авторизации не может быть создана.")
                await update.message.reply_text(
                    f"Добрый день, {user.first_name}! К сожалению, в данный момент авторизация недоступна. Пожалуйста, попробуйте позже."
                )
    return start

def web_app_data_handler(auth_service: AuthService):
    """Фабрика для создания обработчика данных из Mini App."""
    async def handle_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        logger.info(f"Получены данные Web App от пользователя {user.id} ({user.first_name})")
        await update.message.reply_text("Проверяю ваши данные...")
        
        try:
            web_app_data = update.effective_message.web_app_data.data
            logger.info(f"Сырые данные из Web App: {web_app_data}")
            
            # Добавляем проверку на пустые данные
            if not web_app_data:
                logger.warning("Получены пустые данные из Web App")
                await update.message.reply_text("Произошла ошибка при обработке данных. Попробуйте позже.")
                return
                
            data = json.loads(web_app_data)
            logger.info(f"Получены данные из Web App от пользователя {user.id}: {data}")
            
            partner_code = data.get('partner_code')
            partner_phone = data.get('partner_phone')
            
            logger.info(f"Код партнера: {partner_code}, Телефон: {partner_phone}")

            # Логика авторизации
            logger.info("Запуск процесса авторизации...")
            auth_result = auth_service.find_and_update_user(partner_code, partner_phone, user.id)
            logger.info(f"Результат авторизации: {auth_result}")
            
            if auth_result:
                await update.message.reply_text("Авторизация прошла успешно! Добро пожаловать.")
                 # TODO: Показать основное меню
            else:
                logger.warning("Авторизация не удалась - данные не найдены")
                keyboard = [[InlineKeyboardButton("Повторить авторизацию", web_app=WebAppInfo(url=WEB_APP_URL))]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    "Данные не найдены. Пожалуйста, проверьте код партнера и телефон и попробуйте снова.",
                    reply_markup=reply_markup
                )
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка декодирования JSON из Web App: {e}")
            await update.message.reply_text("Произошла ошибка при обработке данных. Попробуйте позже.")
        except Exception as e:
            logger.error(f"Непредвиденная ошибка в web_app_data_handler: {e}")
            await update.message.reply_text("Произошла внутренняя ошибка. Мы уже работаем над этим.")

    return handle_data
