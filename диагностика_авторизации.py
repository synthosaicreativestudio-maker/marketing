#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Полная диагностика авторизации - проверяет таблицы Google Sheets
Запустите: python диагностика_авторизации.py
"""

import os
import sys

def check_files():
    """Проверяем наличие необходимых файлов"""
    print("📁 ПРОВЕРКА ФАЙЛОВ:")
    files_ok = True
    for filename, desc in [('.env', 'Настройки'), ('credentials.json', 'Ключи Google'), ('bot.py', 'Бот')]:
        exists = os.path.exists(filename)
        print(f"   {filename:<20} {'✅ ЕСТЬ' if exists else '❌ НЕТ'}")
        if not exists:
            files_ok = False
    return files_ok

def main():
    print("🔍 ПОЛНАЯ ДИАГНОСТИКА АВТОРИЗАЦИИ")
    print("=" * 50)
    
    # 1. Проверяем файлы
    if not check_files():
        print("\n❌ ОШИБКА: Не хватает файлов для работы!")
        print("Убедитесь что у вас есть .env и credentials.json")
        return
    
    print()
    
    # 2. Пробуем загрузить зависимости
    try:
        from dotenv import load_dotenv
        from sheets_client import GoogleSheetsClient
        print("✅ Зависимости загружены успешно")
    except ImportError as e:
        print(f"❌ ОШИБКА: Не установлены зависимости - {e}")
        print("Запустите: pip install -r requirements.txt")
        return
    
    # 3. Загружаем переменные окружения
    load_dotenv()
    if not os.getenv('TELEGRAM_TOKEN') and os.path.exists('bot.env'):
        load_dotenv('bot.env', override=True)
    
    print("🔧 НАСТРОЙКИ:")
    for var in ['TELEGRAM_TOKEN', 'SHEET_URL', 'TICKETS_SHEET_URL', 'OPENAI_API_KEY']:
        val = os.getenv(var)
        print(f"   {var:<20} {'✅ ЕСТЬ' if val else '❌ НЕТ'}")
    
    print()
    
    # 4. Проверяем основную таблицу авторизации
    SHEET_URL = os.getenv('SHEET_URL')
    WORKSHEET_NAME = os.getenv('WORKSHEET_NAME', 'список сотрудников для авторизации')
    
    if not SHEET_URL:
        print("❌ SHEET_URL не задан в .env")
        return
    
    print(f"📊 ТАБЛИЦА АВТОРИЗАЦИИ:")
    print(f"   URL: {SHEET_URL[:60]}...")
    print(f"   Лист: {WORKSHEET_NAME}")
    
    try:
        # Подключаемся к таблице
        client = GoogleSheetsClient('credentials.json', SHEET_URL, WORKSHEET_NAME)
        
        if not client.sheet:
            print("❌ Не удалось подключиться к таблице")
            return
            
        print(f"✅ Подключение успешно: '{client.sheet.title}'")
        
        # Читаем структуру таблицы
        try:
            headers = client.sheet.row_values(1)
            print(f"   Заголовки: {headers[:6]}")
        except:
            print("   ⚠️ Не удалось прочитать заголовки")
        
        # Анализируем данные авторизации
        print("\n📋 АНАЛИЗ АВТОРИЗАЦИИ:")
        
        try:
            all_statuses = client.sheet.col_values(4)  # Колонка D - статусы
            all_ids = client.sheet.col_values(5)       # Колонка E - Telegram ID
            
            print(f"   Всего строк со статусами: {len(all_statuses)}")
            print(f"   Всего строк с ID: {len(all_ids)}")
            
            # Ищем авторизованных пользователей
            authorized_users = []
            
            for i in range(1, min(len(all_statuses), len(all_ids))):  # Пропускаем заголовок
                status = str(all_statuses[i]).strip() if i < len(all_statuses) else ""
                user_id = str(all_ids[i]).strip() if i < len(all_ids) else ""
                
                if status == "авторизован" and user_id:
                    authorized_users.append((i+1, user_id))  # Номер строки и ID
            
            print(f"\n🎯 НАЙДЕНО АВТОРИЗОВАННЫХ ПОЛЬЗОВАТЕЛЕЙ: {len(authorized_users)}")
            
            if authorized_users:
                print("   Список авторизованных:")
                for row_num, user_id in authorized_users[:10]:  # Показываем первых 10
                    print(f"     Строка {row_num}: Telegram ID = {user_id}")
                if len(authorized_users) > 10:
                    print(f"     ... и ещё {len(authorized_users) - 10} пользователей")
            else:
                print("   ❌ НЕТ АВТОРИЗОВАННЫХ ПОЛЬЗОВАТЕЛЕЙ!")
                print("\n   Возможные причины:")
                print("   1. В колонке D нет записей со статусом 'авторизован'")
                print("   2. В колонке E пустые Telegram ID")
                print("   3. Пользователи ещё не проходили авторизацию через бота")
                
                # Покажем что есть в таблице
                print(f"\n   Первые 5 статусов (колонка D): {all_statuses[1:6]}")
                print(f"   Первые 5 ID (колонка E): {all_ids[1:6]}")
            
        except Exception as e:
            print(f"   ❌ Ошибка анализа: {e}")
        
        # Проверяем таблицу обращений
        TICKETS_SHEET_URL = os.getenv('TICKETS_SHEET_URL')
        if TICKETS_SHEET_URL:
            print(f"\n📝 ТАБЛИЦА ОБРАЩЕНИЙ:")
            try:
                tickets_client = GoogleSheetsClient('credentials.json', TICKETS_SHEET_URL, 'обращения')
                if tickets_client.sheet:
                    all_tickets = tickets_client.sheet.get_all_values()
                    print(f"✅ Подключено: '{tickets_client.sheet.title}'")
                    print(f"   Всего строк: {len(all_tickets)}")
                else:
                    print("❌ Не удалось подключиться к таблице обращений")
            except Exception as e:
                print(f"❌ Ошибка подключения к обращениям: {e}")
        
    except Exception as e:
        print(f"❌ ОШИБКА подключения к Google Sheets: {e}")
        print("\nВозможные причины:")
        print("- Неправильный URL таблицы")
        print("- Нет доступа к таблице")
        print("- Проблемы с credentials.json")
        return
    
    print("\n" + "=" * 50)
    print("💡 ВАЖНАЯ ИНФОРМАЦИЯ:")
    print("   • Авторизация записывается в основную таблицу (SHEET_URL)")
    print("   • Колонка D должна содержать 'авторизован'")
    print("   • Колонка E должна содержать Telegram ID пользователя")
    print("   • Сообщения записываются в отдельную таблицу обращений")
    print("   • Это разные таблицы!")
    
    if len(authorized_users) == 0:
        print("\n🚀 ЧТО ДЕЛАТЬ ДАЛЬШЕ:")
        print("   1. Запустите бота: python bot.py")
        print("   2. Попросите пользователя авторизоваться через бота")
        print("   3. Проверьте что данные появились в таблице")
        print("   4. Используйте команду /check_auth в боте для проверки")

if __name__ == "__main__":
    main()