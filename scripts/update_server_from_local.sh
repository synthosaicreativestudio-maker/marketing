#!/bin/bash

# Скрипт для обновления бота на Yandex VM с локального компьютера
# Хост и ключ: scripts/yandex_vm_config.sh (или YANDEX_VM_IP, SSH_KEY_PATH)
source "$(dirname "$0")/yandex_vm_config.sh"

echo "🚀 Обновление MarketingBot на Yandex VM с локального компьютера..."
echo "==> Подключаюсь к ${VM_USER}@${VM_HOST} и обновляю проект..."

ssh -i "$SSH_KEY" "${VM_USER}@${VM_HOST}" bash <<'EOF'
set -e

REMOTE_DIR="/home/ubuntu/marketingbot"

if [ ! -d "${REMOTE_DIR}" ]; then
  echo "❌ Каталог ${REMOTE_DIR} не найден"
  exit 1
fi

cd "${REMOTE_DIR}"

echo "📥 Обновление кода из GitHub..."
git fetch origin
git reset --hard origin/main

echo "🔄 Перезапуск сервисов..."
sudo systemctl restart marketingbot-bot.service
sudo systemctl restart marketingbot-web.service

echo "📊 Статус сервисов:"
sudo systemctl status marketingbot-bot.service --no-pager -l | head -20
sudo systemctl status marketingbot-web.service --no-pager -l | head -20

echo "✅ Обновление завершено!"
echo "📋 Для просмотра логов выполните:"
echo "   sudo journalctl -u marketingbot-bot.service -f"
echo "   sudo journalctl -u marketingbot-web.service -f"
EOF

echo "==> Обновление на сервере завершено."
