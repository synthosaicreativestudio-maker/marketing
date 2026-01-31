#!/usr/bin/env python3
"""
Скрипт для анализа новой Google Sheets таблицы с листом "Обращения".
"""

import os
from dotenv import load_dotenv
from sheets import _load_service_account, SheetsNotConfiguredError

def analyze_new_spreadsheet():
    """Анализирует новую таблицу с листом 'Обращения'."""
    try:
        # Загружаем .env
        load_dotenv()
        
        # Временно меняем SHEET_ID
        old_sheet_id = os.environ.get('SHEET_ID')
        os.environ['SHEET_ID'] = '15XxSIpD_gMZaSOIrqDVCNI2EqBzphEGiG0ZNJ3HR8hI'
        
        try:
            import gspread
            from google.oauth2.service_account import Credentials
            
            sa_info = _load_service_account()
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            
            creds = Credentials.from_service_account_info(sa_info, scopes=scopes)
            client = gspread.authorize(creds)
            
            sheet_id = os.environ.get('SHEET_ID')
            spreadsheet = client.open_by_key(sheet_id)
            
            print(f"📊 Анализ новой таблицы: {spreadsheet.title}")
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
                        if any(keyword in header_lower for keyword in ['код', 'code', 'телефон', 'phone', 'статус', 'status', 'telegram', 'дата', 'date', 'обращение', 'appeal', 'сообщение', 'message']):
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
                
        finally:
            # Восстанавливаем старый SHEET_ID
            if old_sheet_id:
                os.environ['SHEET_ID'] = old_sheet_id
            else:
                os.environ.pop('SHEET_ID', None)
                
    except SheetsNotConfiguredError as e:
        print(f"❌ Ошибка конфигурации Google Sheets: {e}")
        print("Убедитесь, что в .env заданы GCP_SA_JSON или GCP_SA_FILE")
    except Exception as e:
        print(f"❌ Общая ошибка: {e}")

if __name__ == "__main__":
    analyze_new_spreadsheet()
