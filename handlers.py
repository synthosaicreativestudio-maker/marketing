import logging
import os
import json
import asyncio
from telegram import Update, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters

from auth_service import AuthService
from openai_service import OpenAIService
from appeals_service import AppealsService

logger = logging.getLogger(__name__)

def get_web_app_url() -> str:
    """Ленивое чтение URL WebApp из окружения (после загрузки .env)."""
    return os.getenv("WEB_APP_URL") or ""

def setup_handlers(application, auth_service: AuthService, openai_service: OpenAIService, appeals_service: AppealsService):
    """Регистрирует все обработчики в приложении."""
    application.add_handler(CommandHandler("start", start_command_handler(auth_service)))
    application.add_handler(CommandHandler("appeals", appeals_command_handler(auth_service, appeals_service)))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_handler(auth_service)))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.StatusUpdate.WEB_APP_DATA, chat_handler(auth_service, openai_service, appeals_service)))

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
            WEB_APP_URL = get_web_app_url()
            if WEB_APP_URL:
                keyboard_button = KeyboardButton(
                    text="Авторизоваться в приложении",
                    web_app=WebAppInfo(url=WEB_APP_URL)
                )
                reply_markup = ReplyKeyboardMarkup.from_button(keyboard_button, resize_keyboard=True)
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
                await update.message.reply_text(
                    "Авторизация прошла успешно! Добро пожаловать.",
                    reply_markup=ReplyKeyboardRemove()
                )
                # TODO: Показать основное меню
            else:
                logger.warning("Авторизация не удалась - данные не найдены")
                keyboard_button = KeyboardButton(
                    text="Повторить авторизацию",
                    web_app=WebAppInfo(url=get_web_app_url())
                )
                reply_markup = ReplyKeyboardMarkup.from_button(keyboard_button, resize_keyboard=True)
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


def appeals_command_handler(auth_service: AuthService, appeals_service: AppealsService):
    """Фабрика обработчика команды /appeals для просмотра обращений."""
    async def handle_appeals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        logger.info(f"Команда /appeals от пользователя {user.id}")

        # Проверка авторизации
        if not auth_service.get_user_auth_status(user.id):
            await update.message.reply_text(
                "Для просмотра обращений требуется авторизация. Нажмите кнопку авторизации /start."
            )
            return

        # Проверка доступности сервиса обращений
        if not appeals_service or not appeals_service.is_available():
            await update.message.reply_text(
                "Сервис обращений временно недоступен. Повторите позже."
            )
            return

        try:
            appeals = appeals_service.get_user_appeals(user.id)
            
            if not appeals:
                await update.message.reply_text(
                    "У вас пока нет обращений. Отправьте любое сообщение, чтобы создать обращение."
                )
                return

            # Формируем список обращений
            message = "📋 Ваши обращения:\n\n"
            for i, appeal in enumerate(appeals, 1):
                status_emoji = {
                    'новое': '🆕',
                    'в обработке': '⏳',
                    'решено': '✅',
                    'закрыто': '🔒'
                }.get(appeal.get('статус', '').lower(), '❓')
                
                message += f"{i}. {status_emoji} {appeal.get('статус', 'неизвестно')}\n"
                
                # Показываем последние обращения (первые 2 строки)
                appeals_text = appeal.get('текст_обращений', '')
                if appeals_text:
                    lines = appeals_text.split('\n')
                    recent_appeals = lines[:2]  # Показываем только последние 2 обращения
                    for appeal_line in recent_appeals:
                        if appeal_line.strip():
                            message += f"   📝 {appeal_line[:80]}{'...' if len(appeal_line) > 80 else ''}\n"
                    
                    if len(lines) > 2:
                        message += f"   ... и ещё {len(lines) - 2} обращений\n"
                
                if appeal.get('специалист_ответ'):
                    message += f"   💬 Ответ: {appeal.get('специалист_ответ', '')[:100]}{'...' if len(appeal.get('специалист_ответ', '')) > 100 else ''}\n"
                message += f"   🕒 {appeal.get('время_обновления', '')}\n\n"

            await update.message.reply_text(message)
            
        except Exception as e:
            logger.error(f"Ошибка при получении обращений: {e}")
            await update.message.reply_text(
                "Произошла ошибка при получении обращений. Попробуйте позже."
            )

    return handle_appeals


def chat_handler(auth_service: AuthService, openai_service: OpenAIService, appeals_service: AppealsService):
    """Фабрика обработчика для свободного чата с ассистентом через Threads API.

    Доступно только авторизованным пользователям. При отключенном OpenAIService — вежливое сообщение.
    """
    async def handle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        text = update.effective_message.text or ""
        logger.info(f"Текстовое сообщение от {user.id}: {text}")

        # Проверка авторизации
        if not auth_service.get_user_auth_status(user.id):
            await update.message.reply_text(
                "Для использования ассистента требуется авторизация. Нажмите кнопку авторизации /start."
            )
            return

        # Создаем обращение в таблице
        if appeals_service and appeals_service.is_available():
            try:
                logger.info(f"Попытка создать обращение для пользователя {user.id}")
                # Получаем данные пользователя из таблицы авторизации
                records = auth_service.worksheet.get_all_records()
                user_data = None
                for record in records:
                    if str(record.get('Telegram ID', '')) == str(user.id):
                        user_data = record
                        break
                
                if user_data:
                    logger.info(f"Найдены данные пользователя: {user_data}")
                    result = appeals_service.create_appeal(
                        code=user_data.get('Код партнера', ''),
                        phone=user_data.get('Телефон партнера', ''),
                        fio=user_data.get('ФИО партнера', ''),
                        telegram_id=user.id,
                        text=text
                    )
                    logger.info(f"Результат создания обращения: {result}")
                else:
                    logger.warning(f"Данные пользователя {user.id} не найдены в таблице авторизации")
            except Exception as e:
                logger.error(f"Ошибка при создании обращения: {e}", exc_info=True)

        # Проверка доступности OpenAI
        if not openai_service or not openai_service.is_enabled():
            await update.message.reply_text(
                "Ассистент временно недоступен. Ваше обращение записано, специалист ответит позже."
            )
            return

        # Индикация набора
        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        except Exception:
            pass

        try:
            reply = await asyncio.get_event_loop().run_in_executor(
                None, openai_service.ask, user.id, text
            )
            if reply:
                await update.message.reply_text(reply)
            else:
                await update.message.reply_text(
                    "Не удалось получить ответ ассистента. Попробуйте ещё раз."
                )
        except Exception as e:
            logger.error(f"Ошибка при обращении к OpenAI: {e}")
            await update.message.reply_text(
                "Произошла ошибка при обращении к ассистенту. Попробуйте позже."
            )

    return handle_chat
