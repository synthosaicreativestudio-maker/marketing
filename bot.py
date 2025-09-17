#!/usr/bin/env python3
"""MarketingBot - упрощенный бот для авторизации партнеров"""
import json
import logging
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)


class MarketingBot:
    """Простой Telegram бот для авторизации партнеров"""
    
    def __init__(self, token: str, webapp_url: str):
        self.token = token
        self.api_url = f"https://api.telegram.org/bot{token}"
        self.webapp_url = webapp_url
        self.offset = 0
        self.running = False

    def send_message(self, chat_id: int, text: str, reply_markup=None) -> dict:
        """Отправка сообщения через Telegram API"""
        data = {
            'chat_id': chat_id,
            'text': text
        }
        if reply_markup:
            data['reply_markup'] = json.dumps(reply_markup)
        
        try:
            response = requests.post(
                f"{self.api_url}/sendMessage", 
                json=data, 
                timeout=30
            )
            return response.json()
        except requests.RequestException as e:
            log.error(f"Error sending message: {e}")
            return {'ok': False, 'error': str(e)}

    def get_updates(self) -> dict:
        """Получение обновлений от Telegram"""
        params = {
            'offset': self.offset,
            'timeout': 30
        }
        try:
            response = requests.get(
                f"{self.api_url}/getUpdates", 
                params=params, 
                timeout=35
            )
            return response.json()
        except requests.RequestException as e:
            log.error(f"Error getting updates: {e}")
            return {'ok': False, 'result': []}

    def handle_start(self, update: dict):
        """Обработка команды /start"""
        message = update.get('message', {})
        chat_id = message.get('chat', {}).get('id')
        user = message.get('from', {})
        
        if not chat_id:
            return
        
        name = user.get('first_name') or user.get('username') or "пользователь"
        text = f"Привет, {name}!\n\nДля авторизации нажмите кнопку ниже:"
        
        # Создаем клавиатуру с WebApp кнопкой
        keyboard = {
            'keyboard': [[{
                'text': '🔐 Авторизоваться',
                'web_app': {'url': self.webapp_url}
            }]],
            'resize_keyboard': True,
            'one_time_keyboard': True
        }
        
        result = self.send_message(chat_id, text, keyboard)
        if result.get('ok'):
            log.info(f"Sent start message to user {chat_id}")
        else:
            log.error(f"Failed to send start message: {result}")

    def handle_web_app_data(self, update: dict):
        """Обработка данных из WebApp"""
        message = update.get('message', {})
        chat_id = message.get('chat', {}).get('id')
        web_app_data = message.get('web_app_data', {})
        data = web_app_data.get('data', '')
        
        if not chat_id:
            return
        
        log.info(f"Received web app data from chat {chat_id}")
        
        try:
            # Парсим JSON данные из WebApp
            auth_data = json.loads(data)
            partner_code = auth_data.get('partner_code', '').strip()
            partner_phone = auth_data.get('partner_phone', '').strip()
            
            # Валидация данных
            if not partner_code.isdigit():
                self.send_message(chat_id, "❌ Код партнёра должен содержать только цифры")
                return
            
            if not partner_phone:
                self.send_message(chat_id, "❌ Введите номер телефона")
                return
            
            # Проверка авторизации
            if self.check_authorization(partner_code, partner_phone, chat_id):
                self.send_message(chat_id, "✅ Авторизация успешна!")
            else:
                self.send_message(chat_id, "❌ Партнёр не найден в базе")
                
        except json.JSONDecodeError:
            log.error(f"Invalid JSON data from WebApp: {data}")
            self.send_message(chat_id, "❌ Ошибка обработки данных")
        except Exception as e:
            log.error(f"Error processing web app data: {e}")
            self.send_message(chat_id, "❌ Ошибка обработки данных")

    def check_authorization(self, partner_code: str, partner_phone: str, telegram_id: int) -> bool:
        """Проверка авторизации партнера"""
        try:
            # Пытаемся использовать Google Sheets
            from sheets import normalize_phone, find_row_by_partner_and_phone, update_row_with_auth, SheetsNotConfiguredError
            
            phone_norm = normalize_phone(partner_phone)
            row = find_row_by_partner_and_phone(partner_code, phone_norm)
            
            if row:
                update_row_with_auth(row, telegram_id, status='authorized')
                log.info(f"Authorized partner {partner_code} with phone {phone_norm}")
                return True
            else:
                log.warning(f"Partner {partner_code} with phone {phone_norm} not found")
                return False
                
        except (ImportError, SheetsNotConfiguredError):
            # Fallback: простая проверка для разработки
            log.info("Using fallback authorization (Google Sheets not configured)")
            return self.fallback_authorization(partner_code, partner_phone)
        except Exception as e:
            log.error(f"Error in authorization check: {e}")
            return False

    def fallback_authorization(self, partner_code: str, partner_phone: str) -> bool:
        """Fallback авторизация для разработки"""
        # Простая проверка для демо (как в оригинальном коде)
        if partner_code == '111098' and '1055' in partner_phone:
            log.info(f"Fallback authorization successful for {partner_code}")
            return True
        return False

    def process_update(self, update: dict):
        """Обработка одного обновления"""
        try:
            if 'message' in update:
                message = update['message']
                text = message.get('text', '')
                
                # Обработка команды /start
                if text == '/start':
                    self.handle_start(update)
                # Обработка данных из WebApp
                elif 'web_app_data' in message:
                    self.handle_web_app_data(update)
                    
        except Exception as e:
            log.error(f"Error processing update: {e}")

    def start_polling(self):
        """Запуск бота в режиме polling"""
        self.running = True
        log.info("🚀 MarketingBot запущен!")
        log.info(f"📱 WebApp URL: {self.webapp_url}")
        
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
                log.info("Остановка бота...")
                self.running = False
                break
            except Exception as e:
                log.error(f"Polling error: {e}")
                time.sleep(5)

    def stop(self):
        """Остановка бота"""
        self.running = False
        log.info("Бот остановлен")


def main():
    """Запуск бота"""
    # Получаем конфигурацию из переменных окружения
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    webapp_url = os.environ.get("WEBAPP_URL", "https://your-domain.com/webapp")
    
    if not token:
        log.error("❌ TELEGRAM_BOT_TOKEN не установлен!")
        log.error("Установите переменную окружения или добавьте в .env файл")
        return 1
    
    # Проверяем наличие WebApp URL
    if webapp_url == "https://your-domain.com/webapp":
        log.warning("⚠️ WEBAPP_URL не настроен, используется заглушка")
    
    log.info(f"🔧 Конфигурация:")
    log.info(f"   Token: {token[:15]}...")
    log.info(f"   WebApp URL: {webapp_url}")
    
    # Создаем и запускаем бота
    bot = MarketingBot(token, webapp_url)
    
    try:
        bot.start_polling()
    except KeyboardInterrupt:
        log.info("Бот остановлен пользователем")
    finally:
        bot.stop()
    
    return 0


if __name__ == "__main__":
    exit(main())
