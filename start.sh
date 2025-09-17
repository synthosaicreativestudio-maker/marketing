#!/bin/bash

# Скрипт для запуска бота marketing

PIDFILE="bot.pid"
LOGFILE="bot.log"

echo "Запуск бота..."

# Проверяем, не запущен ли бот уже
if [ -f "$PIDFILE" ]; then
    PID=$(cat "$PIDFILE")
    if ps -p "$PID" > /dev/null; then
        echo "Бот уже запущен (PID: $PID)"
        exit 1
    else
        # PID файл существует, но процесс не запущен. Удаляем старый файл.
        rm "$PIDFILE"
    fi
fi

# Запускаем бота в фоновом режиме и сохраняем PID
nohup python3 bot.py >> "$LOGFILE" 2>&1 &
PID=$!

# Сохраняем PID в файл
echo "$PID" > "$PIDFILE"

echo "Бот запущен (PID: $PID). Логи: $LOGFILE"