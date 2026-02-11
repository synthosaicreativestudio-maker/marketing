#!/usr/bin/env bash

# Скрипт для установки Cloudflare Tunnel на сервере Yandex VM
# Использует токен из cloudflare_tunnel_token.txt
# Хост и ключ: scripts/yandex_vm_config.sh

set -e
source "$(dirname "$0")/yandex_vm_config.sh"

TOKEN_FILE="cloudflare_tunnel_token.txt"

echo "==> Установка Cloudflare Tunnel на ${VM_USER}@${VM_HOST}"

# Проверка наличия файла с токеном
if [ ! -f "$TOKEN_FILE" ]; then
    echo "❌ Файл $TOKEN_FILE не найден!"
    exit 1
fi

# Извлечение токена из файла
TOKEN=$(grep "^CLOUDFLARE_TUNNEL_TOKEN=" "$TOKEN_FILE" | cut -d'=' -f2)

if [ -z "$TOKEN" ]; then
    echo "❌ Токен не найден в файле $TOKEN_FILE"
    exit 1
fi

echo "✅ Токен найден"
echo ""

echo "==> Подключение к серверу и установка cloudflared..."

ssh -i "$SSH_KEY" "${VM_USER}@${VM_HOST}" bash <<EOF
set -e

TOKEN="$TOKEN"

echo "==> Проверка наличия cloudflared..."
if command -v cloudflared &> /dev/null; then
    echo "✅ cloudflared уже установлен"
    cloudflared --version
else
    echo "==> Установка cloudflared..."
    sudo mkdir -p --mode=0755 /usr/share/keyrings
    curl -fsSL https://pkg.cloudflare.com/cloudflare-public-v2.gpg | sudo tee /usr/share/keyrings/cloudflare-public-v2.gpg >/dev/null
    
    echo 'deb [signed-by=/usr/share/keyrings/cloudflare-public-v2.gpg] https://pkg.cloudflare.com/cloudflared any main' | sudo tee /etc/apt/sources.list.d/cloudflared.list
    
    sudo apt-get update && sudo apt-get install -y cloudflared
    echo "✅ cloudflared установлен"
    cloudflared --version
fi

echo ""
echo "==> Установка Cloudflare Tunnel сервиса..."
sudo cloudflared service install "\$TOKEN"

echo ""
echo "==> Запуск и включение сервиса..."
sudo systemctl daemon-reload
sudo systemctl enable cloudflared
sudo systemctl start cloudflared

echo ""
echo "==> Ожидание запуска (5 секунд)..."
sleep 5

echo ""
echo "==> Проверка статуса сервиса..."
sudo systemctl status cloudflared --no-pager -l | head -20 || true

echo ""
echo "==> Извлечение URL туннеля из логов..."
TUNNEL_URL=\$(sudo journalctl -u cloudflared -n 50 --no-pager | grep -oP 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' | head -1 || echo "")

if [ -z "\$TUNNEL_URL" ]; then
    echo "⚠️  Не удалось автоматически определить URL туннеля"
    echo "   Проверьте логи: sudo journalctl -u cloudflared -f"
else
    echo "✅ Туннель запущен!"
    echo "   URL: \$TUNNEL_URL"
    echo ""
    echo "🔍 Проверка доступности API:"
    curl -s "\$TUNNEL_URL/api/promotions" | head -5 || echo "API пока недоступен"
fi

echo ""
echo "✅ Установка завершена!"
EOF

echo ""
echo "✅ Cloudflare Tunnel установлен и запущен на сервере!"
echo ""
echo "📝 Следующие шаги:"
echo "   1. Проверьте URL туннеля выше"
echo "   2. Обновите menu.html с реальным Tunnel URL"
echo "   3. Закоммитьте изменения"
