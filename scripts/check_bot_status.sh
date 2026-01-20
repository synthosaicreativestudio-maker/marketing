#!/bin/bash

# Скрипт для диагностики статуса бота на сервере
# Хост и ключ: scripts/yandex_vm_config.sh
source "$(dirname "$0")/yandex_vm_config.sh"

echo "🔍 Диагностика статуса MarketingBot на сервере..."
echo ""

ssh -i "$SSH_KEY" "${VM_USER}@${VM_HOST}" bash <<'EOF'
set -e

REMOTE_DIR="/home/ubuntu/marketingbot"

echo "=== 1. Статус systemd сервиса ==="
echo ""
sudo systemctl status marketingbot-bot.service --no-pager -l || echo "❌ Сервис не найден или не запущен"
echo ""

echo "=== 2. Проверка запущенных процессов бота ==="
echo ""
BOT_PROCESSES=$(ps aux | grep -E "python.*bot\.py" | grep -v grep || true)
BOT_COUNT=$(echo "$BOT_PROCESSES" | wc -l | tr -d ' ')

if [ "$BOT_COUNT" -eq 0 ]; then
    echo "❌ Процессы бота не найдены"
elif [ "$BOT_COUNT" -eq 1 ]; then
    echo "✅ Найден 1 процесс бота:"
    echo "$BOT_PROCESSES"
else
    echo "⚠️  ВНИМАНИЕ: Найдено $BOT_COUNT процессов бота (возможен конфликт):"
    echo "$BOT_PROCESSES"
fi
echo ""

echo "=== 3. Проверка PID файлов ==="
echo ""
if [ -f "${REMOTE_DIR}/bot.pid" ]; then
    PID=$(cat "${REMOTE_DIR}/bot.pid")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "✅ PID файл существует, процесс с PID $PID запущен"
    else
        echo "⚠️  PID файл существует, но процесс с PID $PID не найден (зависший PID файл)"
    fi
else
    echo "ℹ️  PID файл не найден"
fi
echo ""

echo "=== 4. Последние логи (последние 50 строк) ==="
echo ""
sudo journalctl -u marketingbot-bot.service -n 50 --no-pager || echo "❌ Не удалось получить логи"
echo ""

echo "=== 5. Проверка ошибок в логах (последние 100 строк) ==="
echo ""
ERRORS=$(sudo journalctl -u marketingbot-bot.service -n 100 --no-pager | grep -iE "(error|exception|failed|conflict|timeout)" || echo "Ошибок не найдено")
if [ -n "$ERRORS" ] && [ "$ERRORS" != "Ошибок не найдено" ]; then
    echo "⚠️  Найдены ошибки в логах:"
    echo "$ERRORS" | tail -20
else
    echo "✅ Ошибок в последних логах не найдено"
fi
echo ""

echo "=== 6. Проверка конфликтов Telegram API ==="
echo ""
CONFLICTS=$(sudo journalctl -u marketingbot-bot.service -n 200 --no-pager | grep -iE "conflict|409|another.*instance" || echo "Конфликтов не найдено")
if [ -n "$CONFLICTS" ] && [ "$CONFLICTS" != "Конфликтов не найдено" ]; then
    echo "⚠️  ВНИМАНИЕ: Найдены конфликты Telegram API:"
    echo "$CONFLICTS" | tail -10
else
    echo "✅ Конфликтов Telegram API не найдено"
fi
echo ""

echo "=== 7. Проверка доступности Telegram API ==="
echo ""
if curl -s --max-time 5 https://api.telegram.org > /dev/null; then
    echo "✅ Telegram API доступен"
else
    echo "⚠️  Telegram API недоступен или медленно отвечает"
fi
echo ""

echo "=== 8. Использование ресурсов ==="
echo ""
if [ "$BOT_COUNT" -gt 0 ]; then
    echo "Процессы бота:"
    ps aux | grep -E "python.*bot\.py" | grep -v grep | awk '{print "  PID: "$2", CPU: "$3"%, MEM: "$4"%, TIME: "$10}'
else
    echo "Процессы бота не найдены"
fi
echo ""

echo "=== Резюме ==="
echo ""
if [ "$BOT_COUNT" -eq 0 ]; then
    echo "❌ Бот не запущен"
elif [ "$BOT_COUNT" -gt 1 ]; then
    echo "⚠️  Обнаружен конфликт: запущено $BOT_COUNT процессов бота"
    echo "   Рекомендуется остановить все процессы и запустить заново"
else
    SERVICE_STATUS=$(systemctl is-active marketingbot-bot.service 2>/dev/null || echo "unknown")
    if [ "$SERVICE_STATUS" = "active" ]; then
        echo "✅ Бот запущен и работает (1 процесс, systemd активен)"
    else
        echo "⚠️  Процесс бота найден, но systemd сервис не активен"
    fi
fi
echo ""

EOF

echo "✅ Диагностика завершена"
