import logging
import os
import json
import asyncio
import time
from telegram import Update, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

from auth_service import AuthService
from ai_service import AIService
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
    # Версия для принудительного обновления кеша WebApp
    cache_bust = "v=20260108-2"
    return f"{base_url}menu.html?{cache_bust}"

def create_specialist_button() -> InlineKeyboardMarkup:
    """Создает инлайн-кнопку для обращения к специалисту."""
    keyboard = [[InlineKeyboardButton("👨‍💼 Обратиться к специалисту", callback_data="contact_specialist")]]
    return InlineKeyboardMarkup(keyboard)

async def _safe_background_log(user_id: int, user_text: str, ai_reply: str, appeals_service: AppealsService):
    """Фоновое логирование в Google Sheets и локальный JSONL."""
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    log_entry = {
        "timestamp": timestamp,
        "user_id": user_id,
        "question": user_text,
        "answer": ai_reply
    }
    
    # 1. Локальный JSONL бэкап (мгновенно)
    try:
        os.makedirs("logs", exist_ok=True)
        with open("logs/chat_history.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.error(f"Ошибка локального логирования: {e}")

    # 2. Google Sheets (асинхронно, не блокируя основной поток)
    if appeals_service and appeals_service.is_available():
        try:
            # Сначала записываем вопрос (если еще не записан)
            await appeals_service.add_user_message(user_id, user_text)
            # Затем ответ
            await appeals_service.add_ai_response(user_id, ai_reply)
            logger.info(f"Фоновое логирование завершено для {user_id}")
        except Exception as e:
            logger.error(f"Ошибка фонового логирования в Sheets для {user_id}: {e}")

async def _generate_and_send_image(user_id: int, text_reply: str, chat_id: int, context: ContextTypes.DEFAULT_TYPE, ai_service: AIService):
    """Фоновая генерация и отправка иллюстрации к ответу."""
    try:
        # Уведомляем пользователя (можно пропустить, чтобы не спамить, если генерация быстрая)
        # Но для вау-эффекта лучше показать активность
        status_msg = await context.bot.send_message(
            chat_id=chat_id,
            text="🎨 _Рисую иллюстрацию к ответу..._",
            parse_mode='Markdown'
        )
        
        # 1. Арт-директор: создаем промпт
        prompt = await ai_service.generate_image_prompt(text_reply)
        if not prompt:
            await status_msg.delete()
            return

        # 2. Художник: генерируем изображение
        image_bytes = await ai_service.generate_image(prompt)
        
        if image_bytes:
            # 3. Отправка
            await context.bot.send_chat_action(chat_id=chat_id, action="upload_photo")
            await context.bot.send_photo(
                chat_id=chat_id, 
                photo=image_bytes,
                caption="✨ Сгенерировано AI специально для вас"
            )
            # Удаляем статусное сообщение
            await status_msg.delete()
        else:
            # Если не вышло сгенерировать - тихо удаляем статус
            await status_msg.delete()
            
    except Exception as e:
        logger.error(f"Background image generation failed for {user_id}: {e}")
        # Пытаемся удалить статусное сообщение при ошибке
        try:
            if 'status_msg' in locals():
                await status_msg.delete()
        except Exception:
            pass

def _is_user_escalation_request(text: str) -> bool:
    """
    Проверяет, содержит ли сообщение пользователя триггерные слова для эскалации.
    
    Args:
        text: текст сообщения пользователя
        
    Returns:
        bool: True если найдены триггерные слова
    """
    import re
    
    # Нормализуем текст: убираем знаки препинания и приводим к нижнему регистру
    text_normalized = re.sub(r'[^\w\s]', '', text.lower())
    
    # Прямые триггерные фразы для эскалации (30 фраз)
    escalation_phrases = [
        'хочу поговорить со специалистом',
        'нужен специалист',
        'передайте специалисту',
        'соедините с менеджером',
        'соедините с специалистом',
        'хочу к человеку',
        'живой человек',
        'реальный специалист',
        'дайте мне специалиста',
        'дайте специалиста',
        'хочу специалиста',
        'нужен человек',
        'хочу к специалисту',
        'нужен маркетолог',
        'хочу маркетолога',
        'дайте маркетолога',
        'нужен специалист по маркетингу',
        'хочу специалиста по маркетингу',
        'дайте специалиста по маркетингу',
        'нужен специалист отдела маркетинга',
        'хочу специалиста отдела маркетинга',
        'дайте специалиста отдела маркетинга',
        'передайте мой вопрос',
        'передайте мою проблему',
        'передайте мое обращение',
        'эскалируйте вопрос',
        'эскалируйте проблему',
        'эскалируйте обращение',
        'хочу поговорить с человеком',
        'дайте человека'
    ]
    
    # Фразы подтверждения эскалации (когда ИИ спрашивает)
    # Фразы подтверждения эскалации (когда ИИ спрашивает)
    # confirmation_phrases removed as it was unused

    
    # Проверяем наличие триггерных фраз в нормализованном тексте
    for phrase in escalation_phrases:
        if phrase in text_normalized:
            return True
    
    return False

def _is_ai_asking_for_escalation(ai_response: str) -> bool:
    """
    Проверяет, спрашивает ли ИИ о необходимости передачи специалисту.
    
    Args:
        ai_response: ответ ИИ
        
    Returns:
        bool: True если ИИ спрашивает об эскалации
    """
    if not ai_response:
        return False
        
    response_lower = ai_response.lower()
    
    # Фразы, когда ИИ спрашивает об эскалации
    escalation_questions = [
        'нужно ли передать',
        'передать специалисту',
        'соединить со специалистом',
        'связать со специалистом',
        'передать ваш запрос',
        'передать вашу проблему',
        'передать ваше обращение',
        'эскалировать вопрос',
        'эскалировать проблему',
        'эскалировать обращение',
        'передать менеджеру',
        'соединить с менеджером',
        'связать с менеджером',
        'передать маркетологу',
        'соединить с маркетологом',
        'связать с маркетологом'
    ]
    
    # Проверяем наличие вопросов об эскалации
    for phrase in escalation_questions:
        if phrase in response_lower:
            return True
    
    return False

def _is_escalation_confirmation(text: str) -> bool:
    """
    Проверяет, содержит ли сообщение подтверждение эскалации к специалисту.
    
    Args:
        text: текст сообщения пользователя
        
    Returns:
        bool: True если найдены фразы подтверждения
    """
    text_lower = text.lower()
    
    # Фразы подтверждения эскалации (когда ИИ спрашивает)
    confirmation_phrases = [
        'да',
        'да, нужно',
        'да, передайте',
        'да, соедините',
        'да, свяжите',
        'да, пожалуйста',
        'да, конечно',
        'да, давайте',
        'да, хорошо',
        'да, согласен',
        'нужно',
        'передайте',
        'соедините',
        'свяжите',
        'пожалуйста',
        'конечно',
        'давайте',
        'хорошо',
        'согласен',
        'подтверждаю'
    ]
    
    # Проверяем наличие фраз подтверждения
    for phrase in confirmation_phrases:
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




def setup_handlers(application, auth_service: AuthService, ai_service: AIService, appeals_service: AppealsService):
    """Регистрирует все обработчики в приложении."""
    application.add_handler(CommandHandler("start", start_command_handler(auth_service)))
    application.add_handler(CommandHandler("appeals", appeals_command_handler(auth_service, appeals_service)))
    application.add_handler(CommandHandler("promotions", promotions_command_handler(auth_service)))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_handler(auth_service)))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.StatusUpdate.WEB_APP_DATA, chat_handler(auth_service, ai_service, appeals_service)))
    application.add_handler(CallbackQueryHandler(callback_query_handler(auth_service, appeals_service)))

