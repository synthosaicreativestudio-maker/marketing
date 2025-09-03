#!/usr/bin/env python3
"""
Скрипт для полного сброса Telegram webhook соединений
Решает проблему: "Conflict: terminated by other getUpdates request"
"""

import os
import requests
import sys
import time
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()
if not os.getenv('TELEGRAM_TOKEN') and os.path.exists('bot.env'):
    load_dotenv('bot.env', override=True)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TELEGRAM_TOKEN:
    print("❌ TELEGRAM_TOKEN не найден в переменных окружения!")
    sys.exit(1)

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def make_telegram_request(method, params=None):
    """Выполняет запрос к Telegram API"""
    url = f"{TELEGRAM_API_URL}/{method}"
    try:
        response = requests.post(url, json=params, timeout=30)
        return response.json()
    except Exception as e:
        print(f"❌ Ошибка запроса к Telegram API: {e}")
        return None

def reset_webhook():
    """Сбрасывает webhook для очистки соединений"""
    print("🔄 Сброс webhook соединений...")
    
    # 1. Устанавливаем пустой webhook
    result = make_telegram_request("setWebhook", {"url": ""})
    if result and result.get("ok"):
        print("✅ Webhook сброшен")
    else:
        print(f"❌ Ошибка сброса webhook: {result}")
    
    # 2. Ожидание обработки
    time.sleep(3)
    
    # 3. Получаем информацию о webhook
    webhook_info = make_telegram_request("getWebhookInfo")
    if webhook_info and webhook_info.get("ok"):
        print(f"📋 Webhook info: {webhook_info['result']}")
    
    return True

def drop_pending_updates():
    """Сбрасывает все pending updates"""
    print("🗑️ Сброс всех pending updates...")
    
    # Устанавливаем высокий offset для сброса всех updates
    result = make_telegram_request("getUpdates", {"offset": -1, "timeout": 1})
    if result and result.get("ok"):
        updates = result.get("result", [])
        if updates:
            # Устанавливаем offset на последний update_id + 1
            last_update_id = max(update["update_id"] for update in updates)
            result = make_telegram_request("getUpdates", {"offset": last_update_id + 1, "timeout": 1})
            print(f"✅ Сброшено {len(updates)} pending updates")
        else:
            print("✅ Pending updates не найдены")
    else:
        print(f"❌ Ошибка сброса updates: {result}")

def main():
    """Основная функция сброса"""
    print("🚀 ПОЛНЫЙ СБРОС TELEGRAM СОЕДИНЕНИЙ")
    print("=" * 50)
    
    # Шаг 1: Сброс webhook
    reset_webhook()
    
    # Шаг 2: Сброс pending updates  
    drop_pending_updates()
    
    # Шаг 3: Финальная проверка
    print("\n🔍 Финальная проверка статуса...")
    webhook_info = make_telegram_request("getWebhookInfo")
    if webhook_info and webhook_info.get("ok"):
        info = webhook_info["result"]
        print(f"   Webhook URL: {info.get('url', 'НЕ УСТАНОВЛЕН')}")
        print(f"   Pending updates: {info.get('pending_update_count', 0)}")
        print(f"   Last error: {info.get('last_error_message', 'НЕТ ОШИБОК')}")
    
    print("\n✅ СБРОС ЗАВЕРШЕН")
    print("Теперь можно безопасно запустить бота через polling")
    
if __name__ == "__main__":
    main()