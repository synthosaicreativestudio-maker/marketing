#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Диагностика системы акций
Проверяет подключение к таблице, данные и логику мониторинга
"""

import os
import sys
from dotenv import load_dotenv

# Добавляем путь к проекту
sys.path.append('/Users/verakoroleva/Desktop/@marketing')

from promotions_client import PromotionsClient
from config import PROMOTIONS_CONFIG, PROMOTIONS_SHEET_URL

def main():
    print("🔍 === ДИАГНОСТИКА СИСТЕМЫ АКЦИЙ ===\n")
    
    # Загружаем переменные окружения
    load_dotenv()
    
    # 1. Проверяем конфигурацию
    print("1️⃣ ПРОВЕРКА КОНФИГУРАЦИИ:")
    print(f"   PROMOTIONS_SHEET_URL: {PROMOTIONS_SHEET_URL}")
    print(f"   Интервал мониторинга: {PROMOTIONS_CONFIG['MONITORING_INTERVAL']} сек")
    print(f"   Максимальная длина описания: {PROMOTIONS_CONFIG['MAX_DESCRIPTION_LENGTH']}")
    print(f"   Задержка между уведомлениями: {PROMOTIONS_CONFIG['NOTIFICATION_DELAY']} сек")
    print()
    
    if not PROMOTIONS_SHEET_URL:
        print("❌ ОШИБКА: PROMOTIONS_SHEET_URL не настроен!")
        return
    
    # 2. Проверяем файл credentials
    credentials_path = '/Users/verakoroleva/Desktop/@marketing/credentials.json'
    if not os.path.exists(credentials_path):
        print(f"❌ ОШИБКА: Файл {credentials_path} не найден!")
        return
    else:
        print(f"✅ Файл credentials.json найден")
    
    # 3. Создаем клиент и подключаемся
    print("\n2️⃣ ПОДКЛЮЧЕНИЕ К GOOGLE SHEETS:")
    try:
        client = PromotionsClient(credentials_path, PROMOTIONS_SHEET_URL)
        connected = client.connect()
        
        if not connected:
            print("❌ ОШИБКА: Не удалось подключиться к таблице акций!")
            return
        
        print("✅ Подключение к таблице акций успешно!")
        
        # 4. Проверяем структуру таблицы
        print("\n3️⃣ СТРУКТУРА ТАБЛИЦЫ:")
        all_values = client.sheet.get_all_values()
        print(f"   Всего строк: {len(all_values)}")
        
        if len(all_values) == 0:
            print("❌ ОШИБКА: Таблица пустая!")
            return
        
        # Проверяем заголовки
        headers = all_values[0] if all_values else []
        print(f"   Заголовки ({len(headers)} колонок): {headers}")
        
        # Ожидаемые колонки
        expected_columns = {
            1: 'Дата релиза',
            2: 'Название', 
            3: 'Описание',
            4: 'Статус',
            5: 'Дата начала',
            6: 'Дата окончания',
            7: 'Контент',
            8: 'Опубликовать'
        }
        
        print("\n   Проверка структуры колонок:")
        for col_num, expected_name in expected_columns.items():
            actual_name = headers[col_num - 1] if len(headers) >= col_num else '(отсутствует)'
            status = "✅" if actual_name and expected_name.lower() in actual_name.lower() else "⚠️"
            print(f"   {status} Колонка {col_num}: ожидается '{expected_name}', найдено '{actual_name}'")
        
        # 5. Анализируем данные
        print(f"\n4️⃣ АНАЛИЗ ДАННЫХ ({len(all_values) - 1} строк данных):")
        
        published_count = 0
        active_count = 0
        with_notification_count = 0
        empty_rows = 0
        
        for i, row in enumerate(all_values[1:], 2):  # начинаем с 2-й строки
            if len(row) < 4:
                empty_rows += 1
                continue
                
            name = row[1] if len(row) > 1 else ''
            status = row[3] if len(row) > 3 else ''
            notification = row[8] if len(row) > 8 else ''
            
            if not name.strip():
                empty_rows += 1
                continue
                
            print(f"   Строка {i}: '{name}' | Статус: '{status}' | Уведомление: '{notification}'")
            
            if status == 'Опубликовано':
                published_count += 1
            elif status == 'Активна':
                active_count += 1
                
            if notification == 'отправлено':
                with_notification_count += 1
        
        print(f"\n   📊 СТАТИСТИКА:")
        print(f"   • Пустых строк: {empty_rows}")
        print(f"   • Со статусом 'Опубликовано': {published_count}")
        print(f"   • Со статусом 'Активна': {active_count}")
        print(f"   • С отправленными уведомлениями: {with_notification_count}")
        
        # 6. Проверяем функции клиента
        print(f"\n5️⃣ ТЕСТИРОВАНИЕ ФУНКЦИЙ:")
        
        # Тестируем получение новых акций
        new_promotions = client.get_new_published_promotions()
        print(f"   📬 Новых акций для уведомления: {len(new_promotions)}")
        
        if new_promotions:
            print("   Детали новых акций:")
            for promo in new_promotions:
                print(f"   • '{promo.get('name', 'Без названия')}' (строка {promo.get('row', '?')})")
        
        # Тестируем получение активных акций
        active_promotions = client.get_active_promotions()
        print(f"   🎯 Активных акций для отображения: {len(active_promotions)}")
        
        if active_promotions:
            print("   Детали активных акций:")
            for promo in active_promotions:
                print(f"   • '{promo.get('name', 'Без названия')}' (статус UI: {promo.get('ui_status', '?')})")
        
        # 7. Проверяем права доступа
        print(f"\n6️⃣ ПРОВЕРКА ПРАВ ДОСТУПА:")
        try:
            # Пробуем записать тестовое значение
            test_cell = client.sheet.cell(1, 1)
            print(f"   ✅ Чтение: успешно (A1 = '{test_cell.value}')")
            
            # Пробуем обновить колонку уведомлений (если есть данные)
            if len(all_values) > 1:
                current_cols = client.sheet.col_count
                if current_cols < client.NOTIFICATION_COLUMN:
                    print(f"   ⚠️ Нужно добавить колонки (текущих: {current_cols}, нужно: {client.NOTIFICATION_COLUMN})")
                else:
                    print(f"   ✅ Колонок достаточно ({current_cols})")
            
        except Exception as e:
            print(f"   ❌ Ошибка доступа: {e}")
        
        print(f"\n🎉 === ДИАГНОСТИКА ЗАВЕРШЕНА ===")
        
        # Рекомендации
        print(f"\n💡 РЕКОМЕНДАЦИИ:")
        if published_count == 0 and active_count == 0:
            print("   • В таблице нет акций со статусом 'Опубликовано' или 'Активна'")
            print("   • Добавьте тестовую акцию со статусом 'Опубликовано' для проверки")
        
        if new_promotions:
            print(f"   • Найдены {len(new_promotions)} новых акций - уведомления должны отправиться в течение 5 минут")
        else:
            print("   • Новых акций для уведомления не найдено")
            
        if not active_promotions:
            print("   • Активных акций для отображения нет - мини-приложение будет пустым")
        
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()