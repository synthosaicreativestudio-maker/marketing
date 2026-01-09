"""
Webhook handler для получения уведомлений от Google Sheets
"""
import logging
import os
from flask import Flask, request, jsonify
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from auth_service import AuthService

logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='.', static_url_path='')

# Инициализация бота и сервисов
bot_token = os.getenv('TELEGRAM_TOKEN')
admin_telegram_id = int(os.getenv('ADMIN_TELEGRAM_ID', '0'))
web_app_url = os.getenv('WEB_APP_URL', '')

bot = Bot(token=bot_token)
auth_service = AuthService()

# Импортируем API акций
import promotions_api

@app.after_request
def after_request(response):
    """Добавляем CORS заголовки для всех ответов"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

@app.route('/api/promotions', methods=['GET'])
def get_promotions_api():
    """API endpoint для получения списка акций"""
    try:
        logger.info("API Request: GET /api/promotions")
        promotions_json = promotions_api.get_promotions_json()
        return promotions_json, 200, {'Content-Type': 'application/json'}
    except Exception as e:
        logger.error(f"API Error: {e}")
        return jsonify({'error': 'Internal Server Error'}), 500


@app.route('/api/profile', methods=['GET'])
def get_profile():
    """API endpoint для получения профиля сотрудника по Telegram ID."""
    try:
        telegram_id = request.args.get('telegram_id')
        if not telegram_id:
            return jsonify({'error': 'telegram_id is required'}), 400

        if not auth_service or not auth_service.worksheet:
            logger.error("AuthService недоступен для /api/profile")
            return jsonify({'error': 'auth_service_unavailable'}), 500

        records = auth_service.worksheet.get_all_records()
        for record in records:
            if str(record.get('Telegram ID', '')) == str(telegram_id):
                profile = {
                    'full_name': record.get('ФИО партнера', ''),
                    'partner_code': record.get('Код партнера', ''),
                    'phone': record.get('Телефон партнера', ''),
                }
                return jsonify(profile), 200

        logger.info(f"Профиль для telegram_id={telegram_id} не найден в таблице авторизации")
        return jsonify({'error': 'user_not_found'}), 404
    except Exception as e:
        logger.error(f"API Error in /api/profile: {e}")
        return jsonify({'error': 'Internal Server Error'}), 500

@app.route('/webhook/promotions', methods=['GET', 'POST'])
def handle_promotion_webhook():
    """Обработчик webhook от Google Sheets для публикации акций"""
    # Для GET запроса (когда открывают в браузере) - показываем информационную страницу
    if request.method == 'GET':
        return jsonify({
            'status': 'webhook_active',
            'message': 'Webhook endpoint для уведомлений о публикации акций',
            'method': 'POST',
            'url': '/webhook/promotions',
            'note': 'Этот endpoint работает только с POST запросами. Браузер делает GET запрос, поэтому показывается эта информация.'
        }), 200
    
    # Обработка POST запроса (от Google Apps Script)
    try:
        data = request.get_json()
        promotion_data = data.get('promotion', {})
        action = data.get('action', '')
        title = promotion_data.get('title', 'Неизвестная акция')
        status = promotion_data.get('status', '')
        
        logger.info(f"Получен webhook от Google Sheets: action={action}, title='{title}', status='{status}'")
        logger.info(f"Данные акции: {promotion_data}")
        
        # Проверяем секретный ключ для безопасности
        secret_key = request.headers.get('X-Webhook-Secret')
        expected_secret = os.getenv('WEBHOOK_SECRET', 'default_secret')
        
        if secret_key != expected_secret:
            logger.warning(f"Неверный секретный ключ webhook: получен '{secret_key}', ожидается '{expected_secret}'")
            return jsonify({'error': 'Unauthorized'}), 401
        
        if action == 'publish':
            # Запускаем асинхронную функцию в новом event loop
            import asyncio
            import threading
            
            def run_async(coro):
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(coro)
                finally:
                    loop.close()
            
            # Запускаем в отдельном потоке, чтобы не блокировать ответ webhook
            threading.Thread(target=run_async, args=(send_promotion_notification(promotion_data),), daemon=True).start()
        elif action == 'update':
            import asyncio
            import threading
            
            def run_async(coro):
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(coro)
                finally:
                    loop.close()
            
            threading.Thread(target=run_async, args=(send_promotion_update_notification(promotion_data),), daemon=True).start()
        
        return jsonify({'status': 'success'})
        
    except Exception as e:
        logger.error(f"Ошибка в webhook handler: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500

async def send_promotion_notification(promotion_data):
    """Отправляет уведомление о новой акции всем авторизованным пользователям"""
    try:
        title = promotion_data.get('title', 'Новая акция')
        description = promotion_data.get('description', '')
        start_date = promotion_data.get('start_date', '')
        end_date = promotion_data.get('end_date', '')
        
        # Формируем сообщение для акций со статусом "Активна"
        # Webhook теперь отправляется только для статуса "Активна"
        message = "🎉 **Новая акция!**\n\n"
        message += f"**{title}**\n\n"
        if description:
            message += f"📝 {description}\n\n"
        if start_date and end_date:
            message += f"📅 Период: {start_date} - {end_date}\n\n"
        message += "Нажмите кнопку ниже, чтобы посмотреть все акции!"
        
        # Создаем кнопку для открытия Mini App (добавляем версию для сброса кеша)
        version = "v=20260108-2"
        menu_url = (
            f"{web_app_url}menu.html?{version}#promotions"
            if web_app_url.endswith('/')
            else f"{web_app_url}/menu.html?{version}#promotions"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "👀 Посмотреть все акции", 
                web_app=WebAppInfo(url=menu_url)
            )]
        ])
        
        # Получаем всех авторизованных пользователей
        logger.info(f"👥 Получение списка авторизованных пользователей для отправки уведомления о акции '{title}'")
        authorized_users = get_authorized_users()
        logger.info(f"👥 Найдено {len(authorized_users)} авторизованных пользователей для отправки уведомления")
        
        if not authorized_users:
            logger.warning(f"⚠️ Нет авторизованных пользователей для отправки уведомления о акции '{title}'")
            # Отправляем уведомление админу, если есть
            if admin_telegram_id:
                try:
                    await bot.send_message(
                        chat_id=admin_telegram_id,
                        text=f"⚠️ **Проблема с уведомлениями**\n\n"
                             f"Публикация акции '{title}' прошла успешно, но нет авторизованных пользователей для отправки уведомлений.\n\n"
                             f"Проверьте таблицу авторизации.",
                        parse_mode='Markdown'
                    )
                    logger.info(f"📧 Уведомление о проблеме отправлено админу {admin_telegram_id}")
                except Exception as e:
                    logger.error(f"❌ Ошибка отправки уведомления админу: {e}")
            return
        
        # Отправляем уведомления
        sent_count = 0
        failed_count = 0
        for user_id in authorized_users:
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=message,
                    parse_mode='Markdown',
                    reply_markup=keyboard
                )
                sent_count += 1
                logger.info(f"✅ Уведомление о акции '{title}' (статус: {status}) отправлено пользователю {user_id}")
            except Exception as e:
                failed_count += 1
                logger.error(f"❌ Ошибка отправки уведомления пользователю {user_id}: {e}")
        
        logger.info(f"📊 Итого: уведомление о акции '{title}' (статус: {status}) отправлено {sent_count} пользователям, ошибок: {failed_count}")
        
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о акции: {e}", exc_info=True)

async def send_promotion_update_notification(promotion_data):
    """Отправляет уведомление об обновлении акции"""
    try:
        title = promotion_data.get('title', 'Акция обновлена')
        
        message = "🔄 **Акция обновлена!**\n\n"
        message += f"**{title}**\n\n"
        message += "Информация об акции была изменена. Нажмите кнопку ниже, чтобы посмотреть обновления!"
        
        version = "v=20260108-2"
        menu_url = (
            f"{web_app_url}menu.html?{version}#promotions"
            if web_app_url.endswith('/')
            else f"{web_app_url}/menu.html?{version}#promotions"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "👀 Посмотреть акции", 
                web_app=WebAppInfo(url=menu_url)
            )]
        ])
        
        # Отправляем только админу
        if admin_telegram_id:
            await bot.send_message(
                chat_id=admin_telegram_id,
                text=message,
                parse_mode='Markdown',
                reply_markup=keyboard
            )
            logger.info(f"Уведомление об обновлении акции '{title}' отправлено админу")
        
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления об обновлении акции: {e}")

def get_authorized_users():
    """Получает список всех авторизованных пользователей"""
    try:
        if not auth_service or not auth_service.worksheet:
            logger.error("AuthService или worksheet недоступен")
            return []
            
        records = auth_service.worksheet.get_all_records()
        logger.info(f"📋 Всего записей в таблице авторизации: {len(records)}")
        authorized_users = []
        
        for record in records:
            status = record.get('Статус авторизации', '').strip().lower()
            telegram_id_str = record.get('Telegram ID', '')
            
            # Поддерживаем оба варианта статуса: русский "авторизован" и английский "authorized"
            is_authorized = status in ('авторизован', 'authorized')
            
            if is_authorized and telegram_id_str:
                try:
                    telegram_id = int(telegram_id_str)
                    authorized_users.append(telegram_id)
                    logger.debug(f"✅ Найден авторизованный пользователь: ID={telegram_id}, статус='{record.get('Статус авторизации', '')}'")
                except (ValueError, TypeError) as e:
                    logger.warning(f"⚠️ Не удалось преобразовать Telegram ID в число: '{telegram_id_str}' для записи: {record.get('ФИО партнера', 'N/A')}")
                    continue
            elif telegram_id_str:
                logger.debug(f"⏭️ Пропущен пользователь (статус='{record.get('Статус авторизации', '')}'): ID={telegram_id_str}")
        
        logger.info(f"📋 Найдено {len(authorized_users)} авторизованных пользователей из {len(records)} записей")
        if authorized_users:
            logger.info(f"📋 Список ID авторизованных пользователей: {authorized_users[:10]}")  # Показываем первые 10
        return authorized_users
        
    except Exception as e:
        logger.error(f"Ошибка получения авторизованных пользователей: {e}", exc_info=True)
        return []

@app.route('/')
def index():
    """Serve the authorization page"""
    return app.send_static_file('index.html')

@app.route('/menu.html')
def menu():
    """Serve the menu page"""
    return app.send_static_file('menu.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
