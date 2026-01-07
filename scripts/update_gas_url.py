#!/usr/bin/env python3
"""
Скрипт для автоматического обновления Google Apps Script URL в menu.html
"""

import re
import sys

def update_google_apps_script_url(url):
    """Обновляет Google Apps Script URL в menu.html"""
    
    if not url:
        print("❌ URL не может быть пустым")
        return False
    
    # Проверяем, что URL выглядит правильно
    if not url.startswith('https://script.google.com/macros/s/'):
        print("⚠️  Предупреждение: URL не похож на Google Apps Script URL")
        response = input("Продолжить? (y/n): ")
        if response.lower() != 'y':
            return False
    
    try:
        # Читаем menu.html
        with open('menu.html', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Ищем и заменяем URL
        # Паттерн для поиска: const GOOGLE_APPS_SCRIPT_URL = ''; или const GOOGLE_APPS_SCRIPT_URL = '...';
        pattern = r"const GOOGLE_APPS_SCRIPT_URL = ['\"].*?['\"];"
        replacement = f"const GOOGLE_APPS_SCRIPT_URL = '{url}';"
        
        if re.search(pattern, content):
            new_content = re.sub(pattern, replacement, content)
            
            # Сохраняем обновленный файл
            with open('menu.html', 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            print(f"✅ menu.html обновлен с URL: {url}")
            return True
        else:
            print("❌ Не найдена строка с GOOGLE_APPS_SCRIPT_URL в menu.html")
            return False
            
    except FileNotFoundError:
        print("❌ Файл menu.html не найден")
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

if __name__ == '__main__':
    if len(sys.argv) > 1:
        # URL передан как аргумент командной строки
        url = sys.argv[1]
    else:
        # Запрашиваем URL интерактивно
        print("=== Обновление Google Apps Script URL в menu.html ===")
        print("")
        print("Вставьте ваш Google Apps Script URL (из окна развертывания):")
        print("Пример: https://script.google.com/macros/s/AKfycbzQ8pDvdc6ZriqchBvto6prPk00OwTsHiUx_GAZhkCtXQjtCfM5-KZO4uH7zIUC.../exec")
        print("")
        url = input("URL: ").strip()
    
    if update_google_apps_script_url(url):
        print("")
        print("Следующие шаги:")
        print("1. Проверьте menu.html - убедитесь, что URL вставлен правильно")
        print("2. Закоммитьте изменения:")
        print("   git add menu.html")
        print("   git commit -m 'Обновлен Google Apps Script URL'")
        print("   git push")
        print("3. Протестируйте: откройте URL в браузере - должен вернуться JSON с акциями")
