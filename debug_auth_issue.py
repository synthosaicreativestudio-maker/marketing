#!/usr/bin/env python3
"""
Скрипт для диагностики проблемы авторизации
Поможет понять, почему бот говорит "данные не найдены"
"""

import logging
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def debug_auth_issue():
    """Диагностика проблемы авторизации"""
    print("=== ДИАГНОСТИКА ПРОБЛЕМЫ АВТОРИЗАЦИИ ===\n")
    
    # 1. Проверяем переменные окружения
    print("1. Проверка переменных окружения:")
    sheet_id = os.getenv('SHEET_ID')
    sheet_name = os.getenv('SHEET_NAME', 'Sheet1')
    gcp_sa_json = os.getenv('GCP_SA_JSON')
    
    print(f"   SHEET_ID: {'✓' if sheet_id else '✗'} {sheet_id}")
    print(f"   SHEET_NAME: {sheet_name}")
    print(f"   GCP_SA_JSON: {'✓' if gcp_sa_json else '✗'}")
    print()
    
    # 2. Проверяем подключение к Google Sheets
    print("2. Проверка подключения к Google Sheets:")
    try:
        from sheets import _get_client_and_sheet
        client, worksheet = _get_client_and_sheet()
        print(f"   ✓ Подключение успешно")
        print(f"   Название листа: {worksheet.title}")
        print(f"   ID таблицы: {worksheet.spreadsheet.id}")
    except Exception as e:
        print(f"   ✗ Ошибка подключения: {e}")
        return
    print()
    
    # 3. Проверяем данные в таблице
    print("3. Проверка данных в таблице:")
    try:
        records = worksheet.get_all_records()
        print(f"   Всего записей: {len(records)}")
        
        # Ищем записи с именем Наталья
        natalia_records = []
        for i, record in enumerate(records, start=2):
            name = record.get('ФИО партнера', '')
            if 'натал' in name.lower() or 'наташ' in name.lower():
                natalia_records.append((i, record))
        
        print(f"   Найдено записей с именем Наталья: {len(natalia_records)}")
        for row_num, record in natalia_records:
            print(f"   Строка {row_num}: {record.get('ФИО партнера')} - {record.get('Код партнера')} - {record.get('Телефон партнера')}")
    except Exception as e:
        print(f"   ✗ Ошибка чтения данных: {e}")
        return
    print()
    
    # 4. Тестируем поиск пользователя
    print("4. Тест поиска пользователя:")
    try:
        from sheets import find_row_by_partner_and_phone, normalize_phone
        
        # Тестируем с данными из таблицы
        test_cases = [
            {'code': '1245797092', 'phone': '89634528665', 'name': 'Гайдамака Наталья Сергеевна'},
            {'code': '111098', 'phone': '89827701055', 'name': 'Марченко Роман Олегович'},
        ]
        
        for test in test_cases:
            print(f"   Тест: {test['name']}")
            print(f"     Код: {test['code']}, Телефон: {test['phone']}")
            
            phone_norm = normalize_phone(test['phone'])
            print(f"     Нормализованный телефон: {phone_norm}")
            
            row = find_row_by_partner_and_phone(test['code'], phone_norm)
            print(f"     Найденная строка: {row}")
            
            if row:
                print("     ✅ ПОЛЬЗОВАТЕЛЬ НАЙДЕН")
            else:
                print("     ❌ ПОЛЬЗОВАТЕЛЬ НЕ НАЙДЕН")
            print()
    except Exception as e:
        print(f"   ✗ Ошибка тестирования поиска: {e}")
        return
    
    # 5. Тестируем полный процесс авторизации
    print("5. Тест полного процесса авторизации:")
    try:
        from auth_service import AuthService
        
        auth_service = AuthService()
        if not auth_service.worksheet:
            print("   ✗ AuthService не инициализирован")
            return
        
        # Тестируем авторизацию
        test_telegram_id = 123456789
        result = auth_service.find_and_update_user('1245797092', '89634528665', test_telegram_id)
        print(f"   Результат find_and_update_user: {result}")
        
        if result:
            print("   ✅ АВТОРИЗАЦИЯ УСПЕШНА")
        else:
            print("   ❌ АВТОРИЗАЦИЯ НЕ УДАЛАСЬ")
        
        # Проверяем статус
        status = auth_service.get_user_auth_status(test_telegram_id)
        print(f"   Статус авторизации: {status}")
        
    except Exception as e:
        print(f"   ✗ Ошибка тестирования авторизации: {e}")
        return
    
    print("\n=== ДИАГНОСТИКА ЗАВЕРШЕНА ===")

if __name__ == "__main__":
    debug_auth_issue()
