#!/bin/bash

# Скрипт для обновления бота на Yandex VM
echo "🚀 Обновление MarketingBot на Yandex VM..."

# Переходим в папку проекта
cd /home/ubuntu/marketingbot

# Обновляем код из GitHub
echo "📥 Обновление кода из GitHub..."
git fetch origin
git pull origin main

# Проверяем WEB_APP_URL в .env
echo "🔍 Проверка WEB_APP_URL..."
if grep -q "WEB_APP_URL=https://synthosaicreativestudio-maker.github.io/marketing/" .env; then
    echo "✅ WEB_APP_URL корректный"
else
    echo "⚠️  WEB_APP_URL может быть некорректным. Проверьте файл .env"
    echo "Ожидаемое значение: WEB_APP_URL=https://synthosaicreativestudio-maker.github.io/marketing/"
fi

# Перезапускаем сервисы
echo "🔄 Перезапуск сервисов..."
sudo systemctl restart marketingbot-bot.service
sudo systemctl restart marketingbot-web.service

# Проверяем статус
echo "📊 Статус сервисов:"
sudo systemctl status marketingbot-bot.service --no-pager -l
sudo systemctl status marketingbot-web.service --no-pager -l

echo "✅ Обновление завершено!"
echo "📋 Проверьте логи:"
echo "   sudo journalctl -u marketingbot-bot.service -f"
echo "   sudo journalctl -u marketingbot-web.service -f"
