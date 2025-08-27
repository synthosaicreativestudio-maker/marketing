#!/usr/bin/env python3
"""
Скрипт для полной очистки всех процессов бота
"""

import os
import subprocess
import time

def cleanup_bot():
    print("🧹 Очистка всех процессов бота...")
    
    # Останавливаем все процессы python bot.py
    try:
        subprocess.run(["pkill", "-9", "-f", "python bot.py"], check=False)
        print("✅ Процессы остановлены")
    except:
        pass
    
    # Удаляем файл блокировки
    if os.path.exists("bot.lock"):
        os.remove("bot.lock")
        print("✅ Файл блокировки удален")
    
    # Очищаем кэш Python
    try:
        subprocess.run(["find", ".", "-name", "*.pyc", "-delete"], check=False)
        subprocess.run(["find", ".", "-name", "__pycache__", "-type", "d", "-exec", "rm", "-rf", "{}", "+"], check=False)
        print("✅ Кэш Python очищен")
    except:
        pass
    
    # Ждем немного
    time.sleep(2)
    
    # Проверяем, что процессы действительно остановлены
    try:
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
        if "python bot.py" not in result.stdout:
            print("✅ Все процессы бота остановлены")
        else:
            print("⚠️ Некоторые процессы все еще работают")
    except:
        pass
    
    print("🎯 Готово к запуску!")

if __name__ == "__main__":
    cleanup_bot()