def start_command_handler(auth_service: AuthService):
    """Фабрика для создания обработчика /start с доступом к сервису авторизации."""
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        logger.info(f"Пользователь {user.id} ({user.first_name}) запустил команду /start.")

        # Проверка статуса авторизации
        auth_status = await auth_service.get_user_auth_status(user.id)
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
                auth_status = await auth_service.get_user_auth_status(user.id)
                if not auth_status:
                    logger.warning(f"Пользователь {user.id} не авторизован, но пытается получить акции")
                    await update.message.reply_text("Вы не авторизованы. Пожалуйста, сначала авторизуйтесь.")
                    return
                await handle_promotions_request(update, context)
                return
            
            partner_code = data.get('partner_code')
            partner_phone = data.get('partner_phone')
            
            logger.info(f"Код партнера: {partner_code}, Телефон: {partner_phone}")

            # Проверяем, не авторизован ли пользователь уже
            current_auth_status = await auth_service.get_user_auth_status(user.id)
            logger.info(f"Текущий статус авторизации пользователя {user.id}: {current_auth_status}")
            
            # Логика авторизации
            logger.info("Запуск процесса авторизации...")
            auth_result = await auth_service.find_and_update_user(partner_code, partner_phone, user.id)
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
                logger.warning(f"Авторизация не удалась для пользователя {user.id} - данные не найдены")
                logger.warning(f"Искали: код={partner_code}, телефон={partner_phone}")
                
                # Дополнительная диагностика
                try:
                    from sheets_gateway import normalize_phone
                    phone_norm = normalize_phone(partner_phone)
                    logger.info(f"Нормализованный телефон: {phone_norm}")
                    logger.warning(f"Искали: код={partner_code}, телефон={phone_norm}")
                except Exception as e:
                    logger.error(f"Ошибка нормализации телефона: {e}")
                
                keyboard_button = KeyboardButton(
                    text="Повторить авторизацию",
                    web_app=WebAppInfo(url=get_web_app_url())
                )
                reply_markup = ReplyKeyboardMarkup.from_button(keyboard_button, resize_keyboard=True)
                await update.message.reply_text(
                    "Данные не найдены. Пожалуйста, проверьте код партнера и телефон и попробуйте снова.\n\n"
                    "Если проблема повторяется, обратитесь к администратору.",
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
        if not await auth_service.get_user_auth_status(user.id):
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
            appeals = await appeals_service.get_user_appeals(user.id)
            
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
        if not await auth_service.get_user_auth_status(user.id):
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
        from sheets_gateway import AsyncGoogleSheetsGateway
        
        # Создаем gateway для promotions
        promotions_gateway = AsyncGoogleSheetsGateway(circuit_breaker_name='promotions')
        
        # Проверка доступности системы акций
        if not await is_promotions_available(promotions_gateway):
            await update.message.reply_text(
                "Система акций временно недоступна. Повторите позже."
            )
            return
        
        promotions_json = await get_promotions_json(promotions_gateway)
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


def chat_handler(auth_service: AuthService, ai_service: AIService, appeals_service: AppealsService):
    """Фабрика обработчика для свободного чата с ассистентом.

    Доступно только авторизованным пользователям. При отключенном AIService — вежливое сообщение.
    """
    async def handle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        text = update.effective_message.text or ""
        logger.info(f"CHAT_HANDLER: Текстовое сообщение от {user.id}: {text}")

        # Проверка авторизации
        auth_status = await auth_service.get_user_auth_status(user.id)
        logger.info(f"Статус авторизации для пользователя {user.id}: {auth_status}")
        
        if not auth_status:
            await update.message.reply_text(
                "❌ Для использования ассистента требуется авторизация.\n\n"
                "Нажмите /start для авторизации."
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
                    result = await appeals_service.create_appeal(
                        code=user_data.get('Код партнера', ''),
                        phone=user_data.get('Телефон партнера', ''),
                        fio=user_data.get('ФИО партнера', ''),
                        telegram_id=user.id,
                        text=f"Пользователь: {text}"  # Добавляем префикс для ясности
                    )
                    logger.info(f"Результат создания обращения: {result}")
                else:
                    logger.warning(f"Данные пользователя {user.id} не найдены в таблице авторизации")
            except Exception as e:
                logger.error(f"Ошибка при создании обращения: {e}", exc_info=True)

        # Проверяем запрос специалиста ПЕРЕД вызовом ИИ
        is_escalation_request = _is_user_escalation_request(text)
        if is_escalation_request:
            logger.info(f"Обнаружен запрос специалиста от пользователя {user.id}, показываем кнопку без вызова ИИ")
            try:
                await update.message.reply_text(
                    "Ваш запрос в ближайшее время будет передан специалисту.",
                    reply_markup=create_specialist_button()
                )
                logger.info(f"Показана кнопка специалиста для пользователя {user.id} (без вызова ИИ)")
            except Exception as e:
                logger.error(f"Ошибка отправки кнопки специалиста: {e}")
            return

        # Если обращение находится у специалиста, переключаем в режим общения со специалистом
        if appeals_service and appeals_service.is_available():
            try:
                current_status = await appeals_service.get_appeal_status(user.id)
                current_status = str(current_status or '').strip().lower()
                logger.info(f"Текущий статус обращения пользователя {user.id}: {current_status}")
                # Режим специалиста: любые варианты "в работе" или "передано ..." (без учета регистра)
                is_specialist_mode = (
                    current_status == "в работе" or
                    current_status == "передано специалисту" or
                    ("в работ" in current_status) or
                    ("передано" in current_status)
                )
                if is_specialist_mode:
                    # Режим специалиста: не вызываем ИИ и не отправляем сервисные сообщения
                    # Страховочно логируем сообщение пользователя в таблицу обращений
                    try:
                        await appeals_service.add_user_message(user.id, text)
                    except Exception:
                        pass
                    # Статус УЖЕ "В работе" - не меняем его повторно!
                    # Изменение статуса происходит только при нажатии кнопки пользователем.
                    return
            except Exception as e:
                logger.warning(f"Не удалось проверить статус обращения: {e}")

        # Проверка доступности AI
        if not ai_service or not ai_service.is_enabled():
            await update.message.reply_text(
                "Ассистент временно недоступен. Ваше обращение записано, специалист ответит позже."
            )
            return

        # Индикация набора
        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        except Exception:
            pass

        # Переменные для стриминга
        status_message = None
        current_message_buffer = ""
        full_response_log = ""
        last_update_time = 0
        update_interval = 1.5 
        
        try:
            # Сразу отправляем заглушку
            status_message = await update.message.reply_text("⏳ *Синта печатает...*", parse_mode='Markdown')
            
            # Начинаем стриминг от Gemini
            async for chunk in ai_service.ask_stream(user.id, text):
                # Проверка на вызов инструмента
                if chunk.startswith("__TOOL_CALL__"):
                    tool_name = chunk.split(":")[1]
                    if tool_name == 'get_promotions':
                        await status_message.edit_text("🔍 *Проверяю актуальные акции...*", parse_mode='Markdown')
                    continue
                
                current_message_buffer += chunk
                full_response_log += chunk
                
                # Обработка переполнения сообщения (Telegram лимит 4096)
                if len(current_message_buffer) > 3800: # Берем с запасом 3800
                    # Ищем место для разрыва (абзац или пробел)
                    split_idx = -1
                    # Приоритет 1: Перенос строки
                    last_newline = current_message_buffer.rfind('\n')
                    if last_newline > 3000:
                        split_idx = last_newline
                    else:
                        # Приоритет 2: Пробел
                        last_space = current_message_buffer.rfind(' ')
                        if last_space > 3000:
                            split_idx = last_space
                            
                    if split_idx != -1:
                        part1 = current_message_buffer[:split_idx]
                        part2 = current_message_buffer[split_idx:].strip()
                        
                        # Финализируем текущее сообщение
                        try:
                            await status_message.edit_text(part1, parse_mode='Markdown')
                        except Exception:
                            # Fallback если Markdown кривой
                            await status_message.edit_text(part1, parse_mode=None)
                            
                        # Создаем новое сообщение для продолжения
                        status_message = await update.message.reply_text("⏳ *...*", parse_mode='Markdown')
                        current_message_buffer = part2
                
                # Троттлинг обновлений в Telegram
                now = time.time()
                if (now - last_update_time >= update_interval) and current_message_buffer.strip():
                    try:
                        await status_message.edit_text(current_message_buffer + " ▌", parse_mode='Markdown')
                        last_update_time = now
                    except Exception as e:
                        if "Message is not modified" not in str(e):
                            logger.debug(f"Streaming update error for user {user.id}: {e}")
            
            # Финальное обновление ПОСЛЕДНЕГО сообщения
            if current_message_buffer.strip():
                escalation_tag = "[ESCALATE_ACTION]"
                is_escalation_triggered = escalation_tag in full_response_log or "Передаю ваш запрос специалисту" in full_response_log
                
                # Очищаем теги из буфера (если они попали в этот чанк)
                clean_buffer = current_message_buffer.replace(escalation_tag, "").strip()
                clean_full_log = full_response_log.replace(escalation_tag, "").strip()
                
                markup = create_specialist_button() if is_escalation_triggered else None
                
                try:
                    await status_message.edit_text(clean_buffer, reply_markup=markup, parse_mode='Markdown')
                except Exception:
                    await status_message.edit_text(clean_buffer, reply_markup=markup, parse_mode=None)
                
                # ФОНОВОЕ ЛОГИРОВАНИЕ (полный текст)
                asyncio.create_task(_safe_background_log(user.id, text, clean_full_log, appeals_service))
                
                logger.info(f"Стриминг завершен для {user.id}. Полная длина: {len(clean_full_log)}")

                # АВТОМАТИЧЕСКАЯ ГЕНЕРАЦИЯ ИЛЛЮСТРАЦИИ (Если ответ содержательный)
                if len(clean_full_log) > 200 and not is_escalation_triggered:
                    # FEATURE DISABLED "FOR NOW" (User Request)
                    # asyncio.create_task(_generate_and_send_image(
                    #     user_id=user.id, 
                    #     text_reply=clean_full_log, 
                    #     chat_id=update.effective_chat.id, 
                    #     context=context, 
                    #     ai_service=ai_service
                    # ))
                    pass
            else:
                await status_message.edit_text("Извините, я не смог сформировать ответ.")

        except asyncio.TimeoutError:
            if status_message:
                await status_message.edit_text(
                    "⏱ Запрос обрабатывается дольше обычного. Передаю специалисту.",
                    reply_markup=create_specialist_button()
                )
        except Exception as e:
            logger.error(f"Критическая ошибка в chat_handler: {e}", exc_info=True)
            if status_message:
                try:
                    # Показываем то, что успели напечатать + маркер ошибки
                    final_text = full_response if full_response else "Произошла ошибка при обработке."
                    await status_message.edit_text(f"{final_text}\n\n... [⚠️ Связь прервалась]")
                except Exception:
                    pass
            else:
                await update.message.reply_text("Произошла ошибка при обработке сообщения.")

        return


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
        if not await auth_service.get_user_auth_status(user.id):
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
                        # Меняем статус на "В работе" с желтой заливкой
                        success = await appeals_service.set_status_in_work(user.id)
                        if success:
                            await query.edit_message_text(
                                "✅ Ваше обращение передано специалисту отдела маркетинга. "
                                "Статус изменен на 'В работе'. Специалист ответит в ближайшее время."
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
