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
        
        keyboard = {
            'inline_keyboard': [[{
                'text': 'Авторизоваться',
                'callback_data': 'authorize'
            }]]
        }
        
        self.send_message(chat_id, text, keyboard)
    
    def handle_authorize_callback(self, update):
        """Handle authorization callback."""
        callback_query = update.get('callback_query', {})
        callback_query_id = callback_query.get('id')
        message = callback_query.get('message', {})
        chat_id = message.get('chat', {}).get('id')
        message_id = message.get('message_id')
        
        self.answer_callback_query(callback_query_id)
        
        webapp_url = os.environ.get("WEBAPP_URL", "https://your-webapp-url.com/auth")
        text = f"Для авторизации, пожалуйста, перейдите по ссылке: {webapp_url}"
        
        self.edit_message_text(chat_id, message_id, text)
    
    def process_update(self, update):
        """Process single update."""
        try:
            # Handle messages
            if 'message' in update:
                message = update['message']
                text = message.get('text', '')
                if text == '/start':
                    self.handle_start(update)
            
            # Handle callback queries
            elif 'callback_query' in update:
                callback_query = update['callback_query']
                data = callback_query.get('data', '')
                if data == 'authorize':
                    self.handle_authorize_callback(update)
        
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
