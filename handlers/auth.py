import logging
import json
from telegram import Update, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters

from auth_service import AuthService
from error_handler import safe_handler
from utils import get_web_app_url, get_spa_menu_url, set_dynamic_menu_button

logger = logging.getLogger(__name__)

def register_auth_handlers(application, auth_service: AuthService):
    """Регистрация обработчиков авторизации."""
    application.add_handler(CommandHandler("start", start_command_handler(auth_service)))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_handler(auth_service)))

def start_command_handler(auth_service: AuthService):
    """Фабрика для создания обработчика /start."""
    @safe_handler
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        logger.info(f"Команда /start от {user.id}")

        auth_status = await auth_service.get_user_auth_status(user.id)
        
        # Устанавливаем динамическую кнопку меню (Menu Button)
        await set_dynamic_menu_button(context.bot, user.id, auth_status)

        if auth_status:
            keyboard = [[KeyboardButton(text="👤 ЛК", web_app=WebAppInfo(url=get_spa_menu_url()))]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            await update.message.reply_text(
                f"Добрый день, {user.first_name}! Вы авторизованы. Можете задавать вопросы или перейти в личный кабинет через кнопку внизу. 👇",
                reply_markup=reply_markup
            )
        else:
            keyboard = [[KeyboardButton(text="🔑 Вход", web_app=WebAppInfo(url=get_web_app_url()))]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            await update.message.reply_text(
                f"Добрый день, {user.first_name}! Пожалуйста, нажмите кнопку «🔑 Вход» внизу, чтобы авторизоваться.",
                reply_markup=reply_markup
            )
    return start

def web_app_data_handler(auth_service: AuthService):
    """Маршрутизатор данных из WebApp (Авторизация + Промо)."""
    @safe_handler
    async def handle_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        from config import settings
        user = update.effective_user
        web_app_data = update.effective_message.web_app_data.data
        
        if not web_app_data:
            return

        data = json.loads(web_app_data)
        
        # Маршрутизация на акции
        if data.get('action') == 'get_promotions':
            if settings.ENABLE_PROMOTIONS:
                from handlers.promotions import handle_promotions_request
                await handle_promotions_request(update, context)
            return
        
        # Логика авторизации
        partner_code = data.get('partner_code')
        partner_phone = data.get('partner_phone')
        
        await update.message.reply_text("Проверяю данные авторизации...")
        auth_result = await auth_service.find_and_update_user(partner_code, partner_phone, user.id)
        
        if auth_result:
            # Устанавливаем кнопку ЛК на клавиатуру
            keyboard = [[KeyboardButton(text="👤 ЛК", web_app=WebAppInfo(url=get_spa_menu_url()))]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            await update.message.reply_text(
                "Авторизация успешна! ✨\nКнопка входа обновлена на «👤 ЛК».", 
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text("Данные не найдены. Проверьте код и номер телефона.")
            
    return handle_data
