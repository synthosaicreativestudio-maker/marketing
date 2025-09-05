#!/bin/bash

# Скрипт управления Marketing Telegram Bot
# Поддерживает macOS (launchd) и Linux (systemd)
# Использование: ./manage_bot.sh {start|stop|restart|status|install|logs}

BOT_DIR="/Users/verakoroleva/Desktop/@marketing"
SERVICE_NAME="marketing-bot.service"
SERVICE_FILE="$BOT_DIR/$SERVICE_NAME"
LAUNCHD_PLIST="com.marketing.telegram-bot.plist"
LAUNCHD_FILE="$BOT_DIR/$LAUNCHD_PLIST"

cd "$BOT_DIR" || exit 1

# Определяем операционную систему
if [[ "$(uname)" == "Darwin" ]]; then
    USE_LAUNCHD=true
    echo "🍎 Обнаружена macOS - используем launchd"
else
    USE_LAUNCHD=false
    echo "🐧 Обнаружена Linux - используем systemd"
fi

function install_service() {
    echo "🔧 Устанавливаем службу..."
    
    if [[ "$USE_LAUNCHD" == "true" ]]; then
        # macOS: используем launchd
        if [ ! -f "$LAUNCHD_FILE" ]; then
            echo "❌ Файл $LAUNCHD_FILE не найден!"
            exit 1
        fi
        
        # Копируем файл в LaunchAgents
        mkdir -p ~/Library/LaunchAgents
        cp "$LAUNCHD_FILE" ~/Library/LaunchAgents/
        
        # Загружаем службу
        launchctl load ~/Library/LaunchAgents/$LAUNCHD_PLIST
        
        echo "✅ Служба launchd установлена и включена для автозапуска"
    else
        # Linux: используем systemd
        if [ ! -f "$SERVICE_FILE" ]; then
            echo "❌ Файл $SERVICE_FILE не найден!"
            exit 1
        fi
        
        # Копируем файл службы в systemd
        sudo cp "$SERVICE_FILE" /etc/systemd/system/
        
        # Перезагружаем systemd
        sudo systemctl daemon-reload
        
        # Включаем автозапуск
        sudo systemctl enable "$SERVICE_NAME"
        
        echo "✅ Служба systemd установлена и включена для автозапуска"
    fi
}

function start_bot() {
    echo "🚀 Запускаем Marketing Bot..."
    
    # Останавливаем все существующие процессы бота
    stop_bot_processes
    
    # Очищаем lock файлы
    rm -f "$BOT_DIR/bot.lock"
    rm -f "$BOT_DIR/auth_cache.json"
    
    if [[ "$USE_LAUNCHD" == "true" ]]; then
        # macOS: запускаем через launchd
        launchctl start $LAUNCHD_PLIST
        
        # Проверяем статус
        sleep 3
        if launchctl list | grep -q $LAUNCHD_PLIST; then
            echo "✅ Bot успешно запущен через launchd"
            show_status
        else
            echo "❌ Ошибка запуска бота"
            launchctl list | grep $LAUNCHD_PLIST || echo "Служба не найдена"
            exit 1
        fi
    else
        # Linux: запускаем через systemd
        sudo systemctl start "$SERVICE_NAME"
        
        # Проверяем статус
        sleep 3
        if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
            echo "✅ Bot успешно запущен через systemd"
            show_status
        else
            echo "❌ Ошибка запуска бота"
            sudo systemctl status "$SERVICE_NAME"
            exit 1
        fi
    fi
}

function stop_bot() {
    echo "🛑 Останавливаем Marketing Bot..."
    
    if [[ "$USE_LAUNCHD" == "true" ]]; then
        # macOS: останавливаем через launchd
        launchctl stop $LAUNCHD_PLIST 2>/dev/null || true
    else
        # Linux: останавливаем через systemd
        sudo systemctl stop "$SERVICE_NAME" 2>/dev/null || true
    fi
    
    # Принудительно останавливаем все процессы бота
    stop_bot_processes
    
    # Очищаем временные файлы
    rm -f "$BOT_DIR/bot.lock"
    
    echo "✅ Bot остановлен"
}

function stop_bot_processes() {
    echo "🔍 Поиск и остановка процессов бота..."
    
    # Ищем все процессы python с bot.py
    local bot_pids=$(pgrep -f "python.*bot.py" || true)
    
    if [ -n "$bot_pids" ]; then
        echo "📋 Найдены процессы бота: $bot_pids"
        
        # Сначала мягкая остановка
        echo "$bot_pids" | xargs -r kill -TERM
        sleep 5
        
        # Проверяем, остались ли процессы
        bot_pids=$(pgrep -f "python.*bot.py" || true)
        if [ -n "$bot_pids" ]; then
            echo "⚡ Принудительная остановка: $bot_pids"
            echo "$bot_pids" | xargs -r kill -KILL
        fi
    else
        echo "ℹ️ Процессы бота не найдены"
    fi
}

