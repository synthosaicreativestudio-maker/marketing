#!/bin/bash

# Безопасный запуск бота с проверкой на дубли
BOT_NAME="marketing_bot"
LOCK_FILE="/tmp/${BOT_NAME}.lock"
LOG_FILE="/tmp/${BOT_NAME}.log"

echo "🔍 Проверяю запущенные экземпляры бота..."

# Проверяем процессы по имени
RUNNING_PROCESSES=$(ps aux | grep -E "(python.*bot|bot.py)" | grep -v grep | wc -l)

if [ $RUNNING_PROCESSES -gt 0 ]; then
    echo "❌ Найдено $RUNNING_PROCESSES запущенных экземпляров бота"
    echo "🛑 Останавливаю все процессы..."
    
    # Останавливаем все процессы бота
    pkill -f "python.*bot.py" 2>/dev/null
    sleep 2
    
    # Принудительно убиваем оставшиеся
    ps aux | grep -E "(python.*bot|bot.py)" | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null
    sleep 1
    
    echo "✅ Все процессы остановлены"
else
    echo "✅ Запущенных экземпляров не найдено"
fi

# Проверяем lock файл
if [ -f "$LOCK_FILE" ]; then
    echo "🗑️ Удаляю старый lock файл..."
    rm -f "$LOCK_FILE"
fi

echo "🚀 Запускаю бота..."
echo "📝 Логи: $LOG_FILE"

# Активируем виртуальное окружение и запускаем бота
source .venv/bin/activate
nohup python bot.py > "$LOG_FILE" 2>&1 &

# Получаем PID запущенного процесса
BOT_PID=$!
echo "✅ Бот запущен с PID: $BOT_PID"

# Создаем lock файл с PID
echo "$BOT_PID" > "$LOCK_FILE"

echo "🔒 Lock файл создан: $LOCK_FILE"
echo "📊 Для проверки статуса: ps aux | grep bot.py"
echo "🛑 Для остановки: kill $BOT_PID"
