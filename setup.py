#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Setup script for Marketing Bot
Автоматически проверяет и настраивает окружение для бота
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def check_python_version():
    """Проверка версии Python"""
    print("🐍 Проверка версии Python...")
    if sys.version_info < (3, 7):
        print("❌ Требуется Python 3.7 или выше!")
        print(f"   Текущая версия: {sys.version}")
        return False
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} подходит")
    return True

def install_dependencies():
    """Установка зависимостей"""
    print("\n📦 Установка зависимостей...")
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
        print("✅ Зависимости установлены успешно")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка установки зависимостей: {e}")
        return False

def setup_env_file():
    """Настройка файла .env"""
    print("\n⚙️ Настройка файла окружения...")
    
    if os.path.exists('.env'):
        print("✅ Файл .env уже существует")
        return True
    
    if os.path.exists('.env.example'):
        try:
            shutil.copy('.env.example', '.env')
            print("✅ Создан файл .env из шаблона")
            print("📝 Отредактируйте .env файл с вашими настройками:")
            print("   - TELEGRAM_TOKEN")
            print("   - SHEET_URL") 
            print("   - TICKETS_SHEET_URL")
            print("   - OPENAI_API_KEY")
            return True
        except Exception as e:
            print(f"❌ Ошибка создания .env: {e}")
            return False
    else:
        print("⚠️ Файл .env.example не найден")
        return False

def check_credentials():
    """Проверка Google credentials"""
    print("\n🔐 Проверка Google Cloud credentials...")
    
    if os.path.exists('credentials.json'):
        print("✅ Файл credentials.json найден")
        return True
    else:
        print("❌ Файл credentials.json не найден")
        print("📋 Для настройки Google Sheets:")
        print("   1. Создайте проект в Google Cloud Console")
        print("   2. Включите Google Sheets API")
        print("   3. Создайте Service Account")
        print("   4. Скачайте credentials.json в корень проекта")
        return False

def run_diagnostics():
    """Запуск диагностики"""
    print("\n🔍 Запуск базовой диагностики...")
    try:
        subprocess.run([sys.executable, 'simple_check.py'], check=True)
        print("✅ Базовая диагностика завершена")
        return True
    except subprocess.CalledProcessError:
        print("⚠️ Диагностика выявила проблемы")
        return False
    except FileNotFoundError:
        print("⚠️ Файл диагностики не найден")
        return False

def main():
    """Основная функция настройки"""
    print("🚀 НАСТРОЙКА MARKETING BOT")
    print("=" * 50)
    
    # Проверяем, что мы в правильной директории
    required_files = ['bot.py', 'requirements.txt', 'config.py']
    missing_files = [f for f in required_files if not os.path.exists(f)]
    
    if missing_files:
        print(f"❌ Не найдены важные файлы: {missing_files}")
        print("   Убедитесь что вы в корне проекта Marketing Bot")
        return False
    
    success = True
    
    # 1. Проверка Python
    if not check_python_version():
        success = False
    
    # 2. Установка зависимостей
    if success and not install_dependencies():
        success = False
    
    # 3. Настройка .env
    if success:
        setup_env_file()
    
    # 4. Проверка credentials
    if success:
        check_credentials()
    
    # 5. Диагностика
    if success:
        run_diagnostics()
    
    # Итоговая информация
    print("\n" + "=" * 50)
    if success:
        print("🎉 НАСТРОЙКА ЗАВЕРШЕНА!")
        print("\n📋 Следующие шаги:")
        print("   1. Отредактируйте .env файл с вашими токенами")
        print("   2. Добавьте credentials.json для Google Sheets")
        print("   3. Запустите бота: python bot.py")
        print("   4. Для диагностики: python диагностика_авторизации.py")
    else:
        print("❌ НАСТРОЙКА НЕ ЗАВЕРШЕНА")
        print("   Исправьте ошибки выше и запустите setup.py снова")
    
    return success

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Настройка прервана пользователем")
    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {e}")
        print("   Обратитесь за поддержкой с этой ошибкой")