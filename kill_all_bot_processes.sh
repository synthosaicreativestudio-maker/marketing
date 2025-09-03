#!/bin/bash

# Агрессивная очистка всех процессов бота
# Устраняет проблему "Conflict: terminated by other getUpdates request"

BOT_DIR="/Users/verakoroleva/Desktop/@marketing"
cd "$BOT_DIR" || exit 1

echo "🚨 АГРЕССИВНАЯ ОЧИСТКА ВСЕХ ПРОЦЕССОВ БОТА"
echo "=========================================="

# Шаг 1: Останавливаем launchd сервис (если есть)
echo "1️⃣ Остановка launchd сервиса..."
launchctl stop com.marketing.telegram-bot 2>/dev/null || true
launchctl unload ~/Library/LaunchAgents/com.marketing.telegram-bot.plist 2>/dev/null || true

# Шаг 2: Находим ВСЕ процессы Python
echo "2️⃣ Поиск всех процессов Python..."
ALL_PYTHON_PIDS=$(ps aux | grep -i python | grep -v grep | awk '{print $2}' | tr '\n' ' ')
if [ -n "$ALL_PYTHON_PIDS" ]; then
    echo "   Найдены Python процессы: $ALL_PYTHON_PIDS"
else
    echo "   Python процессы не найдены"
fi

# Шаг 3: Специфический поиск bot.py процессов
echo "3️⃣ Поиск процессов bot.py..."
BOT_PIDS=$(pgrep -f "bot.py" 2>/dev/null | tr '\n' ' ')
if [ -n "$BOT_PIDS" ]; then
    echo "   Найдены bot.py процессы: $BOT_PIDS"
    echo "   Завершаем их..."
    echo "$BOT_PIDS" | xargs -n1 kill -KILL 2>/dev/null || true
else
    echo "   bot.py процессы не найдены"
fi

# Шаг 4: Поиск процессов содержащих marketing
echo "4️⃣ Поиск процессов содержащих 'marketing'..."
MARKETING_PIDS=$(pgrep -f "marketing" 2>/dev/null | tr '\n' ' ')
if [ -n "$MARKETING_PIDS" ]; then
    echo "   Найдены marketing процессы: $MARKETING_PIDS"
    echo "   Завершаем их..."
    echo "$MARKETING_PIDS" | xargs -n1 kill -KILL 2>/dev/null || true
else
    echo "   marketing процессы не найдены"
fi

# Шаг 5: Поиск процессов с токеном в командной строке
echo "5️⃣ Поиск процессов с Telegram токеном..."
TOKEN_PIDS=$(ps aux | grep -i "8232668997" | grep -v grep | awk '{print $2}' | tr '\n' ' ')
if [ -n "$TOKEN_PIDS" ]; then
    echo "   Найдены процессы с токеном: $TOKEN_PIDS"
    echo "   Завершаем их..."
    echo "$TOKEN_PIDS" | xargs -n1 kill -KILL 2>/dev/null || true
else
    echo "   Процессы с токеном не найдены"
fi

# Шаг 6: Поиск процессов в нашей директории
echo "6️⃣ Поиск процессов в директории @marketing..."
DIR_PIDS=$(lsof +D "$BOT_DIR" 2>/dev/null | grep python | awk '{print $2}' | sort -u | tr '\n' ' ')
if [ -n "$DIR_PIDS" ]; then
    echo "   Найдены процессы в директории: $DIR_PIDS"
    echo "   Завершаем их..."
    echo "$DIR_PIDS" | xargs -n1 kill -KILL 2>/dev/null || true
else
    echo "   Процессы в директории не найдены"
fi

# Шаг 7: Очистка всех lock файлов и кэшей
echo "7️⃣ Очистка lock файлов и кэшей..."
rm -f "$BOT_DIR/bot.lock"
rm -f "$BOT_DIR/auth_cache.json"
rm -f "$BOT_DIR/*.pyc"
find "$BOT_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

echo "8️⃣ Ожидание завершения процессов (10 секунд)..."
sleep 10

# Шаг 9: Финальная проверка
echo "9️⃣ Финальная проверка процессов..."
REMAINING_PIDS=$(pgrep -f "bot.py" 2>/dev/null || true)
if [ -n "$REMAINING_PIDS" ]; then
    echo "❌ ВНИМАНИЕ: Остались процессы: $REMAINING_PIDS"
    echo "   Попытка принудительного завершения через SIGKILL..."
    echo "$REMAINING_PIDS" | xargs -n1 kill -9 2>/dev/null || true
    sleep 5
else
    echo "✅ Все процессы бота успешно завершены"
fi

# Шаг 10: Проверка портов (если бот использует webhook)
echo "🔟 Проверка занятых портов..."
USED_PORTS=$(lsof -i :8080 -i :8443 2>/dev/null | grep LISTEN || true)
if [ -n "$USED_PORTS" ]; then
    echo "   Найдены занятые порты:"
    echo "$USED_PORTS"
else
    echo "   Порты свободны"
fi

echo ""
echo "🎯 ОЧИСТКА ЗАВЕРШЕНА"
echo "===================="
echo ""
echo "Теперь можно безопасно запустить бота:"
echo "python3 bot.py"