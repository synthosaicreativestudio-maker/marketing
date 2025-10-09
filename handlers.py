import logging
import os
import json
import asyncio
from telegram import Update, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

from auth_service import AuthService
from openai_service import OpenAIService
from appeals_service import AppealsService
from promotions_api import get_promotions_json, is_promotions_available

logger = logging.getLogger(__name__)

def get_web_app_url() -> str:
    """Ленивое чтение URL WebApp из окружения (после загрузки .env)."""
    base_url = os.getenv("WEB_APP_URL") or ""
    if base_url and not base_url.endswith('/'):
        base_url += '/'
    return base_url + "index.html"

def get_spa_menu_url() -> str:
    """Ленивое чтение URL SPA меню из окружения."""
    base_url = os.getenv("WEB_APP_URL") or ""
    if base_url and not base_url.endswith('/'):
        base_url += '/'
    return base_url + "menu.html"

def create_specialist_button() -> InlineKeyboardMarkup:
    """
    Создает инлайн-кнопку для обращения к специалисту.
    """
    keyboard = [[InlineKeyboardButton("👨‍💼 Обратиться к специалисту", callback_data="contact_specialist")]]
    return InlineKeyboardMarkup(keyboard)

def _is_user_escalation_request(text: str) -> bool:
    """
    Проверяет, содержит ли сообщение пользователя триггерные слова для эскалации.
    
    Args:
        text: текст сообщения пользователя
        
    Returns:
        bool: True если найдены триггерные слова
    """
    text_lower = text.lower()
    
    # Триггерные фразы для эскалации
    escalation_phrases = [
        'хочу поговорить со специалистом',
        'нужен специалист',
        'передайте специалисту',
        'соедините с менеджером',
        'соедините с специалистом',
        'хочу к человеку',
        'живой человек',
        'реальный специалист'
    ]
    
    # Проверяем наличие триггерных фраз
    for phrase in escalation_phrases:
        if phrase in text_lower:
            return True
    
    return False

def _should_show_specialist_button(text: str) -> bool:
    """
    Проверяет, просит ли пользователь соединить его со специалистом/живым человеком.
    
    Args:
        text: текст сообщения пользователя
        
    Returns:
        bool: True если нужно показать кнопку "Обратиться к специалисту"
    """
    text_lower = text.lower()
    
    # Ключевые фразы, которые указывают на желание поговорить со специалистом
    specialist_keywords = [
        'специалист', 'специалиста', 'специалисту', 'специалистом',
        'живой человек', 'живому человеку', 'живым человеком',
        'менеджер', 'менеджера', 'менеджеру', 'менеджером',
        'сотрудник', 'сотрудника', 'сотруднику', 'сотрудником',
        'оператор', 'оператора', 'оператору', 'оператором',
        'консультант', 'консультанта', 'консультанту', 'консультантом',
        'соединить', 'соедините', 'соедини', 'соединиться',
        'поговорить', 'поговорить с', 'поговорить с человеком',
        'человек', 'человека', 'человеку', 'человеком',
        'позвонить', 'позвоните', 'звонок', 'звонить',
        'связаться', 'связаться с', 'связать', 'связать с',
        'поддержка', 'поддержку', 'поддержке', 'поддержкой',
        'помощь', 'помощи', 'помочь', 'помощью',
        'не могу', 'не получается', 'не работает',
        'проблема', 'проблемы', 'проблему', 'проблемой',
        'сложно', 'сложный', 'сложная', 'сложное',
        'не понимаю', 'не понятно', 'не ясно',
        'объясните', 'объясни', 'объяснить',
        'подробнее', 'подробно', 'подробный',
        'детали', 'детализация', 'детально'
    ]
    
    # Проверяем наличие ключевых слов
    for keyword in specialist_keywords:
        if keyword in text_lower:
            return True
    
    return False




def setup_handlers(application, auth_service: AuthService, openai_service: OpenAIService, appeals_service: AppealsService):
    """Регистрирует все обработчики в приложении."""
    application.add_handler(CommandHandler("start", start_command_handler(auth_service)))
    application.add_handler(CommandHandler("appeals", appeals_command_handler(auth_service, appeals_service)))
    application.add_handler(CommandHandler("promotions", promotions_command_handler(auth_service)))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_handler(auth_service)))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.StatusUpdate.WEB_APP_DATA, chat_handler(auth_service, openai_service, appeals_service)))
    application.add_handler(CallbackQueryHandler(callback_query_handler(auth_service, appeals_service)))

