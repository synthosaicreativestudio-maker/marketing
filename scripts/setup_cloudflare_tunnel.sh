#!/usr/bin/env bash

# Скрипт для установки и настройки Cloudflare Tunnel на Yandex VM
# Решает проблему SSL для мини-приложения, предоставляя доверенный HTTPS URL
# Хост и ключ: scripts/yandex_vm_config.sh

set -e
source "$(dirname "$0")/yandex_vm_config.sh"

echo "==> Установка и настройка Cloudflare Tunnel на ${VM_USER}@${VM_HOST}"
echo ""
echo "⚠️  ВАЖНО: Перед выполнением этого скрипта:"
echo "   1. Зарегистрируйтесь на Cloudflare (бесплатно): https://dash.cloudflare.com/sign-up"
echo "   2. Создайте Tunnel через Dashboard: Zero Trust > Networks > Tunnels > Create a tunnel"
echo "   3. Выберите 'Cloudflared' и скопируйте Tunnel ID"
echo "   4. Скачайте credentials файл (JSON)"
echo ""
read -p "Продолжить установку? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Установка отменена"
    exit 1
fi

echo ""
echo "Введите Tunnel ID (из Cloudflare Dashboard):"
read TUNNEL_ID

if [ -z "$TUNNEL_ID" ]; then
    echo "❌ Tunnel ID не может быть пустым"
    exit 1
fi

echo ""
echo "Введите путь к credentials файлу (JSON) на вашем локальном компьютере:"
read CREDENTIALS_FILE

if [ ! -f "$CREDENTIALS_FILE" ]; then
    echo "❌ Файл $CREDENTIALS_FILE не найден"
    exit 1
fi

echo ""
echo "==> Подключение к серверу и установка cloudflared..."

ssh -i "$SSH_KEY" "${VM_USER}@${VM_HOST}" bash <<EOF
set -e

echo "==> Проверка наличия cloudflared..."
if command -v cloudflared &> /dev/null; then
    echo "✅ cloudflared уже установлен"
    cloudflared --version
else
    echo "==> Установка cloudflared..."
    cd /tmp
    wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
    sudo dpkg -i cloudflared-linux-amd64.deb || sudo apt-get install -f -y
    rm -f cloudflared-linux-amd64.deb
    echo "✅ cloudflared установлен"
    cloudflared --version
fi

echo ""
echo "==> Создание директории для конфигурации..."
sudo mkdir -p /etc/cloudflared

echo ""
echo "==> Копирование credentials файла..."
EOF

# Копируем credentials файл на сервер
scp -i "$SSH_KEY" "$CREDENTIALS_FILE" "${VM_USER}@${VM_HOST}:/tmp/${TUNNEL_ID}.json"

ssh -i "$SSH_KEY" "${VM_USER}@${VM_HOST}" bash <<EOF
set -e

TUNNEL_ID="$TUNNEL_ID"

echo "==> Перемещение credentials файла..."
sudo mv "/tmp/\${TUNNEL_ID}.json" "/etc/cloudflared/\${TUNNEL_ID}.json"
sudo chmod 600 "/etc/cloudflared/\${TUNNEL_ID}.json"

echo ""
echo "==> Создание конфигурационного файла..."
sudo tee /etc/cloudflared/config.yml > /dev/null <<CONFIG
tunnel: \${TUNNEL_ID}
credentials-file: /etc/cloudflared/\${TUNNEL_ID}.json

ingress:
  - hostname: marketingbot-\${TUNNEL_ID}.trycloudflare.com
    service: http://localhost:8080
  - service: http_status:404
CONFIG

echo "✅ Конфигурация создана"

echo ""
echo "==> Создание systemd сервиса..."
sudo tee /etc/systemd/system/cloudflared.service > /dev/null <<'SERVICE'
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

echo "✅ Systemd сервис создан"

echo ""
echo "==> Перезагрузка systemd и запуск сервиса..."
sudo systemctl daemon-reload
sudo systemctl enable cloudflared
sudo systemctl restart cloudflared

echo ""
echo "==> Ожидание запуска туннеля (10 секунд)..."
sleep 10

echo ""
echo "==> Проверка статуса сервиса..."
sudo systemctl status cloudflared --no-pager -l || true

echo ""
echo "==> Извлечение URL туннеля из логов..."
TUNNEL_URL=\$(sudo journalctl -u cloudflared -n 100 --no-pager | grep -oP 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' | head -1 || echo "")

if [ -z "\$TUNNEL_URL" ]; then
    echo "⚠️  Не удалось автоматически определить URL туннеля"
    echo "   Проверьте логи: sudo journalctl -u cloudflared -f"
    TUNNEL_URL="https://marketingbot-\${TUNNEL_ID}.trycloudflare.com"
fi

echo ""
echo "✅ Cloudflare Tunnel настроен и запущен!"
echo ""
echo "📋 Информация о туннеле:"
echo "   Tunnel ID: \${TUNNEL_ID}"
echo "   URL: \$TUNNEL_URL"
echo ""
echo "🔍 Проверка доступности API:"
echo "   curl \$TUNNEL_URL/api/promotions"
echo ""
echo "⚠️  ВАЖНО: Обновите API_BASE_URL в menu.html на этот URL:"
echo "   \$TUNNEL_URL"
EOF

echo ""
echo "✅ Установка завершена!"
echo ""
echo "📝 Следующие шаги:"
echo "   1. Проверьте URL туннеля выше"
echo "   2. Обновите menu.html с новым API_BASE_URL (замените <TUNNEL_ID> на реальный ID)"
echo "   3. Проверьте работу мини-приложения"
echo ""
echo "💡 Для просмотра логов туннеля:"
echo "   ssh -i $SSH_KEY ${VM_USER}@${VM_HOST} 'sudo journalctl -u cloudflared -f'"

echo ""
echo "✅ Установка завершена!"
echo ""
echo "📝 Следующие шаги:"
echo "   1. Проверьте URL туннеля выше"
echo "   2. Обновите menu.html с новым API_BASE_URL"
echo "   3. Проверьте работу мини-приложения"
