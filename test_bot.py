#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Простой тест для проверки запуска бота
"""

import os
import sys

# Добавляем текущую папку в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Тестирует импорт всех модулей"""
    try:
        print("🔍 Тестирую импорты...")
        
        print("  ✓ Импортирую config...")
        from config import SECTIONS, get_web_app_url
        
        print("  ✓ Импортирую auth_cache...")
        from auth_cache import auth_cache
        
        print("  ✓ Импортирую openai_client...")
        from openai_client import openai_client
        
        print("  ✓ Импортирую process_lock...")
        from process_lock import ProcessLock
        
        print("  ✓ Импортирую sheets_client...")
        from sheets_client import GoogleSheetsClient
        
        print("  ✓ Импортирую bot...")
        import bot
        
        print("✅ Все модули импортированы успешно!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка импорта: {e}")
        return False

def test_config():
    """Тестирует конфигурацию"""
    try:
        print("\n🔧 Тестирую конфигурацию...")
        
        from config import SECTIONS, get_web_app_url
        
        print(f"  ✓ Разделы меню: {len(SECTIONS)} элементов")
        print(f"  ✓ URL главной страницы: {get_web_app_url('MAIN')}")
        print(f"  ✓ URL меню: {get_web_app_url('MENU')}")
        
        print("✅ Конфигурация работает!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка конфигурации: {e}")
        return False

def test_bot_syntax():
    """Тестирует синтаксис бота"""
    try:
        print("\n🤖 Тестирую синтаксис бота...")
        
        # Проверяем, что bot.py может быть импортирован
        import bot
        
        print("✅ Синтаксис бота корректен!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка синтаксиса бота: {e}")
        return False

def main():
    """Главная функция тестирования"""
    print("🚀 Запускаю тесты проекта Marketing Bot...\n")
    
    tests = [
        ("Импорты модулей", test_imports),
        ("Конфигурация", test_config),
        ("Синтаксис бота", test_bot_syntax),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"📋 Тест: {test_name}")
        if test_func():
            passed += 1
        print()
    
    print(f"📊 Результаты: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("🎉 Все тесты пройдены! Бот готов к запуску.")
        print("\n⚠️  Для полного запуска нужно:")
        print("   1. Создать файл .env с токенами")
        print("   2. Настроить Google Sheets")
        print("   3. Получить API ключ OpenAI")
    else:
        print("❌ Некоторые тесты не пройдены. Нужно исправить ошибки.")
    
    return passed == total

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
