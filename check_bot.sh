#!/bin/bash

# Проверка статуса бота
BOT_NAME="marketing_bot"
LOCK_FILE="/tmp/${BOT_NAME}.lock"

echo "🔍 Проверяю статус бота..."

# Проверяем lock файл
if [ -f "$LOCK_FILE" ]; then
    BOT_PID=$(cat "$LOCK_FILE")
    echo "📋 Lock файл найден с PID: $BOT_PID"
    
    # Проверяем, существует ли процесс
    if ps -p $BOT_PID > /dev/null 2>&1; then
        echo "✅ Процесс $BOT_PID активен"
        
        # Показываем детали процесса
        echo "📊 Детали процесса:"
        ps -p $BOT_PID -o pid,ppid,cmd,etime,pcpu,pmem
        
        # Проверяем логи
        LOG_FILE="/tmp/${BOT_NAME}.log"
        if [ -f "$LOG_FILE" ]; then
            echo "📝 Последние 5 строк лога:"
            tail -5 "$LOG_FILE"
        fi
    else
        echo "❌ Процесс $BOT_PID не найден (zombie lock)"
        echo "🗑️ Удаляю неактуальный lock файл..."
        rm -f "$LOCK_FILE"
    fi
else
    echo "⚠️ Lock файл не найден"
fi

# Проверяем все процессы бота
echo ""
echo "🔍 Поиск всех процессов бота:"
RUNNING_PROCESSES=$(ps aux | grep -E "(python.*bot|bot.py)" | grep -v grep)

if [ -n "$RUNNING_PROCESSES" ]; then
    echo "📊 Найдено процессов:"
    echo "$RUNNING_PROCESSES"
else
    echo "✅ Процессы бота не найдены"
fi

# Проверяем порты (если бот использует webhook)
echo ""
echo "🌐 Проверка сетевых соединений:"
netstat -an | grep -E "(443|8443|80)" | head -5
