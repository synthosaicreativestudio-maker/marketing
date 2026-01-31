#!/bin/bash

# Скрипт для запуска бота на PythonAnywhere
echo "🚀 Запуск MarketingBot на PythonAnywhere..."

# Определяем путь к проекту
PROJECT_DIR="$HOME/marketing"
cd "$PROJECT_DIR" || exit 1

# Проверяем наличие .env
if [ ! -f .env ]; then
    echo "❌ Ошибка: .env файл не найден!"
    echo "Создайте .env файл с необходимыми переменными окружения"
    exit 1
fi

# Определяем версию Python
if command -v python3.10 &> /dev/null; then
    PYTHON_CMD="python3.10"
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
else
    echo "❌ Ошибка: Python не найден!"
    exit 1
fi

echo "📦 Используется: $PYTHON_CMD"

# Останавливаем старый процесс, если запущен
echo "⏹️ Проверка запущенных процессов..."
pkill -f "python.*bot.py" 2>/dev/null && echo "Старый процесс остановлен" || echo "Процесс не был запущен"

# Небольшая задержка
sleep 2

# Проверяем зависимости
echo "🔍 Проверка зависимостей..."
if ! $PYTHON_CMD -c "import telegram" 2>/dev/null; then
    echo "📦 Установка зависимостей..."
    pip3.10 install --user -r requirements.txt || pip3 install --user -r requirements.txt
fi

# Запускаем бота
echo "▶️ Запуск бота..."
nohup $PYTHON_CMD bot.py > bot.log 2>&1 &

# Ждем немного
sleep 3

# Проверяем, что процесс запущен
if pgrep -f "python.*bot.py" > /dev/null; then
    echo "✅ Бот успешно запущен!"
    echo ""
    echo "📋 Полезные команды:"
    echo "  Просмотр логов: tail -f bot.log"
    echo "  Проверка процесса: ps aux | grep python | grep bot"
    echo "  Остановка бота: pkill -f 'python.*bot.py'"
else
    echo "❌ Ошибка: Бот не запустился!"
    echo "Проверьте логи: tail -20 bot.log"
    exit 1
fi
