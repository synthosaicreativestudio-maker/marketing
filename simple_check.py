#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Простая проверка файлов проекта
"""

import os

def main():
    print("=== ПРОСТАЯ ДИАГНОСТИКА ===")
    print()
    
    # Проверяем важные файлы
    files_to_check = [
        ('.env', 'Настройки окружения'),
        ('credentials.json', 'Ключи Google Sheets'),
        ('bot.py', 'Основной файл бота'),
        ('sheets_client.py', 'Клиент Google Sheets'),
    ]
    
    print("📁 ПРОВЕРКА ФАЙЛОВ:")
    all_files_ok = True
    for filename, description in files_to_check:
        exists = os.path.exists(filename)
        status = "✅ ЕСТЬ" if exists else "❌ НЕТ"
        print(f"   {filename:<20} {description:<25} {status}")
        if not exists:
            all_files_ok = False
    
    print()
    
    # Если есть .env, читаем его
    if os.path.exists('.env'):
        print("🔧 НАСТРОЙКИ ИЗ .ENV:")
        try:
            with open('.env', 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            important_vars = ['TELEGRAM_TOKEN', 'SHEET_URL', 'TICKETS_SHEET_URL', 'OPENAI_API_KEY']
            found_vars = {}
            
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key = line.split('=')[0].strip()
                        value = line.split('=', 1)[1].strip()
                        found_vars[key] = len(value) > 0
            
            for var in important_vars:
                status = "✅ ЕСТЬ" if found_vars.get(var, False) else "❌ НЕТ"
                print(f"   {var:<20} {status}")
                
        except Exception as e:
            print(f"   ❌ Ошибка чтения .env: {e}")
    else:
        print("⚠️  Файл .env не найден!")
        print("   Скопируйте .env.example в .env и заполните его")
    
    print()
    print("🔍 ЧТО ПРОВЕРИТЬ В GOOGLE SHEETS:")
    print("   1. Откройте таблицу авторизации (SHEET_URL)")
    print("   2. Найдите лист 'список сотрудников для авторизации'")
    print("   3. Посмотрите колонки:")
    print("      - Колонка A: Код партнера")
    print("      - Колонка B: ФИО")  
    print("      - Колонка C: Телефон")
    print("      - Колонка D: Статус авторизации (здесь должно появиться 'авторизован')")
    print("      - Колонка E: Telegram ID (здесь должен появиться ID пользователя)")
    print()
    print("💡 ВАЖНО:")
    print("   - Авторизация записывается в основную таблицу (SHEET_URL)")
    print("   - Сообщения записываются в таблицу обращений (TICKETS_SHEET_URL)")
    print("   - Это РАЗНЫЕ таблицы!")
    
    if not all_files_ok:
        print()
        print("⚠️  НАЙДЕНЫ ПРОБЛЕМЫ:")
        print("   Не хватает важных файлов для работы бота")
        print("   Убедитесь что у вас есть .env и credentials.json")

if __name__ == "__main__":
    main()