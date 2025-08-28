#!/bin/bash

# Скрипт управления Marketing Bot
# Использование: ./manage_bot.sh [start|stop|restart|status|logs|install]

BOT_NAME="marketing-bot"
SERVICE_FILE="marketing-bot.service"
SERVICE_PATH="/Library/LaunchDaemons/${SERVICE_FILE}"

case "$1" in
    install)
        echo "🔧 Установка Marketing Bot как системного сервиса..."
        
        # Копируем сервис в системную папку
        sudo cp "$SERVICE_FILE" "$SERVICE_PATH"
        
        # Устанавливаем права
        sudo chown root:wheel "$SERVICE_PATH"
        sudo chmod 644 "$SERVICE_PATH"
        
        # Загружаем сервис
        sudo launchctl load "$SERVICE_PATH"
        
        echo "✅ Сервис установлен и загружен"
        echo "📋 Команды управления:"
        echo "   start   - запустить бота"
        echo "   stop    - остановить бота"
        echo "   restart - перезапустить бота"
        echo "   status  - статус бота"
        echo "   logs    - показать логи"
        ;;
        
    start)
        echo "🚀 Запуск Marketing Bot..."
        sudo launchctl start "$BOT_NAME"
        echo "✅ Бот запущен"
        ;;
        
    stop)
        echo "⏹️ Остановка Marketing Bot..."
        sudo launchctl stop "$BOT_NAME"
        echo "✅ Бот остановлен"
        ;;
        
    restart)
        echo "🔄 Перезапуск Marketing Bot..."
        sudo launchctl stop "$BOT_NAME"
        sleep 2
        sudo launchctl start "$BOT_NAME"
        echo "✅ Бот перезапущен"
        ;;
        
    status)
        echo "📊 Статус Marketing Bot..."
        sudo launchctl list | grep "$BOT_NAME"
        
        # Проверяем процессы
        echo "🔍 Активные процессы:"
        ps aux | grep "python bot.py" | grep -v grep
        ;;
        
    logs)
        echo "📝 Логи Marketing Bot..."
        sudo journalctl -u "$BOT_NAME" -f --no-pager
        ;;
        
    uninstall)
        echo "🗑️ Удаление Marketing Bot сервиса..."
        
        # Останавливаем и выгружаем сервис
        sudo launchctl stop "$BOT_NAME" 2>/dev/null
        sudo launchctl unload "$SERVICE_PATH" 2>/dev/null
        
        # Удаляем файл сервиса
        sudo rm -f "$SERVICE_PATH"
        
        echo "✅ Сервис удален"
        ;;
        
    *)
        echo "❌ Неизвестная команда: $1"
        echo "📋 Доступные команды:"
        echo "   install   - установить как системный сервис"
        echo "   start     - запустить бота"
        echo "   stop      - остановить бота"
        echo "   restart   - перезапустить бота"
        echo "   status    - показать статус"
        echo "   logs      - показать логи"
        echo "   uninstall - удалить сервис"
        echo ""
        echo "💡 Пример: ./manage_bot.sh install"
        exit 1
        ;;
esac