function restart_bot() {
    echo "🔄 Перезапускаем Marketing Bot..."
    stop_bot
    sleep 2
    start_bot
}

function show_status() {
    echo "📊 Статус Marketing Bot:"
    echo "========================"
    
    if [[ "$USE_LAUNCHD" == "true" ]]; then
        # macOS: статус launchd службы
        if launchctl list | grep -q $LAUNCHD_PLIST; then
            echo "🟢 Launchd служба: АКТИВНА"
        else
            echo "🔴 Launchd служба: НЕАКТИВНА"
        fi
    else
        # Linux: статус systemd службы
        if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
            echo "🟢 Systemd служба: АКТИВНА"
        else
            echo "🔴 Systemd служба: НЕАКТИВНА"
        fi
    fi
    
    # Проверяем процессы
    local bot_pids=$(pgrep -f "python.*bot.py" || true)
    if [ -n "$bot_pids" ]; then
        echo "🟢 Процессы бота: $bot_pids"
    else
        echo "🔴 Процессы бота: НЕ НАЙДЕНЫ"
    fi
    
    # Проверяем lock файл
    if [ -f "$BOT_DIR/bot.lock" ]; then
        echo "🔒 Lock файл: СУЩЕСТВУЕТ"
    else
        echo "🔓 Lock файл: ОТСУТСТВУЕТ"
    fi
    
    # Размер лога
    if [ -f "$BOT_DIR/bot.log" ]; then
        local log_size=$(wc -l < "$BOT_DIR/bot.log")
        echo "📋 Размер лога: $log_size строк"
    fi
}

function show_logs() {
    echo "📋 Логи Marketing Bot (последние 50 строк):"
    echo "============================================"
    
    if [[ "$USE_LAUNCHD" == "true" ]]; then
        # macOS: логи launchd
        echo "📊 Логи launchd:"
        if [ -f "$BOT_DIR/launchd_stdout.log" ]; then
            echo "--- STDOUT ---"
            tail -n 20 "$BOT_DIR/launchd_stdout.log"
        fi
        if [ -f "$BOT_DIR/launchd_stderr.log" ]; then
            echo "--- STDERR ---"
            tail -n 20 "$BOT_DIR/launchd_stderr.log"
        fi
        echo ""
    else
        # Linux: логи через journalctl (если доступны)
        if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
            echo "📊 Системные логи:"
            sudo journalctl -u "$SERVICE_NAME" -n 20 --no-pager
            echo ""
        fi
    fi
    
    # Логи из файла
    if [ -f "$BOT_DIR/bot.log" ]; then
        echo "📄 Файловые логи:"
        tail -n 30 "$BOT_DIR/bot.log"
    else
        echo "❌ Файл bot.log не найден"
    fi
}

function follow_logs() {
    echo "📋 Отслеживание логов Marketing Bot (Ctrl+C для выхода):"
    echo "========================================================"
    
    if [[ "$USE_LAUNCHD" == "true" ]]; then
        # macOS: отслеживаем логи launchd
        if [ -f "$BOT_DIR/bot.log" ]; then
            tail -f "$BOT_DIR/bot.log" 2>/dev/null || echo "❌ Логи недоступны"
        else
            echo "❌ Логи недоступны"
        fi
    else
        # Linux: отслеживаем логи systemd
        if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
            sudo journalctl -u "$SERVICE_NAME" -f
        else
            tail -f "$BOT_DIR/bot.log" 2>/dev/null || echo "❌ Логи недоступны"
        fi
    fi
}

# Обработка команд
case "$1" in
    install)
        install_service
        ;;
    start)
        start_bot
        ;;
    stop)
        stop_bot
        ;;
    restart)
        restart_bot
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    follow)
        follow_logs
        ;;
    *)
        echo "Использование: $0 {install|start|stop|restart|status|logs|follow}"
        echo ""
        echo "Команды:"
        echo "  install  - Установить systemd службу"
        echo "  start    - Запустить бота"
        echo "  stop     - Остановить бота"
        echo "  restart  - Перезапустить бота"
        echo "  status   - Показать статус"
        echo "  logs     - Показать последние логи"
        echo "  follow   - Отслеживать логи в реальном времени"
        exit 1
        ;;
esac