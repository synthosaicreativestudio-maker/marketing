#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Расширенная диагностика системы Marketing Bot
Проверяет все компоненты и предоставляет детальный отчет
"""

import os
import sys
import asyncio
import json
import time
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent))

def main():
    """Основная функция диагностики"""
    print("🔍 РАСШИРЕННАЯ ДИАГНОСТИКА MARKETING BOT")
    print("=" * 60)
    
    results = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'sections': {}
    }
    
    # 1. Проверка Python окружения
    print("\n📋 1. ПРОВЕРКА PYTHON ОКРУЖЕНИЯ")
    python_check = check_python_environment()
    results['sections']['python'] = python_check
    print_section_result(python_check)
    
    # 2. Проверка файловой структуры
    print("\n📁 2. ПРОВЕРКА ФАЙЛОВОЙ СТРУКТУРЫ")
    files_check = check_file_structure()
    results['sections']['files'] = files_check
    print_section_result(files_check)
    
    # 3. Проверка зависимостей
    print("\n📦 3. ПРОВЕРКА ЗАВИСИМОСТЕЙ")
    deps_check = check_dependencies()
    results['sections']['dependencies'] = deps_check
    print_section_result(deps_check)
    
    # 4. Проверка конфигурации
    print("\n⚙️ 4. ПРОВЕРКА КОНФИГУРАЦИИ")
    config_check = check_configuration()
    results['sections']['configuration'] = config_check
    print_section_result(config_check)
    
    # 5. Проверка Google Sheets
    print("\n📊 5. ПРОВЕРКА GOOGLE SHEETS")
    sheets_check = check_google_sheets()
    results['sections']['google_sheets'] = sheets_check
    print_section_result(sheets_check)
    
    # 6. Проверка OpenAI
    print("\n🤖 6. ПРОВЕРКА OPENAI")
    openai_check = check_openai()
    results['sections']['openai'] = openai_check
    print_section_result(openai_check)
    
    # 7. Проверка производительности
    print("\n⚡ 7. ПРОВЕРКА ПРОИЗВОДИТЕЛЬНОСТИ")
    perf_check = check_performance()
    results['sections']['performance'] = perf_check
    print_section_result(perf_check)
    
    # 8. Проверка кэша
    print("\n💾 8. ПРОВЕРКА КЭША")
    cache_check = check_cache_system()
    results['sections']['cache'] = cache_check
    print_section_result(cache_check)
    
    # Общий итог
    print("\n" + "=" * 60)
    print_summary(results)
    
    # Сохраняем отчет
    save_report(results)

def check_python_environment():
    """Проверяет Python окружение"""
    checks = {}
    
    # Версия Python
    version = sys.version_info
    checks['python_version'] = {
        'value': f"{version.major}.{version.minor}.{version.micro}",
        'status': 'success' if version >= (3, 7) else 'error',
        'message': 'OK' if version >= (3, 7) else 'Требуется Python 3.7+'
    }
    
    # Рабочая директория
    cwd = os.getcwd()
    bot_py_exists = os.path.exists('bot.py')
    checks['working_directory'] = {
        'value': cwd,
        'status': 'success' if bot_py_exists else 'error',
        'message': 'Корневая директория проекта' if bot_py_exists else 'Неверная директория'
    }
    
    # Права доступа
    readable = os.access('.', os.R_OK)
    writable = os.access('.', os.W_OK)
    checks['permissions'] = {
        'value': f"R: {readable}, W: {writable}",
        'status': 'success' if readable and writable else 'warning',
        'message': 'Достаточно прав' if readable and writable else 'Ограниченные права'
    }
    
    return checks

def check_file_structure():
    """Проверяет структуру файлов"""
    checks = {}
    
    required_files = {
        'bot.py': 'Основной файл бота',
        'config.py': 'Конфигурация',
        'auth_cache.py': 'Кэш авторизации',
        'sheets_client.py': 'Клиент Google Sheets',
        'openai_client.py': 'Клиент OpenAI',
        'requirements.txt': 'Зависимости Python',
        'index.html': 'Веб-интерфейс авторизации',
        'spa_menu.html': 'Веб-интерфейс меню'
    }
    
    for file, description in required_files.items():
        exists = os.path.exists(file)
        size = os.path.getsize(file) if exists else 0
        
        checks[file] = {
            'value': f"{size} байт" if exists else "Отсутствует",
            'status': 'success' if exists and size > 0 else 'error',
            'message': description
        }
    
    # Проверка credentials.json
    creds_exists = os.path.exists('credentials.json')
    checks['credentials.json'] = {
        'value': "Найден" if creds_exists else "Отсутствует",
        'status': 'success' if creds_exists else 'warning',
        'message': 'Google Cloud credentials'
    }
    
    # Проверка .env
    env_exists = os.path.exists('.env')
    checks['.env'] = {
        'value': "Найден" if env_exists else "Отсутствует",
        'status': 'success' if env_exists else 'warning',
        'message': 'Файл переменных окружения'
    }
    
    return checks

def check_dependencies():
    """Проверяет зависимости Python"""
    checks = {}
    
    required_modules = [
        'telegram',
        'gspread',
        'oauth2client',
        'openai',
        'psutil',
        'python-dotenv'
    ]
    
    for module in required_modules:
        try:
            # Особый случай для python-dotenv
            if module == 'python-dotenv':
                import dotenv
            else:
                __import__(module.replace('-', '_'))
            checks[module] = {
                'value': 'Установлен',
                'status': 'success',
                'message': 'OK'
            }
        except ImportError as e:
            checks[module] = {
                'value': 'Не найден',
                'status': 'error',
                'message': str(e)
            }
    
    return checks

def check_configuration():
    """Проверяет конфигурацию"""
    checks = {}
    
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        # Проверяем переменные окружения
        env_vars = {
            'TELEGRAM_TOKEN': 'Токен Telegram бота',
            'SHEET_URL': 'URL таблицы авторизации',
            'TICKETS_SHEET_URL': 'URL таблицы обращений',
            'OPENAI_API_KEY': 'Ключ OpenAI API'
        }
        
        for var, description in env_vars.items():
            value = os.getenv(var)
            if value:
                # Маскируем чувствительные данные
                masked_value = value[:10] + '...' if len(value) > 10 else value
                checks[var] = {
                    'value': masked_value,
                    'status': 'success',
                    'message': description
                }
            else:
                checks[var] = {
                    'value': 'Не задан',
                    'status': 'error',
                    'message': f'Отсутствует {description}'
                }
        
        # Валидация конфигурации
        try:
            from validator import validator
            env_valid, env_errors = validator.validate_environment()
            
            checks['validation'] = {
                'value': 'Пройдена' if env_valid else f'{len(env_errors)} ошибок',
                'status': 'success' if env_valid else 'error',
                'message': 'Конфигурация валидна' if env_valid else '; '.join(env_errors[:3])
            }
        except ImportError:
            checks['validation'] = {
                'value': 'Пропущена',
                'status': 'warning',
                'message': 'Модуль validator недоступен'
            }
    
    except Exception as e:
        checks['loading'] = {
            'value': 'Ошибка',
            'status': 'error',
            'message': str(e)
        }
    
    return checks

def check_google_sheets():
    """Проверяет подключение к Google Sheets"""
    checks = {}
    
    try:
        from sheets_client import GoogleSheetsClient
        from dotenv import load_dotenv
        load_dotenv()
        
        sheet_url = os.getenv('SHEET_URL')
        tickets_url = os.getenv('TICKETS_SHEET_URL')
        
        # Проверка основной таблицы
        if sheet_url and os.path.exists('credentials.json'):
            try:
                client = GoogleSheetsClient('credentials.json', sheet_url, 'список сотрудников для авторизации')
                if client.sheet:
                    row_count = len(client.sheet.get_all_values())
                    checks['auth_sheet'] = {
                        'value': f'{row_count} строк',
                        'status': 'success',
                        'message': 'Подключение успешно'
                    }
                else:
                    checks['auth_sheet'] = {
                        'value': 'Ошибка подключения',
                        'status': 'error',
                        'message': 'Не удалось подключиться'
                    }
            except Exception as e:
                checks['auth_sheet'] = {
                    'value': 'Ошибка',
                    'status': 'error',
                    'message': str(e)[:100]
                }
        else:
            checks['auth_sheet'] = {
                'value': 'Не настроена',
                'status': 'warning',
                'message': 'Отсутствует URL или credentials.json'
            }
        
        # Проверка таблицы обращений
        if tickets_url and os.path.exists('credentials.json'):
            try:
                tickets_client = GoogleSheetsClient('credentials.json', tickets_url, 'обращения')
                if tickets_client.sheet:
                    tickets_count = len(tickets_client.sheet.get_all_values())
                    checks['tickets_sheet'] = {
                        'value': f'{tickets_count} строк',
                        'status': 'success',
                        'message': 'Подключение успешно'
                    }
                else:
                    checks['tickets_sheet'] = {
                        'value': 'Ошибка подключения',
                        'status': 'error',
                        'message': 'Не удалось подключиться'
                    }
            except Exception as e:
                checks['tickets_sheet'] = {
                    'value': 'Ошибка',
                    'status': 'error',
                    'message': str(e)[:100]
                }
        else:
            checks['tickets_sheet'] = {
                'value': 'Не настроена',
                'status': 'warning',
                'message': 'Отсутствует URL или credentials.json'
            }
    
    except ImportError as e:
        checks['import_error'] = {
            'value': 'Модуль недоступен',
            'status': 'error',
            'message': str(e)
        }
    
    return checks

def check_openai():
    """Проверяет подключение к OpenAI"""
    checks = {}
    
    try:
        from openai_client import openai_client
        
        # Проверка доступности
        available = openai_client.is_available()
        checks['availability'] = {
            'value': 'Доступен' if available else 'Недоступен',
            'status': 'success' if available else 'warning',
            'message': 'OpenAI API отвечает' if available else 'OpenAI API не отвечает'
        }
        
        # Проверка конфигурации
        has_key = bool(os.getenv('OPENAI_API_KEY'))
        has_assistant = bool(os.getenv('OPENAI_ASSISTANT_ID'))
        
        checks['configuration'] = {
            'value': f"Key: {has_key}, Assistant: {has_assistant}",
            'status': 'success' if has_key else 'warning',
            'message': 'Конфигурация OpenAI настроена' if has_key else 'Отсутствуют ключи'
        }
    
    except ImportError as e:
        checks['import_error'] = {
            'value': 'Модуль недоступен',
            'status': 'error',
            'message': str(e)
        }
    
    return checks

def check_performance():
    """Проверяет производительность системы"""
    checks = {}
    
    try:
        import psutil
        
        # CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        checks['cpu_usage'] = {
            'value': f'{cpu_percent}%',
            'status': 'success' if cpu_percent < 80 else 'warning',
            'message': 'Нормальная нагрузка' if cpu_percent < 80 else 'Высокая нагрузка'
        }
        
        # Память
        memory = psutil.virtual_memory()
        checks['memory_usage'] = {
            'value': f'{memory.percent}%',
            'status': 'success' if memory.percent < 80 else 'warning',
            'message': 'Достаточно памяти' if memory.percent < 80 else 'Высокое потребление'
        }
        
        # Диск
        disk = psutil.disk_usage('.')
        checks['disk_space'] = {
            'value': f'{disk.percent}%',
            'status': 'success' if disk.percent < 90 else 'warning',
            'message': 'Достаточно места' if disk.percent < 90 else 'Мало места на диске'
        }
    
    except ImportError:
        checks['psutil_error'] = {
            'value': 'Модуль psutil недоступен',
            'status': 'warning',
            'message': 'Не удалось проверить производительность'
        }
    
    return checks

def check_cache_system():
    """Проверяет систему кэширования"""
    checks = {}
    
    try:
        from auth_cache import auth_cache
        
        # Статистика кэша
        stats = auth_cache.get_cache_stats()
        
        checks['cache_stats'] = {
            'value': f"Users: {stats['user_cache_count']}, Auth: {stats['authorized_count']}",
            'status': 'success',
            'message': 'Кэш функционирует'
        }
        
        checks['cache_age'] = {
            'value': f"{stats['cache_age']:.1f}s",
            'status': 'success' if stats['cache_age'] < 3600 else 'warning',
            'message': 'Свежий кэш' if stats['cache_age'] < 3600 else 'Устаревший кэш'
        }
    
    except ImportError as e:
        checks['import_error'] = {
            'value': 'Модуль недоступен',
            'status': 'error',
            'message': str(e)
        }
    
    return checks

def print_section_result(checks):
    """Выводит результаты секции"""
    for name, check in checks.items():
        status_symbol = {
            'success': '✅',
            'warning': '⚠️',
            'error': '❌'
        }.get(check['status'], '❓')
        
        print(f"  {status_symbol} {name}: {check['value']} - {check['message']}")

def print_summary(results):
    """Выводит общий итог"""
    total_checks = 0
    success_count = 0
    warning_count = 0
    error_count = 0
    
    for section_name, section_checks in results['sections'].items():
        for check_name, check in section_checks.items():
            total_checks += 1
            if check['status'] == 'success':
                success_count += 1
            elif check['status'] == 'warning':
                warning_count += 1
            else:
                error_count += 1
    
    print("📊 ИТОГОВАЯ СТАТИСТИКА:")
    print(f"  ✅ Успешно: {success_count}")
    print(f"  ⚠️ Предупреждения: {warning_count}")
    print(f"  ❌ Ошибки: {error_count}")
    print(f"  📋 Всего проверок: {total_checks}")
    
    if error_count == 0 and warning_count <= 2:
        print("\n🎉 СИСТЕМА ГОТОВА К РАБОТЕ!")
    elif error_count == 0:
        print("\n⚠️ СИСТЕМА РАБОТОСПОСОБНА, НО ЕСТЬ ПРЕДУПРЕЖДЕНИЯ")
    else:
        print("\n❌ ТРЕБУЕТСЯ УСТРАНЕНИЕ ОШИБОК ПЕРЕД ЗАПУСКОМ")

def save_report(results):
    """Сохраняет отчет в файл"""
    try:
        with open('diagnostic_report.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Отчет сохранен в diagnostic_report.json")
    except Exception as e:
        print(f"\n❌ Ошибка сохранения отчета: {e}")

if __name__ == "__main__":
    main()