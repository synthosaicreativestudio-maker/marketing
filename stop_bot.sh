#!/bin/bash

# Безопасная остановка бота
BOT_NAME="marketing_bot"
LOCK_FILE="/tmp/${BOT_NAME}.lock"

echo "🛑 Останавливаю бота..."

# Проверяем lock файл
if [ -f "$LOCK_FILE" ]; then
    BOT_PID=$(cat "$LOCK_FILE")
    echo "📋 Найден PID в lock файле: $BOT_PID"
    
    # Проверяем, существует ли процесс
    if ps -p $BOT_PID > /dev/null 2>&1; then
        echo "🔍 Процесс $BOT_PID найден, останавливаю..."
        kill $BOT_PID
        sleep 2
        
        # Принудительно убиваем, если не остановился
        if ps -p $BOT_PID > /dev/null 2>&1; then
            echo "⚡ Принудительно останавливаю процесс..."
            kill -9 $BOT_PID
        fi
    else
        echo "⚠️ Процесс $BOT_PID не найден"
    fi
    
    # Удаляем lock файл
    rm -f "$LOCK_FILE"
    echo "🗑️ Lock файл удален"
else
    echo "⚠️ Lock файл не найден"
fi

# Дополнительная проверка - ищем все процессы бота
RUNNING_PROCESSES=$(ps aux | grep -E "(python.*bot|bot.py)" | grep -v grep | wc -l)

if [ $RUNNING_PROCESSES -gt 0 ]; then
    echo "🔍 Найдено $RUNNING_PROCESSES процессов бота, останавливаю..."
    pkill -f "python.*bot.py" 2>/dev/null
    sleep 2
    
    # Принудительно убиваем оставшиеся
    ps aux | grep -E "(python.*bot|bot.py)" | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null
    echo "✅ Все процессы остановлены"
else
    echo "✅ Процессы бота не найдены"
fi

echo "🛑 Бот остановлен"
