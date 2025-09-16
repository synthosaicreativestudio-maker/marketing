#!/usr/bin/env python3
"""Synchronous Telegram bot using HTTP API directly."""
import logging
import os
import time
import json
from pathlib import Path
import requests
from threading import Thread

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


class TelegramBot:
    def __init__(self, token):
        self.token = token
        self.api_url = f"https://api.telegram.org/bot{token}"
        self.offset = 0
        self.running = False
    
    def send_message(self, chat_id, text, reply_markup=None):
        """Send message via HTTP API."""
        data = {
            'chat_id': chat_id,
            'text': text
        }
        if reply_markup:
            data['reply_markup'] = json.dumps(reply_markup)
        
        response = requests.post(f"{self.api_url}/sendMessage", json=data, timeout=30)
        return response.json()
    
    def answer_callback_query(self, callback_query_id):
        """Answer callback query."""
        data = {'callback_query_id': callback_query_id}
        response = requests.post(f"{self.api_url}/answerCallbackQuery", json=data, timeout=30)
        return response.json()
    
    def edit_message_text(self, chat_id, message_id, text):
        """Edit message text."""
        data = {
            'chat_id': chat_id,
            'message_id': message_id,
            'text': text
        }
        response = requests.post(f"{self.api_url}/editMessageText", json=data, timeout=30)
        return response.json()
    
    def get_updates(self):
        """Get updates from Telegram."""
        params = {
            'offset': self.offset,
            'timeout': 30
        }
        try:
            response = requests.get(f"{self.api_url}/getUpdates", params=params, timeout=35)
            return response.json()
        except requests.RequestException as e:
            log.error(f"Error getting updates: {e}")
            return {'ok': False, 'result': []}
    
    def handle_start(self, update):
        """Handle /start command."""
        message = update.get('message', {})
        chat_id = message.get('chat', {}).get('id')
        user = message.get('from', {})
        
        name = user.get('first_name') or user.get('username') or "пользователь"
        text = f"Привет, {name}!\nВам необходимо пройти авторизацию."
        
        webapp_url = os.environ.get("WEBAPP_URL", "https://your-webapp-url.com/auth")
        
        keyboard = {
            'keyboard': [[{
                'text': 'Авторизоваться',
                'web_app': {'url': webapp_url}
            }]],
            'resize_keyboard': True,
            'one_time_keyboard': True
        }
        
        self.send_message(chat_id, text, keyboard)
    
    def handle_web_app_data(self, update):
        """Handle data received from Web App."""
        message = update.get('message', {})
        chat_id = message.get('chat', {}).get('id')
        web_app_data = message.get('web_app_data', {})
        data = web_app_data.get('data', '')
        
        log.info(f"Received web app data from chat {chat_id}: {data}")
        
        try:
            # Parse JSON data from web app
            import json
            auth_data = json.loads(data)
            partner_code = auth_data.get('partner_code', '')
            partner_phone = auth_data.get('partner_phone', '')
            
            # Simple validation
            if not partner_code.isdigit():
                self.send_message(chat_id, "❌ Код партнёра должен содержать только цифры")
                return
            
            if not partner_phone:
                self.send_message(chat_id, "❌ Введите номер телефона")
                return
            
            # For now, simple success response (later integrate with sheets)
            if partner_code == '111098' and '1055' in partner_phone:
                self.send_message(chat_id, "✅ Авторизация успешна!")
            else:
                self.send_message(chat_id, "❌ Партнёр не найден в базе")
                
        except Exception as e:
            log.error(f"Error processing web app data: {e}")
            self.send_message(chat_id, "❌ Ошибка обработки данных")
    
    def process_update(self, update):
        """Process single update."""
        try:
            # Handle messages
            if 'message' in update:
                message = update['message']
                text = message.get('text', '')
                if text == '/start':
                    self.handle_start(update)
            
            # Handle web app data from keyboard button
            elif 'message' in update and 'web_app_data' in update['message']:
                self.handle_web_app_data(update)
        
        except Exception as e:
            log.error(f"Error processing update: {e}")
    
    def start_polling(self):
        """Start polling for updates."""
        self.running = True
        log.info("Starting bot polling (HTTP API)")
        
        while self.running:
            try:
                result = self.get_updates()
                
                if result.get('ok'):
                    updates = result.get('result', [])
                    
                    for update in updates:
                        self.process_update(update)
                        self.offset = update['update_id'] + 1
                
                else:
                    log.error(f"API error: {result}")
                    time.sleep(5)
                    
            except KeyboardInterrupt:
                log.info("Stopping bot...")
                self.running = False
                break
            except Exception as e:
                log.error(f"Polling error: {e}")
                time.sleep(5)
    
    def stop(self):
        """Stop the bot."""
        self.running = False


def main():
    """Start the bot."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        log.error("TELEGRAM_BOT_TOKEN env var not set!")
        return

    bot = TelegramBot(token)
    
    try:
        bot.start_polling()
    except KeyboardInterrupt:
        log.info("Bot stopped by user")
    finally:
        bot.stop()


if __name__ == "__main__":
    main()
