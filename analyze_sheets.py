#!/usr/bin/env python3
"""
Скрипт для анализа структуры Google Sheets таблицы.
Читает заголовки и первые несколько строк всех листов.
"""

import os
import json
from dotenv import load_dotenv
from sheets import _get_client_and_sheet, SheetsNotConfiguredError

def analyze_spreadsheet():
    """Анализирует структуру таблицы и выводит информацию о листах."""
    try:
        # Загружаем .env
        load_dotenv()
        
        # Получаем клиент и основную таблицу
        client, main_worksheet = _get_client_and_sheet()
        spreadsheet = main_worksheet.spreadsheet
        
        print(f"📊 Анализ таблицы: {spreadsheet.title}")
        print(f"🔗 ID таблицы: {spreadsheet.id}")
        print(f"📋 URL: https://docs.google.com/spreadsheets/d/{spreadsheet.id}")
        print("=" * 80)
        
        # Получаем все листы
        worksheets = spreadsheet.worksheets()
        print(f"📄 Найдено листов: {len(worksheets)}")
        print()
        
        for i, worksheet in enumerate(worksheets, 1):
            print(f"📝 Лист {i}: '{worksheet.title}'")
            print(f"   Размер: {worksheet.row_count} строк × {worksheet.col_count} колонок")
            
            try:
                # Читаем заголовки (первая строка)
                headers = worksheet.row_values(1)
                print(f"   Заголовки ({len(headers)}): {headers}")
                
                # Читаем первые 3 строки данных
                if worksheet.row_count > 1:
                    print("   Первые строки данных:")
                    for row_num in range(2, min(5, worksheet.row_count + 1)):
                        row_data = worksheet.row_values(row_num)
                        print(f"     Строка {row_num}: {row_data}")
                
                # Проверяем наличие ключевых колонок
                key_columns = []
                for header in headers:
                    header_lower = header.lower()
                    if any(keyword in header_lower for keyword in ['код', 'code', 'телефон', 'phone', 'статус', 'status', 'telegram', 'дата', 'date']):
                        key_columns.append(header)
                
                if key_columns:
                    print(f"   🔑 Ключевые колонки: {key_columns}")
                
            except Exception as e:
                print(f"   ❌ Ошибка чтения листа: {e}")
            
            print("-" * 60)
        
        # Специальный анализ листа "Обращения"
        print("\n🔍 Детальный анализ листа 'Обращения':")
        try:
            appeals_sheet = None
            for worksheet in worksheets:
                if 'обращения' in worksheet.title.lower() or 'appeals' in worksheet.title.lower():
                    appeals_sheet = worksheet
                    break
            
            if appeals_sheet:
                print(f"✅ Найден лист: '{appeals_sheet.title}'")
                
                # Читаем все данные
                all_data = appeals_sheet.get_all_records()
                print(f"📊 Всего записей: {len(all_data)}")
                
                if all_data:
                    print("\n📋 Структура данных:")
                    for i, record in enumerate(all_data[:3], 1):  # Первые 3 записи
                        print(f"   Запись {i}:")
                        for key, value in record.items():
                            print(f"     {key}: {value}")
                        print()
                
                # Анализ колонок
                if all_data:
                    headers = list(all_data[0].keys())
                    print(f"📝 Все колонки ({len(headers)}):")
                    for i, header in enumerate(headers, 1):
                        print(f"   {i:2d}. {header}")
                
            else:
                print("❌ Лист 'Обращения' не найден")
                print("Доступные листы:")
                for worksheet in worksheets:
                    print(f"   - {worksheet.title}")
                    
        except Exception as e:
            print(f"❌ Ошибка анализа листа 'Обращения': {e}")
            
    except SheetsNotConfiguredError as e:
        print(f"❌ Ошибка конфигурации Google Sheets: {e}")
        print("Убедитесь, что в .env заданы SHEET_ID, GCP_SA_JSON или GCP_SA_FILE")
    except Exception as e:
        print(f"❌ Общая ошибка: {e}")

if __name__ == "__main__":
    analyze_spreadsheet()