def start_command_handler(auth_service: AuthService):
    """Фабрика для создания обработчика /start с доступом к сервису авторизации."""
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        logger.info(f"Пользователь {user.id} ({user.first_name}) запустил команду /start.")

        # Проверка статуса авторизации
        auth_status = auth_service.get_user_auth_status(user.id)
        logger.info(f"Статус авторизации для пользователя {user.id}: {auth_status}")
        if auth_status:
            # Показываем SPA меню для авторизованных пользователей
            SPA_MENU_URL = get_spa_menu_url()
            logger.info(f"SPA_MENU_URL для авторизованного пользователя: {SPA_MENU_URL}")
            if SPA_MENU_URL:
                # Создаем клавиатуру только с кнопкой "Личный кабинет"
                keyboard = [
                    [KeyboardButton(
                        text="👤 Личный кабинет",
                        web_app=WebAppInfo(url=SPA_MENU_URL)
                    )]
                ]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
                
                await update.message.reply_text(
                    f"Добрый день, {user.first_name}! Добро пожаловать в MarketingBot! 🎯\n\n"
                    "Выберите действие или откройте личный кабинет для доступа к разделам.",
                    reply_markup=reply_markup
                )
            else:
                await update.message.reply_text(
                    f"Добрый день, {user.first_name}! Вы уже авторизованы. Можете задать любой вопрос ассистенту."
                )
        else:
            WEB_APP_URL = get_web_app_url()
            logger.info(f"WEB_APP_URL для неавторизованного пользователя: {WEB_APP_URL}")
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
        
        # Проверяем авторизацию пользователя только для запросов акций
        # Для процесса авторизации эта проверка не нужна
        
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
            
            # Проверяем, это запрос акций или авторизация
            if data.get('action') == 'get_promotions':
                logger.info(f"Запрос акций от пользователя {user.id}")
                # Для запросов акций проверяем авторизацию
                auth_status = auth_service.get_user_auth_status(user.id)
                if not auth_status:
                    logger.warning(f"Пользователь {user.id} не авторизован, но пытается получить акции")
                    await update.message.reply_text("Вы не авторизованы. Пожалуйста, сначала авторизуйтесь.")
                    return
                await handle_promotions_request(update, context)
                return
            
            partner_code = data.get('partner_code')
            partner_phone = data.get('partner_phone')
            
            logger.info(f"Код партнера: {partner_code}, Телефон: {partner_phone}")

            # Логика авторизации
            logger.info("Запуск процесса авторизации...")
            auth_result = auth_service.find_and_update_user(partner_code, partner_phone, user.id)
            logger.info(f"Результат авторизации: {auth_result}")
            
            if auth_result:
                await update.message.reply_text(
                    "Авторизация прошла успешно! Добро пожаловать в MarketingBot! 🎯",
                    reply_markup=ReplyKeyboardRemove()
                )
                # Показываем SPA меню
                SPA_MENU_URL = get_spa_menu_url()
                if SPA_MENU_URL:
                    # Создаем клавиатуру только с кнопкой "Личный кабинет"
                    keyboard = [
                        [KeyboardButton(
                            text="👤 Личный кабинет",
                            web_app=WebAppInfo(url=SPA_MENU_URL)
                        )]
                    ]
                    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
                    
                    await update.message.reply_text(
                        "Выберите действие или откройте личный кабинет для доступа к разделам.",
                        reply_markup=reply_markup
                    )
                else:
                    await update.message.reply_text(
                        "Теперь вы можете задать любой вопрос ассистенту."
                    )
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


