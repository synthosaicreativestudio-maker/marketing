#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Диагностика авторизации - проверяет подключение к Google Sheets и данные авторизации
"""

import os
from dotenv import load_dotenv
from sheets_client import GoogleSheetsClient

def main():
    print("=== ДИАГНОСТИКА АВТОРИЗАЦИИ ===")
    
    # Загружаем переменные окружения
    load_dotenv()
    if not os.getenv('TELEGRAM_TOKEN') and os.path.exists('bot.env'):
        load_dotenv('bot.env', override=True)
    
    # Проверяем файлы
    print(f"✓ Файл credentials.json: {'✅ ЕСТЬ' if os.path.exists('credentials.json') else '❌ НЕТ'}")
    print(f"✓ Файл .env: {'✅ ЕСТЬ' if os.path.exists('.env') else '❌ НЕТ'}")
    print(f"✓ SHEET_URL в .env: {'✅ ЕСТЬ' if os.getenv('SHEET_URL') else '❌ НЕТ'}")
    print(f"✓ TICKETS_SHEET_URL в .env: {'✅ ЕСТЬ' if os.getenv('TICKETS_SHEET_URL') else '❌ НЕТ'}")
    
    # Проверяем подключение к основной таблице (авторизация)
    SHEET_URL = os.getenv('SHEET_URL')
    WORKSHEET_NAME = os.getenv('WORKSHEET_NAME', 'список сотрудников для авторизации')
    
    if not SHEET_URL or not os.path.exists('credentials.json'):
        print("❌ Не хватает данных для подключения к Google Sheets")
        print("   Нужны: SHEET_URL в .env и файл credentials.json")
        return
    
    try:
        print(f"\n🔄 Подключаемся к таблице авторизации...")
        print(f"   URL: {SHEET_URL[:50]}...")
        print(f"   Лист: {WORKSHEET_NAME}")
        
        client = GoogleSheetsClient('credentials.json', SHEET_URL, WORKSHEET_NAME)
        
        if client.sheet:
            print("✅ Подключение к таблице авторизации: УСПЕШНО")
            print(f"   Название листа: {client.sheet.title}")
            
            # Читаем заголовки
            headers = client.sheet.row_values(1)
            print(f"   Заголовки: {headers}")
            
            # Проверяем данные авторизации
            print(f"\n📊 Проверяем данные авторизации...")
            
            # Читаем все статусы и ID
            all_statuses = client.sheet.col_values(4)  # Колонка D
            all_ids = client.sheet.col_values(5)       # Колонка E
            
            print(f"   Всего строк со статусами: {len(all_statuses)}")
            print(f"   Всего строк с Telegram ID: {len(all_ids)}")
            
            if len(all_statuses) > 1:
                print(f"   Первые 5 статусов: {all_statuses[1:6]}")
            if len(all_ids) > 1:
                print(f"   Первые 5 Telegram ID: {all_ids[1:6]}")
            
            # Считаем авторизованных пользователей
            auth_count = 0
            auth_ids = []
            
            for i in range(1, min(len(all_statuses), len(all_ids))):
                status = str(all_statuses[i]).strip() if i < len(all_statuses) else ""
                user_id = str(all_ids[i]).strip() if i < len(all_ids) else ""
                
                if status == "авторизован" and user_id:
                    auth_count += 1
                    auth_ids.append(user_id)
                    if auth_count <= 3:
                        print(f"   Строка {i+1}: статус='{status}', Telegram ID='{user_id}'")
            
            print(f"\n📈 ИТОГО АВТОРИЗОВАННЫХ ПОЛЬЗОВАТЕЛЕЙ: {auth_count}")
            if auth_ids:
                print(f"   ID авторизованных: {auth_ids[:5]}{'...' if len(auth_ids) > 5 else ''}")
            else:
                print("   ⚠️  НЕ НАЙДЕНО НИ ОДНОГО АВТОРИЗОВАННОГО ПОЛЬЗОВАТЕЛЯ")
                print("      Возможные причины:")
                print("      - Нет пользователей со статусом 'авторизован' в колонке D")
                print("      - Пустые Telegram ID в колонке E")
                print("      - Неправильный формат данных")
        
        else:
            print("❌ Не удалось подключиться к таблице")
            
    except Exception as e:
        print(f"❌ Ошибка при подключении: {e}")
    
    # Проверяем таблицу обращений
    TICKETS_SHEET_URL = os.getenv('TICKETS_SHEET_URL')
    TICKETS_WORKSHEET = os.getenv('TICKETS_WORKSHEET', 'обращения')
    
    if TICKETS_SHEET_URL:
        print(f"\n🔄 Проверяем таблицу обращений...")
        try:
            tickets_client = GoogleSheetsClient('credentials.json', TICKETS_SHEET_URL, TICKETS_WORKSHEET)
            if tickets_client.sheet:
                print("✅ Подключение к таблице обращений: УСПЕШНО")
                print(f"   Название листа: {tickets_client.sheet.title}")
                
                # Считаем количество обращений
                all_tickets = tickets_client.sheet.get_all_values()
                print(f"   Всего строк с обращениями: {len(all_tickets)}")
            else:
                print("❌ Не удалось подключиться к таблице обращений")
        except Exception as e:
            print(f"❌ Ошибка подключения к таблице обращений: {e}")
    else:
        print("\n⚠️  TICKETS_SHEET_URL не задан - таблица обращений отключена")
    
    print(f"\n📋 ЗАКЛЮЧЕНИЕ:")
    print("   Данные авторизации записываются в таблицу 'список сотрудников для авторизации'")
    print("   Обращения и сообщения записываются в таблицу 'обращения'")
    print("   Если авторизованных пользователей 0 - проверьте данные в таблице авторизации")

if __name__ == "__main__":
    main()