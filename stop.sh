#!/bin/bash

# Скрипт для остановки бота marketing

PIDFILE="bot.pid"

echo "Остановка бота..."

# Проверяем, существует ли PID файл
if [ ! -f "$PIDFILE" ]; then
    echo "PID файл не найден. Бот, возможно, не запущен."
    exit 1
fi

# Читаем PID из файла
PID=$(cat "$PIDFILE")

# Проверяем, запущен ли процесс с этим PID
if ps -p "$PID" > /dev/null; then
    # Завершаем процесс
    kill "$PID"
    echo "Бот с PID $PID остановлен."
else
    echo "Процесс с PID $PID не найден. Бот, возможно, уже остановлен."
fi

# Удаляем PID файл
rm "$PIDFILE"