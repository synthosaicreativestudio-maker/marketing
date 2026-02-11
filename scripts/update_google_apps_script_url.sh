#!/bin/bash

# Скрипт для автоматического обновления Google Apps Script URL в menu.html

echo "=== Обновление Google Apps Script URL в menu.html ==="
echo ""
echo "Вставьте ваш Google Apps Script URL (из окна развертывания):"
echo "Пример: https://script.google.com/macros/s/AKfycbzQ8pDvdc6ZriqchBvto6prPk00OwTsHiUx_GAZhkCtXQjtCfM5-KZO4uH7zIUC.../exec"
echo ""
read -p "URL: " GOOGLE_APPS_SCRIPT_URL

if [ -z "$GOOGLE_APPS_SCRIPT_URL" ]; then
    echo "❌ URL не может быть пустым"
    exit 1
fi

# Обновляем menu.html
if [ -f "menu.html" ]; then
    # Используем sed для замены URL (экранируем специальные символы)
    ESCAPED_URL=$(echo "$GOOGLE_APPS_SCRIPT_URL" | sed 's/[[\.*^$()+?{|]/\\&/g')
    
    # Заменяем пустую строку или TODO комментарий на реальный URL
    sed -i.bak "s|const GOOGLE_APPS_SCRIPT_URL = '';.*|const GOOGLE_APPS_SCRIPT_URL = '$GOOGLE_APPS_SCRIPT_URL';|g" menu.html
    
    echo "✅ menu.html обновлен с URL: $GOOGLE_APPS_SCRIPT_URL"
    echo ""
    echo "Следующие шаги:"
    echo "1. Проверьте menu.html - убедитесь, что URL вставлен правильно"
    echo "2. Закоммитьте изменения: git add menu.html && git commit -m 'Обновлен Google Apps Script URL' && git push"
    echo "3. Протестируйте: откройте URL в браузере - должен вернуться JSON с акциями"
else
    echo "❌ Файл menu.html не найден"
    exit 1
fi
