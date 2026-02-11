#!/bin/bash

# Скрипт для проверки версии бота на сервере и сравнения с локальной
# Проверяет:
# 1. Последний git commit на сервере
# 2. Количество запущенных процессов бота
# 3. Статус systemd сервиса
# Хост и ключ: scripts/yandex_vm_config.sh

source "$(dirname "$0")/yandex_vm_config.sh"

echo "🔍 Проверка версии бота на сервере..."
echo ""

# Получаем локальную версию
LOCAL_COMMIT=$(cd "$(dirname "$0")/.." && git log -1 --format="%H" 2>/dev/null || echo "unknown")
LOCAL_DATE=$(cd "$(dirname "$0")/.." && git log -1 --format="%ai" 2>/dev/null || echo "unknown")
LOCAL_MSG=$(cd "$(dirname "$0")/.." && git log -1 --format="%s" 2>/dev/null || echo "unknown")

echo "📦 Локальная версия:"
echo "   Commit: ${LOCAL_COMMIT:0:12}..."
echo "   Date: $LOCAL_DATE"
echo "   Message: $LOCAL_MSG"
echo ""

# Проверяем версию на сервере
ssh -i "$SSH_KEY" "${VM_USER}@${VM_HOST}" bash <<'EOF'
set -e

REMOTE_DIR="/home/ubuntu/marketingbot"

echo "=== Версия на сервере ==="
if [ -d "$REMOTE_DIR" ]; then
    cd "$REMOTE_DIR"
    if [ -d ".git" ]; then
        REMOTE_COMMIT=$(git log -1 --format="%H" 2>/dev/null || echo "unknown")
        REMOTE_DATE=$(git log -1 --format="%ai" 2>/dev/null || echo "unknown")
        REMOTE_MSG=$(git log -1 --format="%s" 2>/dev/null || echo "unknown")
        
        echo "   Commit: ${REMOTE_COMMIT:0:12}..."
        echo "   Date: $REMOTE_DATE"
        echo "   Message: $REMOTE_MSG"
        echo ""
        
        # Сохраняем для сравнения
        echo "$REMOTE_COMMIT|$REMOTE_DATE|$REMOTE_MSG" > /tmp/remote_version.txt
    else
        echo "   ❌ Не git репозиторий"
        echo "unknown|unknown|unknown" > /tmp/remote_version.txt
    fi
else
    echo "   ❌ Директория $REMOTE_DIR не найдена"
    echo "unknown|unknown|unknown" > /tmp/remote_version.txt
fi

echo ""
echo "=== Количество запущенных процессов бота ==="
BOT_PROCESSES=$(ps aux | grep -E "python.*bot\.py" | grep -v grep || true)
BOT_COUNT=$(echo "$BOT_PROCESSES" | grep -c "python.*bot\.py" || echo "0")

if [ "$BOT_COUNT" -eq 0 ]; then
    echo "   ❌ Процессы бота не найдены"
elif [ "$BOT_COUNT" -eq 1 ]; then
    echo "   ✅ Найден 1 процесс бота"
    echo "$BOT_PROCESSES" | head -1 | awk '{print "   PID: "$2", CPU: "$3"%, MEM: "$4"%"}'
else
    echo "   ⚠️  ВНИМАНИЕ: Найдено $BOT_COUNT процессов бота (возможен конфликт):"
    echo "$BOT_PROCESSES" | while read line; do
        echo "$line" | awk '{print "   PID: "$2", CPU: "$3"%, MEM: "$4"%"}'
    done
fi

echo ""
echo "=== Статус systemd сервиса ==="
SERVICE_STATUS=$(systemctl is-active marketingbot-bot.service 2>/dev/null || echo "unknown")
if [ "$SERVICE_STATUS" = "active" ]; then
    echo "   ✅ Сервис активен"
    systemctl status marketingbot-bot.service --no-pager -l | head -5 | tail -1
else
    echo "   ⚠️  Сервис не активен (статус: $SERVICE_STATUS)"
fi

echo ""
echo "=== Последние изменения в git (если есть) ==="
cd "$REMOTE_DIR" 2>/dev/null || exit 0
if [ -d ".git" ]; then
    UNCOMMITTED=$(git status --porcelain 2>/dev/null | wc -l)
    if [ "$UNCOMMITTED" -gt 0 ]; then
        echo "   ⚠️  Есть незакоммиченные изменения: $UNCOMMITTED файлов"
    else
        echo "   ✅ Нет незакоммиченных изменений"
    fi
    
    BEHIND=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo "0")
    AHEAD=$(git rev-list --count origin/main..HEAD 2>/dev/null || echo "0")
    
    if [ "$BEHIND" -gt 0 ]; then
        echo "   ⚠️  Сервер отстает от origin/main на $BEHIND коммитов"
    fi
    if [ "$AHEAD" -gt 0 ]; then
        echo "   ℹ️  Сервер впереди origin/main на $AHEAD коммитов"
    fi
    if [ "$BEHIND" -eq 0 ] && [ "$AHEAD" -eq 0 ]; then
        echo "   ✅ Сервер синхронизирован с origin/main"
    fi
fi

EOF

# Получаем версию с сервера для сравнения
REMOTE_VERSION=$(ssh -i "$SSH_KEY" "${VM_USER}@${VM_HOST}" "cat /tmp/remote_version.txt 2>/dev/null || echo 'unknown|unknown|unknown'")
REMOTE_COMMIT=$(echo "$REMOTE_VERSION" | cut -d'|' -f1)
REMOTE_DATE=$(echo "$REMOTE_VERSION" | cut -d'|' -f2)
REMOTE_MSG=$(echo "$REMOTE_VERSION" | cut -d'|' -f3)

echo ""
echo "=== Сравнение версий ==="
if [ "$LOCAL_COMMIT" = "$REMOTE_COMMIT" ] && [ "$LOCAL_COMMIT" != "unknown" ]; then
    echo "✅ Версии совпадают!"
    echo "   Обе версии: ${LOCAL_COMMIT:0:12}..."
elif [ "$REMOTE_COMMIT" = "unknown" ]; then
    echo "⚠️  Не удалось определить версию на сервере"
elif [ "$LOCAL_COMMIT" = "unknown" ]; then
    echo "⚠️  Не удалось определить локальную версию"
else
    echo "⚠️  Версии отличаются!"
    echo "   Локальная:  ${LOCAL_COMMIT:0:12}... ($LOCAL_DATE)"
    echo "   На сервере: ${REMOTE_COMMIT:0:12}... ($REMOTE_DATE)"
    echo ""
    echo "   Для обновления сервера выполните:"
    echo "   bash scripts/update_yandex_server.sh"
fi

echo ""
echo "✅ Проверка завершена"
