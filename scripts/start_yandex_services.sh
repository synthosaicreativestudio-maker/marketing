#!/usr/bin/env bash

# Удобный запуск/проверка сервисов MarketingBot на ВМ Yandex Cloud.
# Хост и ключ: scripts/yandex_vm_config.sh

set -e
source "$(dirname "$0")/yandex_vm_config.sh"

ssh -t -i "$SSH_KEY" "${VM_USER}@${VM_HOST}" <<'EOF'
set -e

echo "==> Запускаю сервисы marketingbot-bot и marketingbot-web"
sudo systemctl start marketingbot-bot.service
sudo systemctl start marketingbot-web.service

echo "==> Статус сервисов:"
sudo systemctl --no-pager status marketingbot-bot.service || true
sudo systemctl --no-pager status marketingbot-web.service || true

echo "==> Логи (последние строки):"
sudo journalctl -u marketingbot-bot.service -n 50 --no-pager || true
sudo journalctl -u marketingbot-web.service -n 50 --no-pager || true
EOF