def promotions_command_handler(auth_service: AuthService):
    """Фабрика обработчика команды /promotions для получения данных акций."""
    async def handle_promotions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        logger.info(f"Команда /promotions от пользователя {user.id}")

        # Проверка авторизации
        if not auth_service.get_user_auth_status(user.id):
            await update.message.reply_text(
                "Для просмотра акций требуется авторизация. Нажмите кнопку авторизации /start."
            )
            return

        # Проверка доступности системы акций
        if not is_promotions_available():
            await update.message.reply_text(
                "Система акций временно недоступна. Повторите позже."
            )
            return

        try:
            # Получаем JSON с акциями
            promotions_json = get_promotions_json()
            promotions_data = json.loads(promotions_json)
            
            if not promotions_data:
                await update.message.reply_text(
                    "🎉 Акции и события\n\n"
                    "В данный момент активных акций нет. "
                    "Следите за обновлениями!"
                )
                return

            # Формируем сообщение с акциями
            message = "🎉 Активные акции и события:\n\n"
            for i, promotion in enumerate(promotions_data, 1):
                message += f"{i}. **{promotion.get('title', 'Без названия')}**\n"
                message += f"   📅 {promotion.get('start_date', '')} - {promotion.get('end_date', '')}\n"
                message += f"   📝 {promotion.get('description', '')[:100]}{'...' if len(promotion.get('description', '')) > 100 else ''}\n\n"

            # Добавляем JSON для отладки (только для админов)
            if user.id == int(os.getenv('ADMIN_TELEGRAM_ID', '0')):
                message += f"\n📊 JSON данные:\n```json\n{promotions_json}\n```"

            await update.message.reply_text(
                message,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Ошибка при получении акций: {e}")
            await update.message.reply_text(
                "Произошла ошибка при получении акций. Попробуйте позже."
            )

    return handle_promotions

async def handle_promotions_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик запроса акций от WebApp."""
    user = update.effective_user
    logger.info(f"Обработка запроса акций от пользователя {user.id}")
    
    try:
        # Получаем JSON с акциями
        from promotions_api import get_promotions_json, is_promotions_available
        
        # Проверка доступности системы акций
        if not is_promotions_available():
            await update.message.reply_text(
                "Система акций временно недоступна. Повторите позже."
            )
            return
        
        promotions_json = get_promotions_json()
        promotions_data = json.loads(promotions_json)
        
        if not promotions_data:
            await update.message.reply_text(
                "🎉 Акции и события\n\n"
                "В данный момент активных акций нет. "
                "Следите за обновлениями!"
            )
            return
        
        # Формируем сообщение с акциями
        message = "🎉 Активные акции и события:\n\n"
        for i, promotion in enumerate(promotions_data, 1):
            message += f"{i}. **{promotion.get('title', 'Без названия')}**\n"
            message += f"   📅 {promotion.get('start_date', '')} - {promotion.get('end_date', '')}\n"
            message += f"   📝 {promotion.get('description', '')[:100]}{'...' if len(promotion.get('description', '')) > 100 else ''}\n\n"
        
        await update.message.reply_text(
            message,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Ошибка при обработке запроса акций: {e}")
        await update.message.reply_text(
            "Произошла ошибка при получении акций. Попробуйте позже."
        )


def chat_handler(auth_service: AuthService, openai_service: OpenAIService, appeals_service: AppealsService):
    """Фабрика обработчика для свободного чата с ассистентом через Threads API.

    Доступно только авторизованным пользователям. При отключенном OpenAIService — вежливое сообщение.
    """
    async def handle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        text = update.effective_message.text or ""
        logger.info(f"CHAT_HANDLER: Текстовое сообщение от {user.id}: {text}")

        # Проверка авторизации
        if not auth_service.get_user_auth_status(user.id):
            await update.message.reply_text(
                "Для использования ассистента требуется авторизация. Нажмите кнопку авторизации /start."
            )
            return

        # Обработка кнопок меню (убраны кнопки "Обратиться к специалисту" и "Продолжить с ассистентом")

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

        # Проверяем триггерные слова для эскалации
        if _is_user_escalation_request(text):
            logger.info(f"Пользователь {user.id} запросил специалиста через триггерные слова")
            
            # Устанавливаем статус "в работе" в таблице обращений
            if appeals_service and appeals_service.is_available():
                try:
                    success = appeals_service.set_status_in_work(user.id)
                    if success:
                        logger.info(f"Статус 'в работе' установлен для пользователя {user.id}")
                        await update.message.reply_text(
                            "✅ Ваше обращение передано специалисту отдела маркетинга. "
                            "Статус изменен на 'в работе'. Специалист ответит в ближайшее время."
                        )
                    else:
                        logger.warning(f"Не удалось установить статус 'в работе' для пользователя {user.id}")
                        await update.message.reply_text(
                            "Ваше обращение записано. Специалист свяжется с вами в ближайшее время."
                        )
                except Exception as e:
                    logger.error(f"Ошибка при установке статуса эскалации: {e}")
                    await update.message.reply_text(
                        "Ваше обращение записано. Специалист свяжется с вами в ближайшее время."
                    )
            else:
                await update.message.reply_text(
                    "Ваше обращение записано. Специалист свяжется с вами в ближайшее время."
                )
            return

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
                # Логируем ответ ИИ для отладки
                logger.info(f"Ответ ИИ для пользователя {user.id}: {reply[:200]}...")
                
                # Записываем ответ ИИ в таблицу обращений
                if appeals_service and appeals_service.is_available():
                    try:
                        success = appeals_service.add_ai_response(user.id, reply)
                        if success:
                            logger.info(f"Ответ ИИ записан для пользователя {user.id}")
                        else:
                            logger.warning(f"Не удалось записать ответ ИИ для пользователя {user.id}")
                    except Exception as e:
                        logger.error(f"Ошибка при записи ответа ИИ: {e}")
                
                # Очищаем ответ от неправильного Markdown
                clean_reply = reply.replace('*', '').replace('_', '').replace('[', '').replace(']', '').replace('`', '')
                
                # Отправляем ответ ИИ пользователю
                try:
                    await update.message.reply_text(
                        clean_reply
                    )
                    logger.info(f"Ответ ИИ отправлен пользователю {user.id}")
                except Exception as e:
                    logger.error(f"Ошибка отправки ответа ИИ: {e}")
                    # Если все еще не работает, отправляем простой текст
                    await update.message.reply_text(
                        "Получен ответ от ассистента, но произошла ошибка форматирования."
                    )
                
                # Показываем инлайн-кнопку "Обратиться к специалисту" если есть триггерные слова
                if _is_user_escalation_request(text):
                    try:
                        await update.message.reply_text(
                            "Если вам нужна помощь специалиста, нажмите кнопку ниже:",
                            reply_markup=create_specialist_button()
                        )
                        logger.info(f"Показана кнопка специалиста для пользователя {user.id}")
                    except Exception as e:
                        logger.error(f"Ошибка отправки кнопки специалиста: {e}")
                
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


def callback_query_handler(auth_service: AuthService, appeals_service: AppealsService):
    """Фабрика обработчика для callback query (инлайн кнопки)."""
    async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        user = update.effective_user
        
        # Подтверждаем получение callback
        await query.answer()
        
        logger.info(f"Callback query от пользователя {user.id}: {query.data}")
        
        # Проверка авторизации
        if not auth_service.get_user_auth_status(user.id):
            await query.edit_message_text(
                "Для использования этой функции требуется авторизация. Нажмите кнопку авторизации /start."
            )
            return
        
        if query.data == "contact_specialist":
            # Обращение к специалисту
            if appeals_service and appeals_service.is_available():
                try:
                    # Получаем данные пользователя из таблицы авторизации
                    records = auth_service.worksheet.get_all_records()
                    user_data = None
                    for record in records:
                        if str(record.get('Telegram ID', '')) == str(user.id):
                            user_data = record
                            break
                    
                    if user_data:
                        # Меняем статус на "в работе" с заливкой
                        success = appeals_service.set_status_in_work(user.id)
                        if success:
                            await query.edit_message_text(
                                "✅ Ваше обращение передано специалисту отдела маркетинга. "
                                "Статус изменен на 'в работе'. Специалист ответит в ближайшее время."
                            )
                        else:
                            await query.edit_message_text(
                                "❌ Не удалось изменить статус обращения. Попробуйте позже."
                            )
                    else:
                        await query.edit_message_text(
                            "❌ Не найдены данные пользователя. Обратитесь к администратору."
                        )
                except Exception as e:
                    logger.error(f"Ошибка при обращении к специалисту: {e}")
                    await query.edit_message_text(
                        "❌ Произошла ошибка при передаче обращения специалисту. Попробуйте позже."
                    )
            else:
                await query.edit_message_text(
                    "❌ Сервис обращений временно недоступен. Попробуйте позже."
                )
        else:
            await query.edit_message_text("Неизвестная команда.")
    
    return handle_callback_query
