#!/usr/bin/env python3
"""
Комплексное тестирование всех систем бота
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

def test_env_variables():
    """Тест наличия всех переменных окружения"""
    print("=== ТЕСТ 1: Переменные окружения ===")
    required_vars = [
        'TELEGRAM_TOKEN',
        'ADMIN_TELEGRAM_ID',
        'SHEET_ID',
        'APPEALS_SHEET_ID',
        'PROMOTIONS_SHEET_ID',
        'GCP_SA_FILE',
        'OPENAI_API_KEY'
    ]
    
    missing = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: установлена")
        else:
            print(f"❌ {var}: НЕ НАЙДЕНА")
            missing.append(var)
    
    if missing:
        print(f"\n⚠️  Отсутствуют переменные: {', '.join(missing)}")
        return False
    print("\n✅ Все переменные окружения настроены\n")
    return True

def test_sheets_connection():
    """Тест подключения к Google Sheets"""
    print("=== ТЕСТ 2: Google Sheets Connection ===")
    try:
        from sheets_gateway import _get_client_and_sheet
        
        # Синхронная проверка
        try:
            _, worksheet = _get_client_and_sheet()
            print(f"✅ AuthSheet подключен: {worksheet.title}")
        except Exception as e:
            print(f"❌ AuthSheet ОШИБКА: {e}")
            return False
            
        print("✅ Google Sheets доступны\n")
        return True
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}\n")
        return False

def test_async_gateway():
    """Тест AsyncGoogleSheetsGateway"""
    print("=== ТЕСТ 3: AsyncGoogleSheetsGateway ===")
    try:
        from sheets_gateway import AsyncGoogleSheetsGateway
        gateway = AsyncGoogleSheetsGateway(circuit_breaker_name='auth')
        print(f"✅ Gateway создан: {gateway.circuit_breaker_name}")
        print("✅ AsyncGoogleSheetsGateway работает\n")
        return True
    except Exception as e:
        print(f"❌ ОШИБКА: {e}\n")
        return False

def test_services():
    """Тест инициализации сервисов"""
    print("=== ТЕСТ 4: Инициализация сервисов ===")
    try:
        from auth_service import AuthService
        from appeals_service import AppealsService
        
        # AuthService
        try:
            auth = AuthService()
            if auth.worksheet:
                print("✅ AuthService: worksheet готов")
            else:
                print("⚠️  AuthService: worksheet не инициализирован")
        except Exception as e:
            print(f"❌ AuthService ОШИБКА: {e}")
            return False
        
        # AppealsService  
        try:
            appeals = AppealsService()
            if appeals.worksheet:
                print("✅ AppealsService: worksheet готов")
            else:
                print("⚠️  AppealsService: worksheet не инициализирован")
        except Exception as e:
            print(f"❌ AppealsService ОШИБКА: {e}")
            return False
            
        print("✅ Все сервисы инициализированы\n")
        return True
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}\n")
        return False

def main():
    """Запуск всех тестов"""
    print("\n" + "="*50)
    print("КОМПЛЕКСНОЕ ТЕСТИРОВАНИЕ СИСТЕМ БОТА")
    print("="*50 + "\n")
    
    tests = [
        ("Переменные окружения", test_env_variables),
        ("Google Sheets", test_sheets_connection),
        ("AsyncGateway", test_async_gateway),
        ("Сервисы", test_services),
    ]
    
    results = {}
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"❌ КРИТИЧЕСКАЯ ОШИБКА В ТЕСТЕ '{name}': {e}\n")
            results[name] = False
    
    print("="*50)
    print("ИТОГОВЫЙ ОТЧЁТ")
    print("="*50)
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    for name, result in results.items():
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        print(f"{status}: {name}")
    
    print(f"\nВсего: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        return 0
    else:
        print(f"\n⚠️  НЕ ВСЕ ТЕСТЫ ПРОЙДЕНЫ ({total - passed} провалено)")
        return 1

if __name__ == "__main__":
    sys.exit(main())
