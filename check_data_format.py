#!/usr/bin/env python3
import os
from sheets_client import GoogleSheetsClient
from dotenv import load_dotenv

load_dotenv()

def check_data_format():
    SHEET_URL = os.getenv('SHEET_URL')
    WORKSHEET_NAME = os.getenv('WORKSHEET_NAME', 'список сотрудников для авторизации')
    
    print(f"🔍 Проверяем формат данных в таблице авторизации")
    print(f"SHEET_URL: {SHEET_URL}")
    print(f"WORKSHEET_NAME: {WORKSHEET_NAME}")
    
    if not SHEET_URL:
        print("❌ SHEET_URL не задан")
        return
    
    if not os.path.exists('credentials.json'):
        print("❌ credentials.json не найден")
        return
    
    try:
        print("\n🔌 Подключаемся к Google Sheets...")
        client = GoogleSheetsClient(
            credentials_path='credentials.json',
            sheet_url=SHEET_URL,
            worksheet_name=WORKSHEET_NAME
        )
        
        if not client.sheet:
            print("❌ Не удалось подключиться к таблице")
            return
        
        print("✅ Подключение успешно!")
        
        # Получаем заголовки
        headers = client.sheet.row_values(1)
        print(f"\n📋 Заголовки: {headers}")
        
        # Получаем все данные
        all_values = client.sheet.get_all_values()
        print(f"\n📊 Всего строк: {len(all_values)}")
        
        # Анализируем каждую строку данных (пропускаем заголовок)
        for i, row in enumerate(all_values[1:], start=2):
            if len(row) >= 5:  # Проверяем, что есть все колонки
                code = row[0] if len(row) > 0 else ""
                phone = row[2] if len(row) > 2 else ""
                status = row[3] if len(row) > 3 else ""
                telegram_id = row[4] if len(row) > 4 else ""
                
                print(f"\n📝 Строка {i}:")
                print(f"   🔑 Код партнера: '{code}' (тип: {type(code).__name__})")
                print(f"   📞 Телефон: '{phone}' (тип: {type(phone).__name__})")
                print(f"   ✅ Статус: '{status}' (тип: {type(status).__name__})")
                print(f"   🆔 Telegram ID: '{telegram_id}' (тип: {type(telegram_id).__name__})")
                
                # Проверяем формат кода
                if code:
                    code_digits = ''.join(filter(str.isdigit, str(code)))
                    print(f"   🔢 Код (только цифры): '{code_digits}' (длина: {len(code_digits)})")
                
                # Проверяем формат телефона
                if phone:
                    phone_digits = ''.join(filter(str.isdigit, str(phone)))
                    print(f"   🔢 Телефон (только цифры): '{phone_digits}' (длина: {len(phone_digits)})")
                    
                    # Проверяем, начинается ли с 8
                    if phone_digits and phone_digits.startswith('8'):
                        print(f"   ✅ Телефон начинается с 8")
                    else:
                        print(f"   ⚠️ Телефон НЕ начинается с 8")
        
        # Тестируем функцию поиска с разными форматами
        print(f"\n🧪 Тестируем функцию поиска...")
        
        # Тестовые данные
        test_cases = [
            ("111098", "89827701055"),
            ("111098", "89827701055"),
            ("111098", "89827701055"),
            ("111098", "89827701055"),
        ]
        
        for code, phone in test_cases:
            print(f"\n🔍 Ищем: код='{code}', телефон='{phone}'")
            
            # Очищаем телефон от всех символов кроме цифр
            phone_digits = ''.join(filter(str.isdigit, phone))
            print(f"   📱 Телефон (очищенный): '{phone_digits}'")
            
            try:
                row = client.find_user_by_credentials(code, phone_digits)
                print(f"   ✅ Результат поиска: строка {row}")
                
                if row:
                    # Получаем данные найденной строки
                    found_code = client.sheet.cell(row, 1).value
                    found_phone = client.sheet.cell(row, 3).value
                    found_status = client.sheet.cell(row, 4).value
                    found_telegram_id = client.sheet.cell(row, 5).value
                    
                    print(f"   📋 Найденные данные:")
                    print(f"      Код: '{found_code}'")
                    print(f"      Телефон: '{found_phone}'")
                    print(f"      Статус: '{found_status}'")
                    print(f"      Telegram ID: '{found_telegram_id}'")
                    
            except Exception as e:
                print(f"   ❌ Ошибка поиска: {e}")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    check_data_format()
