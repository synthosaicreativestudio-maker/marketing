"""
Webhook handler для получения уведомлений от Google Sheets
"""
import logging
import os
from flask import Flask, request, jsonify
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from auth_service import AuthService

logger = logging.getLogger(__name__)

app = Flask(__name__)

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

@app.route('/webhook/promotions', methods=['POST'])
def handle_promotion_webhook():
    """Обработчик webhook от Google Sheets для публикации акций"""
    try:
        data = request.get_json()
        logger.info(f"Получен webhook от Google Sheets: {data}")
        
        # Проверяем секретный ключ для безопасности
        secret_key = request.headers.get('X-Webhook-Secret')
        expected_secret = os.getenv('WEBHOOK_SECRET', 'default_secret')
        
        if secret_key != expected_secret:
            logger.warning("Неверный секретный ключ webhook")
            return jsonify({'error': 'Unauthorized'}), 401
        
        # Извлекаем данные акции
        promotion_data = data.get('promotion', {})
        action = data.get('action', '')
        
        if action == 'publish':
            import asyncio
            asyncio.create_task(send_promotion_notification(promotion_data))
        elif action == 'update':
            import asyncio
            asyncio.create_task(send_promotion_update_notification(promotion_data))
        
        return jsonify({'status': 'success'})
        
    except Exception as e:
        logger.error(f"Ошибка в webhook handler: {e}")
        return jsonify({'error': 'Internal server error'}), 500

async def send_promotion_notification(promotion_data):
    """Отправляет уведомление о новой акции всем авторизованным пользователям"""
    try:
        title = promotion_data.get('title', 'Новая акция')
        description = promotion_data.get('description', '')
        start_date = promotion_data.get('start_date', '')
        end_date = promotion_data.get('end_date', '')
        
        # Формируем сообщение
        message = "🎉 **Новая акция!**\n\n"
        message += f"**{title}**\n\n"
        if description:
            message += f"📝 {description}\n\n"
        if start_date and end_date:
            message += f"📅 Период: {start_date} - {end_date}\n\n"
        message += "Нажмите кнопку ниже, чтобы посмотреть все акции!"
        
        # Создаем кнопку для открытия Mini App
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "👀 Посмотреть все акции", 
                web_app={'url': f"{web_app_url}menu.html#promotions"}
            )]
        ])
        
        # Получаем всех авторизованных пользователей
        authorized_users = get_authorized_users()
        
        # Отправляем уведомления
        sent_count = 0
        for user_id in authorized_users:
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=message,
                    parse_mode='Markdown',
                    reply_markup=keyboard
                )
                sent_count += 1
                logger.info(f"Уведомление о акции '{title}' отправлено пользователю {user_id}")
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления пользователю {user_id}: {e}")
        
        logger.info(f"Уведомление о акции '{title}' отправлено {sent_count} пользователям")
        
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о акции: {e}")

async def send_promotion_update_notification(promotion_data):
    """Отправляет уведомление об обновлении акции"""
    try:
        title = promotion_data.get('title', 'Акция обновлена')
        
        message = "🔄 **Акция обновлена!**\n\n"
        message += f"**{title}**\n\n"
        message += "Информация об акции была изменена. Нажмите кнопку ниже, чтобы посмотреть обновления!"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "👀 Посмотреть акции", 
                web_app={'url': f"{web_app_url}menu.html#promotions"}
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
        records = auth_service.worksheet.get_all_records()
        authorized_users = []
        
        for record in records:
            if (record.get('Статус авторизации', '').lower() == 'авторизован' and 
                record.get('Telegram ID')):
                try:
                    telegram_id = int(record.get('Telegram ID'))
                    authorized_users.append(telegram_id)
                except (ValueError, TypeError):
                    continue
        
        logger.info(f"Найдено {len(authorized_users)} авторизованных пользователей")
        return authorized_users
        
    except Exception as e:
        logger.error(f"Ошибка получения авторизованных пользователей: {e}")
        return []

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
