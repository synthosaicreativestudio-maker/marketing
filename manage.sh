#!/bin/bash

# Единый скрипт для управления Marketing Bot
#
# Команды:
#   start   - Безопасно запустить бота
#   stop    - Остановить бота
#   restart - Перезапустить бота
#   status  - Проверить статус
#   logs    - Показать последние логи

# --- Настройки ---
BOT_NAME="marketing_bot"
# Используем директорию проекта для lock и log файлов для простоты
LOCK_FILE="bot.lock"
LOG_FILE="bot.log"
PYTHON_CMD="python3"
BOT_SCRIPT="bot.py"

# --- Функции ---

# Функция для остановки всех процессов бота
stop_bot() {
    echo "🛑 Останавливаю все процессы бота..."
    
    # 1. По PID из lock-файла (самый безопасный способ)
    if [ -f "$LOCK_FILE" ]; then
        BOT_PID=$(cat "$LOCK_FILE")
        if [ -n "$BOT_PID" ] && ps -p $BOT_PID > /dev/null 2>&1; then
            echo "   - Останавливаю процесс с PID $BOT_PID..."
            kill $BOT_PID
            sleep 1
        fi
        rm -f "$LOCK_FILE"
        echo "   - Lock-файл удален."
    fi

    # 2. По имени процесса (запасной вариант)
    PIDS=$(ps aux | grep -E "($PYTHON_CMD.*$BOT_SCRIPT)" | grep -v grep | awk '{print $2}')
    if [ -n "$PIDS" ]; then
        echo "   - Найдены и остановлены процессы по имени: $PIDS"
        pkill -f "$PYTHON_CMD.*$BOT_SCRIPT" 2>/dev/null
        sleep 1
    fi
    
    # 3. Принудительная остановка (самый крайний случай)
    PIDS=$(ps aux | grep -E "($PYTHON_CMD.*$BOT_SCRIPT)" | grep -v grep | awk '{print $2}')
    if [ -n "$PIDS" ]; then
        echo "   - ⚡ Принудительно останавливаю оставшиеся процессы: $PIDS"
        kill -9 $PIDS 2>/dev/null
    fi

    echo "✅ Процессы бота остановлены."
}

# --- Логика скрипта ---

# Получаем команду от пользователя
COMMAND=$1

case "$COMMAND" in
    start)
        echo "🚀 Запускаю бота..."
        
        # Проверяем, не запущен ли уже бот
        if [ -f "$LOCK_FILE" ]; then
            BOT_PID=$(cat "$LOCK_FILE")
            if [ -n "$BOT_PID" ] && ps -p $BOT_PID > /dev/null 2>&1; then
                echo "⚠️  Бот уже запущен с PID $BOT_PID. Для перезапуска используйте: ./manage.sh restart"
                exit 1
            else
                # Если процесс мертв, а lock-файл остался
                echo "   - Найден неактуальный lock-файл. Удаляю..."
                rm -f "$LOCK_FILE"
            fi
        fi

        # Запускаем бота в фоновом режиме
        # nohup python3 bot.py > bot.log 2>&1 &
        nohup $PYTHON_CMD $BOT_SCRIPT >> "$LOG_FILE" 2>&1 & 
        
        # Получаем PID запущенного процесса
        BOT_PID=$!
        echo "$BOT_PID" > "$LOCK_FILE"
        
        echo "✅ Бот успешно запущен с PID: $BOT_PID"
        echo "   - Логи пишутся в файл: $LOG_FILE"
        echo "   - Lock-файл создан: $LOCK_FILE"
        ;;

    stop)
        stop_bot
        ;;

    restart)
        echo "🔄 Перезапускаю бота..."
        stop_bot
        sleep 1
        # Вызываем start в этом же скрипте
        bash "$0" start
        ;;

    status)
        echo "🔍 Проверка статуса бота..."
        if [ -f "$LOCK_FILE" ]; then
            BOT_PID=$(cat "$LOCK_FILE")
            if [ -n "$BOT_PID" ] && ps -p $BOT_PID > /dev/null 2>&1; then
                echo "✅ Бот работает. PID: $BOT_PID"
                echo "📊 Детали процесса:"
                ps -p $BOT_PID -o pid,ppid,cmd,etime,pcpu,pmem
            else
                echo "❌ Бот не работает (но есть lock-файл)."
                echo "   - Рекомендуется выполнить: ./manage.sh stop, а затем ./manage.sh start"
            fi
        else
            echo "❌ Бот не работает (lock-файл не найден)."
        fi
        ;;

    logs)
        echo "📝 Последние 15 строк лога ($LOG_FILE):"
        tail -n 15 "$LOG_FILE"
        ;;

    *)
        echo "Неизвестная команда: '$COMMAND'"
        echo ""
        echo "Доступные команды:"
        echo "  start   - Безопасно запустить бота"
        echo "  stop    - Остановить бота"
        echo "  restart - Перезапустить бота"
        echo "  status  - Проверить статус"
        echo "  logs    - Показать последние логи"
        exit 1
        ;;
esac
