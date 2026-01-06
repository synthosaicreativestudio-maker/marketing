#!/usr/bin/env bash

# Удобный запуск/проверка сервисов MarketingBot на ВМ Yandex Cloud.

set -e

VM_USER="ubuntu"
VM_HOST="158.160.0.127"
SSH_KEY="${SSH_KEY_PATH:-$HOME/.ssh/ssh-key-1767684261599/ssh-key-1767684261599}"

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

