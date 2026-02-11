#!/usr/bin/env bash

# Упрощенный скрипт для настройки Cloudflare Tunnel
# Используется когда туннель уже создан через Dashboard
# и нужно только установить cloudflared и настроить его на сервере

set -e

VM_USER="ubuntu"
VM_HOST="158.160.0.127"
SSH_KEY="${SSH_KEY_PATH:-$HOME/.ssh/ssh-key-1767684261599/ssh-key-1767684261599}"

echo "==> Упрощенная установка Cloudflare Tunnel"
echo ""
echo "Этот скрипт предполагает, что вы уже:"
echo "  1. Создали туннель через Cloudflare Dashboard"
echo "  2. Настроили Public Hostname (marketingbot-xxx.trycloudflare.com → localhost:8080)"
echo "  3. Скачали credentials файл (JSON)"
echo ""
read -p "Продолжить? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
fi

echo ""
echo "Введите Tunnel ID:"
read TUNNEL_ID

if [ -z "$TUNNEL_ID" ]; then
    echo "❌ Tunnel ID не может быть пустым"
    exit 1
fi

echo ""
echo "Введите путь к credentials файлу (JSON):"
read CREDENTIALS_FILE

if [ ! -f "$CREDENTIALS_FILE" ]; then
    echo "❌ Файл не найден: $CREDENTIALS_FILE"
    exit 1
fi

echo ""
echo "==> Установка cloudflared на сервере..."

ssh -i "$SSH_KEY" "${VM_USER}@${VM_HOST}" bash <<EOF
set -e

# Установка cloudflared
if ! command -v cloudflared &> /dev/null; then
    echo "Установка cloudflared..."
    cd /tmp
    wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
    sudo dpkg -i cloudflared-linux-amd64.deb || sudo apt-get install -f -y
    rm -f cloudflared-linux-amd64.deb
fi

# Создание директории
sudo mkdir -p /etc/cloudflared

# Копирование credentials
sudo cp /tmp/${TUNNEL_ID}.json /etc/cloudflared/ 2>/dev/null || true
sudo chmod 600 /etc/cloudflared/${TUNNEL_ID}.json

# Создание конфигурации
sudo tee /etc/cloudflared/config.yml > /dev/null <<CONFIG
tunnel: ${TUNNEL_ID}
credentials-file: /etc/cloudflared/${TUNNEL_ID}.json

ingress:
  - hostname: marketingbot-${TUNNEL_ID}.trycloudflare.com
    service: http://localhost:8080
  - service: http_status:404
CONFIG

# Создание systemd сервиса
sudo tee /etc/systemd/system/cloudflared.service > /dev/null <<SERVICE
[Unit]
Description=Cloudflare Tunnel
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/cloudflared tunnel --config /etc/cloudflared/config.yml run
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
SERVICE

# Запуск сервиса
sudo systemctl daemon-reload
sudo systemctl enable cloudflared
sudo systemctl restart cloudflared

echo "Ожидание запуска (10 секунд)..."
sleep 10

echo ""
echo "Статус сервиса:"
sudo systemctl status cloudflared --no-pager -l | head -20 || true

echo ""
echo "✅ Туннель запущен!"
echo "URL: https://marketingbot-${TUNNEL_ID}.trycloudflare.com"
EOF

# Копирование credentials файла
scp -i "$SSH_KEY" "$CREDENTIALS_FILE" "${VM_USER}@${VM_HOST}:/tmp/${TUNNEL_ID}.json"

echo ""
echo "✅ Настройка завершена!"
echo "URL туннеля: https://marketingbot-${TUNNEL_ID}.trycloudflare.com"
echo ""
echo "Проверка:"
echo "  curl https://marketingbot-${TUNNEL_ID}.trycloudflare.com/api/promotions"
