#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Тест системы уведомлений об акциях
Проверяет весь цикл: обнаружение → получение пользователей → отправка
"""

import os
import sys
from dotenv import load_dotenv

# Добавляем путь к проекту
sys.path.append('/Users/verakoroleva/Desktop/@marketing')

from promotions_client import PromotionsClient
from sheets_client import GoogleSheetsClient
from config import PROMOTIONS_CONFIG, PROMOTIONS_SHEET_URL, AUTH_WORKSHEET_NAME

def test_promotions_system():
    print("🧪 === ТЕСТ СИСТЕМЫ АКЦИЙ ===\n")
    
    # Загружаем переменные окружения
    load_dotenv()
    
    # 1. Тестируем клиент акций
    print("1️⃣ ТЕСТ КЛИЕНТА АКЦИЙ:")
    promotions_client = PromotionsClient('credentials.json', PROMOTIONS_SHEET_URL)
    connected = promotions_client.connect()
    
    if not connected:
        print("❌ Не удалось подключиться к таблице акций!")
        return
    
    print("✅ Подключение к таблице акций успешно")
    
    # Проверяем новые акции
    new_promotions = promotions_client.get_new_published_promotions()
    print(f"📬 Новых акций для уведомления: {len(new_promotions)}")
    
    if new_promotions:
        for promo in new_promotions:
            print(f"   • {promo['name']} (строка {promo['row']})")
    
    # Проверяем активные акции  
    active_promotions = promotions_client.get_active_promotions()
    print(f"🎯 Активных акций: {len(active_promotions)}")
    
    # 2. Тестируем получение авторизованных пользователей
    print(f"\n2️⃣ ТЕСТ АВТОРИЗОВАННЫХ ПОЛЬЗОВАТЕЛЕЙ:")
    
    sheet_url = os.getenv('SHEET_URL')
    if not sheet_url:
        print("❌ SHEET_URL не настроен!")
        return
        
    auth_client = GoogleSheetsClient('credentials.json', sheet_url, AUTH_WORKSHEET_NAME)
    
    try:
        # Тестируем пакетное получение пользователей
        authorized_users_dict = auth_client.get_authorized_users_batch()
        print(f"📊 Тип возвращаемых данных: {type(authorized_users_dict)}")
        print(f"👥 Найдено авторизованных пользователей: {len(authorized_users_dict)}")
        
        if authorized_users_dict:
            print("   Детали пользователей:")
            for telegram_id, user_data in list(authorized_users_dict.items())[:3]:
                print(f"   • Telegram ID: {telegram_id}")
                print(f"     Тип данных: {type(user_data)}")
                print(f"     Данные: {user_data}")
                print()
        
        # 3. Тестируем преобразование данных (как в боте)
        print("3️⃣ ТЕСТ ПРЕОБРАЗОВАНИЯ ДАННЫХ:")
        users_with_telegram = []
        
        for telegram_id, user_data in authorized_users_dict.items():
            if not isinstance(user_data, dict):
                print(f"⚠️ Проблема с пользователем {telegram_id}: данные не являются словарем ({type(user_data)})")
                continue
                
            user_obj = {
                'telegram_id': telegram_id,
                'code': user_data.get('code', ''),
                'phone': user_data.get('phone', ''),
                'fio': user_data.get('fio', '')
            }
            users_with_telegram.append(user_obj)
        
        print(f"✅ Преобразовано пользователей: {len(users_with_telegram)}")
        
        # 4. Симуляция отправки уведомлений
        print(f"\n4️⃣ СИМУЛЯЦИЯ ОТПРАВКИ УВЕДОМЛЕНИЙ:")
        
        if new_promotions and users_with_telegram:
            print(f"🎉 Будет отправлено {len(new_promotions)} уведомлений {len(users_with_telegram)} пользователям")
            
            for promo in new_promotions:
                print(f"\n📢 Акция: {promo['name']}")
                print(f"   Получатели:")
                
                for user in users_with_telegram:
                    telegram_id = user.get('telegram_id')
                    fio = user.get('fio', 'Без имени')
                    if telegram_id:
                        print(f"   • {fio} (ID: {telegram_id})")
                
                # Здесь мы могли бы пометить уведомление как отправленное
                # promotions_client.mark_notification_sent(promo['row'])
                print(f"   ✅ Уведомление готово к отправке")
        
        elif not new_promotions:
            print("ℹ️ Нет новых акций для отправки")
        elif not users_with_telegram:
            print("⚠️ Нет авторизованных пользователей для уведомления")
        
        print(f"\n🎉 === ТЕСТ ЗАВЕРШЕН ===")
        
        # Рекомендации
        print(f"\n💡 РЕКОМЕНДАЦИИ:")
        if not new_promotions:
            print("   • Добавьте тестовую акцию со статусом 'Опубликовано' в таблицу")
        if not users_with_telegram:
            print("   • Проверьте таблицу авторизации - должны быть пользователи со статусом 'авторизован' и Telegram ID")
        if new_promotions and users_with_telegram:
            print("   • Система готова к работе! Уведомления будут отправляться автоматически каждые 5 минут")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_promotions_system()