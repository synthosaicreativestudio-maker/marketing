#!/usr/bin/env python3
"""
Скрипт для проверки состояния бота на PythonAnywhere
Запустите этот скрипт на PythonAnywhere для диагностики
"""

import logging
import os
import json
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_pythonanywhere_status():
    """Проверка состояния на PythonAnywhere"""
    print("=== ПРОВЕРКА СОСТОЯНИЯ НА PYTHONANYWHERE ===\n")
    
    # 1. Проверяем переменные окружения
    print("1. Переменные окружения:")
    env_vars = [
        'SHEET_ID', 'SHEET_NAME', 'GCP_SA_JSON', 'GCP_SA_FILE',
        'TELEGRAM_TOKEN', 'WEB_APP_URL', 'SPA_MENU_URL'
    ]
    
    for var in env_vars:
        value = os.getenv(var)
        if value:
            if 'TOKEN' in var or 'JSON' in var:
                print(f"   {var}: ✓ (скрыто)")
            else:
                print(f"   {var}: ✓ {value}")
        else:
            print(f"   {var}: ✗")
    print()
    
    # 2. Проверяем подключение к Google Sheets
    print("2. Подключение к Google Sheets:")
    try:
        from sheets import _get_client_and_sheet
        client, worksheet = _get_client_and_sheet()
        print("   ✓ Подключение успешно")
        print(f"   Название листа: {worksheet.title}")
        print(f"   ID таблицы: {worksheet.spreadsheet.id}")
        
        # Получаем все записи
        records = worksheet.get_all_records()
        print(f"   Всего записей: {len(records)}")
        
        # Показываем первые 3 записи для проверки
        print("   Первые 3 записи:")
        for i, record in enumerate(records[:3], start=2):
            name = record.get('ФИО партнера', '')
            code = record.get('Код партнера', '')
            phone = record.get('Телефон партнера', '')
            status = record.get('Статус авторизации', '')
            print(f"     Строка {i}: {name} | {code} | {phone} | {status}")
        
    except Exception as e:
        print(f"   ✗ Ошибка: {e}")
        return
    print()
    
    # 3. Тестируем поиск конкретного пользователя
    print("3. Тест поиска пользователя Натальи:")
    try:
        from sheets import find_row_by_partner_and_phone, normalize_phone
        
        # Данные из таблицы
        partner_code = '1245797092'
        partner_phone = '89634528665'
        
        print(f"   Ищем: код={partner_code}, телефон={partner_phone}")
        
        phone_norm = normalize_phone(partner_phone)
        print(f"   Нормализованный телефон: {phone_norm}")
        
        row = find_row_by_partner_and_phone(partner_code, phone_norm)
        print(f"   Найденная строка: {row}")
        
        if row:
            print("   ✅ ПОЛЬЗОВАТЕЛЬ НАЙДЕН")
        else:
            print("   ❌ ПОЛЬЗОВАТЕЛЬ НЕ НАЙДЕН")
            
    except Exception as e:
        print(f"   ✗ Ошибка поиска: {e}")
    print()
    
    # 4. Тестируем авторизацию
    print("4. Тест авторизации:")
    try:
        from auth_service import AuthService
        
        auth_service = AuthService()
        if not auth_service.worksheet:
            print("   ✗ AuthService не инициализирован")
            return
        
        # Тестируем с тестовым Telegram ID
        test_telegram_id = 999999999
        result = auth_service.find_and_update_user(partner_code, partner_phone, test_telegram_id)
        print(f"   Результат авторизации: {result}")
        
        if result:
            print("   ✅ АВТОРИЗАЦИЯ УСПЕШНА")
        else:
            print("   ❌ АВТОРИЗАЦИЯ НЕ УДАЛАСЬ")
            
    except Exception as e:
        print(f"   ✗ Ошибка авторизации: {e}")
    print()
    
    # 5. Проверяем кэш авторизации
    print("5. Проверка кэша авторизации:")
    try:
        if os.path.exists('auth_cache.json'):
            with open('auth_cache.json', 'r', encoding='utf-8') as f:
                cache = json.load(f)
            print(f"   Кэш найден, записей: {len(cache)}")
            for user_id, data in cache.items():
                print(f"     Пользователь {user_id}: {data}")
        else:
            print("   Кэш не найден")
    except Exception as e:
        print(f"   ✗ Ошибка чтения кэша: {e}")
    print()
    
    print("=== ПРОВЕРКА ЗАВЕРШЕНА ===")
    print(f"Время проверки: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    check_pythonanywhere_status()
