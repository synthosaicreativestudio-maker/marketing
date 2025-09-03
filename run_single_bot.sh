#!/bin/bash

# ОКОНЧАТЕЛЬНОЕ РЕШЕНИЕ ПРОБЛЕМЫ МНОЖЕСТВЕННЫХ ЭКЗЕМПЛЯРОВ
# Wrapper скрипт, обеспечивающий ГАРАНТИРОВАННУЮ единственность экземпляра
# Делегирует управление жизненным циклом операционной системе

BOT_DIR="/Users/verakoroleva/Desktop/@marketing"
PID_FILE="$BOT_DIR/marketing_bot.pid"
LOCK_FILE="$BOT_DIR/marketing_bot.lock"
LOG_FILE="$BOT_DIR/bot.log"
BOT_SCRIPT="$BOT_DIR/bot.py"

cd "$BOT_DIR" || exit 1

echo "🚀 СИСТЕМА ГАРАНТИРОВАННОЙ ЕДИНСТВЕННОСТИ ЭКЗЕМПЛЯРА"
echo "======================================================"

# Функция для получения блокировки
acquire_lock() {
    local timeout=30
    local counter=0
    
    while [ $counter -lt $timeout ]; do
        # Попытка создать блокировку атомарно
        if (set -C; echo $$ > "$LOCK_FILE") 2>/dev/null; then
            echo "✅ Блокировка получена (PID: $$)"
            return 0
        fi
        
        # Проверяем, не является ли блокировка устаревшей
        if [ -f "$LOCK_FILE" ]; then
            local lock_pid=$(cat "$LOCK_FILE" 2>/dev/null)
            if [ -n "$lock_pid" ] && ! kill -0 "$lock_pid" 2>/dev/null; then
                echo "🧹 Удаляем устаревшую блокировку (PID: $lock_pid)"
                rm -f "$LOCK_FILE"
                continue
            fi
        fi
        
        echo "⏳ Ожидание освобождения блокировки... ($counter/$timeout)"
        sleep 1
        counter=$((counter + 1))
    done
    
    echo "❌ Не удалось получить блокировку за $timeout секунд"
    return 1
}

# Функция освобождения блокировки
release_lock() {
    if [ -f "$LOCK_FILE" ]; then
        local lock_pid=$(cat "$LOCK_FILE" 2>/dev/null)
        if [ "$lock_pid" = "$$" ]; then
            rm -f "$LOCK_FILE"
            echo "🔓 Блокировка освобождена"
        fi
    fi
}

# Обработка сигналов для корректного завершения
cleanup_on_exit() {
    echo "📡 Получен сигнал завершения..."
    
    # Останавливаем все дочерние процессы
    local child_pids=$(jobs -p)
    if [ -n "$child_pids" ]; then
        echo "🛑 Завершаем дочерние процессы: $child_pids"
        echo "$child_pids" | xargs -r kill -TERM
        sleep 5
        echo "$child_pids" | xargs -r kill -KILL 2>/dev/null || true
    fi
    
    # Освобождаем блокировку
    release_lock
    
    # Очищаем PID файл
    rm -f "$PID_FILE"
    
    echo "🧹 Очистка завершена"
    exit 0
}

# Устанавливаем обработчики сигналов
trap cleanup_on_exit SIGTERM SIGINT SIGQUIT

# Шаг 1: РАДИКАЛЬНАЯ ОЧИСТКА всех процессов бота
echo "1️⃣ Радикальная очистка всех процессов..."

# Останавливаем launchd сервис если запущен
launchctl stop com.marketing.telegram-bot 2>/dev/null || true
launchctl unload ~/Library/LaunchAgents/com.marketing.telegram-bot.plist 2>/dev/null || true

# Находим ВСЕ процессы Python связанные с ботом
ALL_BOT_PIDS=$(pgrep -f "python.*bot.py" 2>/dev/null || true)
if [ -n "$ALL_BOT_PIDS" ]; then
    echo "   Найдены процессы бота: $ALL_BOT_PIDS"
    echo "$ALL_BOT_PIDS" | xargs -r kill -TERM
    sleep 10
    
    # Проверяем, остались ли процессы
    ALL_BOT_PIDS=$(pgrep -f "python.*bot.py" 2>/dev/null || true)
    if [ -n "$ALL_BOT_PIDS" ]; then
        echo "   Принудительное завершение: $ALL_BOT_PIDS"
        echo "$ALL_BOT_PIDS" | xargs -r kill -KILL
    fi
else
    echo "   Процессы бота не найдены"
fi

# Очищаем все lock и cache файлы
rm -f "$BOT_DIR"/bot.lock
rm -f "$BOT_DIR"/auth_cache.json
rm -f "$BOT_DIR"/marketing_bot.lock
rm -f "$BOT_DIR"/marketing_bot.pid

echo "   ✅ Очистка завершена"

# Шаг 2: Сброс Telegram соединений
echo "2️⃣ Сброс Telegram webhook соединений..."
python3 "$BOT_DIR/reset_telegram_webhook.py" || echo "   ⚠️ Сброс webhook не удался"

# Шаг 3: Получение эксклюзивной блокировки
echo "3️⃣ Получение эксклюзивной блокировки..."
if ! acquire_lock; then
    echo "❌ Не удалось получить блокировку. Возможно, другой экземпляр уже работает."
    exit 1
fi

# Шаг 4: Финальная проверка отсутствия конфликтующих процессов
echo "4️⃣ Финальная проверка..."
REMAINING_PIDS=$(pgrep -f "python.*bot.py" 2>/dev/null || true)
if [ -n "$REMAINING_PIDS" ]; then
    echo "❌ КРИТИЧЕСКАЯ ОШИБКА: Найдены работающие процессы: $REMAINING_PIDS"
    release_lock
    exit 1
fi

echo "   ✅ Система готова к запуску единственного экземпляра"

# Шаг 5: Запуск бота с гарантированной единственностью
echo "5️⃣ Запуск единственного экземпляра бота..."
echo "   📅 Время запуска: $(date)"
echo "   🆔 Wrapper PID: $$"

# Запускаем бота в фоне и получаем его PID
python3 "$BOT_SCRIPT" >> "$LOG_FILE" 2>&1 &
BOT_PID=$!

# Сохраняем PID бота
echo "$BOT_PID" > "$PID_FILE"
echo "   🤖 Bot PID: $BOT_PID"

# Ожидаем завершения бота
echo "   👀 Мониторинг процесса бота..."
wait $BOT_PID
BOT_EXIT_CODE=$?

echo "📊 Бот завершился с кодом: $BOT_EXIT_CODE"

# Финальная очистка
cleanup_on_exit